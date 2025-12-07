#!/usr/bin/env python3
"""
GHE Session Recovery - Check for active issue and recover context
Called by SessionStart hook

This script:
1. Checks if there's a current issue set in config
2. If not, checks for last_active_issue.json and auto-activates it
3. Recovers context for the active issue
"""

import json
import subprocess
import sys
from pathlib import Path

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from ghe_common import ghe_init, GHE_CURRENT_ISSUE, GHE_PLUGIN_ROOT


def auto_resume_last_issue() -> str:
    """
    Check for last_active_issue.json and auto-resume if found.

    Returns:
        Issue number if resumed, empty string otherwise
    """
    last_active_file = Path(".claude/last_active_issue.json")

    if not last_active_file.exists():
        return ""

    try:
        data = json.loads(last_active_file.read_text())
        issue_num = str(data.get("issue", ""))
        title = data.get("title", "")
        repo = data.get("repo", "")

        if not issue_num:
            return ""

        # Build gh command with repo if available
        gh_cmd = ["gh", "issue", "view", issue_num, "--json", "number", "--jq", ".number"]
        if repo:
            gh_cmd.extend(["--repo", repo])

        # Verify issue still exists on GitHub
        result = subprocess.run(
            gh_cmd,
            capture_output=True,
            text=True,
            check=True
        )

        if result.stdout.strip() != issue_num:
            return ""

        # Auto-activate by calling set-issue
        auto_transcribe = Path(GHE_PLUGIN_ROOT) / 'scripts' / 'auto_transcribe.py'
        subprocess.run(
            [sys.executable, str(auto_transcribe), "set-issue", issue_num],
            capture_output=True,
            text=True,
            check=False
        )

        return issue_num

    except (json.JSONDecodeError, subprocess.CalledProcessError, FileNotFoundError):
        return ""


def main() -> None:
    """Main function"""
    # Initialize GHE environment
    ghe_init()

    # Import again after init to get updated values
    from ghe_common import GHE_CURRENT_ISSUE, GHE_PLUGIN_ROOT

    active_issue = GHE_CURRENT_ISSUE

    # If no current issue, try to auto-resume from last_active_issue.json
    if not active_issue or active_issue == "null":
        active_issue = auto_resume_last_issue()

    if active_issue and active_issue != "null":
        # Try to run recall-elements script silently
        recall_script = Path(GHE_PLUGIN_ROOT) / 'scripts' / 'recall_elements.py'

        try:
            subprocess.run(
                [sys.executable, str(recall_script),
                 '--issue', active_issue, '--recover'],
                capture_output=True,
                text=True,
                check=False
            )
        except (subprocess.SubprocessError, FileNotFoundError):
            pass

    # Suppress output from user view
    print(json.dumps({"suppressOutput": True}))


if __name__ == '__main__':
    main()
