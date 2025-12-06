#!/usr/bin/env python3
"""
Auto-approve PreToolUse hook for background Claude sessions
Works WITHOUT --dangerously-skip-permissions flag!

Philosophy: Allow operations that TARGET the project directory.
- Reading from anywhere is fine (system libs, etc.)
- Writing/modifying/deleting MUST target allowed directories

Allowed write directories:
  - Project folder (and subfolders)
  - /tmp/ (macOS/Linux) or %TEMP% (Windows)
  - ~/.claude/ (Claude Code config)

Permission decisions:
  - "allow" = auto-approve (no user prompt)
  - "deny"  = block operation
  - "ask"   = prompt user for approval
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Set

# Optional logging (set via environment variable)
LOG_FILE = os.environ.get("BACKGROUND_AGENT_LOG", "")


def log(message: str) -> None:
    """Log message if LOG_FILE is set."""
    if LOG_FILE:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        with open(LOG_FILE, "a") as f:
            f.write(f"[{timestamp}] {message}\n")


def approve(reason: str = "Auto-approved by background-agents hook") -> None:
    """Output approval decision and exit."""
    log(f"ALLOW: {reason}")
    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason
        }
    }
    print(json.dumps(response))
    sys.exit(0)


def deny_it(reason: str = "Denied by background-agents hook") -> None:
    """Output denial decision and exit."""
    log(f"DENY: {reason}")
    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason
        }
    }
    print(json.dumps(response))
    sys.exit(0)


def ask_user(reason: str = "Requires user approval") -> None:
    """Output ask decision and exit."""
    log(f"ASK: {reason}")
    response = {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason
        }
    }
    print(json.dumps(response))
    sys.exit(0)


def detect_platform() -> tuple:
    """Detect platform and return (platform_name, temp_dir, claude_dir)."""
    system = platform.system()
    home = Path.home()

    if system == "Darwin":
        return ("macos", "/tmp", str(home / ".claude"))
    elif system == "Linux":
        return ("linux", "/tmp", str(home / ".claude"))
    elif system == "Windows":
        # Windows - use TEMP or TMP environment variables
        temp_dir = os.environ.get("TEMP", os.environ.get("TMP", "/tmp"))
        return ("windows", temp_dir, str(home / ".claude"))
    else:
        return ("unknown", "/tmp", str(home / ".claude"))


def normalize_path(path: str) -> str:
    """Normalize a path for comparison (remove trailing slash, resolve . and ..)."""
    # Remove trailing slashes
    path = path.rstrip("/").rstrip("\\")

    # Use realpath if available (don't require file to exist)
    if shutil.which("realpath"):
        try:
            # -m: don't require file to exist, -s: no symlink resolution (faster)
            result = subprocess.run(
                ["realpath", "-ms", path],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass

    return path


def path_starts_with(path: str, directory: str) -> bool:
    """Check if path P starts with prefix DIR (proper directory containment check)."""
    # Empty dir matches nothing
    if not directory:
        return False

    # Exact match
    if path == directory:
        return True

    # P is under DIR (ensure we match directory boundary, not just string prefix)
    # e.g., /home/user/project should match, but /home/user/project2 should not
    if path.startswith(directory + "/") or path.startswith(directory + "\\"):
        return True

    return False


def is_allowed_write_path(path: str, project_root: str, extra_project_dirs: List[str],
                          temp_dir: str, claude_dir: str) -> bool:
    """Check if a path is within allowed write directories."""
    if not path:
        return True

    # /dev/null is always safe (common redirect target)
    if path == "/dev/null":
        return True

    # Relative paths are inside project (allowed)
    # Check for absolute paths: Unix-style (/) or Windows-style (C:)
    is_absolute = path.startswith("/") or (len(path) > 1 and path[1] == ":")
    if not is_absolute:
        return True

    # Normalize the path for consistent comparison
    normalized = normalize_path(path)

    # Log the comparison for debugging
    log(f"PATH CHECK: '{normalized}' against PROJECT_ROOT='{project_root}'")

    # Project directory (and subfolders) - use proper containment check
    if path_starts_with(normalized, project_root):
        log(f"PATH ALLOWED: in PROJECT_ROOT")
        return True

    # Check extra project directories
    for directory in extra_project_dirs:
        directory = normalize_path(directory)
        if path_starts_with(normalized, directory):
            log(f"PATH ALLOWED: in EXTRA_PROJECT_DIRS ({directory})")
            return True

    # Temp directory - platform specific
    # macOS/Linux: /tmp or /private/tmp
    if path_starts_with(normalized, "/tmp"):
        return True
    if path_starts_with(normalized, "/private/tmp"):
        return True

    # Windows: various temp locations
    temp_env = os.environ.get("TEMP")
    if temp_env and path_starts_with(normalized, normalize_path(temp_env)):
        return True
    tmp_env = os.environ.get("TMP")
    if tmp_env and path_starts_with(normalized, normalize_path(tmp_env)):
        return True

    # Claude config directory (~/.claude/)
    if path_starts_with(normalized, claude_dir):
        return True

    home_claude = str(Path.home() / ".claude")
    if path_starts_with(normalized, home_claude):
        return True

    # Claude plugins cache (installed plugins)
    home_claude_plugins = str(Path.home() / ".claude" / "plugins")
    if path_starts_with(normalized, home_claude_plugins):
        return True

    # Not in allowed directories
    log(f"PATH DENIED: '{normalized}' not in any allowed directory")
    return False


def resolve_path(path: str, project_root: str) -> str:
    """Resolve a path (handle relative paths)."""
    # Handle Windows-style paths
    if len(path) > 1 and path[1] == ":":
        return path
    elif not path.startswith("/"):
        # Relative path - prepend project root
        return str(Path(project_root) / path)
    else:
        return path


def is_catastrophic(command: str) -> bool:
    """
    Check if command contains catastrophic system operations.
    Only blocks truly destructive SYSTEM-level operations.
    External drives (USB, etc.) are allowed - user's choice.
    """
    # Privilege escalation - always block
    if "sudo " in command:
        return True

    # Root filesystem destruction
    if "rm -rf /" in command:
        return True
    if "rm -rf ~" in command:
        return True
    if "rm -rf $HOME" in command:
        return True

    # Writing to system devices (not external drives)
    # Block: /dev/sda (Linux system), /dev/disk0 /dev/disk1 (macOS system)
    # Allow: /dev/sdb, /dev/sdc, /dev/disk2+ (external drives)
    if "> /dev/null" in command:
        return False  # /dev/null is safe

    dangerous_devices = [
        "> /dev/sda", "> /dev/nvme0",
        "of=/dev/sda", "of=/dev/nvme0",
        "of=/dev/disk0", "of=/dev/disk1"
    ]
    for device in dangerous_devices:
        if device in command:
            return True

    # System drive formatting only
    # macOS: diskutil on disk0/disk1 (system drives)
    if "diskutil" in command and ("/dev/disk0" in command or "/dev/disk1" in command):
        return True

    # Linux: mkfs on sda/nvme0 (system drives)
    if "mkfs" in command and ("/dev/sda" in command or "/dev/nvme0" in command):
        return True

    # Windows: format C: (system drive)
    if "format " in command and ("C:" in command or "c:" in command):
        return True

    # Fork bomb
    if ":(){:|:&};:" in command:
        return True

    # System control - always block
    dangerous_commands = ["shutdown", "reboot", "init 0", "init 6"]
    for dangerous in dangerous_commands:
        if dangerous in command:
            return True

    # Windows system destruction
    if "del /f /s /q C:\\" in command:
        return True
    if "rd /s /q C:\\" in command:
        return True

    return False


def get_write_targets(command: str) -> List[str]:
    """
    Extract WRITE targets from a command.
    Returns paths that the command would write/modify/delete.
    """
    targets = []

    # Output redirections: > >> 2> 2>> &>
    # Exclude shell special chars like ) ; | & from capture to avoid false positives
    redirect_pattern = r'(>|>>|2>|2>>|&>)\s*([^\s);|&]+)'
    redirects = re.findall(redirect_pattern, command)
    for _, target in redirects:
        targets.append(target)

    # rm targets (everything after rm and flags)
    if re.search(r'\brm\s', command):
        rm_match = re.search(r'\brm\s+(?:-[^\s]*\s+)*(.+)', command)
        if rm_match:
            targets.extend(rm_match.group(1).split())

    # mv destination (last argument)
    if re.search(r'\bmv\s', command):
        mv_match = re.search(r'\bmv\s.*\s+([^\s]+)\s*$', command)
        if mv_match:
            targets.append(mv_match.group(1))

    # cp destination (last argument)
    if re.search(r'\bcp\s', command):
        cp_match = re.search(r'\bcp\s.*\s+([^\s]+)\s*$', command)
        if cp_match:
            targets.append(cp_match.group(1))

    # touch, mkdir targets
    if re.search(r'\b(touch|mkdir)\s', command):
        create_match = re.search(r'\b(touch|mkdir)\s+(?:-[^\s]*\s+)*(.+)', command)
        if create_match:
            targets.extend(create_match.group(2).split())

    # chmod, chown targets
    if re.search(r'\b(chmod|chown)\s', command):
        perm_match = re.search(r'\b(chmod|chown)\s+[^\s]+\s+(.+)', command)
        if perm_match:
            targets.extend(perm_match.group(2).split())

    # tee writes to files
    if re.search(r'\|\s*tee\s', command):
        tee_match = re.search(r'\|\s*tee\s+(?:-[^\s]*\s+)*(.+)', command)
        if tee_match:
            targets.extend(tee_match.group(1).split())

    return targets


def all_writes_allowed(command: str, project_root: str, extra_project_dirs: List[str],
                       temp_dir: str, claude_dir: str) -> bool:
    """Check if all write targets are in allowed directories."""
    targets = get_write_targets(command)

    # No write targets detected = safe (read-only command)
    if not targets or all(not t.strip() for t in targets):
        return True

    for target in targets:
        # Skip empty
        if not target.strip():
            continue
        # Skip flags
        if target.startswith("-"):
            continue

        # Resolve and check
        resolved = resolve_path(target, project_root)

        if not is_allowed_write_path(resolved, project_root, extra_project_dirs,
                                     temp_dir, claude_dir):
            log(f"BLOCKED TARGET: {target} -> {resolved}")
            return False

    return True


def get_registered_repo_path() -> Optional[str]:
    """Get registered repo path from ghe_common module."""
    try:
        # Import ghe_common Python module and use its function
        from ghe_common import ghe_get_repo_path
        repo_path = ghe_get_repo_path()
        if repo_path:
            return repo_path
    except ImportError:
        pass
    except Exception:
        pass

    return None


def get_parent_git_root(repo_path: str) -> Optional[str]:
    """Get parent git root if registered repo is inside a parent git repo."""
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(repo_path).parent), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=False
        )

        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass

    return None


def main():
    """Main hook logic."""
    # Read JSON input from stdin
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        deny_it("Invalid JSON input")

    # Extract tool information
    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path", "")
    command = tool_input.get("command", "")
    cwd = input_data.get("cwd", os.getcwd())

    # Get project root from current working directory
    project_root = cwd or os.getcwd()
    project_root = project_root.rstrip("/").rstrip("\\")

    # Detect platform
    platform_name, temp_dir, claude_dir = detect_platform()

    # Get extra project directories from environment
    extra_project_dirs = []
    env_dirs = os.environ.get("CLAUDE_PROJECT_DIRS", "")
    if env_dirs:
        extra_project_dirs = [d.strip() for d in env_dirs.split(":") if d.strip()]

    # Add registered repo as allowed directory if it exists and differs from PROJECT_ROOT
    registered_repo = get_registered_repo_path()
    if registered_repo and registered_repo != project_root:
        extra_project_dirs.append(registered_repo)
        log(f"Added registered repo to allowed dirs: {registered_repo}")

        # If registered repo is inside a parent git repo, also allow the parent
        parent_git_root = get_parent_git_root(registered_repo)
        if parent_git_root and parent_git_root != registered_repo and parent_git_root != project_root:
            extra_project_dirs.append(parent_git_root)
            log(f"Added parent repo to allowed dirs: {parent_git_root}")

    # Log request
    log(f"Platform: {platform_name}, Tool: {tool_name}, Path: {file_path}, Cmd: {command[:80]}")

    # Main decision logic
    if tool_name in ["Read", "Glob", "Grep", "LS", "Task", "WebFetch", "WebSearch",
                     "TodoWrite", "TodoRead", "ListMcpResourcesTool", "ReadMcpResourceTool"]:
        # Read-only tools - always safe
        approve("Safe read-only tool")

    elif tool_name in ["Write", "Edit", "MultiEdit", "NotebookEdit"]:
        # Write tools - check path is in allowed directories
        if is_allowed_write_path(file_path, project_root, extra_project_dirs,
                                temp_dir, claude_dir):
            approve("Write targets allowed directory")
        else:
            deny_it(f"Write targets outside allowed directories: {file_path}")

    elif tool_name == "Bash":
        # Bash commands - check write targets
        # First, check for catastrophic commands
        if is_catastrophic(command):
            deny_it("Catastrophic system command blocked")
        # Then check if all write targets are in allowed directories
        elif all_writes_allowed(command, project_root, extra_project_dirs,
                               temp_dir, claude_dir):
            approve("All write targets in allowed directories")
        else:
            deny_it("Command writes outside allowed directories")

    elif tool_name.startswith("mcp__"):
        # MCP tools - generally safe (they have their own auth)
        approve("MCP tool")

    elif tool_name in ["Skill", "SlashCommand"]:
        # Skill/SlashCommand execution - safe
        approve("Skill/command execution")

    else:
        # Unknown tools - ask user
        ask_user(f"Unknown tool: {tool_name}")


if __name__ == "__main__":
    main()
