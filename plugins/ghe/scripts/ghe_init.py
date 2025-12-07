#!/usr/bin/env python3
"""
GHE Initialization Script - runs on every SessionStart
Ensures configuration exists and required folders are created in the correct repo
"""

import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def debug_log(message: str) -> None:
    """Append debug message to .claude/hook_debug.log with timestamp."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] ghe_init: {message}\n")
    except Exception:
        pass  # Never fail on logging


def find_config() -> str | None:
    """
    Determine where to look for config
    Priority: 1) Current project .claude/ 2) Find git root's .claude/

    Returns:
        Path to config file if found, None otherwise
    """
    # First check current directory
    config_path = Path(".claude/ghe.local.md")
    if config_path.is_file():
        return str(config_path)

    # Check if we're in a git repo and look at its root
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            git_root = result.stdout.strip()
            config_path = Path(git_root) / '.claude' / 'ghe.local.md'
            if config_path.is_file():
                return str(config_path)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return None


def get_repo_path(config_file: str) -> str | None:
    """
    Parse repo_path from config file's YAML frontmatter

    Args:
        config_file: Path to config file

    Returns:
        repo_path value or None
    """
    try:
        with open(config_file, 'r', encoding='utf-8') as f:
            content = f.read()
        # Extract repo_path from YAML frontmatter
        match = re.search(r'^repo_path:\s*["\']?([^"\'\n]+)["\']?', content, re.MULTILINE)
        if match:
            path = match.group(1).strip().strip('"').strip("'")
            return path if path else None
    except (IOError, OSError):
        pass
    return None


def ensure_folder(folder_path: str, folder_name: str) -> None:
    """
    Check if folder exists, create if not

    Args:
        folder_path: Full path to folder
        folder_name: Display name for logging
    """
    path = Path(folder_path)
    if not path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
        # Create .gitkeep file
        gitkeep = path / '.gitkeep'
        gitkeep.touch(exist_ok=True)
        print(f"[GHE-INIT] Created {folder_name} at {folder_path}")


def main() -> None:
    """Main initialization logic"""
    debug_log("main() started")

    # Try to find config
    config_file = find_config()
    debug_log(f"find_config() returned: {config_file or 'None'}")

    if config_file:
        # Config exists - read repo_path and ensure folders
        repo_path = get_repo_path(config_file)
        debug_log(f"repo_path from config: {repo_path or 'None'}")

        if not repo_path:
            # Config exists but no repo_path - corrupted config
            debug_log("ERROR: Config file found but repo_path is missing!")
            print("[GHE-INIT] WARNING: Config file found but repo_path is missing!")
            print("[GHE-INIT] Run /ghe:setup to reconfigure")
            sys.exit(0)

        # Verify repo_path exists
        if not Path(repo_path).is_dir():
            debug_log(f"ERROR: repo_path does not exist: {repo_path}")
            print(f"[GHE-INIT] WARNING: Configured repo_path does not exist: {repo_path}")
            print("[GHE-INIT] Run /ghe:setup to reconfigure")
            sys.exit(0)

        debug_log("Ensuring required folders exist...")
        # Ensure REQUIREMENTS folder exists in repo
        ensure_folder(f"{repo_path}/REQUIREMENTS", "REQUIREMENTS")
        ensure_folder(f"{repo_path}/REQUIREMENTS/_templates", "REQUIREMENTS/_templates")

        # Ensure GHE_REPORTS folder exists in repo
        ensure_folder(f"{repo_path}/GHE_REPORTS", "GHE_REPORTS")

        # Silent success - output JSON to suppress from user view
        debug_log("Outputting success JSON")
        import json
        print(json.dumps({"event": "SessionStart", "suppressOutput": True, "success": True}))
        debug_log("ghe_init completed successfully")
    else:
        # No config found - need setup
        debug_log("No config found - outputting setup prompt")
        # MUST output valid JSON with event field for Claude Code hooks
        import json
        output = {
            "event": "SessionStart",
            "hookSpecificOutput": {
                "additionalContext": "GHE not configured. Run /ghe:setup to enable GitHub Elements tracking."
            }
        }
        print(json.dumps(output))
        debug_log("ghe_init completed (needs setup)")


if __name__ == '__main__':
    main()
