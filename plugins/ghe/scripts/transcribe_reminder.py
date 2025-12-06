#!/usr/bin/env python3
"""
Reminder hook for significant bash commands
Returns "allow" with a reminder message about transcription
"""

import json


def main() -> None:
    """Output the hook response"""
    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": "Reminder: If this makes significant changes (git commit, deployment), note for transcription if active."
        }
    }
    print(json.dumps(response, indent=2))


if __name__ == '__main__':
    main()
