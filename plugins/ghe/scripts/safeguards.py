#!/usr/bin/env python3
"""
GHE Safeguards - Comprehensive error prevention and recovery
Import this module to use safeguard functions in your scripts

Usage:
    from safeguards import *
    ghe_init()  # Initialize GHE environment

Functions provided:
    - verify_worktree_health(path)
    - safe_worktree_cleanup(path, force=False)
    - acquire_merge_lock_safe(issue_num)
    - release_merge_lock_safe(issue_num)
    - heartbeat_merge_lock(issue_num)
    - wait_for_merge_lock(issue_num, timeout=None)
    - atomic_commit_push(branch, message, files)
    - reconcile_ghe_state()
    - validate_with_retry(script, file)
    - pre_flight_check(issue_num)
    - recover_from_merge_crash(issue_num)
"""

import os
import re
import sys
import json
import time
import argparse
import subprocess
import shutil
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone

# Import from ghe_common module
from ghe_common import (
    ghe_init as GHE_INIT,
    ghe_get_setting,
    ghe_find_config_file,
    ghe_git,
    ghe_gh,
    GHE_RED as RED,
    GHE_GREEN as GREEN,
    GHE_YELLOW as YELLOW,
    GHE_NC as NC,
)

# Configuration - read from environment or use defaults
LOCK_TTL = int(os.environ.get("LOCK_TTL", "900"))  # 15 minutes default
HEARTBEAT_INTERVAL = int(os.environ.get("HEARTBEAT_INTERVAL", "60"))  # 1 minute
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.environ.get("RETRY_DELAY", "2"))
GHE_WORKTREES_DIR = os.environ.get("GHE_WORKTREES_DIR", "../ghe-worktrees")


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
            f.write(f"{timestamp} {level:<5} [safeguards] - {message}\n")
    except Exception:
        pass  # Never fail on logging


def log_error(message: str) -> None:
    """Log error message to stderr"""
    print(f"{RED}ERROR: {message}{NC}", file=sys.stderr)


def log_warn(message: str) -> None:
    """Log warning message to stderr"""
    print(f"{YELLOW}WARNING: {message}{NC}", file=sys.stderr)


def log_ok(message: str) -> None:
    """Log success message"""
    print(f"{GREEN}OK: {message}{NC}")


def log_info(message: str) -> None:
    """Log info message"""
    print(f"INFO: {message}")


# =============================================================================
# WORKTREE SAFEGUARDS
# =============================================================================


def verify_worktree_health(worktree_path: str) -> bool:
    """
    Verify worktree is healthy and usable

    Args:
        worktree_path: Path to the worktree directory

    Returns:
        True if healthy, False if not
    """
    log_info(f"Verifying worktree health: {worktree_path}")

    worktree_path_obj = Path(worktree_path)

    # Check 1: Directory exists
    if not worktree_path_obj.is_dir():
        log_error(f"Worktree directory does not exist: {worktree_path}")
        return False

    # Check 2: .git file exists (worktrees have .git file, not directory)
    git_file = worktree_path_obj / ".git"
    if not git_file.is_file():
        log_error(f"Not a valid worktree (missing .git file): {worktree_path}")
        return False

    # Check 3: .git file points to valid location
    try:
        with open(git_file, "r") as f:
            git_content = f.read().strip()
        git_dir = git_content.replace("gitdir: ", "")
        if not Path(git_dir).is_dir():
            log_error(f"Worktree .git file points to non-existent directory: {git_dir}")
            return False
    except (IOError, OSError) as e:
        log_error(f"Failed to read .git file: {e}")
        return False

    # Check 4: Git recognizes it as worktree
    result = ghe_git("worktree", "list", capture=True)
    if result.returncode != 0:
        log_error("Failed to list worktrees")
        return False

    realpath = str(worktree_path_obj.resolve())
    if realpath not in result.stdout:
        log_warn(f"Git does not recognize worktree: {worktree_path}")
        log_info("Attempting repair with: git worktree prune")
        ghe_git("worktree", "prune")

        # Re-check after prune
        result = ghe_git("worktree", "list", capture=True)
        if result.returncode != 0 or realpath not in result.stdout:
            log_error("Worktree still not recognized after prune")
            return False

    # Check 5: Branch exists and is checked out
    result = subprocess.run(
        ["git", "branch", "--show-current"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=False,
    )
    branch = result.stdout.strip() if result.returncode == 0 else ""

    if not branch:
        log_error("Worktree has no branch checked out (detached HEAD or corrupted)")
        return False

    # Check 6: No uncommitted changes that would block operations
    result = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=worktree_path,
        capture_output=True,
        text=True,
        check=False,
    )
    git_status_output = result.stdout.strip() if result.returncode == 0 else ""

    if git_status_output:
        log_warn("Worktree has uncommitted changes")
        # Not a failure, just a warning

    log_ok(f"Worktree health verified: {worktree_path} (branch: {branch})")
    return True


def safe_worktree_cleanup(worktree_path: str, force: bool = False) -> bool:
    """
    Safely clean up a worktree, handling all edge cases

    Args:
        worktree_path: Path to the worktree directory
        force: If True, force cleanup even with uncommitted changes

    Returns:
        True if cleanup successful, False otherwise
    """
    log_info(f"Cleaning up worktree: {worktree_path} (force={force})")

    worktree_path_obj = Path(worktree_path)

    # Step 1: Check if directory exists at all
    if not worktree_path_obj.is_dir():
        log_info(f"Worktree directory already removed: {worktree_path}")
        ghe_git("worktree", "prune")
        return True

    # Step 2: Check for uncommitted changes
    git_file = worktree_path_obj / ".git"
    if git_file.is_file():
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
        git_status_output = result.stdout.strip() if result.returncode == 0 else ""

        if git_status_output and not force:
            log_error("Worktree has uncommitted changes. Use force=True to override.")
            log_info("Changes:")
            print(git_status_output)
            return False

    # Step 3: Try normal removal first
    result = ghe_git("worktree", "remove", worktree_path, capture=True)
    if result.returncode == 0:
        log_ok(f"Worktree removed successfully: {worktree_path}")
        return True

    # Step 4: If normal removal failed and force=True, do manual cleanup
    if force:
        log_warn("Normal removal failed, forcing cleanup...")

        # Remove .git file to unlink from main repo
        try:
            git_file.unlink(missing_ok=True)
        except OSError:
            pass

        # Prune stale worktrees from git's tracking
        ghe_git("worktree", "prune")

        # Remove directory
        try:
            shutil.rmtree(worktree_path)
        except OSError as e:
            log_error(f"Failed to remove directory: {e}")
            return False

        log_ok(f"Worktree force-removed: {worktree_path}")
        return True

    log_error("Could not remove worktree. Use force=True to override.")
    return False


# =============================================================================
# MERGE LOCK SAFEGUARDS
# =============================================================================


def acquire_merge_lock_safe(issue_num: str) -> bool:
    """
    Acquire merge lock with race condition detection and TTL enforcement

    Args:
        issue_num: Issue number to acquire lock for

    Returns:
        True if lock acquired, False if not
    """
    lock_label = "merge:active"

    log_info(f"Attempting to acquire merge lock for issue #{issue_num}")

    # Check for existing lock (using ghe_gh to run from correct repo root)
    result = ghe_gh(
        "issue",
        "list",
        "--label",
        lock_label,
        "--state",
        "open",
        "--json",
        "number,updatedAt",
        capture=True,
    )

    existing_lock = ""
    if result.returncode == 0:
        existing_lock = result.stdout.strip()

    if existing_lock and existing_lock != "[]":
        try:
            lock_data = json.loads(existing_lock)
            if lock_data:
                lock_issue = str(lock_data[0]["number"])
                lock_time = lock_data[0]["updatedAt"]

                # Calculate lock age
                now_epoch = int(time.time())
                try:
                    # Parse ISO 8601 timestamp
                    lock_dt = datetime.fromisoformat(lock_time.replace("Z", "+00:00"))
                    lock_epoch = int(lock_dt.timestamp())
                except (ValueError, AttributeError):
                    lock_epoch = 0

                if lock_epoch != 0:
                    lock_age = now_epoch - lock_epoch

                    if lock_age > LOCK_TTL:
                        log_warn(
                            f"Stale lock detected on issue #{lock_issue} (age: {lock_age}s > TTL: {LOCK_TTL}s)"
                        )
                        log_info("Force-releasing stale lock...")
                        ghe_gh(
                            "issue", "edit", lock_issue, "--remove-label", lock_label
                        )
                    else:
                        log_warn(
                            f"Lock held by issue #{lock_issue} (age: {lock_age}s, TTL: {LOCK_TTL}s)"
                        )
                        log_info("Wait for lock release or TTL expiry")
                        return False
                else:
                    log_warn("Could not parse lock timestamp, assuming stale")
                    ghe_gh("issue", "edit", lock_issue, "--remove-label", lock_label)
        except (json.JSONDecodeError, KeyError, IndexError):
            pass

    # Acquire lock
    result = ghe_gh("issue", "edit", issue_num, "--add-label", lock_label, capture=True)
    if result.returncode != 0:
        log_error("Failed to add merge lock label")
        return False

    # Brief pause to detect race conditions
    time.sleep(2)

    # Verify we're the only lock holder (race condition check)
    result = ghe_gh(
        "issue",
        "list",
        "--label",
        lock_label,
        "--state",
        "open",
        "--json",
        "number",
        capture=True,
    )

    holders = 0
    if result.returncode == 0:
        try:
            lock_data = json.loads(result.stdout.strip())
            holders = len(lock_data)
        except json.JSONDecodeError:
            holders = 0

    if holders > 1:
        log_error("Race condition detected - multiple lock holders!")
        log_info("Releasing our lock to avoid deadlock...")
        ghe_gh("issue", "edit", issue_num, "--remove-label", lock_label)
        return False

    log_ok(f"Merge lock acquired for issue #{issue_num}")
    return True


def release_merge_lock_safe(issue_num: str) -> None:
    """
    Release merge lock

    Args:
        issue_num: Issue number to release lock for
    """
    lock_label = "merge:active"

    log_info(f"Releasing merge lock for issue #{issue_num}")

    # Remove lock label (ignore errors - lock might already be released)
    ghe_gh("issue", "edit", issue_num, "--remove-label", lock_label)

    log_ok(f"Merge lock released for issue #{issue_num}")


def heartbeat_merge_lock(issue_num: str) -> None:
    """
    Send heartbeat to keep lock alive during long operations

    Args:
        issue_num: Issue number to send heartbeat for
    """
    # Update issue to refresh updatedAt timestamp
    # Use a hidden comment to minimize noise
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    comment = f"<!-- ghe-merge-heartbeat: {timestamp} -->"
    ghe_gh("issue", "comment", issue_num, "--body", comment)


def wait_for_merge_lock(issue_num: str, timeout: Optional[int] = None) -> bool:
    """
    Wait for merge lock with timeout

    Args:
        issue_num: Issue number to wait for lock on
        timeout: Timeout in seconds (defaults to LOCK_TTL)

    Returns:
        True if lock acquired, False if timeout
    """
    if timeout is None:
        timeout = LOCK_TTL

    start_time = int(time.time())

    log_info(f"Waiting for merge lock (timeout: {timeout}s)...")

    while True:
        if acquire_merge_lock_safe(issue_num):
            return True

        elapsed = int(time.time()) - start_time
        if elapsed > timeout:
            log_error(f"Timeout waiting for merge lock ({elapsed}s > {timeout}s)")
            return False

        log_info(f"Lock busy, waiting... ({elapsed}s / {timeout}s)")
        time.sleep(30)


# =============================================================================
# ATOMIC GIT OPERATIONS
# =============================================================================


def atomic_commit_push(branch: str, message: str, files: List[str]) -> bool:
    """
    Perform atomic commit and push with rollback on failure

    Args:
        branch: Branch name to push to
        message: Commit message
        files: List of files to commit

    Returns:
        True if successful, False otherwise
    """
    log_info(f"Atomic commit-push: {len(files)} files to branch {branch}")

    # Create savepoint (using ghe_git to operate on correct repo)
    result = ghe_git("rev-parse", "HEAD", capture=True)
    if result.returncode != 0:
        log_error("Failed to get current HEAD")
        return False

    savepoint = result.stdout.strip()
    log_info(f"Savepoint: {savepoint}")

    # Stage files
    for file in files:
        if not Path(file).exists():
            log_error(f"File does not exist: {file}")
            ghe_git("reset", "HEAD")
            return False

        result = ghe_git("add", file, capture=True)
        if result.returncode != 0:
            log_error(f"Failed to stage: {file}")
            ghe_git("reset", "HEAD")
            return False

    # Check if there's anything to commit
    result = ghe_git("diff", "--cached", "--quiet", capture=True)
    if result.returncode == 0:
        log_warn("No changes to commit")
        return True

    # Commit
    result = ghe_git("commit", "-m", message, capture=True)
    if result.returncode != 0:
        log_error("Commit failed, rolling back staged changes")
        ghe_git("reset", "HEAD")
        return False

    result = ghe_git("rev-parse", "HEAD", capture=True)
    commit_hash = result.stdout.strip() if result.returncode == 0 else "unknown"
    log_info(f"Committed: {commit_hash}")

    # Push
    result = ghe_git("push", "origin", branch, capture=True)
    if result.returncode != 0:
        log_error("Push failed, rolling back commit")
        ghe_git("reset", "--hard", savepoint)
        return False

    log_ok(f"Atomic commit-push completed: {commit_hash}")
    return True


# =============================================================================
# STATE RECONCILIATION
# =============================================================================


def reconcile_ghe_state() -> None:
    """
    Reconcile ghe.local.md state with actual GitHub state
    """
    # Use library to find config file (no need to pass it manually)
    config_file = os.environ.get("GHE_CONFIG_FILE") or ghe_find_config_file()

    log_info("Reconciling GHE state...")

    if not config_file or not Path(config_file).is_file():
        log_warn("Config file not found")
        return

    # Read current state from config using library function
    config_issue = ghe_get_setting("current_issue", "")

    # Check if referenced issue is still open
    if config_issue and config_issue != "null":
        result = ghe_gh(
            "issue",
            "view",
            config_issue,
            "--json",
            "state",
            "--jq",
            ".state",
            capture=True,
        )
        issue_state = result.stdout.strip() if result.returncode == 0 else "UNKNOWN"

        if issue_state == "CLOSED":
            log_warn(f"ghe.local.md references closed issue #{config_issue}")
            log_info("Resetting state to null...")

            # Use Python string operations (cross-platform, no sed dependency)
            try:
                with open(config_file, "r", encoding="utf-8") as f:
                    content = f.read()
                # Replace current_issue and current_phase with null
                content = re.sub(
                    r"^current_issue:.*$",
                    "current_issue: null",
                    content,
                    flags=re.MULTILINE,
                )
                content = re.sub(
                    r"^current_phase:.*$",
                    "current_phase: null",
                    content,
                    flags=re.MULTILINE,
                )
                with open(config_file, "w", encoding="utf-8") as f:
                    f.write(content)
            except (IOError, OSError) as e:
                log_error(f"Failed to update config file: {e}")

    # Check for orphaned worktrees
    worktrees_dir = Path(GHE_WORKTREES_DIR)
    if worktrees_dir.is_dir():
        for wt in worktrees_dir.glob("issue-*/"):
            if wt.is_dir():
                issue_num = wt.name.replace("issue-", "")

                result = ghe_gh(
                    "issue",
                    "view",
                    issue_num,
                    "--json",
                    "state",
                    "--jq",
                    ".state",
                    capture=True,
                )
                issue_state = (
                    result.stdout.strip() if result.returncode == 0 else "UNKNOWN"
                )

                if issue_state == "CLOSED":
                    log_warn(
                        f"Orphaned worktree found for closed issue #{issue_num}: {wt}"
                    )
                    log_info("Cleaning up orphaned worktree...")
                    safe_worktree_cleanup(str(wt), force=True)

    # Prune any stale worktrees (using ghe_git)
    ghe_git("worktree", "prune")

    log_ok("State reconciliation complete")


# =============================================================================
# VALIDATION WITH RETRIES
# =============================================================================


def validate_with_retry(script: str, file: str) -> bool:
    """
    Run validation script with retries for transient failures

    Args:
        script: Path to validation script
        file: File to validate

    Returns:
        True if validation passed, False otherwise
    """
    log_info(f"Validating: {file} (max {MAX_RETRIES} attempts)")

    for i in range(1, MAX_RETRIES + 1):
        result = subprocess.run([script, file], capture_output=True, check=False)

        if result.returncode == 0:
            log_ok(f"Validation passed on attempt {i}")
            return True

        if i < MAX_RETRIES:
            log_warn(
                f"Validation failed (attempt {i}/{MAX_RETRIES}), retrying in {RETRY_DELAY}s..."
            )
            time.sleep(RETRY_DELAY)

    log_error(f"Validation failed after {MAX_RETRIES} attempts")
    return False


# =============================================================================
# PRE-FLIGHT CHECK
# =============================================================================


def pre_flight_check(issue_num: str) -> bool:
    """
    Run all safety checks before starting work on an issue

    Args:
        issue_num: Issue number to check

    Returns:
        True if all checks passed, False otherwise
    """
    worktree_path = Path(GHE_WORKTREES_DIR) / f"issue-{issue_num}"
    errors = 0

    log_info(f"Running pre-flight checks for issue #{issue_num}")
    print("=" * 50)

    # Check 1: Issue exists and is open
    print(f"[1/6] Issue #{issue_num} status: ", end="")
    result = ghe_gh(
        "issue", "view", issue_num, "--json", "state", "--jq", ".state", capture=True
    )
    issue_state = result.stdout.strip() if result.returncode == 0 else "NOT_FOUND"

    if issue_state == "OPEN":
        print(f"{GREEN}OPEN{NC}")
    else:
        print(f"{RED}{issue_state}{NC}")
        errors += 1

    # Check 2: Worktree exists
    print("[2/6] Worktree exists: ", end="")
    if worktree_path.is_dir():
        print(f"{GREEN}YES{NC}")
    else:
        print(f"{YELLOW}NO (will be created){NC}")

    # Check 3: Worktree health (if exists)
    print("[3/6] Worktree health: ", end="")
    if worktree_path.is_dir():
        # Suppress output from verify_worktree_health by redirecting
        import io
        import contextlib

        f = io.StringIO()
        with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
            is_healthy = verify_worktree_health(str(worktree_path))

        if is_healthy:
            print(f"{GREEN}HEALTHY{NC}")
        else:
            print(f"{RED}UNHEALTHY{NC}")
            errors += 1
    else:
        print(f"{YELLOW}N/A{NC}")

    # Check 4: Not on main branch (if in worktree)
    print("[4/6] Branch check: ", end="")
    if worktree_path.is_dir():
        result = subprocess.run(
            ["git", "branch", "--show-current"],
            cwd=str(worktree_path),
            capture_output=True,
            text=True,
            check=False,
        )
        current_branch = result.stdout.strip() if result.returncode == 0 else ""

        if current_branch == "main":
            print(f"{RED}ON MAIN (FORBIDDEN){NC}")
            errors += 1
        elif current_branch:
            print(f"{GREEN}{current_branch}{NC}")
        else:
            print(f"{RED}DETACHED HEAD{NC}")
            errors += 1
    else:
        print(f"{YELLOW}N/A{NC}")

    # Check 5: No active merge lock (unless it's ours)
    print("[5/6] Merge lock: ", end="")
    result = ghe_gh(
        "issue",
        "list",
        "--label",
        "merge:active",
        "--state",
        "open",
        "--json",
        "number",
        "--jq",
        ".[0].number",
        capture=True,
    )
    lock_holder = result.stdout.strip() if result.returncode == 0 else ""

    if not lock_holder:
        print(f"{GREEN}FREE{NC}")
    elif lock_holder == issue_num:
        print(f"{YELLOW}HELD BY US{NC}")
    else:
        print(f"{YELLOW}HELD BY #{lock_holder}{NC}")

    # Check 6: GitHub CLI authenticated
    print("[6/6] GitHub auth: ", end="")
    result = subprocess.run(["gh", "auth", "status"], capture_output=True, check=False)
    if result.returncode == 0:
        print(f"{GREEN}OK{NC}")
    else:
        print(f"{RED}NOT AUTHENTICATED{NC}")
        errors += 1

    print("=" * 50)

    if errors > 0:
        log_error(f"Pre-flight check failed with {errors} error(s)")
        return False

    log_ok("All pre-flight checks passed")
    return True


# =============================================================================
# RECOVERY PROCEDURES
# =============================================================================


def recover_from_merge_crash(issue_num: str) -> None:
    """
    Recover from a crashed/interrupted merge operation

    Args:
        issue_num: Issue number to recover
    """
    log_info(f"Attempting recovery from merge crash for issue #{issue_num}")

    # Step 1: Release any held locks
    release_merge_lock_safe(issue_num)

    # Step 2: Check worktree state
    worktree_path = Path(GHE_WORKTREES_DIR) / f"issue-{issue_num}"

    if worktree_path.is_dir():
        # Check for in-progress rebase
        rebase_merge = worktree_path / ".git" / "rebase-merge"
        rebase_apply = worktree_path / ".git" / "rebase-apply"

        if rebase_merge.is_dir() or rebase_apply.is_dir():
            log_warn("Found in-progress rebase, aborting...")
            subprocess.run(
                ["git", "rebase", "--abort"], cwd=str(worktree_path), check=False
            )

        # Check for merge in progress
        merge_head = worktree_path / ".git" / "MERGE_HEAD"
        if merge_head.is_file():
            log_warn("Found in-progress merge, aborting...")
            subprocess.run(
                ["git", "merge", "--abort"], cwd=str(worktree_path), check=False
            )

    # Step 3: Reconcile state
    reconcile_ghe_state()

    log_ok(f"Recovery complete for issue #{issue_num}")


# =============================================================================
# HELP AND CLI
# =============================================================================


def print_safeguards_help() -> None:
    """Print usage/help information"""
    help_text = """
GHE Safeguards - Available Functions

WORKTREE OPERATIONS:
  verify_worktree_health(path)          - Check if worktree is healthy
  safe_worktree_cleanup(path, force)    - Safely remove worktree

MERGE LOCK OPERATIONS:
  acquire_merge_lock_safe(issue)        - Acquire lock with TTL enforcement
  release_merge_lock_safe(issue)        - Release merge lock
  wait_for_merge_lock(issue, timeout)   - Wait for lock with timeout
  heartbeat_merge_lock(issue)           - Send heartbeat to keep lock alive

GIT OPERATIONS:
  atomic_commit_push(branch, msg, files) - Atomic commit+push

STATE MANAGEMENT:
  reconcile_ghe_state()                 - Fix state desync
  pre_flight_check(issue)               - Run all safety checks
  recover_from_merge_crash(issue)       - Recover from crash

VALIDATION:
  validate_with_retry(script, file)     - Validate with retries

CONFIGURATION (environment variables):
  LOCK_TTL=900              - Lock timeout in seconds (default: 15 min)
  MAX_RETRIES=3             - Retry attempts for validation
  RETRY_DELAY=2             - Delay between retries in seconds
  GHE_WORKTREES_DIR=../ghe-worktrees - Worktrees directory

"""
    print(help_text)


def main() -> int:
    """Main entry point when script is run directly"""
    debug_log("safeguards started")
    parser = argparse.ArgumentParser(
        description="GHE Safeguards - Comprehensive error prevention and recovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "command",
        nargs="?",
        help="Command to run (help, preflight, reconcile, recover)",
    )
    parser.add_argument("--issue", type=str, help="Issue number")
    parser.add_argument("--worktree", type=str, help="Worktree path")
    parser.add_argument("--force", action="store_true", help="Force operation")

    args = parser.parse_args()

    # Initialize GHE environment
    GHE_INIT()

    if not args.command or args.command == "help":
        debug_log("Running check: help")
        print_safeguards_help()
        debug_log("safeguards completed")
        return 0

    if args.command == "preflight":
        debug_log("Running check: preflight")
        if not args.issue:
            debug_log("Violation found: --issue required for preflight check", "WARN")
            print("Error: --issue required for preflight check", file=sys.stderr)
            return 1
        success = pre_flight_check(args.issue)
        debug_log("safeguards completed")
        return 0 if success else 1

    if args.command == "reconcile":
        debug_log("Running check: reconcile")
        reconcile_ghe_state()
        debug_log("safeguards completed")
        return 0

    if args.command == "recover":
        debug_log("Running check: recover")
        if not args.issue:
            debug_log("Violation found: --issue required for recovery", "WARN")
            print("Error: --issue required for recovery", file=sys.stderr)
            return 1
        recover_from_merge_crash(args.issue)
        debug_log("safeguards completed")
        return 0

    if args.command == "verify":
        debug_log("Running check: verify")
        if not args.worktree:
            debug_log("Violation found: --worktree required for verification", "WARN")
            print("Error: --worktree required for verification", file=sys.stderr)
            return 1
        success = verify_worktree_health(args.worktree)
        debug_log("safeguards completed")
        return 0 if success else 1

    if args.command == "cleanup":
        debug_log("Running check: cleanup")
        if not args.worktree:
            debug_log("Violation found: --worktree required for cleanup", "WARN")
            print("Error: --worktree required for cleanup", file=sys.stderr)
            return 1
        success = safe_worktree_cleanup(args.worktree, args.force)
        debug_log("safeguards completed")
        return 0 if success else 1

    debug_log(f"Violation found: Unknown command: {args.command}", "ERROR")
    print(f"Unknown command: {args.command}", file=sys.stderr)
    print_safeguards_help()
    return 1


# Export all public functions
__all__ = [
    # Worktree operations
    "verify_worktree_health",
    "safe_worktree_cleanup",
    # Merge lock operations
    "acquire_merge_lock_safe",
    "release_merge_lock_safe",
    "heartbeat_merge_lock",
    "wait_for_merge_lock",
    # Git operations
    "atomic_commit_push",
    # State management
    "reconcile_ghe_state",
    "pre_flight_check",
    "recover_from_merge_crash",
    # Validation
    "validate_with_retry",
    # Logging
    "log_error",
    "log_warn",
    "log_ok",
    "log_info",
]


if __name__ == "__main__":
    sys.exit(main())
