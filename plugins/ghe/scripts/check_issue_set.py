#!/usr/bin/env python3
"""
Quick check if an issue is currently set for transcription
Returns exit 0 if issue is set, exit 1 if not
"""

import sys
from pathlib import Path

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from ghe_common import ghe_init, ghe_get_setting, ghe_info


def main() -> None:
    """Main function"""
    # Initialize GHE environment
    ghe_init()

    # Check if a current issue is set
    issue = ghe_get_setting("current_issue", "")

    if issue and issue != "null":
        ghe_info(f"TRANSCRIPTION ACTIVE: Issue #{issue}")
        sys.exit(0)

    ghe_info("TRANSCRIPTION INACTIVE: No issue set")
    sys.exit(0)  # Exit 0 to not block the hook, just inform


if __name__ == '__main__':
    main()
