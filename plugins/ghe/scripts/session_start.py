#!/usr/bin/env python3
"""
GHE Unified SessionStart Hook

This single script replaces 4 separate SessionStart hooks:
1. ghe_init.py - Initialize GHE environment, ensure folders exist
2. auto_transcribe.py check - Verify GitHub repo connectivity
3. session_recover.py - Auto-resume last active issue
4. transcription_notify.py - Notify user of active transcription

Having multiple hooks caused parallel execution issues where all 4 scripts
output JSON simultaneously, confusing Claude Code's hook parser.

CRITICAL: This script outputs EXACTLY ONE JSON object to stdout.
"""

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.

    Format: YYYY-MM-DD HH:MM:SS,mmm LEVEL [logger] - message
    Compatible with: lnav, glogg, Splunk, ELK, Log4j viewers
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [session_start] - {message}\n")
    except Exception:
        pass  # Never fail on logging


def output_json_and_exit(output: dict, exit_code: int = 0) -> None:
    """
    Output JSON to stdout and exit.

    CRITICAL: This is the ONLY function that outputs to stdout.
    All other functions must return data, not print.
    """
    # Ensure event field is present
    if "event" not in output:
        output["event"] = "SessionStart"

    # CRITICAL: flush=True ensures output is written to pipe before exit
    # Without this, stdout may be block-buffered and not flushed before sys.exit()
    print(json.dumps(output), flush=True)
    sys.stdout.flush()  # Belt and suspenders - ensure flush
    sys.exit(exit_code)


# =============================================================================
# PHASE 1: Find GHE Configuration (from ghe_init.py)
# =============================================================================

def find_config() -> Optional[str]:
    """
    Find GHE configuration file.
    Priority: 1) Current project .claude/ 2) Git root's .claude/

    Returns:
        Path to config file if found, None otherwise
    """
    debug_log("Phase 1: Finding GHE configuration...")

    # First check current directory
    config_path = Path(".claude/ghe.local.md")
    if config_path.is_file():
        debug_log(f"Found config at {config_path}")
        return str(config_path)

    # Check if we're in a git repo and look at its root
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            check=False,
            timeout=5
        )
        if result.returncode == 0:
            git_root = result.stdout.strip()
            config_path = Path(git_root) / '.claude' / 'ghe.local.md'
            if config_path.is_file():
                debug_log(f"Found config at {config_path}")
                return str(config_path)
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, FileNotFoundError):
        pass

    debug_log("No GHE config found")
    return None


def get_repo_path(config_file: str) -> Optional[str]:
    """
    Parse repo_path from config file's YAML frontmatter.

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
            debug_log(f"repo_path from config: {path}")
            return path if path else None
    except (IOError, OSError):
        pass
    return None


def ensure_folder(folder_path: str, folder_name: str) -> bool:
    """
    Check if folder exists, create if not.

    Args:
        folder_path: Full path to folder
        folder_name: Display name for logging

    Returns:
        True if folder was created, False if it already existed
    """
    path = Path(folder_path)
    if not path.is_dir():
        path.mkdir(parents=True, exist_ok=True)
        # Create .gitkeep file
        gitkeep = path / '.gitkeep'
        gitkeep.touch(exist_ok=True)
        debug_log(f"Created {folder_name} at {folder_path}")
        return True
    return False


# =============================================================================
# PHASE 2: Verify GitHub Connectivity (from auto_transcribe.py check)
# =============================================================================

def check_github_repo(repo_root: str) -> bool:
    """
    Check if we have a working GitHub repo.

    Args:
        repo_root: Path to repository root

    Returns:
        True if GitHub repo is configured and accessible, False otherwise
    """
    debug_log("Phase 2: Checking GitHub connectivity...")

    # Check if it's a git repository
    try:
        subprocess.run(
            ["git", "-C", repo_root, "rev-parse", "--git-dir"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        debug_log("Not a git repository", "WARN")
        return False

    # Check for GitHub remote
    try:
        result = subprocess.run(
            ["git", "-C", repo_root, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        remote = result.stdout.strip()
        if not remote or "github.com" not in remote:
            debug_log("No GitHub remote found", "WARN")
            return False
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        debug_log("No GitHub remote found", "WARN")
        return False

    # Verify gh is authenticated (quick check)
    try:
        subprocess.run(
            ["gh", "auth", "status"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
        debug_log("GitHub connectivity verified")
        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        debug_log("GitHub CLI not authenticated", "WARN")
        return False


# =============================================================================
# PHASE 3: Session Recovery (from session_recover.py)
# =============================================================================

def get_repo_from_settings() -> str:
    """
    Read repo from plugin settings file .claude/ghe.local.md

    Returns:
        repo string (owner/repo format) or empty string
    """
    settings_file = Path(".claude/ghe.local.md")

    if not settings_file.exists():
        return ""

    try:
        content = settings_file.read_text()
        # Extract frontmatter between --- markers
        match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not match:
            return ""

        frontmatter = match.group(1)
        # Extract repo field
        repo_match = re.search(r'^repo:\s*["\']?([^"\'\n]+)["\']?\s*$', frontmatter, re.MULTILINE)
        if repo_match:
            return repo_match.group(1).strip()
        return ""
    except Exception:
        return ""


def get_current_issue_from_config() -> Optional[str]:
    """
    Get current issue from config file.

    Returns:
        Issue number as string, or None
    """
    settings_file = Path(".claude/ghe.local.md")

    if not settings_file.exists():
        return None

    try:
        content = settings_file.read_text()
        match = re.search(r'^current_issue:\s*(\d+)', content, re.MULTILINE)
        if match:
            return match.group(1)
        return None
    except Exception:
        return None


def auto_resume_last_issue() -> Tuple[Optional[str], Optional[str]]:
    """
    Check for last_active_issue.json and auto-resume if found.

    Returns:
        Tuple of (issue_number, issue_title) or (None, None)
    """
    debug_log("Phase 3: Checking for session recovery...")

    last_active_file = Path(".claude/last_active_issue.json")

    if not last_active_file.exists():
        debug_log("No last_active_issue.json found")
        return None, None

    debug_log("Found last_active_issue.json")
    try:
        data = json.loads(last_active_file.read_text())
        issue_num = str(data.get("issue", ""))
        title = data.get("title", "")
        debug_log(f"Parsed issue={issue_num}, title={title[:50] if title else 'N/A'}")

        if not issue_num:
            debug_log("No issue number in file")
            return None, None

        # Get repo from plugin settings
        repo = get_repo_from_settings()
        debug_log(f"Repo from settings: {repo or 'N/A'}")

        # Build gh command with repo if available
        gh_cmd = ["gh", "issue", "view", issue_num, "--json", "number", "--jq", ".number"]
        if repo:
            gh_cmd.extend(["--repo", repo])

        # Verify issue still exists on GitHub (quick check, 5s timeout)
        debug_log("Verifying issue with gh (5s timeout)...")
        result = subprocess.run(
            gh_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        debug_log(f"gh returned: {result.stdout.strip()}")

        if result.stdout.strip() != issue_num:
            debug_log(f"Issue mismatch: expected {issue_num}, got {result.stdout.strip()}")
            return None, None

        # Direct config update - FAST, no subprocess call
        config_file = Path(".claude/ghe.local.md")
        if config_file.exists():
            debug_log("Updating config file directly")
            content = config_file.read_text()
            # Update current_issue
            if re.search(r'^current_issue:.*$', content, re.MULTILINE):
                content = re.sub(r'^current_issue:.*$', f'current_issue: {issue_num}', content, flags=re.MULTILINE)
            # Update current_phase
            if re.search(r'^current_phase:.*$', content, re.MULTILINE):
                content = re.sub(r'^current_phase:.*$', 'current_phase: CONVERSATION', content, flags=re.MULTILINE)
            config_file.write_text(content)
            debug_log("Config updated successfully")

        debug_log(f"Auto-resumed issue #{issue_num}")
        return issue_num, title

    except json.JSONDecodeError as e:
        debug_log(f"JSONDecodeError: {e}", "ERROR")
    except subprocess.CalledProcessError as e:
        debug_log(f"CalledProcessError: {e.returncode} - {e.stderr}", "ERROR")
    except subprocess.TimeoutExpired:
        debug_log("TimeoutExpired: gh command took >5s", "WARN")
    except FileNotFoundError as e:
        debug_log(f"FileNotFoundError: {e}", "ERROR")
    except Exception as e:
        debug_log(f"Unexpected error: {type(e).__name__}: {e}", "ERROR")

    return None, None


def run_recall_elements(issue_num: str, plugin_root: str) -> None:
    """
    Run recall_elements.py to recover issue context.

    Args:
        issue_num: Issue number to recover
        plugin_root: Path to GHE plugin root
    """
    recall_script = Path(plugin_root) / 'scripts' / 'recall_elements.py'
    if not recall_script.exists():
        debug_log(f"recall_elements.py not found at {recall_script}", "WARN")
        return

    debug_log(f"Running recall_elements.py for issue #{issue_num} (10s timeout)...")
    try:
        result = subprocess.run(
            [sys.executable, str(recall_script), '--issue', issue_num, '--recover'],
            capture_output=True,
            text=True,
            check=False,
            timeout=10
        )
        debug_log(f"recall_elements.py completed: exit={result.returncode}")
    except subprocess.TimeoutExpired:
        debug_log("recall_elements.py TIMEOUT (>10s)", "WARN")
    except subprocess.SubprocessError as e:
        debug_log(f"recall_elements.py SubprocessError: {e}", "ERROR")
    except FileNotFoundError as e:
        debug_log(f"recall_elements.py FileNotFoundError: {e}", "ERROR")


# =============================================================================
# PHASE 4: Build Output (from transcription_notify.py)
# =============================================================================

def get_active_issue() -> Tuple[Optional[int], str]:
    """
    Get the current active issue number and title from last_active_issue.json.

    Returns:
        Tuple of (issue_number, title)
    """
    debug_log("Phase 4: Getting active issue for notification...")

    # Find .claude directory
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"

    if not claude_dir.exists():
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                claude_dir = parent / ".claude"
                break
        else:
            return None, ""

    config_path = claude_dir / "last_active_issue.json"
    if not config_path.exists():
        debug_log("No last_active_issue.json found")
        return None, ""

    try:
        with open(config_path) as f:
            data = json.load(f)
            issue = data.get("issue")
            title = data.get("title", "")
            debug_log(f"Active issue: #{issue} - {title[:50] if title else 'N/A'}")
            return issue, title
    except (json.JSONDecodeError, IOError) as e:
        debug_log(f"Error reading last_active_issue.json: {e}", "ERROR")
        return None, ""


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    """
    Unified SessionStart hook - runs all initialization phases in sequence.

    Phases:
    1. Find GHE configuration
    2. Verify GitHub connectivity
    3. Session recovery (auto-resume last issue)
    4. Build and output JSON response

    CRITICAL: Outputs EXACTLY ONE JSON object to stdout.
    """
    debug_log("=" * 60)
    debug_log("UNIFIED SESSION START HOOK BEGINNING")
    debug_log("=" * 60)

    # Get plugin root from environment
    plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", str(script_dir.parent))
    debug_log(f"CLAUDE_PLUGIN_ROOT={plugin_root}")

    # =========================================================================
    # PHASE 1: Find configuration
    # =========================================================================
    config_file = find_config()

    if not config_file:
        # No config - prompt user to run setup
        debug_log("No GHE config - prompting for setup")
        # Always use suppressOutput to avoid parsing issues
        output_json_and_exit({
            "event": "SessionStart",
            "suppressOutput": True
        })

    # Get repo path from config
    repo_path = get_repo_path(config_file)
    if not repo_path:
        debug_log("Config file found but repo_path is missing!", "ERROR")
        # Always use suppressOutput to avoid parsing issues
        output_json_and_exit({
            "event": "SessionStart",
            "suppressOutput": True
        })

    # Verify repo_path exists
    if not Path(repo_path).is_dir():
        debug_log(f"repo_path does not exist: {repo_path}", "ERROR")
        # Always use suppressOutput to avoid parsing issues
        output_json_and_exit({
            "event": "SessionStart",
            "suppressOutput": True
        })

    # Ensure required folders exist (silent)
    ensure_folder(f"{repo_path}/REQUIREMENTS", "REQUIREMENTS")
    ensure_folder(f"{repo_path}/REQUIREMENTS/_templates", "REQUIREMENTS/_templates")
    ensure_folder(f"{repo_path}/GHE_REPORTS", "GHE_REPORTS")

    # =========================================================================
    # PHASE 2: Verify GitHub connectivity
    # =========================================================================
    github_ok = check_github_repo(repo_path)
    if not github_ok:
        debug_log("GitHub connectivity check failed - continuing anyway", "WARN")

    # =========================================================================
    # PHASE 2.5: Recover messages from previous session transcript
    # =========================================================================
    # This ensures NO messages are ever lost - we extract them from the
    # transcript file that was saved by the Stop hook in the previous session
    try:
        from recover_transcript import recover_messages
        recovered = recover_messages()
        if recovered > 0:
            debug_log(f"Recovered {recovered} messages from previous session")
    except ImportError:
        debug_log("recover_transcript not available", "WARN")
    except Exception as e:
        debug_log(f"Transcript recovery failed: {e}", "WARN")

    # =========================================================================
    # PHASE 3: Session recovery
    # =========================================================================
    # First check if there's already an active issue in config
    current_issue = get_current_issue_from_config()
    issue_title = ""

    if not current_issue or current_issue == "null":
        # Try to auto-resume from last_active_issue.json
        current_issue, issue_title = auto_resume_last_issue()

    # Run recall_elements if we have an active issue
    if current_issue and current_issue != "null":
        run_recall_elements(current_issue, plugin_root)
    else:
        debug_log("No active issue to recover")

    # =========================================================================
    # PHASE 4: Check for unposted WAL entries and spawn worker
    # =========================================================================
    try:
        from wal_manager import has_unposted_entries, is_worker_running
        if has_unposted_entries() and not is_worker_running():
            debug_log("Found unposted WAL entries, spawning worker...")
            import subprocess
            worker_script = Path(plugin_root) / "scripts" / "transcription_worker.py"
            if worker_script.exists():
                subprocess.Popen(
                    [sys.executable, str(worker_script)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    stdin=subprocess.DEVNULL,
                    start_new_session=True,
                    cwd=repo_path,
                )
                debug_log("Spawned transcription worker")
    except ImportError:
        debug_log("wal_manager not available, skipping worker spawn", "WARN")
    except Exception as e:
        debug_log(f"Error spawning worker: {e}", "WARN")

    # =========================================================================
    # PHASE 5: Build output
    # =========================================================================
    # Get active issue for notification (may have been set during recovery)
    issue, title = get_active_issue()

    if issue:
        # Build notification message
        if title:
            message = f"GHE Transcription ON: Issue #{issue} - {title}"
        else:
            message = f"GHE Transcription ON: Issue #{issue}"

        debug_log(f"Output: {message[:80]}")
        debug_log("UNIFIED SESSION START HOOK COMPLETE - with notification")
        # SIMPLIFIED: Always use suppressOutput to avoid hookSpecificOutput parsing issues
        # The notification is logged but not shown to user via hook output
        output_json_and_exit({
            "event": "SessionStart",
            "suppressOutput": True
        })
    else:
        # No issue - suppress output
        debug_log("No active issue - suppressing output")
        debug_log("UNIFIED SESSION START HOOK COMPLETE - suppressed")
        output_json_and_exit({
            "event": "SessionStart",
            "suppressOutput": True
        })


# Need to import os for environ access
import os

if __name__ == "__main__":
    main()
