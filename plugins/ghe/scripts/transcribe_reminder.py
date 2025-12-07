#!/usr/bin/env python3
"""
Reminder hook for significant bash commands
Returns "allow" with a reminder message about transcription
"""

import json


def main() -> None:
    """Output the hook response"""
    response = {
        "event": "PreToolUse",
        "suppressOutput": True,
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow"
        }
    }
    print(json.dumps(response))


if __name__ == '__main__':
    main()
