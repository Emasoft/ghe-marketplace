#!/usr/bin/env python3
"""
Real-Time Message Capture for GHE Transcription System

This script handles the UserPromptSubmit hook and captures BOTH:
1. Claude's previous response (from transcript) - posted immediately
2. User's new message - posted immediately

CRITICAL: Outputs JSON response IMMEDIATELY after reading stdin to prevent
Claude Code's internal timeout from aborting the process. The actual capture
work is done in a subprocess to avoid blocking.

Target execution time: <50ms to JSON output
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

# Add scripts directory to path for imports
_script_dir = Path(__file__).parent.resolve()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to hook_debug.log."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [capture_user] - {message}\n")
    except Exception:
        pass


def main() -> None:
    """
    Main entry point for UserPromptSubmit hook.

    CRITICAL: Output JSON immediately to satisfy Claude Code's internal timeout,
    then fork the actual work to a subprocess.
    """
    # Step 1: Read stdin IMMEDIATELY
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Output valid JSON even on error
        print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
        sys.exit(0)

    # Step 2: Output JSON response IMMEDIATELY to prevent abort
    # This satisfies Claude Code's internal timeout
    print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
    sys.stdout.flush()

    # Step 3: Fork the capture work to a subprocess
    # This runs in background while we exit cleanly
    prompt = input_data.get("prompt", "")
    transcript_path = input_data.get("transcript_path", "")

    if prompt or transcript_path:
        try:
            # Pass data via environment variables to avoid argument parsing issues
            env = os.environ.copy()
            env["GHE_PROMPT"] = prompt
            env["GHE_TRANSCRIPT_PATH"] = transcript_path
            env["GHE_CWD"] = str(Path.cwd())

            worker_script = _script_dir / "capture_worker.py"
            if worker_script.exists():
                subprocess.Popen(
                    [sys.executable, str(worker_script)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    env=env,
                    cwd=str(Path.cwd()),
                )
                debug_log("Forked capture_worker subprocess")
        except Exception as e:
            debug_log(f"Failed to fork worker: {e}", "ERROR")

    debug_log("capture_user exiting cleanly")
    sys.exit(0)


if __name__ == "__main__":
    main()
