#!/usr/bin/env python3
"""
GHE Session Recovery - Check for active issue and recover context
Called by SessionStart hook
"""

import json
import subprocess
import sys
from pathlib import Path

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from ghe_common import ghe_init, GHE_CURRENT_ISSUE, GHE_PLUGIN_ROOT


def main() -> None:
    """Main function"""
    # Initialize GHE environment
    ghe_init()

    # Import again after init to get updated values
    from ghe_common import GHE_CURRENT_ISSUE, GHE_PLUGIN_ROOT

    if GHE_CURRENT_ISSUE and GHE_CURRENT_ISSUE != "null":
        # Try to run recall-elements script silently
        recall_script = Path(GHE_PLUGIN_ROOT) / 'scripts' / 'recall_elements.py'

        try:
            subprocess.run(
                [sys.executable, str(recall_script),
                 '--issue', GHE_CURRENT_ISSUE, '--recover'],
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
