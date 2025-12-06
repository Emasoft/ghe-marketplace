#!/usr/bin/env python3
"""
Spawn a Claude session in a BACKGROUND Terminal window.
Cross-platform: macOS, Windows, Linux

WINDOW IDENTITY GUARANTEE:
The prompt is piped directly to Claude as part of the command that creates the window.
This is ATOMIC - there is NO separate "send to window" step, NO keystroke routing.
It is PHYSICALLY IMPOSSIBLE for the prompt to go to a different window.

Usage: python spawn_background.py "Your prompt here" [working_dir]

Platforms:
- macOS: Uses Terminal.app with AppleScript (no focus stealing)
- Windows: Uses Windows Terminal (wt) or cmd.exe with START
- Linux: Uses gnome-terminal, konsole, xterm, or tmux (auto-detected)
"""

import sys
import os
import platform
import subprocess
import tempfile
import uuid
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def log_message(log_file: Path, agent_id: str, message: str) -> None:
    """Log a message with timestamp and agent ID."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(log_file, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] [{agent_id}] {message}\n")


def get_security_prefix(working_dir: str, parent_dir: str) -> str:
    """Generate the security prefix with agent guidelines."""
    return f"""[AGENT GUIDELINES]
You are a background agent. Execute your task with these boundaries:
- Project directory: {working_dir}
- Parent directory (if sub-git): {parent_dir}
- Allowed write locations: project dir, parent dir, ~/.claude (for plugin/settings fixes), temp dir
- Do NOT write outside these locations.

REPORT POSTING (MANDATORY):
- ALL reports MUST be posted to BOTH locations:
  1. GitHub Issue Thread - Full report text (NOT just a link!)
  2. GHE_REPORTS/ folder - Same full report text (FLAT structure, no subfolders!)
- Report naming: <TIMESTAMP>_<title or description>_(<AGENT>).md
  Example: 20251206143022GMT+01_issue_42_dev_complete_(Hephaestus).md
  Timestamp format: YYYYMMDDHHMMSSTimezone
- REQUIREMENTS/ is SEPARATE - permanent design docs, never deleted
- REDACT before posting: API keys, passwords, emails, user paths -> REDACTED

[TASK]
"""


def get_temp_dir() -> str:
    """Get platform-appropriate temp directory."""
    if platform.system() == "Windows":
        return os.environ.get('TEMP', os.environ.get('TMP', 'C:\\Temp'))
    return '/tmp'


def detect_linux_terminal() -> Optional[str]:
    """Detect available terminal emulator on Linux."""
    terminals = [
        ('gnome-terminal', ['gnome-terminal', '--']),
        ('konsole', ['konsole', '-e']),
        ('xfce4-terminal', ['xfce4-terminal', '-e']),
        ('mate-terminal', ['mate-terminal', '-e']),
        ('terminator', ['terminator', '-e']),
        ('xterm', ['xterm', '-e']),
        ('tmux', ['tmux', 'new-session', '-d']),
    ]
    for name, _ in terminals:
        if shutil.which(name):
            return name
    return None


def spawn_macos(full_cmd: str, agent_id: str, log_file: Path) -> Tuple[str, str]:
    """Spawn background terminal on macOS using AppleScript."""
    applescript = f'''
tell application "Terminal"
    -- ATOMIC: Command is bound to this tab at creation time
    set newTab to do script "{full_cmd}"
    set newWindow to first window whose tabs contains newTab
    set custom title of newTab to "{agent_id}"
    return (id of newWindow as text) & "|" & (tty of newTab)
end tell
'''
    result = subprocess.run(
        ['osascript', '-e', applescript],
        capture_output=True,
        text=True,
        check=True
    )
    window_info = result.stdout.strip()
    parts = window_info.split('|')
    window_id = parts[0] if len(parts) > 0 else "unknown"
    tty_path = parts[1] if len(parts) > 1 else "unknown"
    return window_id, tty_path


def spawn_windows(full_cmd: str, agent_id: str, working_dir: str, log_file: Path) -> Tuple[str, str]:
    """Spawn background terminal on Windows."""
    # Check for Windows Terminal first (modern)
    if shutil.which('wt'):
        # Windows Terminal with new tab
        subprocess.Popen(
            ['wt', 'new-tab', '--title', agent_id, '-d', working_dir, 'cmd', '/c', full_cmd],
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
        return "wt", "Windows Terminal"
    else:
        # Fallback to cmd.exe with START
        # START /MIN runs minimized (background-like)
        bat_content = f'@echo off\ncd /d "{working_dir}"\n{full_cmd}\n'
        bat_file = Path(get_temp_dir()) / f'claude_spawn_{agent_id}.bat'
        bat_file.write_text(bat_content, encoding='utf-8')
        subprocess.Popen(
            ['cmd', '/c', 'start', '/MIN', f'"{agent_id}"', str(bat_file)],
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
        )
        return "cmd", "Command Prompt"


def spawn_linux(full_cmd: str, agent_id: str, working_dir: str, log_file: Path) -> Tuple[str, str]:
    """Spawn background terminal on Linux."""
    terminal = detect_linux_terminal()
    if not terminal:
        print("ERROR: No supported terminal emulator found.", file=sys.stderr)
        print("Install one of: gnome-terminal, konsole, xterm, or tmux", file=sys.stderr)
        sys.exit(1)

    if terminal == 'tmux':
        # tmux runs truly in background
        session_name = agent_id.replace('-', '_')[:20]
        subprocess.run([
            'tmux', 'new-session', '-d', '-s', session_name, '-c', working_dir,
            'bash', '-c', full_cmd
        ], check=True)
        return session_name, f"tmux session: {session_name}"
    elif terminal == 'gnome-terminal':
        subprocess.Popen([
            'gnome-terminal', '--title', agent_id, '--working-directory', working_dir,
            '--', 'bash', '-c', full_cmd
        ])
        return "gnome-terminal", "GNOME Terminal"
    elif terminal == 'konsole':
        subprocess.Popen([
            'konsole', '--workdir', working_dir, '-e', 'bash', '-c', full_cmd
        ])
        return "konsole", "Konsole"
    elif terminal == 'xterm':
        subprocess.Popen([
            'xterm', '-title', agent_id, '-e', 'bash', '-c', f'cd "{working_dir}" && {full_cmd}'
        ])
        return "xterm", "XTerm"
    else:
        # Generic fallback
        subprocess.Popen([terminal, '-e', 'bash', '-c', f'cd "{working_dir}" && {full_cmd}'])
        return terminal, terminal

    return "unknown", "unknown"


def spawn_background_agent(prompt: str, working_dir: str) -> None:
    """Spawn a Claude session in a background Terminal window (cross-platform)."""
    system = platform.system()

    # Generate unique identifier for tracking
    agent_uuid = str(uuid.uuid4())
    agent_id = f"GHE-AGENT-{agent_uuid}"

    # Get log file location
    default_log = Path(get_temp_dir()) / 'background_agent_hook.log'
    log_file = Path(os.environ.get('BACKGROUND_AGENT_LOG', str(default_log)))

    # Resolve working directory to absolute path
    working_dir_path = Path(working_dir).resolve()
    working_dir = str(working_dir_path)

    # Get parent directory (for sub-git projects)
    parent_dir = str(working_dir_path.parent)

    # Create GHE_REPORTS directory (FLAT structure - no subfolders!)
    ghe_reports_dir = working_dir_path / "GHE_REPORTS"
    ghe_reports_dir.mkdir(parents=True, exist_ok=True)

    # Write prompt to temp file (avoids shell escaping issues)
    temp_dir = get_temp_dir()
    with tempfile.NamedTemporaryFile(
        mode='w',
        prefix='claude_prompt_',
        suffix='.txt',
        dir=temp_dir,
        delete=False,
        encoding='utf-8'
    ) as prompt_file:
        prompt_file_path = prompt_file.name
        security_prefix = get_security_prefix(working_dir, parent_dir)
        prompt_file.write(f"{security_prefix}{prompt}")

    # Log spawn event
    log_message(log_file, agent_id, "=" * 42)
    log_message(log_file, agent_id, f"Spawning agent: {agent_id}")
    log_message(log_file, agent_id, f"Platform: {system}")
    log_message(log_file, agent_id, f"Directory: {working_dir}")
    log_message(log_file, agent_id, f"Prompt: {prompt[:100]}...")

    # Build platform-specific command
    # THE IRONCLAD GUARANTEE:
    # This entire command runs ATOMICALLY in a single terminal.
    # The prompt is piped/redirected directly to Claude - there is NO separate send step.
    # It is PHYSICALLY IMPOSSIBLE for the prompt to go to a different window.
    if system == "Windows":
        # Windows uses type instead of cat, and del instead of rm
        prompt_file_path_win = prompt_file_path.replace('/', '\\')
        full_cmd = f'type "{prompt_file_path_win}" | claude --dangerously-skip-permissions & del "{prompt_file_path_win}"'
    else:
        # macOS and Linux use cat and rm
        full_cmd = f"cd '{working_dir}' && cat '{prompt_file_path}' | claude --dangerously-skip-permissions; rm -f '{prompt_file_path}'"

    try:
        # Platform-specific spawn
        if system == "Darwin":
            window_id, tty_path = spawn_macos(full_cmd, agent_id, log_file)
        elif system == "Windows":
            window_id, tty_path = spawn_windows(full_cmd, agent_id, working_dir, log_file)
        elif system == "Linux":
            window_id, tty_path = spawn_linux(full_cmd, agent_id, working_dir, log_file)
        else:
            print(f"ERROR: Unsupported platform: {system}", file=sys.stderr)
            Path(prompt_file_path).unlink(missing_ok=True)
            sys.exit(1)

        # Log completion
        log_message(log_file, agent_id, f"Window/Session: {window_id}, TTY/Terminal: {tty_path}")
        log_message(log_file, agent_id, "Spawn complete")

        # Print success message
        print()
        print("=" * 50)
        print("Background Agent Spawned")
        print("=" * 50)
        print(f"Agent ID:   {agent_id}")
        print(f"Platform:   {system}")
        print(f"Terminal:   {tty_path}")
        print(f"Window ID:  {window_id}")
        print(f"Directory:  {working_dir}")
        print(f"Prompt:     {prompt[:60]}...")
        print()
        print("WINDOW IDENTITY: 100% GUARANTEED")
        print("  Prompt piped directly to Claude (atomic, no keystrokes)")
        print("  Physically impossible for prompt to go elsewhere")
        print()
        print("Working in background - no interruptions!")
        print("Check GHE_REPORTS/ for output.")
        print("=" * 50)

    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to spawn terminal: {e.stderr if e.stderr else e}", file=sys.stderr)
        Path(prompt_file_path).unlink(missing_ok=True)
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        Path(prompt_file_path).unlink(missing_ok=True)
        sys.exit(1)


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        prompt = "Hello! Please run git status and create a summary."
    else:
        prompt = sys.argv[1]

    if len(sys.argv) < 3:
        working_dir = os.getcwd()
    else:
        working_dir = sys.argv[2]

    spawn_background_agent(prompt, working_dir)


if __name__ == "__main__":
    main()
