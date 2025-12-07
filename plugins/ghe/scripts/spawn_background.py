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
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [spawn_background] - {message}\n")
    except Exception:
        pass


def log_message(log_file: Path, agent_id: str, message: str) -> None:
    """Log a message with timestamp and agent ID."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] [{agent_id}] {message}\n")
    except (IOError, OSError):
        pass  # Logging is best-effort, don't fail if log can't be written


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
        return os.environ.get("TEMP", os.environ.get("TMP", "C:\\Temp"))
    return "/tmp"


def escape_for_applescript(s: str) -> str:
    """Escape a string for use inside AppleScript double quotes."""
    # Escape backslashes first, then double quotes
    return s.replace("\\", "\\\\").replace('"', '\\"')


def escape_for_shell(s: str) -> str:
    """Escape a string for use inside single quotes in shell."""
    # Replace single quotes with '\'' (end quote, escaped quote, start quote)
    return s.replace("'", "'\\''")


def sanitize_session_name(name: str) -> str:
    """Sanitize a string for use as tmux session name."""
    # tmux session names: alphanumeric, underscore, dash only
    # Replace invalid chars with underscore, truncate to 20 chars
    sanitized = re.sub(r"[^a-zA-Z0-9_-]", "_", name)
    return sanitized[:20]


def detect_linux_terminal() -> Optional[str]:
    """Detect available terminal emulator on Linux."""
    debug_log("detect_linux_terminal() called")
    terminals = [
        "gnome-terminal",
        "konsole",
        "xfce4-terminal",
        "mate-terminal",
        "terminator",
        "xterm",
        "tmux",
    ]
    for name in terminals:
        if shutil.which(name):
            debug_log(f"Found terminal: {name}")
            return name
    debug_log("No terminal emulator found")
    return None


def spawn_macos(full_cmd: str, agent_id: str, log_file: Path) -> Tuple[str, str]:
    """Spawn background terminal on macOS using AppleScript."""
    debug_log("spawn_macos() called")
    # Escape the command for AppleScript double-quoted string
    escaped_cmd = escape_for_applescript(full_cmd)
    escaped_agent_id = escape_for_applescript(agent_id)
    debug_log(f"Escaped agent_id for AppleScript: {escaped_agent_id}")

    applescript = f'''
tell application "Terminal"
    -- ATOMIC: Command is bound to this tab at creation time
    set newTab to do script "{escaped_cmd}"
    set newWindow to first window whose tabs contains newTab
    set custom title of newTab to "{escaped_agent_id}"
    return (id of newWindow as text) & "|" & (tty of newTab)
end tell
'''
    debug_log("Executing AppleScript via osascript")
    result = subprocess.run(
        ["osascript", "-e", applescript], capture_output=True, text=True, check=True
    )
    window_info = result.stdout.strip()
    debug_log(f"AppleScript returned: {window_info}")
    parts = window_info.split("|")
    window_id = parts[0] if len(parts) > 0 else "unknown"
    tty_path = parts[1] if len(parts) > 1 else "unknown"
    debug_log(f"Parsed window_id={window_id}, tty_path={tty_path}")
    return window_id, tty_path


def spawn_windows(
    full_cmd: str, agent_id: str, working_dir: str, log_file: Path
) -> Tuple[str, str]:
    """Spawn background terminal on Windows."""
    debug_log("spawn_windows() called")
    # Windows-specific subprocess flags
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008
    creation_flags = CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS

    # Check for Windows Terminal first (modern)
    if shutil.which("wt"):
        debug_log("Windows Terminal (wt) detected, using it")
        # Windows Terminal with new tab
        subprocess.Popen(
            [
                "wt",
                "new-tab",
                "--title",
                agent_id,
                "-d",
                working_dir,
                "cmd",
                "/c",
                full_cmd,
            ],
            creationflags=creation_flags,
        )
        debug_log("Windows Terminal spawned successfully")
        return "wt", "Windows Terminal"
    else:
        debug_log("Windows Terminal not found, falling back to cmd.exe")
        # Fallback to cmd.exe with START
        # START /MIN runs minimized (background-like)
        # Write batch file to avoid complex escaping
        bat_content = f'@echo off\r\ncd /d "{working_dir}"\r\n{full_cmd}\r\n'
        bat_file = Path(get_temp_dir()) / f"claude_spawn_{agent_id}.bat"
        bat_file.write_text(bat_content, encoding="utf-8")
        debug_log(f"Created batch file: {bat_file}")

        # Use string command for shell=True to avoid escaping issues
        start_cmd = f'start /MIN "{agent_id}" "{bat_file}"'
        subprocess.Popen(start_cmd, shell=True, creationflags=creation_flags)
        debug_log("cmd.exe spawned successfully")
        return "cmd", "Command Prompt"


def spawn_linux(
    full_cmd: str, agent_id: str, working_dir: str, log_file: Path
) -> Tuple[str, str]:
    """Spawn background terminal on Linux."""
    debug_log("spawn_linux() called")
    terminal = detect_linux_terminal()
    debug_log(f"Detected Linux terminal: {terminal}")
    if not terminal:
        debug_log("No supported terminal emulator found", level="ERROR")
        print("ERROR: No supported terminal emulator found.", file=sys.stderr)
        print(
            "Install one of: gnome-terminal, konsole, xterm, or tmux", file=sys.stderr
        )
        sys.exit(1)

    if terminal == "tmux":
        # tmux runs truly in background
        session_name = sanitize_session_name(agent_id)
        debug_log(f"Using tmux with session name: {session_name}")
        subprocess.run(
            [
                "tmux",
                "new-session",
                "-d",
                "-s",
                session_name,
                "-c",
                working_dir,
                "bash",
                "-c",
                full_cmd,
            ],
            check=True,
        )
        debug_log("tmux session created successfully")
        return session_name, f"tmux session: {session_name}"
    elif terminal == "gnome-terminal":
        debug_log("Using gnome-terminal")
        subprocess.Popen(
            [
                "gnome-terminal",
                "--title",
                agent_id,
                "--working-directory",
                working_dir,
                "--",
                "bash",
                "-c",
                full_cmd,
            ]
        )
        debug_log("gnome-terminal spawned successfully")
        return "gnome-terminal", "GNOME Terminal"
    elif terminal == "konsole":
        debug_log("Using konsole")
        subprocess.Popen(
            ["konsole", "--workdir", working_dir, "-e", "bash", "-c", full_cmd]
        )
        debug_log("konsole spawned successfully")
        return "konsole", "Konsole"
    elif terminal == "xfce4-terminal":
        debug_log("Using xfce4-terminal")
        subprocess.Popen(
            [
                "xfce4-terminal",
                "--title",
                agent_id,
                "--working-directory",
                working_dir,
                "-e",
                f'bash -c "{escape_for_shell(full_cmd)}"',
            ]
        )
        debug_log("xfce4-terminal spawned successfully")
        return "xfce4-terminal", "XFCE Terminal"
    elif terminal == "mate-terminal":
        debug_log("Using mate-terminal")
        subprocess.Popen(
            [
                "mate-terminal",
                "--title",
                agent_id,
                "--working-directory",
                working_dir,
                "-e",
                f'bash -c "{escape_for_shell(full_cmd)}"',
            ]
        )
        debug_log("mate-terminal spawned successfully")
        return "mate-terminal", "MATE Terminal"
    elif terminal == "terminator":
        debug_log("Using terminator")
        subprocess.Popen(
            [
                "terminator",
                "--title",
                agent_id,
                "--working-directory",
                working_dir,
                "-e",
                f'bash -c "{escape_for_shell(full_cmd)}"',
            ]
        )
        debug_log("terminator spawned successfully")
        return "terminator", "Terminator"
    elif terminal == "xterm":
        debug_log("Using xterm")
        subprocess.Popen(
            ["xterm", "-title", agent_id, "-e", "bash", "-c", full_cmd], cwd=working_dir
        )
        debug_log("xterm spawned successfully")
        return "xterm", "XTerm"
    else:
        # Should not reach here, but handle gracefully
        debug_log(f"Unhandled terminal: {terminal}", level="ERROR")
        print(f"ERROR: Unhandled terminal: {terminal}", file=sys.stderr)
        sys.exit(1)


def spawn_background_agent(prompt: str, working_dir: str) -> None:
    """Spawn a Claude session in a background Terminal window (cross-platform)."""
    debug_log("spawn_background_agent() called")
    system = platform.system()
    debug_log(f"Detected platform: {system}")

    # Generate unique identifier for tracking
    agent_uuid = str(uuid.uuid4())
    agent_id = f"GHE-AGENT-{agent_uuid}"
    debug_log(f"Generated agent_id: {agent_id}")

    # Get log file location
    default_log = Path(get_temp_dir()) / "background_agent_hook.log"
    log_file = Path(os.environ.get("BACKGROUND_AGENT_LOG", str(default_log)))
    debug_log(f"Log file location: {log_file}")

    # Resolve working directory to absolute path
    working_dir_path = Path(working_dir).resolve()
    working_dir = str(working_dir_path)
    debug_log(f"Resolved working_dir: {working_dir}")

    # Get parent directory (for sub-git projects)
    parent_dir = str(working_dir_path.parent)
    debug_log(f"Parent directory: {parent_dir}")

    # Create GHE_REPORTS directory (FLAT structure - no subfolders!)
    ghe_reports_dir = working_dir_path / "GHE_REPORTS"
    ghe_reports_dir.mkdir(parents=True, exist_ok=True)
    debug_log(f"GHE_REPORTS directory ensured: {ghe_reports_dir}")

    # Write prompt to temp file (avoids shell escaping issues)
    temp_dir = get_temp_dir()
    debug_log(f"Using temp directory: {temp_dir}")
    with tempfile.NamedTemporaryFile(
        mode="w",
        prefix="claude_prompt_",
        suffix=".txt",
        dir=temp_dir,
        delete=False,
        encoding="utf-8",
    ) as prompt_file:
        prompt_file_path = prompt_file.name
        security_prefix = get_security_prefix(working_dir, parent_dir)
        prompt_file.write(f"{security_prefix}{prompt}")
    debug_log(f"Created prompt temp file: {prompt_file_path}")

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
    debug_log("Building platform-specific command")
    if system == "Windows":
        # Windows uses type instead of cat, and del instead of rm
        # Use Path to get proper Windows path format
        prompt_file_path_win = str(Path(prompt_file_path))
        # Use && so del only runs if type succeeds
        full_cmd = f'type "{prompt_file_path_win}" | claude --dangerously-skip-permissions && del "{prompt_file_path_win}"'
        debug_log(f"Windows command built: {full_cmd[:100]}...")
    else:
        # macOS and Linux use cat and rm
        # Escape paths for shell safety
        escaped_working_dir = escape_for_shell(working_dir)
        escaped_prompt_path = escape_for_shell(prompt_file_path)
        full_cmd = f"cd '{escaped_working_dir}' && cat '{escaped_prompt_path}' | claude --dangerously-skip-permissions; rm -f '{escaped_prompt_path}'"
        debug_log(f"Unix command built: {full_cmd[:100]}...")

    try:
        # Platform-specific spawn
        debug_log(f"Spawning terminal for platform: {system}")
        if system == "Darwin":
            debug_log("Calling spawn_macos()")
            window_id, tty_path = spawn_macos(full_cmd, agent_id, log_file)
            debug_log(f"spawn_macos() returned: window_id={window_id}, tty={tty_path}")
        elif system == "Windows":
            debug_log("Calling spawn_windows()")
            window_id, tty_path = spawn_windows(
                full_cmd, agent_id, working_dir, log_file
            )
            debug_log(
                f"spawn_windows() returned: window_id={window_id}, tty={tty_path}"
            )
        elif system == "Linux":
            debug_log("Calling spawn_linux()")
            window_id, tty_path = spawn_linux(full_cmd, agent_id, working_dir, log_file)
            debug_log(f"spawn_linux() returned: window_id={window_id}, tty={tty_path}")
        else:
            debug_log(f"Unsupported platform: {system}", level="ERROR")
            print(f"ERROR: Unsupported platform: {system}", file=sys.stderr)
            Path(prompt_file_path).unlink(missing_ok=True)
            sys.exit(1)

        # Log completion
        log_message(
            log_file, agent_id, f"Window/Session: {window_id}, TTY/Terminal: {tty_path}"
        )
        log_message(log_file, agent_id, "Spawn complete")
        debug_log("Spawn completed successfully")

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
        debug_log(f"CalledProcessError: {e.stderr if e.stderr else e}", level="ERROR")
        print(
            f"ERROR: Failed to spawn terminal: {e.stderr if e.stderr else e}",
            file=sys.stderr,
        )
        Path(prompt_file_path).unlink(missing_ok=True)
        sys.exit(1)
    except Exception as e:
        debug_log(f"Unexpected error: {e}", level="ERROR")
        print(f"ERROR: Unexpected error: {e}", file=sys.stderr)
        Path(prompt_file_path).unlink(missing_ok=True)
        sys.exit(1)


def main() -> None:
    """Main entry point."""
    debug_log("main() called")
    debug_log(f"sys.argv: {sys.argv}")

    if len(sys.argv) < 2:
        prompt = "Hello! Please run git status and create a summary."
        debug_log("Using default prompt (no argument provided)")
    else:
        prompt = sys.argv[1]
        debug_log(f"Prompt from argv[1]: {prompt[:100]}...")

    if len(sys.argv) < 3:
        working_dir = os.getcwd()
        debug_log(f"Using cwd as working_dir: {working_dir}")
    else:
        working_dir = sys.argv[2]
        debug_log(f"Working dir from argv[2]: {working_dir}")

    debug_log("Calling spawn_background_agent()")
    spawn_background_agent(prompt, working_dir)
    debug_log("spawn_background_agent() completed")


if __name__ == "__main__":
    main()
