#!/usr/bin/env python3
"""
Spawn a Claude session in a BACKGROUND Terminal window (macOS only)
Terminal window stays in background - NEVER steals focus!

WINDOW IDENTITY GUARANTEE:
The prompt is piped directly to Claude as part of the command that creates the window.
This is ATOMIC - there is NO separate "send to window" step, NO keystroke routing.
It is PHYSICALLY IMPOSSIBLE for the prompt to go to a different window.

Usage: spawn_background.py "Your prompt here" [working_dir]
"""

import sys
import os
import platform
import subprocess
import tempfile
import uuid
from datetime import datetime
from pathlib import Path


def log_message(log_file: Path, agent_id: str, message: str) -> None:
    """Log a message with timestamp and agent ID."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_file, 'a') as f:
        f.write(f"[{timestamp}] [{agent_id}] {message}\n")


def get_security_prefix(working_dir: str, parent_dir: str) -> str:
    """Generate the security prefix with agent guidelines."""
    return f"""[AGENT GUIDELINES]
You are a background agent. Execute your task with these boundaries:
- Project directory: {working_dir}
- Parent directory (if sub-git): {parent_dir}
- Allowed write locations: project dir, parent dir, ~/.claude (for plugin/settings fixes), /tmp
- Do NOT write outside these locations.

REPORT POSTING (MANDATORY):
- ALL reports MUST be posted to BOTH locations:
  1. GitHub Issue Thread - Full report text (NOT just a link!)
  2. GHE_REPORTS/ folder - Same full report text (FLAT structure, no subfolders!)
- Report naming: <TIMESTAMP>_<title or description>_(<AGENT>).md
  Example: 20251206143022GMT+01_issue_42_dev_complete_(Hephaestus).md
  Timestamp format: YYYYMMDDHHMMSSTimezone
- REQUIREMENTS/ is SEPARATE - permanent design docs, never deleted
- REDACT before posting: API keys, passwords, emails, user paths → ✕✕REDACTED✕✕

[TASK]
"""


def spawn_background_agent(prompt: str, working_dir: str) -> None:
    """Spawn a Claude session in a background Terminal window (macOS only)."""

    # Ensure macOS
    if platform.system() != "Darwin":
        print("ERROR: macOS only", file=sys.stderr)
        sys.exit(1)

    # Generate unique identifier for tracking
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    agent_uuid = str(uuid.uuid4())
    agent_id = f"GHE-AGENT-{agent_uuid}"

    # Get log file location
    log_file = Path(os.environ.get('BACKGROUND_AGENT_LOG', '/tmp/background_agent_hook.log'))

    # Resolve working directory to absolute path
    working_dir_path = Path(working_dir).resolve()
    working_dir = str(working_dir_path)

    # Get parent directory (for sub-git projects)
    parent_dir = str(working_dir_path.parent)

    # Create GHE_REPORTS directory (FLAT structure - no subfolders!)
    ghe_reports_dir = working_dir_path / "GHE_REPORTS"
    ghe_reports_dir.mkdir(parents=True, exist_ok=True)

    # Write prompt to temp file (avoids shell escaping issues)
    with tempfile.NamedTemporaryFile(
        mode='w',
        prefix='claude_prompt_',
        suffix='.txt',
        dir='/tmp',
        delete=False
    ) as prompt_file:
        prompt_file_path = prompt_file.name
        security_prefix = get_security_prefix(working_dir, parent_dir)
        prompt_file.write(f"{security_prefix}{prompt}")

    # Log spawn event
    log_message(log_file, agent_id, "=" * 42)
    log_message(log_file, agent_id, f"Spawning agent: {agent_id}")
    log_message(log_file, agent_id, f"Directory: {working_dir}")
    log_message(log_file, agent_id, f"Prompt: {prompt[:100]}...")

    # THE IRONCLAD GUARANTEE:
    # This entire command runs ATOMICALLY in a single Terminal tab.
    # The prompt is piped directly to Claude - there is NO separate send step.
    # It is PHYSICALLY IMPOSSIBLE for the prompt to go to a different window.
    full_cmd = f"cd '{working_dir}' && cat '{prompt_file_path}' | claude --dangerously-skip-permissions; rm -f '{prompt_file_path}'"

    # Create Terminal window in background (no activation, no focus stealing)
    applescript = f'''
tell application "Terminal"
    -- ATOMIC: Command is bound to this tab at creation time
    set newTab to do script "{full_cmd}"
    set newWindow to first window whose tabs contains newTab
    set custom title of newTab to "{agent_id}"
    return (id of newWindow as text) & "|" & (tty of newTab)
end tell
'''

    try:
        result = subprocess.run(
            ['osascript', '-e', applescript],
            capture_output=True,
            text=True,
            check=True
        )
        window_info = result.stdout.strip()

        # Parse window info
        parts = window_info.split('|')
        window_id = parts[0] if len(parts) > 0 else "unknown"
        tty_path = parts[1] if len(parts) > 1 else "unknown"

        # Log completion
        log_message(log_file, agent_id, f"Window ID: {window_id}, TTY: {tty_path}")
        log_message(log_file, agent_id, "Spawn complete")

        # Print success message
        print()
        print("=" * 46)
        print("Background Agent Spawned")
        print("=" * 46)
        print(f"Agent ID:   {agent_id}")
        print(f"Window ID:  {window_id}")
        print(f"TTY:        {tty_path}")
        print(f"Directory:  {working_dir}")
        print(f"Prompt:     {prompt[:60]}...")
        print()
        print("WINDOW IDENTITY: 100% GUARANTEED")
        print("  Prompt piped directly to Claude (atomic, no keystrokes)")
        print("  Physically impossible for prompt to go elsewhere")
        print()
        print("Working in background - no interruptions!")
        print("Check GHE_REPORTS/ for output.")
        print("=" * 46)

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to spawn Terminal window: {e.stderr}", file=sys.stderr)
        # Clean up temp file on error
        Path(prompt_file_path).unlink(missing_ok=True)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        # Clean up temp file on error
        Path(prompt_file_path).unlink(missing_ok=True)
        sys.exit(1)


def main():
    """Main entry point."""
    # Parse arguments
    if len(sys.argv) < 2:
        prompt = "Hello! Please run git status and create a summary."
    else:
        prompt = sys.argv[1]

    if len(sys.argv) < 3:
        working_dir = os.getcwd()
    else:
        working_dir = sys.argv[2]

    # Spawn the background agent
    spawn_background_agent(prompt, working_dir)


if __name__ == "__main__":
    main()
