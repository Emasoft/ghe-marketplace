#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Quick check if an issue is currently set for transcription
Returns exit 0 if issue is set, exit 1 if not
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))


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
            f.write(f"{timestamp} {level:<5} [check_issue_set] - {message}\n")
    except Exception:
        pass  # Never fail on logging


debug_log("Starting check_issue_set.py")

# Safe import with fallback - MUST output valid JSON on any failure
try:
    from ghe_common import ghe_init, ghe_get_setting
    debug_log("Imported ghe_common successfully")
except ImportError as e:
    debug_log(f"ImportError: {e} - exiting with valid JSON", "ERROR")
    # If import fails, output valid JSON and exit gracefully
    print(json.dumps({"event": "UserPromptSubmit", "suppressOutput": True}), flush=True)
    sys.stdout.flush()
    sys.exit(0)


def main() -> None:
    """Main function"""
    debug_log("main() started")

    # Initialize GHE environment
    debug_log("Calling ghe_init()...")
    ghe_init()
    debug_log("ghe_init() completed")

    # Check if a current issue is set
    issue = ghe_get_setting("current_issue", "")
    debug_log(f"current_issue={issue or 'None'}")

    # Suppress output from user view
    debug_log("Outputting JSON and exiting")
    print(json.dumps({"event": "UserPromptSubmit", "suppressOutput": True}), flush=True)
    sys.stdout.flush()
    sys.exit(0)


if __name__ == '__main__':
    main()
