#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Transcript Recovery for GHE Transcription System

This script recovers Claude messages from a previous session's transcript.
Called by SessionStart to ensure NO messages are ever lost.

The transcript is a JSONL file with conversation messages.
We extract all assistant messages and add them to the WAL.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add scripts directory to path for imports
_script_dir = Path(__file__).parent.resolve()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to hook_debug.log."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [recover_transcript] - {message}\n")
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
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def get_current_issue_local() -> Optional[int]:
    """Get current issue from local files ONLY."""
    claude_dir = get_claude_dir()

    # Try last_active_issue.json first
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

    # Fallback: read from ghe.local.md
    import re
    config_file = claude_dir / "ghe.local.md"
    if config_file.exists():
        try:
            with open(config_file) as f:
                content = f.read()
            match = re.search(r'^current_issue:\s*["\']?(\d+)["\']?', content, re.MULTILINE)
            if match:
                return int(match.group(1))
        except (IOError, ValueError):
            pass

    return None


def extract_messages_from_transcript(transcript_path: str) -> List[Dict[str, Any]]:
    """
    Extract all user and assistant messages from transcript.

    Returns list of dicts with: role, content, timestamp
    """
    if not transcript_path:
        return []

    # Expand tilde
    expanded_path = os.path.expanduser(transcript_path)

    if not Path(expanded_path).exists():
        debug_log(f"Transcript not found: {expanded_path}", "WARN")
        return []

    messages = []

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

                    role = message.get("role", "")
                    if role not in ("user", "assistant"):
                        continue

                    # Extract text content
                    content = message.get("content", "")
                    if isinstance(content, list):
                        text_parts = []
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                            elif isinstance(block, str):
                                text_parts.append(block)
                        content = "\n".join(text_parts)

                    if content:
                        messages.append({
                            "role": role,
                            "content": content,
                            "timestamp": entry.get("timestamp", datetime.now(timezone.utc).isoformat()),
                        })

                except json.JSONDecodeError:
                    continue

        debug_log(f"Extracted {len(messages)} messages from transcript")
        return messages

    except IOError as e:
        debug_log(f"Error reading transcript: {e}", "ERROR")
        return []


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


def recover_messages() -> int:
    """
    Main recovery function.

    1. Check for pending transcript
    2. Extract all messages
    3. Add missing ones to WAL
    4. Delete pending file
    5. Spawn worker

    Returns number of messages recovered.
    """
    debug_log("Starting transcript recovery")

    claude_dir = get_claude_dir()
    pending_file = claude_dir / "ghe_pending_transcript.json"

    if not pending_file.exists():
        debug_log("No pending transcript to recover")
        return 0

    # Read pending transcript info
    try:
        with open(pending_file) as f:
            pending_data = json.load(f)
        transcript_path = pending_data.get("transcript_path", "")
    except (json.JSONDecodeError, IOError) as e:
        debug_log(f"Failed to read pending file: {e}", "ERROR")
        pending_file.unlink(missing_ok=True)
        return 0

    if not transcript_path:
        debug_log("Empty transcript path in pending file")
        pending_file.unlink(missing_ok=True)
        return 0

    # Extract messages from transcript
    messages = extract_messages_from_transcript(transcript_path)

    if not messages:
        debug_log("No messages in transcript")
        pending_file.unlink(missing_ok=True)
        return 0

    # Get existing hashes to avoid duplicates
    existing_hashes = get_existing_hashes()
    debug_log(f"Found {len(existing_hashes)} existing hashes in WAL")

    # Get current issue
    issue = get_current_issue_local() or 0

    # Import WAL manager
    try:
        from wal_manager import wal_append
    except ImportError as e:
        debug_log(f"Failed to import wal_manager: {e}", "ERROR")
        return 0

    # Add missing messages to WAL
    recovered = 0
    for msg in messages:
        content = msg["content"]
        content_hash = compute_hash(content)

        # Skip if already in WAL
        if content_hash in existing_hashes:
            continue

        # Determine speaker
        speaker = "claude" if msg["role"] == "assistant" else "user"

        # Append to WAL
        seq = wal_append(
            speaker=speaker,
            issue=issue,
            content=content,
            content_hash=content_hash
        )

        if seq > 0:
            recovered += 1
            existing_hashes.add(content_hash)  # Avoid duplicates within same recovery
            debug_log(f"Recovered {speaker} message seq={seq}")

    debug_log(f"Recovered {recovered} messages")

    # Delete pending file
    pending_file.unlink(missing_ok=True)

    # Spawn worker if we recovered anything
    if recovered > 0:
        try:
            worker_script = _script_dir / "transcription_worker.py"
            if worker_script.exists():
                subprocess.Popen(
                    [sys.executable, str(worker_script)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    cwd=str(Path.cwd()),
                )
                debug_log("Spawned worker to post recovered messages")
        except Exception as e:
            debug_log(f"Failed to spawn worker: {e}", "ERROR")

    return recovered


def main() -> None:
    """CLI entry point."""
    recovered = recover_messages()
    print(f"Recovered {recovered} messages")


if __name__ == "__main__":
    main()
