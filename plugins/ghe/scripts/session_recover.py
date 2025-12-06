#!/usr/bin/env python3
"""
GHE Session Recovery - Check for active issue and recover context
Called by SessionStart hook
"""

import subprocess
import sys
from pathlib import Path

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from ghe_common import (
    ghe_init, ghe_info, ghe_warn,
    GHE_CURRENT_ISSUE, GHE_PLUGIN_ROOT
)


def main() -> None:
    """Main function"""
    # Initialize GHE environment
    ghe_init()

    # Import again after init to get updated values
    from ghe_common import GHE_CURRENT_ISSUE, GHE_PLUGIN_ROOT

    if GHE_CURRENT_ISSUE and GHE_CURRENT_ISSUE != "null":
        ghe_info(f"Recovering context from Issue #{GHE_CURRENT_ISSUE}...")

        # Try to run recall-elements script
        recall_script = Path(GHE_PLUGIN_ROOT) / 'scripts' / 'recall_elements.py'

        try:
            result = subprocess.run(
                [sys.executable, str(recall_script),
                 '--issue', GHE_CURRENT_ISSUE, '--recover'],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                ghe_warn(f"Element recall not available - run manually: "
                        f"recall_elements.py --issue {GHE_CURRENT_ISSUE} --recover")
        except (subprocess.SubprocessError, FileNotFoundError):
            ghe_warn(f"Element recall not available - run manually: "
                    f"recall_elements.py --issue {GHE_CURRENT_ISSUE} --recover")


if __name__ == '__main__':
    main()
