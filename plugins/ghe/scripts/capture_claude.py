#!/usr/bin/env python3
"""
Fast Claude Response Capture for GHE Transcription System

This script handles the Stop hook and captures Claude's response
to the Write-Ahead Log (WAL) for later posting by the background worker.

Target execution time: <500ms
NO GitHub API calls - only local file operations.
Spawns background worker (fire-and-forget) to post messages.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add scripts directory to path for imports
_script_dir = Path(__file__).parent.resolve()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from wal_manager import (
    wal_append,
    compute_hash,
    has_unposted_entries,
    is_worker_running,
)


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


def silent_exit(event: str = "Stop") -> None:
    """Exit silently with proper JSON output."""
    print(json.dumps({"event": event, "suppressOutput": True}), flush=True)
    sys.stdout.flush()
    sys.exit(0)


def get_current_issue_local() -> Optional[int]:
    """
    Get current issue from local files ONLY - NO GitHub API calls.

    Reads from:
    1. .claude/last_active_issue.json (primary)
    2. .claude/ghe.local.md current_issue setting (fallback)

    Returns None if no issue configured (worker will handle fallback).
    """
    # Find .claude directory
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"
    if not claude_dir.exists():
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                claude_dir = parent / ".claude"
                break
        else:
            return None

    # Try last_active_issue.json first (most reliable)
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
    config_file = claude_dir / "ghe.local.md"
    if config_file.exists():
        try:
            import re
            with open(config_file) as f:
                content = f.read()
            match = re.search(r'^current_issue:\s*["\']?(\d+)["\']?', content, re.MULTILINE)
            if match:
                return int(match.group(1))
        except (IOError, ValueError):
            pass

    return None


def extract_last_assistant_message(transcript_path: str) -> Optional[str]:
    """
    Extract Claude's last response from the transcript file.

    The transcript is a JSONL file with conversation messages.
    We look for the last assistant message.
    """
    if not transcript_path:
        debug_log("No transcript path provided")
        return None

    # Expand tilde (Stop hook provides ~/ paths)
    expanded_path = os.path.expanduser(transcript_path)

    if not Path(expanded_path).exists():
        debug_log(f"Transcript doesn't exist: {expanded_path}", "WARN")
        return None

    try:
        last_assistant_msg = None
        with open(expanded_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)

                    # The transcript structure: {"message": {"role": "assistant", "content": [...]}}
                    message = entry.get("message", {})
                    if not isinstance(message, dict):
                        continue

                    if message.get("role") == "assistant":
                        content = message.get("content", "")
                        if isinstance(content, list):
                            # Content is a list of blocks (text, tool_use, thinking, etc.)
                            text_parts = []
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text_parts.append(block.get("text", ""))
                                elif isinstance(block, str):
                                    text_parts.append(block)
                            content = "\n".join(text_parts)
                        if content:
                            last_assistant_msg = content
                except json.JSONDecodeError:
                    continue

        if last_assistant_msg:
            debug_log(f"Found assistant message, len={len(last_assistant_msg)}")
        else:
            debug_log("No assistant message found in transcript", "WARN")

        return last_assistant_msg

    except IOError as e:
        debug_log(f"Error reading transcript: {e}", "ERROR")
        return None


def spawn_worker_if_not_running() -> None:
    """
    Spawn the background transcription worker if not already running.

    Fire-and-forget - we don't wait for it to complete.
    """
    # Check if there are messages to post
    if not has_unposted_entries():
        debug_log("No unposted entries, not spawning worker")
        return

    # Check if worker is already running
    if is_worker_running():
        debug_log("Worker already running, skipping spawn")
        return

    # Spawn worker in background
    worker_script = _script_dir / "transcription_worker.py"
    if not worker_script.exists():
        debug_log(f"Worker script not found: {worker_script}", "ERROR")
        return

    try:
        # Use subprocess.Popen with DEVNULL to completely detach
        subprocess.Popen(
            [sys.executable, str(worker_script)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            start_new_session=True,  # Fully detach from parent
            cwd=str(Path.cwd()),
        )
        debug_log("Spawned background worker")
    except Exception as e:
        debug_log(f"Failed to spawn worker: {e}", "ERROR")


def main() -> None:
    """Main entry point for Stop hook."""
    debug_log("capture_claude started")

    # Read JSON from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        debug_log(f"JSON decode error: {e}", "ERROR")
        silent_exit()

    transcript_path = input_data.get("transcript_path", "")

    # Extract Claude's last response from transcript
    response = extract_last_assistant_message(transcript_path)

    if not response:
        debug_log("No response to capture")
        # Still spawn worker in case there are pending user messages
        spawn_worker_if_not_running()
        silent_exit()

    # Get current issue from local config (NO API call)
    issue = get_current_issue_local()

    if not issue:
        debug_log("No issue configured, using issue=0 placeholder")
        issue = 0

    # Append to WAL
    content_hash = compute_hash(response)
    seq = wal_append(
        speaker="claude",
        issue=issue,
        content=response,
        content_hash=content_hash
    )

    debug_log(f"Captured claude response seq={seq} issue={issue} len={len(response)}")

    # Spawn background worker to post messages
    spawn_worker_if_not_running()

    # Exit cleanly
    silent_exit()


if __name__ == "__main__":
    main()
