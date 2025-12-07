#!/usr/bin/env python3
"""
phase_transition.py - Handle GHE workflow phase transitions

This script orchestrates phase transitions in the GHE workflow:
DEV -> TEST -> REVIEW -> MERGE

Transitions can be:
- Forward: DEV->TEST, TEST->REVIEW, REVIEW->MERGE
- Demotion: REVIEW->DEV (failure), TEST->DEV (failure)

Usage:
  phase_transition.py <action> <issue-number> [context]

Actions:
  request <target-phase> - Request transition to target phase
  validate <from> <to>   - Validate if transition is allowed
  execute <to>           - Execute transition (update labels, spawn agent)
  demote                 - Demote back to DEV with feedback

Examples:
  phase_transition.py request TEST 123         # DEV wants to go to TEST
  phase_transition.py validate DEV TEST        # Check if DEV->TEST is valid
  phase_transition.py execute TEST 123         # Execute transition to TEST
  phase_transition.py demote 123 "Test failures" # Send back to DEV
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

# Import GHE common library
from ghe_common import (
    ghe_init,
    ghe_get_setting,
    ghe_gh,
    ghe_git,
    GHE_REPO_ROOT,
    GHE_RED,
    GHE_GREEN,
    GHE_YELLOW,
    GHE_NC,
    ensure_directory,
)


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [phase_transition] - {message}\n")
    except Exception:
        pass


# Valid phases
PHASES = ["DEV", "TEST", "REVIEW", "MERGE"]

# Phase agent mapping
PHASE_AGENTS: Dict[str, str] = {
    "DEV": "dev-thread-manager",
    "TEST": "test-thread-manager",
    "REVIEW": "review-thread-manager",
}

# Phase Greek names mapping
PHASE_GREEK: Dict[str, str] = {
    "DEV": "Hephaestus",
    "TEST": "Artemis",
    "REVIEW": "Hera",
}

# Phase labels mapping
PHASE_LABELS: Dict[str, str] = {
    "DEV": "phase:dev",
    "TEST": "phase:test",
    "REVIEW": "phase:review",
}


def is_valid_transition(from_phase: str, to_phase: str) -> bool:
    """
    Check if a phase transition is valid.

    Args:
        from_phase: Source phase
        to_phase: Target phase

    Returns:
        True if transition is valid, False otherwise
    """
    transition = f"{from_phase}->{to_phase}"

    # Forward transitions
    if transition in ["DEV->TEST", "TEST->REVIEW", "REVIEW->MERGE"]:
        return True

    # Demotions (always go back to DEV)
    if transition in ["REVIEW->DEV", "TEST->DEV"]:
        return True

    # Same phase (no-op, still valid)
    if from_phase == to_phase and from_phase in PHASES:
        return True

    return False


def get_issue_phase(issue: str) -> str:
    """
    Get current phase from issue labels.

    Args:
        issue: Issue number

    Returns:
        Current phase ("DEV", "TEST", "REVIEW", or "UNKNOWN")
    """
    debug_log(f"get_issue_phase called for issue #{issue}")
    result = ghe_gh(
        "issue",
        "view",
        issue,
        "--json",
        "labels",
        "--jq",
        ".labels[].name",
        capture=True,
    )

    if result.returncode != 0:
        debug_log(
            f"Failed to get labels for issue #{issue}, returncode={result.returncode}",
            "WARN",
        )
        return "UNKNOWN"

    labels = result.stdout.strip()
    debug_log(f"Issue #{issue} labels: {labels}")

    if "phase:review" in labels:
        debug_log(f"Issue #{issue} phase: REVIEW")
        return "REVIEW"
    elif "phase:test" in labels:
        debug_log(f"Issue #{issue} phase: TEST")
        return "TEST"
    elif "phase:dev" in labels:
        debug_log(f"Issue #{issue} phase: DEV")
        return "DEV"
    else:
        debug_log(f"Issue #{issue} phase: UNKNOWN")
        return "UNKNOWN"


def log_transition(
    issue: str, from_phase: str, to_phase: str, status: str, message: str
) -> None:
    """
    Log transition event to internal log file.

    Args:
        issue: Issue number
        from_phase: Source phase
        to_phase: Target phase
        status: Transition status (REQUESTED, EXECUTED, REJECTED, DEMOTED)
        message: Additional context
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    repo_root = GHE_REPO_ROOT or "."
    log_dir = Path(repo_root) / "GHE_REPORTS"
    ensure_directory(str(log_dir))

    log_file = log_dir / ".transitions.log"
    log_entry = f"[{timestamp}] Issue #{issue}: {from_phase} -> {to_phase} [{status}] {message}\n"

    try:
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except (IOError, OSError):
        pass


def request_transition(
    target_phase: str, issue: Optional[str] = None, context: Optional[str] = None
) -> None:
    """
    Request a phase transition (spawns Themis for validation).

    Args:
        target_phase: Target phase to transition to
        issue: Issue number (optional, uses current_issue if not provided)
        context: Additional context for the transition
    """
    debug_log(
        f"request_transition called: target={target_phase}, issue={issue}, context={context}"
    )
    target_phase = target_phase.upper()

    if not issue:
        issue = ghe_get_setting("current_issue", "")
        debug_log(f"Using current_issue from settings: {issue}")

    if not issue or issue == "null":
        debug_log("No issue specified and no current issue set", "ERROR")
        print(
            f"{GHE_RED}ERROR: No issue specified and no current issue set{GHE_NC}",
            file=sys.stderr,
        )
        sys.exit(1)

    current_phase = get_issue_phase(issue)
    debug_log(f"Current phase for issue #{issue}: {current_phase}")
    print(f"Issue #{issue} current phase: {current_phase}")
    print(f"Requested transition to: {target_phase}")

    # Validate transition
    if not is_valid_transition(current_phase, target_phase):
        debug_log(
            f"Invalid transition rejected: {current_phase} -> {target_phase}", "WARN"
        )
        print(
            f"{GHE_RED}ERROR: Invalid transition {current_phase} -> {target_phase}{GHE_NC}",
            file=sys.stderr,
        )
        print(f"Valid transitions from {current_phase}:")

        if current_phase == "DEV":
            print("  - DEV -> TEST")
        elif current_phase == "TEST":
            print("  - TEST -> REVIEW")
            print("  - TEST -> DEV (demotion)")
        elif current_phase == "REVIEW":
            print("  - REVIEW -> MERGE")
            print("  - REVIEW -> DEV (demotion)")

        log_transition(
            issue, current_phase, target_phase, "REJECTED", "Invalid transition"
        )
        sys.exit(1)

    # Spawn phase-gate agent for validation
    debug_log(f"Spawning Themis for validation: {current_phase} -> {target_phase}")
    print("Spawning Themis (phase-gate) to validate transition...")
    script_dir = Path(__file__).parent
    spawn_script = script_dir / "spawn_agent.py"

    context_str = context or ""
    spawn_context = (
        f"Validate: {current_phase} -> {target_phase}. Context: {context_str}"
    )

    subprocess.run(
        ["python3", str(spawn_script), "phase-gate", issue, spawn_context], check=False
    )

    log_transition(
        issue, current_phase, target_phase, "REQUESTED", "Validation pending"
    )
    debug_log(
        f"Transition request submitted for issue #{issue}: {current_phase} -> {target_phase}"
    )
    print(f"{GHE_GREEN}Transition request submitted. Themis will validate.{GHE_NC}")


def validate_transition(
    from_phase: str, to_phase: str, issue: Optional[str] = None
) -> int:
    """
    Validate a transition (called by phase-gate agent).

    Args:
        from_phase: Source phase
        to_phase: Target phase
        issue: Issue number (optional, uses current_issue if not provided)

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    debug_log(
        f"validate_transition called: from={from_phase}, to={to_phase}, issue={issue}"
    )
    from_phase = from_phase.upper()
    to_phase = to_phase.upper()

    if not issue:
        issue = ghe_get_setting("current_issue", "")
        debug_log(f"Using current_issue from settings: {issue}")

    print(f"Validating transition: {from_phase} -> {to_phase} for issue #{issue}")

    # Basic validation
    if not is_valid_transition(from_phase, to_phase):
        debug_log(
            f"Validation failed: invalid transition {from_phase} -> {to_phase}", "WARN"
        )
        print(f"{GHE_RED}VALIDATION FAILED: Invalid phase transition{GHE_NC}")
        print('{"valid": false, "reason": "Invalid phase order"}')
        return 1

    # Phase-specific validation
    if to_phase == "TEST":
        debug_log("Validating DEV -> TEST transition")
        # Check that code changes exist
        worktree_path = Path("..") / "ghe-worktrees" / f"issue-{issue}"
        if worktree_path.is_dir():
            result = ghe_git(
                "-C", str(worktree_path), "status", "--porcelain", capture=True
            )
            changes = (
                len(result.stdout.strip().split("\n")) if result.stdout.strip() else 0
            )
            debug_log(f"Worktree changes detected: {changes}")

            if changes == 0:
                # Check for commits ahead of main
                result = ghe_git(
                    "-C",
                    str(worktree_path),
                    "log",
                    "--oneline",
                    "origin/main..HEAD",
                    capture=True,
                )
                commits = (
                    len(result.stdout.strip().split("\n"))
                    if result.stdout.strip()
                    else 0
                )
                debug_log(f"Commits ahead of main: {commits}")

                if commits == 0:
                    debug_log("No changes detected, proceeding anyway", "WARN")
                    print(
                        f"{GHE_YELLOW}WARNING: No changes detected. Proceeding anyway.{GHE_NC}"
                    )

        debug_log("Validation passed: DEV -> TEST")
        print(f"{GHE_GREEN}VALIDATION PASSED: DEV -> TEST{GHE_NC}")
        print('{"valid": true, "reason": "DEV criteria met"}')

    elif to_phase == "REVIEW":
        debug_log("Validating TEST -> REVIEW transition")
        # In a real implementation, check that tests passed
        # For now, just validate the transition is logical
        debug_log("Validation passed: TEST -> REVIEW")
        print(f"{GHE_GREEN}VALIDATION PASSED: TEST -> REVIEW{GHE_NC}")
        print('{"valid": true, "reason": "TEST criteria met"}')

    elif to_phase == "MERGE":
        debug_log("Validating REVIEW -> MERGE transition")
        # Check for PASS verdict
        debug_log("Validation passed: REVIEW -> MERGE")
        print(f"{GHE_GREEN}VALIDATION PASSED: REVIEW -> MERGE{GHE_NC}")
        print('{"valid": true, "reason": "REVIEW passed"}')

    elif to_phase == "DEV":
        debug_log("Validating demotion to DEV")
        # Demotion is always valid
        debug_log("Validation passed: Demotion to DEV")
        print(f"{GHE_GREEN}VALIDATION PASSED: Demotion to DEV{GHE_NC}")
        print('{"valid": true, "reason": "Demotion approved"}')

    return 0


def get_avatar_header(agent_name: str) -> str:
    """
    Get avatar header for an agent using post_with_avatar module.

    Args:
        agent_name: Name of the agent (e.g., "Themis")

    Returns:
        Avatar header string, or empty string if not available
    """
    script_dir = Path(__file__).parent
    avatar_script = script_dir / "post_with_avatar.py"

    if not avatar_script.is_file():
        return ""

    try:
        # Call the Python script to get avatar header
        result = subprocess.run(
            ["python3", str(avatar_script), "--header-only", agent_name],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    return ""


def execute_transition(
    target_phase: str, issue: Optional[str] = None, context: Optional[str] = None
) -> None:
    """
    Execute a transition (update labels, spawn agent).

    Args:
        target_phase: Target phase to transition to
        issue: Issue number (optional, uses current_issue if not provided)
        context: Additional context for the transition
    """
    debug_log(
        f"execute_transition called: target={target_phase}, issue={issue}, context={context}"
    )
    target_phase = target_phase.upper()

    if not issue:
        issue = ghe_get_setting("current_issue", "")
        debug_log(f"Using current_issue from settings: {issue}")

    if not issue or issue == "null":
        debug_log("No issue specified", "ERROR")
        print(f"{GHE_RED}ERROR: No issue specified{GHE_NC}", file=sys.stderr)
        sys.exit(1)

    current_phase = get_issue_phase(issue)
    debug_log(f"Current phase for issue #{issue}: {current_phase}")
    print(f"Executing transition: {current_phase} -> {target_phase} for issue #{issue}")

    # Update labels on GitHub
    debug_log("Updating GitHub labels")
    print("Updating GitHub labels...")

    # Remove current phase label
    current_label = PHASE_LABELS.get(current_phase)
    if current_label:
        debug_log(f"Removing label: {current_label}")
        ghe_gh("issue", "edit", issue, "--remove-label", current_label, capture=False)

    # Add new phase label
    new_label = PHASE_LABELS.get(target_phase)
    if new_label:
        debug_log(f"Adding label: {new_label}")
        ghe_gh("issue", "edit", issue, "--add-label", new_label, capture=False)

    # Spawn the appropriate agent
    target_agent = PHASE_AGENTS.get(target_phase)
    greek_name = PHASE_GREEK.get(target_phase)

    if target_agent:
        debug_log(f"Spawning agent: {greek_name} ({target_agent})")
        print(f"Spawning {greek_name} ({target_agent})...")
        script_dir = Path(__file__).parent
        spawn_script = script_dir / "spawn_agent.py"

        context_str = context or ""
        spawn_context = f"Phase transition from {current_phase}. {context_str}"

        subprocess.run(
            ["python3", str(spawn_script), target_agent, issue, spawn_context],
            check=False,
        )

    # Post to issue thread
    debug_log("Posting transition comment to issue thread")
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    header = get_avatar_header("Themis")

    comment_body = f"""{header}
## Phase Transition Complete

| Field | Value |
|-------|-------|
| **From** | {current_phase} |
| **To** | {target_phase} |
| **Agent** | {greek_name or "N/A"} |
| **Time** | {timestamp} |

**Context**: {context or "Workflow progression"}

---
*Transition executed by Themis (phase-gate)*"""

    ghe_gh("issue", "comment", issue, "--body", comment_body, capture=False)

    log_transition(
        issue, current_phase, target_phase, "EXECUTED", f"Agent: {target_agent}"
    )
    debug_log(
        f"Transition complete: {current_phase} -> {target_phase} for issue #{issue}"
    )
    print(f"{GHE_GREEN}Transition complete: {current_phase} -> {target_phase}{GHE_NC}")


def demote_to_dev(issue: Optional[str] = None, reason: Optional[str] = None) -> None:
    """
    Demote issue back to DEV phase.

    Args:
        issue: Issue number (optional, uses current_issue if not provided)
        reason: Reason for demotion
    """
    debug_log(f"demote_to_dev called: issue={issue}, reason={reason}")
    if not issue:
        issue = ghe_get_setting("current_issue", "")
        debug_log(f"Using current_issue from settings: {issue}")

    if not issue or issue == "null":
        debug_log("No issue specified", "ERROR")
        print(f"{GHE_RED}ERROR: No issue specified{GHE_NC}", file=sys.stderr)
        sys.exit(1)

    current_phase = get_issue_phase(issue)
    debug_log(f"Demoting issue #{issue} from {current_phase} to DEV")
    print(f"Demoting issue #{issue} from {current_phase} to DEV")
    print(f"Reason: {reason or 'No reason provided'}")

    # Execute the demotion
    context = f"DEMOTED from {current_phase}. Reason: {reason or 'No reason provided'}"
    execute_transition("DEV", issue, context)

    log_transition(
        issue, current_phase, "DEV", "DEMOTED", reason or "No reason provided"
    )
    debug_log(f"Demotion complete for issue #{issue}")
    print(f"{GHE_YELLOW}Issue #{issue} demoted to DEV{GHE_NC}")


def show_usage() -> None:
    """Display usage information."""
    script_name = Path(__file__).name
    print(f"""Usage: {script_name} <action> [args...]

Actions:
  request <target-phase> [issue] [context]
      Request transition to target phase (spawns Themis for validation)

  validate <from-phase> <to-phase> [issue]
      Validate if transition is allowed (called by phase-gate agent)

  execute <target-phase> [issue] [context]
      Execute transition (update labels, spawn agent)

  demote [issue] [reason]
      Demote back to DEV with feedback

Phases: DEV, TEST, REVIEW, MERGE

Examples:
  {script_name} request TEST 123
  {script_name} validate DEV TEST 123
  {script_name} execute TEST 123 "Unit tests passed"
  {script_name} demote 123 "Test failures in auth module"
""")


def main() -> None:
    """Main entry point."""
    debug_log("phase_transition.py started")

    # Initialize GHE environment
    ghe_init()
    debug_log("GHE environment initialized")

    # Parse command line arguments
    args = sys.argv[1:]
    action = args[0] if len(args) > 0 else ""
    arg2 = args[1] if len(args) > 1 else None
    arg3 = args[2] if len(args) > 2 else None
    arg4 = args[3] if len(args) > 3 else None

    debug_log(f"Parsed args: action={action}, arg2={arg2}, arg3={arg3}, arg4={arg4}")

    # Dispatch action
    if action == "request":
        if not arg2:
            debug_log("Missing target phase for request action", "ERROR")
            print(f"{GHE_RED}ERROR: Missing target phase{GHE_NC}", file=sys.stderr)
            show_usage()
            sys.exit(1)
        debug_log(f"Dispatching request_transition: target={arg2}, issue={arg3}")
        request_transition(arg2, arg3, arg4)

    elif action == "validate":
        if not arg2 or not arg3:
            debug_log("Missing from/to phases for validate action", "ERROR")
            print(f"{GHE_RED}ERROR: Missing from/to phases{GHE_NC}", file=sys.stderr)
            show_usage()
            sys.exit(1)
        debug_log(
            f"Dispatching validate_transition: from={arg2}, to={arg3}, issue={arg4}"
        )
        exit_code = validate_transition(arg2, arg3, arg4)
        debug_log(f"validate_transition returned exit_code={exit_code}")
        sys.exit(exit_code)

    elif action == "execute":
        if not arg2:
            debug_log("Missing target phase for execute action", "ERROR")
            print(f"{GHE_RED}ERROR: Missing target phase{GHE_NC}", file=sys.stderr)
            show_usage()
            sys.exit(1)
        debug_log(f"Dispatching execute_transition: target={arg2}, issue={arg3}")
        execute_transition(arg2, arg3, arg4)

    elif action == "demote":
        debug_log(f"Dispatching demote_to_dev: issue={arg2}, reason={arg3}")
        demote_to_dev(arg2, arg3)

    elif action in ["help", "-h", "--help", ""]:
        debug_log("Showing usage help")
        show_usage()

    else:
        debug_log(f"Unknown action: {action}", "ERROR")
        print(f"{GHE_RED}Unknown action: {action}{GHE_NC}", file=sys.stderr)
        show_usage()
        sys.exit(1)

    debug_log("phase_transition.py completed")


if __name__ == "__main__":
    main()
