#!/usr/bin/env python3
"""
Fast User Message Capture for GHE Transcription System

This script handles the UserPromptSubmit hook and captures user messages
to the Write-Ahead Log (WAL) for later posting by the background worker.

Target execution time: <100ms
NO GitHub API calls - only local file operations.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Add scripts directory to path for imports
_script_dir = Path(__file__).parent.resolve()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from wal_manager import wal_append, compute_hash


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

    if not prompt:
        debug_log("Empty prompt, skipping")
        silent_exit()

    # Skip hook feedback messages
    if is_hook_feedback(prompt):
        debug_log("Hook feedback detected, skipping")
        silent_exit()

    # Get current issue from local config (NO API call)
    issue = get_current_issue_local()

    if not issue:
        # No issue configured - still capture but worker will handle fallback
        debug_log("No issue configured, using issue=0 placeholder")
        issue = 0

    # Append to WAL
    content_hash = compute_hash(prompt)
    seq = wal_append(
        speaker="user",
        issue=issue,
        content=prompt,
        content_hash=content_hash
    )

    debug_log(f"Captured user message seq={seq} issue={issue} len={len(prompt)}")

    # Exit cleanly
    silent_exit()


if __name__ == "__main__":
    main()
