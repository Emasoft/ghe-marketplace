#!/usr/bin/env python3
"""
Background worker for Stop hook.
Receives JSON from stdin, extracts Claude's response from transcript, adds to WAL.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

_script_dir = Path(__file__).parent.resolve()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from wal_manager import wal_append, compute_hash, get_claude_dir


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to hook_debug.log."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [capture_claude_worker] - {message}\n")
    except Exception:
        pass


def get_current_issue_local() -> Optional[int]:
    """Get current issue from local files ONLY."""
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

    return None


def get_existing_hashes() -> Set[str]:
    """Get hashes of all messages already in WAL."""
    wal_path = get_claude_dir() / "ghe_wal.jsonl"
    hashes: Set[str] = set()

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


def extract_last_claude_message(transcript_path: str) -> Optional[Dict[str, Any]]:
    """Extract the last Claude message from transcript."""
    if not transcript_path:
        return None

    expanded_path = os.path.expanduser(transcript_path)

    if not Path(expanded_path).exists():
        debug_log(f"Transcript not found: {expanded_path}", "WARN")
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
                            "hash": compute_hash(content),
                        }

                except json.JSONDecodeError:
                    continue

        return last_message

    except IOError as e:
        debug_log(f"Error reading transcript: {e}", "ERROR")
        return None


def spawn_worker() -> None:
    """Spawn the transcription worker to post messages."""
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
            debug_log("Spawned transcription worker")
    except Exception as e:
        debug_log(f"Failed to spawn worker: {e}", "ERROR")


def main() -> None:
    """Main entry point."""
    debug_log("capture_claude_worker started")

    # Read JSON from stdin (piped from bash)
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        debug_log(f"JSON decode error: {e}", "ERROR")
        sys.exit(0)

    transcript_path = input_data.get("transcript_path", "")

    if not transcript_path:
        debug_log("No transcript path provided")
        sys.exit(0)

    # Get existing hashes
    existing_hashes = get_existing_hashes()

    # Extract last Claude message
    msg = extract_last_claude_message(transcript_path)

    if not msg:
        debug_log("No Claude message found in transcript")
        sys.exit(0)

    # Check if already captured
    if msg["hash"] in existing_hashes:
        debug_log("Message already captured, skipping")
        sys.exit(0)

    # Get issue
    issue = get_current_issue_local() or 0

    # Append to WAL
    seq = wal_append(
        speaker="claude",
        issue=issue,
        content=msg["content"],
        content_hash=msg["hash"]
    )

    if seq > 0:
        debug_log(f"Captured Claude message seq={seq} len={len(msg['content'])}")
        spawn_worker()

    sys.exit(0)


if __name__ == "__main__":
    main()
