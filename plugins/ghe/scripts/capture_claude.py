#!/usr/bin/env python3
"""
Stop Hook for GHE Transcription System

Captures Claude's response from the transcript and adds to WAL for posting.

CRITICAL: Outputs JSON response IMMEDIATELY after reading stdin to prevent
Claude Code's internal timeout from aborting the process. The actual capture
work is done by reusing capture_worker.py.

Target execution time: <50ms to JSON output
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


_script_dir = Path(__file__).parent.resolve()


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to hook_debug.log."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [capture_claude] - {message}\n")
    except Exception:
        pass


def main():
    """
    Main entry point for Stop hook.

    CRITICAL: Output JSON immediately to satisfy Claude Code's internal timeout,
    then fork the actual work to a subprocess.
    """
    # Step 1: Read stdin IMMEDIATELY
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"event": "Stop"}), flush=True)
        sys.exit(0)

    # Step 2: Output JSON response IMMEDIATELY to prevent abort
    print(json.dumps({"event": "Stop"}), flush=True)
    sys.stdout.flush()

    # Step 3: Fork the capture work to subprocess
    # Reuse capture_worker.py which handles all the capture logic
    transcript_path = input_data.get("transcript_path", "")

    if transcript_path:
        try:
            env = os.environ.copy()
            env["GHE_PROMPT"] = ""  # No user prompt in Stop hook
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

    debug_log("capture_claude exiting cleanly")
    sys.exit(0)


if __name__ == "__main__":
    main()
