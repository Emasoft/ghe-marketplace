#!/usr/bin/env python3
"""
WAL (Write-Ahead Log) Manager for GHE Transcription System

This module provides atomic, crash-safe operations for the transcription
queue using a JSONL-based write-ahead log pattern.

Key features:
- Append-only log for crash safety
- File locking for concurrent access
- Monotonic sequence numbers for ordering
- Deduplication via content hashing
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def get_claude_dir() -> Path:
    """Find or create the .claude directory."""
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"

    if not claude_dir.exists():
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                return parent / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)

    return claude_dir


def get_wal_path() -> Path:
    """Get path to the WAL file."""
    return get_claude_dir() / "ghe_wal.jsonl"


def get_sequence_path() -> Path:
    """Get path to the sequence counter file."""
    return get_claude_dir() / "ghe_sequence.json"


def get_lock_path() -> Path:
    """Get path to the WAL lock file."""
    return get_claude_dir() / "ghe_wal.lock"


def get_worker_lock_path() -> Path:
    """Get path to the worker lock file."""
    return get_claude_dir() / "ghe_worker.lock"


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content for deduplication."""
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def acquire_wal_lock(lock_file) -> bool:
    """Acquire exclusive lock on WAL file."""
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (IOError, OSError):
        return False


def release_wal_lock(lock_file) -> None:
    """Release WAL file lock."""
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
    except (IOError, OSError):
        pass


def get_next_sequence() -> int:
    """Get and increment the sequence number atomically."""
    import time
    seq_path = get_sequence_path()
    lock_path = get_lock_path()

    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, 'w') as lock_file:
        # Non-blocking lock with retry (max 2 seconds)
        for attempt in range(20):
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (IOError, OSError):
                if attempt < 19:
                    time.sleep(0.1)
                else:
                    # Fallback: use timestamp-based sequence
                    return int(time.time() * 1000) % 1000000
        try:
            if seq_path.exists():
                try:
                    with open(seq_path, 'r') as f:
                        data = json.load(f)
                        next_seq = data.get('next_seq', 1)
                except (json.JSONDecodeError, IOError):
                    next_seq = 1
            else:
                next_seq = 1

            with open(seq_path, 'w') as f:
                json.dump({'next_seq': next_seq + 1}, f)
                f.flush()
                os.fsync(f.fileno())

            return next_seq
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def wal_append(
    speaker: str,
    issue: int,
    content: str,
    content_hash: Optional[str] = None
) -> int:
    """
    Append a new entry to the WAL atomically.

    Args:
        speaker: Either "user" or "claude" (NEVER phase agents)
        issue: Target issue number
        content: Full message content
        content_hash: Optional pre-computed hash

    Returns:
        The sequence number of the appended entry
    """
    import time
    wal_path = get_wal_path()
    lock_path = get_lock_path()

    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, 'w') as lock_file:
        # Non-blocking lock with retry (max 2 seconds)
        for attempt in range(20):
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except (IOError, OSError):
                if attempt < 19:
                    time.sleep(0.1)
                else:
                    return -1  # Failed to acquire lock
        try:
            seq = get_next_sequence()

            entry = {
                'seq': seq,
                'ts': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
                'speaker': speaker,
                'issue': issue,
                'content': content,
                'posted': False,
                'comment_id': None,
                'hash': content_hash or compute_hash(content)
            }

            with open(wal_path, 'a') as f:
                f.write(json.dumps(entry) + '\n')
                f.flush()
                os.fsync(f.fileno())

            return seq
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def wal_read_all() -> List[Dict[str, Any]]:
    """Read all entries from the WAL."""
    wal_path = get_wal_path()

    if not wal_path.exists():
        return []

    entries = []
    with open(wal_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return entries


def wal_read_unposted() -> List[Dict[str, Any]]:
    """Read only unposted entries from the WAL."""
    return [e for e in wal_read_all() if not e.get('posted', False)]


def wal_read_by_issue(issue: int) -> List[Dict[str, Any]]:
    """Read all entries for a specific issue."""
    return [e for e in wal_read_all() if e.get('issue') == issue]


def wal_find_by_hash(content_hash: str) -> Optional[Dict[str, Any]]:
    """Find an entry by its content hash."""
    for entry in wal_read_all():
        if entry.get('hash') == content_hash:
            return entry
    return None


def wal_mark_posted(seq: int, comment_id: str) -> bool:
    """
    Mark an entry as posted by rewriting the WAL.

    This is an atomic operation that reads the entire WAL,
    updates the target entry, and writes it back.

    Args:
        seq: Sequence number of entry to mark
        comment_id: GitHub comment ID

    Returns:
        True if entry was found and updated
    """
    wal_path = get_wal_path()
    lock_path = get_lock_path()

    with open(lock_path, 'w') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            entries = wal_read_all()
            found = False

            for entry in entries:
                if entry.get('seq') == seq:
                    entry['posted'] = True
                    entry['comment_id'] = comment_id
                    found = True
                    break

            if not found:
                return False

            temp_path = wal_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                for entry in entries:
                    f.write(json.dumps(entry) + '\n')
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, wal_path)
            return True
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def wal_compact(keep_posted_days: int = 7) -> int:
    """
    Compact the WAL by removing old posted entries.

    Args:
        keep_posted_days: Keep posted entries for this many days

    Returns:
        Number of entries removed
    """
    wal_path = get_wal_path()
    lock_path = get_lock_path()

    cutoff = datetime.now(timezone.utc).timestamp() - (keep_posted_days * 86400)

    with open(lock_path, 'w') as lock_file:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        try:
            entries = wal_read_all()
            original_count = len(entries)

            kept = []
            for entry in entries:
                if not entry.get('posted', False):
                    kept.append(entry)
                else:
                    try:
                        ts = datetime.fromisoformat(entry['ts'].replace('Z', '+00:00'))
                        if ts.timestamp() > cutoff:
                            kept.append(entry)
                    except (ValueError, KeyError):
                        kept.append(entry)

            temp_path = wal_path.with_suffix('.tmp')
            with open(temp_path, 'w') as f:
                for entry in kept:
                    f.write(json.dumps(entry) + '\n')
                f.flush()
                os.fsync(f.fileno())

            os.replace(temp_path, wal_path)
            return original_count - len(kept)
        finally:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)


def has_unposted_entries() -> bool:
    """Check if there are any unposted entries."""
    return len(wal_read_unposted()) > 0


def get_unposted_count() -> int:
    """Get count of unposted entries."""
    return len(wal_read_unposted())


def acquire_worker_lock() -> Optional[Any]:
    """
    Acquire exclusive lock for the background worker.
    Returns the lock file handle if acquired, None otherwise.
    """
    lock_path = get_worker_lock_path()
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        lock_file = open(lock_path, 'w')
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        lock_file.write(str(os.getpid()))
        lock_file.flush()
        return lock_file
    except (IOError, OSError):
        return None


def release_worker_lock(lock_file) -> None:
    """Release the worker lock."""
    if lock_file:
        try:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            lock_file.close()
        except (IOError, OSError):
            pass


def is_worker_running() -> bool:
    """Check if a worker is currently running."""
    lock_path = get_worker_lock_path()
    if not lock_path.exists():
        return False

    try:
        with open(lock_path, 'r') as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            return False
    except (IOError, OSError):
        return True


if __name__ == '__main__':
    print("WAL Manager - GHE Transcription System")
    print(f"WAL path: {get_wal_path()}")
    print(f"Sequence path: {get_sequence_path()}")

    entries = wal_read_all()
    unposted = wal_read_unposted()
    print(f"Total entries: {len(entries)}")
    print(f"Unposted entries: {len(unposted)}")

    if unposted:
        print("\nUnposted messages:")
        for e in unposted[:5]:
            print(f"  [{e['seq']}] {e['speaker']}: {e['content'][:50]}...")
