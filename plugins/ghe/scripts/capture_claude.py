#!/usr/bin/env python3
"""
Stop Hook for GHE Transcription System

Captures Claude's response from the transcript and adds to WAL for posting.
Uses the same pattern as proven working TTS hooks.
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to hook_debug.log."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [capture_claude] - {message}\n")
    except Exception:
        pass


def get_claude_dir() -> Path:
    """Find the .claude directory."""
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"
    if not claude_dir.exists():
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                return parent / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
    return claude_dir


def compute_hash(content: str) -> str:
    """Compute SHA-256 hash of content for deduplication."""
    import hashlib
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def get_existing_hashes() -> set:
    """Get hashes of all messages already in WAL."""
    wal_path = get_claude_dir() / "ghe_wal.jsonl"
    hashes = set()

    if not wal_path.exists():
        return hashes

    try:
        with open(wal_path, 'r') as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    if entry.get("hash"):
                        hashes.add(entry["hash"])
                except json.JSONDecodeError:
                    continue
    except IOError:
        pass

    return hashes


def get_current_issue() -> int:
    """Get current issue from local files."""
    claude_dir = get_claude_dir()

    last_active = claude_dir / "last_active_issue.json"
    if last_active.exists():
        try:
            with open(last_active) as f:
                data = json.load(f)
                issue = data.get("issue")
                if issue:
                    return int(issue)
        except (json.JSONDecodeError, IOError, ValueError):
            pass

    return 0


def extract_last_claude_message(transcript_path: str) -> dict | None:
    """Extract the last Claude message from transcript."""
    if not transcript_path:
        return None

    expanded_path = os.path.expanduser(transcript_path)

    if not Path(expanded_path).exists():
        return None

    last_message = None

    try:
        with open(expanded_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    message = entry.get("message", {})
                    if not isinstance(message, dict):
                        continue

                    if message.get("role") != "assistant":
                        continue

                    content = message.get("content", "")
                    if isinstance(content, list):
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                text_parts.append(block)
                        content = "\n".join(text_parts)

                    if content and len(content.strip()) >= 5:
                        last_message = {
                            "content": content,
                            "timestamp": entry.get("timestamp", ""),
                        }

                except json.JSONDecodeError:
                    continue

        return last_message

    except IOError:
        return None


def wal_append(speaker: str, issue: int, content: str, content_hash: str) -> int:
    """Append a message to the WAL."""
    import fcntl
    import time

    claude_dir = get_claude_dir()
    wal_path = claude_dir / "ghe_wal.jsonl"
    lock_path = claude_dir / "ghe_wal.lock"

    # Generate sequence number
    seq = int(time.time() * 1000000) % 1000000

    entry = {
        "seq": seq,
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "speaker": speaker,
        "issue": issue,
        "content": content,
        "posted": False,
        "comment_id": None,
        "hash": content_hash,
    }

    # Write with lock
    try:
        with open(lock_path, 'w') as lock_file:
            for attempt in range(10):
                try:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except (IOError, OSError):
                    if attempt < 9:
                        time.sleep(0.05)
                    else:
                        return -1

            with open(wal_path, 'a') as f:
                f.write(json.dumps(entry) + "\n")

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

        return seq
    except Exception:
        return -1


def spawn_worker() -> None:
    """Spawn the transcription worker."""
    try:
        script_dir = Path(__file__).parent
        worker_script = script_dir / "transcription_worker.py"
        if worker_script.exists():
            subprocess.Popen(
                [sys.executable, str(worker_script)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                cwd=str(Path.cwd()),
            )
    except Exception:
        pass


def main():
    try:
        debug_log("capture_claude started (uv run)")

        # Read JSON input from stdin
        input_data = json.load(sys.stdin)

        transcript_path = input_data.get("transcript_path", "")

        if not transcript_path:
            debug_log("No transcript path")
            sys.exit(0)

        # Get existing hashes
        existing_hashes = get_existing_hashes()

        # Extract last Claude message
        msg = extract_last_claude_message(transcript_path)

        if not msg:
            debug_log("No Claude message found")
            sys.exit(0)

        content_hash = compute_hash(msg["content"])

        # Check if already captured
        if content_hash in existing_hashes:
            debug_log("Message already captured")
            sys.exit(0)

        # Get issue
        issue = get_current_issue()

        # Append to WAL
        seq = wal_append(
            speaker="claude",
            issue=issue,
            content=msg["content"],
            content_hash=content_hash
        )

        if seq > 0:
            debug_log(f"Captured Claude message seq={seq} len={len(msg['content'])}")
            spawn_worker()

        sys.exit(0)

    except json.JSONDecodeError:
        sys.exit(0)
    except Exception:
        sys.exit(0)


if __name__ == "__main__":
    main()
