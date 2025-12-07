#!/usr/bin/env python3
"""
GHE Transcription Notification for SessionStart hook.

For SessionStart hooks, stdout is NOT shown to user.
Must use JSON with hookSpecificOutput.additionalContext.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, Tuple


def get_active_issue() -> Tuple[Optional[int], str]:
    """Get the current active issue number and title."""
    # Find .claude directory
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"

    if not claude_dir.exists():
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                claude_dir = parent / ".claude"
                break
        else:
            return None, ""

    config_path = claude_dir / "last_active_issue.json"
    if not config_path.exists():
        return None, ""

    try:
        with open(config_path) as f:
            data = json.load(f)
            issue = data.get("issue")
            title = data.get("title", "")
            return issue, title
    except (json.JSONDecodeError, IOError):
        return None, ""


def main() -> None:
    """Output notification via hookSpecificOutput.additionalContext for SessionStart."""
    issue, title = get_active_issue()

    if issue:
        # Build notification message
        if title:
            message = f"GHE Transcription ON: Issue #{issue} - {title}"
        else:
            message = f"GHE Transcription ON: Issue #{issue}"

        # For SessionStart, must use JSON with additionalContext
        # Plain stdout is NOT shown to user for SessionStart hooks
        output = {
            "hookSpecificOutput": {
                "additionalContext": message
            }
        }
        print(json.dumps(output))
    else:
        # No issue - suppress output entirely
        print(json.dumps({"suppressOutput": True}))


if __name__ == "__main__":
    main()
