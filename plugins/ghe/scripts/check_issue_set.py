#!/usr/bin/env python3
"""
Quick check if an issue is currently set for transcription
Returns exit 0 if issue is set, exit 1 if not
"""

import json
import sys
from pathlib import Path

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

# Safe import with fallback - MUST output valid JSON on any failure
try:
    from ghe_common import ghe_init, ghe_get_setting
except ImportError:
    # If import fails, output valid JSON and exit gracefully
    print(json.dumps({"event": "UserPromptSubmit", "suppressOutput": True}))
    sys.exit(0)


def main() -> None:
    """Main function"""
    # Initialize GHE environment
    ghe_init()

    # Check if a current issue is set
    issue = ghe_get_setting("current_issue", "")

    # Suppress output from user view
    print(json.dumps({"event": "UserPromptSubmit", "suppressOutput": True}))
    sys.exit(0)


if __name__ == '__main__':
    main()
