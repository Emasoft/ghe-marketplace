#!/usr/bin/env python3
"""
Example Worker Script - Background Processing

This worker is spawned by example_hook.py to do the actual work.
It runs in background after the hook exits, so it can take as long as needed.

Input is received via environment variables:
- HOOK_PROMPT: The user's prompt text
- HOOK_TRANSCRIPT_PATH: Path to the transcript file
- HOOK_CWD: Original working directory
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to hook_debug.log."""
    try:
        cwd = os.environ.get("HOOK_CWD", str(Path.cwd()))
        log_file = Path(cwd) / ".claude" / "hook_debug.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [example_worker] - {message}\n")
    except Exception:
        pass


def main() -> None:
    """
    Main entry point for the worker.

    This runs in background after the hook exits.
    Do all your heavy processing here.
    """
    debug_log("Worker started")

    # Read input from environment variables
    prompt = os.environ.get("HOOK_PROMPT", "")
    transcript_path = os.environ.get("HOOK_TRANSCRIPT_PATH", "")
    cwd = os.environ.get("HOOK_CWD", str(Path.cwd()))

    # ============================================================
    # YOUR ACTUAL WORK GOES HERE
    # ============================================================

    # Example: Log the prompt
    if prompt:
        debug_log(f"Received prompt: {prompt[:100]}...")

    # Example: Read transcript
    if transcript_path:
        expanded_path = os.path.expanduser(transcript_path)
        if Path(expanded_path).exists():
            debug_log(f"Transcript exists at: {expanded_path}")
            # Process transcript...
        else:
            debug_log(f"Transcript not found: {expanded_path}", "WARN")

    # Example: Write to a file
    output_file = Path(cwd) / ".claude" / "example_output.txt"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "a") as f:
        f.write(f"[{datetime.now().isoformat()}] Processed: {prompt[:50]}...\n")

    # Example: Make API calls (would be slow in hook, fine here)
    # response = requests.post("https://api.example.com/...", json={...})

    # Example: Spawn another subprocess if needed
    # subprocess.run([...])

    debug_log("Worker completed")


if __name__ == "__main__":
    main()
