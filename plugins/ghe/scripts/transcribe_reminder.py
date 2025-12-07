#!/usr/bin/env python3
"""
Reminder hook for significant bash commands
Returns "allow" with a reminder message about transcription
"""

import json
from datetime import datetime
from pathlib import Path


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
            f.write(f"{timestamp} {level:<5} [transcribe_reminder] - {message}\n")
    except Exception:
        pass  # Never fail on logging


def main() -> None:
    """Output the hook response"""
    debug_log("PreToolUse Bash hook called")
    response = {
        "event": "PreToolUse",
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow"
        }
    }
    print(json.dumps(response))
    debug_log("PreToolUse Bash hook completed")


if __name__ == '__main__':
    main()
