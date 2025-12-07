#!/usr/bin/env python3
"""
GHE Transcription Notification for SessionStart hook.

For SessionStart hooks, stdout is NOT shown to user.
Must use JSON with hookSpecificOutput.additionalContext.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.

    Format: YYYY-MM-DD HH:MM:SS,mmm LEVEL [logger] - message
    Compatible with: lnav, glogg, Splunk, ELK, Log4j viewers
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [transcription_notify] - {message}\n")
    except Exception:
        pass  # Never fail on logging


def get_active_issue() -> Tuple[Optional[int], str]:
    """Get the current active issue number and title."""
    debug_log("get_active_issue() called")

    # Find .claude directory
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"
    debug_log(f"cwd={cwd}")

    if not claude_dir.exists():
        debug_log("Looking for .claude in parent directories...")
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                claude_dir = parent / ".claude"
                debug_log(f"Found .claude at {claude_dir}")
                break
        else:
            debug_log("No .claude directory found")
            return None, ""

    config_path = claude_dir / "last_active_issue.json"
    if not config_path.exists():
        debug_log(f"File not found: {config_path}")
        return None, ""

    debug_log(f"Reading {config_path}")
    try:
        with open(config_path) as f:
            data = json.load(f)
            issue = data.get("issue")
            title = data.get("title", "")
            debug_log(f"Parsed issue={issue}, title={title[:50] if title else 'N/A'}")
            return issue, title
    except json.JSONDecodeError as e:
        debug_log(f"JSONDecodeError: {e}", "ERROR")
        return None, ""
    except IOError as e:
        debug_log(f"IOError: {e}", "ERROR")
        return None, ""


def main() -> None:
    """Output notification via hookSpecificOutput.additionalContext for SessionStart."""
    debug_log("main() started")
    issue, title = get_active_issue()

    if issue:
        # Build notification message
        if title:
            message = f"GHE Transcription ON: Issue #{issue} - {title}"
        else:
            message = f"GHE Transcription ON: Issue #{issue}"

        debug_log(f"Outputting notification: {message[:80]}")
        # For SessionStart, must use JSON with event field and additionalContext
        # Plain stdout is NOT shown to user for SessionStart hooks
        output = {
            "event": "SessionStart",
            "hookSpecificOutput": {
                "additionalContext": message
            }
        }
        print(json.dumps(output))
        debug_log("Output complete with additionalContext")
    else:
        # No issue - suppress output entirely
        debug_log("No issue found, suppressing output")
        print(json.dumps({"event": "SessionStart", "suppressOutput": True}))
        debug_log("Output complete with suppressOutput")


if __name__ == "__main__":
    main()
