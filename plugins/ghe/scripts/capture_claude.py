#!/usr/bin/env python3
"""
Minimal Stop Hook for GHE Transcription System

This script does ONE thing only: save the transcript path for later processing.
The actual Claude response extraction happens in SessionStart (next session),
which is reliable and has unlimited time.

This design ensures NO messages are ever lost, even if this hook is killed.

Target execution time: <10ms (just a single file write)
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


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


def get_claude_dir() -> Path:
    """Find the .claude directory."""
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"
    if not claude_dir.exists():
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                return parent / ".claude"
        claude_dir.mkdir(parents=True, exist_ok=True)
    return claude_dir


def main() -> None:
    """
    Main entry point for Stop hook.

    Does ONLY ONE THING: save transcript_path to a file.
    This is a ~1ms operation that almost never fails.

    The actual message extraction happens in SessionStart.
    """
    # Output JSON immediately to avoid any timeout issues
    print(json.dumps({"event": "Stop", "suppressOutput": True}), flush=True)

    # Read stdin (must consume it even if we don't use much)
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    transcript_path = input_data.get("transcript_path", "")

    if not transcript_path:
        debug_log("No transcript path provided")
        sys.exit(0)

    # Save transcript path for SessionStart to process later
    # This is the ONLY operation we do - it's fast and reliable
    try:
        claude_dir = get_claude_dir()
        pending_file = claude_dir / "ghe_pending_transcript.json"

        with open(pending_file, "w") as f:
            json.dump({
                "transcript_path": transcript_path,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }, f)

        debug_log(f"Saved transcript path: {transcript_path}")
    except Exception as e:
        debug_log(f"Failed to save transcript path: {e}", "ERROR")

    sys.exit(0)


if __name__ == "__main__":
    main()
