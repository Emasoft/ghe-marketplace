#!/usr/bin/env python3
"""
Real-Time Message Capture for GHE Transcription System

This script handles the UserPromptSubmit hook and captures BOTH:
1. Claude's previous response (from transcript) - posted immediately
2. User's new message - posted immediately

This gives near-real-time transcription: Claude's response is posted
when the user sends their next message.

Target execution time: <500ms
NO GitHub API calls - only local file operations + worker spawn.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add scripts directory to path for imports
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
            f.write(f"{timestamp} {level:<5} [capture_user] - {message}\n")
    except Exception:
        pass


def silent_exit(event: str = "UserPromptSubmit") -> None:
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


def is_hook_feedback(prompt: str) -> bool:
    """Check if this prompt is hook feedback (should be skipped)."""
    skip_patterns = [
        "Stop hook feedback:",
        "TRANSCRIPTION BLOCKING",
        "PreToolUse hook feedback:",
        "PostToolUse hook feedback:",
        "SessionStart hook feedback:",
        "UserPromptSubmit hook feedback:",
        "[GHE]",  # Our own messages
    ]
    for pattern in skip_patterns:
        if pattern in prompt:
            return True
    return False


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


def get_last_captured_timestamp() -> Optional[str]:
    """Get timestamp of last captured message from state file."""
    claude_dir = get_claude_dir()
    state_file = claude_dir / "ghe_capture_state.json"

    if not state_file.exists():
        return None

    try:
        with open(state_file) as f:
            data = json.load(f)
            return data.get("last_timestamp")
    except (json.JSONDecodeError, IOError):
        return None


def save_capture_state(timestamp: str) -> None:
    """Save timestamp of last captured message."""
    claude_dir = get_claude_dir()
    state_file = claude_dir / "ghe_capture_state.json"

    try:
        with open(state_file, 'w') as f:
            json.dump({"last_timestamp": timestamp, "updated": datetime.now(timezone.utc).isoformat()}, f)
    except IOError:
        pass


def extract_new_claude_messages(transcript_path: str, existing_hashes: Set[str]) -> List[Dict[str, Any]]:
    """
    Extract Claude messages from transcript that we haven't captured yet.

    Returns list of dicts with: content, timestamp, hash
    """
    if not transcript_path:
        return []

    # Expand tilde
    expanded_path = os.path.expanduser(transcript_path)

    if not Path(expanded_path).exists():
        debug_log(f"Transcript not found: {expanded_path}", "WARN")
        return []

    messages = []
    last_ts = get_last_captured_timestamp()

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

                    # Only assistant messages
                    role = message.get("role", "")
                    if role != "assistant":
                        continue

                    # Check timestamp - only get messages after last capture
                    entry_ts = entry.get("timestamp", "")
                    if last_ts and entry_ts and entry_ts <= last_ts:
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

                    if not content or len(content.strip()) < 5:
                        continue

                    # Compute hash for deduplication
                    content_hash = compute_hash(content)

                    # Skip if already captured
                    if content_hash in existing_hashes:
                        continue

                    messages.append({
                        "content": content,
                        "timestamp": entry_ts,
                        "hash": content_hash,
                    })

                except json.JSONDecodeError:
                    continue

        debug_log(f"Found {len(messages)} new Claude messages in transcript")
        return messages

    except IOError as e:
        debug_log(f"Error reading transcript: {e}", "ERROR")
        return []


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
    """Main entry point for UserPromptSubmit hook."""
    debug_log("capture_user started")

    # Read JSON from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        debug_log(f"JSON decode error: {e}", "ERROR")
        silent_exit()

    prompt = input_data.get("prompt", "")
    transcript_path = input_data.get("transcript_path", "")

    # Get current issue from local config (NO API call)
    issue = get_current_issue_local()
    if not issue:
        debug_log("No issue configured, using issue=0 placeholder")
        issue = 0

    # Get existing hashes for deduplication
    existing_hashes = get_existing_hashes()
    messages_captured = 0
    last_timestamp = None

    # STEP 1: Capture Claude's previous response(s) from transcript
    # This happens BEFORE we capture the user's new message
    if transcript_path:
        claude_messages = extract_new_claude_messages(transcript_path, existing_hashes)
        for msg in claude_messages:
            seq = wal_append(
                speaker="claude",
                issue=issue,
                content=msg["content"],
                content_hash=msg["hash"]
            )
            if seq > 0:
                messages_captured += 1
                existing_hashes.add(msg["hash"])
                if msg["timestamp"]:
                    last_timestamp = msg["timestamp"]
                debug_log(f"Captured Claude message seq={seq} len={len(msg['content'])}")

        # Save capture state
        if last_timestamp:
            save_capture_state(last_timestamp)

    # STEP 2: Capture user's new message
    if prompt and not is_hook_feedback(prompt):
        content_hash = compute_hash(prompt)
        if content_hash not in existing_hashes:
            seq = wal_append(
                speaker="user",
                issue=issue,
                content=prompt,
                content_hash=content_hash
            )
            if seq > 0:
                messages_captured += 1
                debug_log(f"Captured user message seq={seq} len={len(prompt)}")
    elif is_hook_feedback(prompt):
        debug_log("Hook feedback detected, skipping user message")

    # STEP 3: Spawn worker to post messages immediately
    if messages_captured > 0:
        spawn_worker()
        debug_log(f"Total {messages_captured} messages captured, worker spawned")

    # Exit cleanly
    silent_exit()


if __name__ == "__main__":
    main()
