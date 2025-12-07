#!/usr/bin/env python3
"""
Simple notification script for GHE Transcription System.

Outputs ONLY the transcription status:
- "Transcription ON to issue #XYZ" when active
- Nothing when no issue is set

This is the "silent hooks" implementation - minimal output.
"""
from __future__ import annotations

import json
import os
import sys
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
    """Output minimal transcription status notification."""
    issue, title = get_active_issue()

    if issue:
        # Output the simple notification
        if title:
            print(f"Transcription ON to issue #{issue}: {title}")
        else:
            print(f"Transcription ON to issue #{issue}")
    # If no issue, output nothing (truly silent)


if __name__ == "__main__":
    main()
