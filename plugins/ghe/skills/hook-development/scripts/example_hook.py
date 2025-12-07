#!/usr/bin/env python3
"""
Example Hook Script - Immediate Response Pattern

This is a template for writing Claude Code hooks that never get aborted.
Copy and modify this script for your own hooks.

CRITICAL: Output JSON immediately after reading stdin to prevent
Claude Code's internal timeout from aborting the process.
"""

import json
import os
import subprocess
import sys
from pathlib import Path


_script_dir = Path(__file__).parent.resolve()


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to hook_debug.log."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        from datetime import datetime, timezone
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [example_hook] - {message}\n")
    except Exception:
        pass


def main() -> None:
    """
    Main entry point for the hook.

    Pattern:
    1. Read stdin IMMEDIATELY
    2. Output JSON IMMEDIATELY (prevents abort)
    3. Fork subprocess for actual work
    """
    # ============================================================
    # STEP 1: Read stdin IMMEDIATELY
    # ============================================================
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # Even on error, output valid JSON
        print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
        sys.exit(0)

    # ============================================================
    # STEP 2: Output JSON IMMEDIATELY
    # This satisfies Claude Code's internal timeout
    # ============================================================
    print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
    sys.stdout.flush()

    # ============================================================
    # STEP 3: Fork subprocess to do actual work
    # The work runs in background while this script exits cleanly
    # ============================================================

    # Extract data you need from input
    prompt = input_data.get("prompt", "")
    transcript_path = input_data.get("transcript_path", "")

    if prompt or transcript_path:
        try:
            # Pass data via environment variables (safer than args)
            env = os.environ.copy()
            env["HOOK_PROMPT"] = prompt
            env["HOOK_TRANSCRIPT_PATH"] = transcript_path
            env["HOOK_CWD"] = str(Path.cwd())

            worker_script = _script_dir / "example_worker.py"
            if worker_script.exists():
                subprocess.Popen(
                    [sys.executable, str(worker_script)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,  # Detach from parent
                    env=env,
                    cwd=str(Path.cwd()),
                )
                debug_log("Forked worker subprocess")
        except Exception as e:
            debug_log(f"Failed to fork worker: {e}", "ERROR")

    debug_log("Hook exiting cleanly")
    sys.exit(0)


if __name__ == "__main__":
    main()
