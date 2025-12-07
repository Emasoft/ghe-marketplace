#!/usr/bin/env python3
"""
Detect when Claude creates, closes, or reopens issues.

PostToolUse hook script that:
1. Watches for Bash commands: gh issue create/close/reopen
2. Extracts the issue number from command or output
3. Updates last_active_issue.json accordingly:
   - CREATE: Switch to the new issue
   - CLOSE: Switch to GENERAL DISCUSSION fallback
   - REOPEN: Switch to the reopened issue

This ensures transcription automatically follows issue lifecycle changes.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Tuple

# Get plugin root for cwd in subprocess calls
GHE_PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT", str(Path(__file__).parent.parent)
)

# Debug mode
DEBUG_MODE = os.environ.get("GHE_DEBUG", "0") == "1"


def get_plugin_repo_root() -> str:
    """Get the plugin's repository root for gh commands."""
    return str(Path(GHE_PLUGIN_ROOT).parent.parent)


def debug_print(msg: str) -> None:
    """Print debug message only if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(f"DEBUG detect_issue: {msg}", file=sys.stderr)


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.

    Format: YYYY-MM-DD HH:MM:SS,mmm LEVEL [logger] - message
    Compatible with: lnav, glogg, Splunk, ELK, Log4j viewers
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [detect_issue_changes] - {message}\n")
    except Exception:
        pass  # Never fail on logging


def get_claude_dir() -> Path:
    """Find the .claude directory."""
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"

    if not claude_dir.exists():
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                claude_dir = parent / ".claude"
                break
        else:
            claude_dir = cwd / ".claude"
            claude_dir.mkdir(exist_ok=True)

    return claude_dir


def get_current_issue() -> Optional[int]:
    """Get current active issue number."""
    claude_dir = get_claude_dir()
    config_path = claude_dir / "last_active_issue.json"

    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
                issue = data.get("issue")
                return int(issue) if issue is not None else None
        except (json.JSONDecodeError, IOError):
            pass
    return None


def extract_issue_from_output(text: str) -> Tuple[Optional[int], str]:
    """
    Extract issue number from gh command output.

    Returns:
        Tuple of (issue_number, issue_title or empty string)
    """
    # Pattern 1: GitHub issue URL
    url_match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", text)
    if url_match:
        return int(url_match.group(1)), ""

    # Pattern 2: JSON output with number field
    try:
        json_match = re.search(r'\{[^{}]*"number"\s*:\s*(\d+)[^{}]*\}', text)
        if json_match:
            return int(json_match.group(1)), ""

        data = json.loads(text.strip())
        if isinstance(data, dict) and "number" in data:
            return int(data["number"]), data.get("title", "")
    except (json.JSONDecodeError, ValueError):
        pass

    # Pattern 3: "Created/Closed/Reopened issue #123" message
    action_match = re.search(
        r"(?:Created|Closed|Reopened)\s+(?:issue\s+)?#?(\d+)", text, re.IGNORECASE
    )
    if action_match:
        return int(action_match.group(1)), ""

    return None, ""


def extract_issue_from_command(command: str) -> Optional[int]:
    """
    Extract issue number from the command itself.

    Commands like: gh issue close 123, gh issue reopen #45
    Also handles flags: gh issue close --reason completed 123
    """
    # First check if this is a close/reopen command
    if not re.search(r"gh\s+issue\s+(?:close|reopen)", command):
        return None

    # Extract any number that appears after close/reopen (may have flags in between)
    # Look for standalone numbers (not part of other args)
    parts = command.split()
    found_action = False
    for part in parts:
        if part in ("close", "reopen"):
            found_action = True
            continue
        if found_action:
            # Skip flags
            if part.startswith("-"):
                continue
            # Check if this is a number (possibly with #)
            num_match = re.match(r"#?(\d+)$", part)
            if num_match:
                return int(num_match.group(1))
    return None


def get_issue_title(issue_num: int) -> str:
    """Fetch issue title from GitHub."""
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--json", "title"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
            cwd=get_plugin_repo_root(),
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            return str(data.get("title", ""))
    except (
        subprocess.TimeoutExpired,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ):
        pass
    return ""


def get_or_create_fallback_issue() -> Optional[int]:
    """Get or create a GENERAL DISCUSSION fallback issue."""
    repo_root = get_plugin_repo_root()
    try:
        # Check for existing GENERAL DISCUSSION issue
        result = subprocess.run(
            [
                "gh",
                "issue",
                "list",
                "--search",
                "GENERAL DISCUSSION in:title",
                "--state",
                "open",
                "--json",
                "number,title",
                "--limit",
                "1",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
            cwd=repo_root,
        )
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            if issues:
                return int(issues[0]["number"])

        # Create new fallback issue
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        result = subprocess.run(
            [
                "gh",
                "issue",
                "create",
                "--title",
                f"[GENERAL] GENERAL DISCUSSION - {timestamp}",
                "--label",
                "general",
                "--body",
                "Auto-created fallback issue for general conversation when no specific issue is active.",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
            cwd=repo_root,
        )
        if result.returncode == 0:
            # Extract issue number from output URL
            url_match = re.search(r"/issues/(\d+)", result.stdout)
            if url_match:
                return int(url_match.group(1))
    except (
        subprocess.TimeoutExpired,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ):
        pass
    return None


def update_active_issue(issue_num: Optional[int], title: str, reason: str) -> None:
    """Update last_active_issue.json with the new issue."""
    claude_dir = get_claude_dir()
    config_path = claude_dir / "last_active_issue.json"

    if issue_num is None:
        # Clear active issue
        if config_path.exists():
            config_path.unlink()
        debug_print("Cleared active issue")
        return

    # Get title if not provided
    if not title:
        title = get_issue_title(issue_num)

    data = {
        "issue": issue_num,
        "title": title,
        "last_active": datetime.now(timezone.utc).isoformat(),
        "auto_detected": True,
        "reason": reason,
    }

    with open(config_path, "w") as f:
        json.dump(data, f, indent=2)

    debug_log(f"Updating active issue to #{issue_num}")
    debug_print(f"Updated active issue to #{issue_num}: {title} ({reason})")


def detect_command_type(command: str) -> Optional[str]:
    """Detect if command is create, close, or reopen."""
    if "gh issue create" in command:
        return "create"
    elif "gh issue close" in command:
        return "close"
    elif "gh issue reopen" in command:
        return "reopen"
    return None


def main() -> None:
    """
    Main entry point - called by PostToolUse hook.

    Reads hook input from stdin with format:
    {
        "tool_name": "Bash",
        "tool_input": {"command": "..."},
        "tool_output": "..."
    }
    """
    debug_log("PostToolUse hook called")
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        debug_log("Failed to parse stdin JSON", level="ERROR")
        print(json.dumps({"event": "PostToolUse", "suppressOutput": True}))
        sys.exit(0)

    tool_name = input_data.get("tool_name", "")
    tool_input = input_data.get("tool_input", {})
    tool_output = input_data.get("tool_output", "")

    # Only process Bash commands
    if tool_name != "Bash":
        print(json.dumps({"event": "PostToolUse", "suppressOutput": True}))
        sys.exit(0)

    command = tool_input.get("command", "")
    cmd_type = detect_command_type(command)

    if not cmd_type:
        debug_log("PostToolUse hook completed")
        print(json.dumps({"event": "PostToolUse", "suppressOutput": True}))
        sys.exit(0)

    debug_log(f"Detected command: {cmd_type}")
    debug_print(f"Detected gh issue {cmd_type}: {command[:100]}...")

    if cmd_type == "create":
        # Extract new issue number from output
        issue_num, title = extract_issue_from_output(tool_output)
        if issue_num:
            update_active_issue(issue_num, title, "created")
            print(f"Auto-switched to new issue #{issue_num}")
        else:
            debug_log(
                "Could not extract issue number from create output", level="ERROR"
            )
            debug_print("Could not extract issue number from create output")
            print(json.dumps({"event": "PostToolUse", "suppressOutput": True}))

    elif cmd_type == "close":
        # Get the issue being closed
        closed_issue = extract_issue_from_command(command)
        if not closed_issue:
            closed_issue, _ = extract_issue_from_output(tool_output)

        current = get_current_issue()

        # If we're closing the current active issue, switch to fallback
        if closed_issue and closed_issue == current:
            fallback = get_or_create_fallback_issue()
            if fallback:
                update_active_issue(fallback, "GENERAL DISCUSSION", "closed_active")
                print(f"Issue #{closed_issue} closed. Switched to fallback #{fallback}")
            else:
                update_active_issue(None, "", "closed_active")
                print(f"Issue #{closed_issue} closed. No fallback available.")
        else:
            # Closed a different issue, just notify
            if closed_issue:
                print(f"Closed issue #{closed_issue} (not active issue)")
            else:
                print(json.dumps({"event": "PostToolUse", "suppressOutput": True}))

    elif cmd_type == "reopen":
        # Get the issue being reopened
        reopened_issue = extract_issue_from_command(command)
        if not reopened_issue:
            reopened_issue, _ = extract_issue_from_output(tool_output)

        if reopened_issue:
            # Switch to the reopened issue
            update_active_issue(reopened_issue, "", "reopened")
            print(f"Issue #{reopened_issue} reopened. Auto-switched to it.")
        else:
            debug_log("Could not extract issue number from reopen", level="ERROR")
            debug_print("Could not extract issue number from reopen")
            print(json.dumps({"event": "PostToolUse", "suppressOutput": True}))

    debug_log("PostToolUse hook completed")
    sys.exit(0)


if __name__ == "__main__":
    main()
