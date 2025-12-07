#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
agent_request_spawn.py - Request spawning another GHE agent

This script allows agents to spawn other agents, creating the
inter-agent communication mechanism for GHE workflow automation.

When an agent completes its work and needs to trigger the next phase,
it calls this script to spawn the appropriate agent.

Usage:
    agent_request_spawn.py <target-agent> <issue-number> [context-message]

Examples:
    # DEV agent requesting transition to TEST
    agent_request_spawn.py test-thread-manager 123 "DEV complete, ready for testing"

    # TEST agent passing to REVIEW after tests pass
    agent_request_spawn.py review-thread-manager 123 "All tests passed"

    # REVIEW agent demoting back to DEV
    agent_request_spawn.py dev-thread-manager 123 "Review failed: missing error handling"

    # Any agent requesting transition validation
    agent_request_spawn.py phase-gate 123 "DEV->TEST"

This script:
1. Validates the spawn request
2. Logs the request for audit trail
3. Optionally validates transition via phase-gate
4. Spawns the target agent via spawn_agent.py
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Import from local GHE library
from ghe_common import ghe_init, GHE_REPO_ROOT
from post_with_avatar import avatar_header


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to .claude/hook_debug.log in standard log format."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [agent_request_spawn] - {message}\n")
    except Exception:
        pass


# Agent Greek names for logging
AGENT_NAMES = {
    "dev-thread-manager": "Hephaestus",
    "test-thread-manager": "Artemis",
    "review-thread-manager": "Hera",
    "phase-gate": "Themis",
    "memory-sync": "Mnemosyne",
    "reporter": "Hermes",
    "enforcement": "Ares",
    "ci-issue-opener": "Chronos",
    "pr-checker": "Cerberus",
    "github-elements-orchestrator": "Athena",
}


def log_request(
    spawn_log: str,
    timestamp: str,
    target_name: str,
    target_agent: str,
    issue_num: str,
    context: str,
) -> None:
    """
    Log the spawn request to the audit trail.

    Args:
        spawn_log: Path to the spawn log file
        timestamp: Current timestamp string
        target_name: Human-readable agent name
        target_agent: Technical agent identifier
        issue_num: Issue number
        context: Context message
    """
    with open(spawn_log, "a", encoding="utf-8") as f:
        f.write(
            f"[{timestamp}] SPAWN REQUEST: {target_name} ({target_agent}) for #{issue_num}\n"
        )
        f.write(f"  Context: {context if context else 'none'}\n")
        f.write(f"  Caller: {os.getpid()}\n")


def needs_validation(target_agent: str) -> bool:
    """
    Determine if this spawn needs phase-gate validation.

    Phase transitions that require validation:
    - DEV -> TEST (test-thread-manager)
    - TEST -> REVIEW (review-thread-manager)

    Args:
        target_agent: Target agent identifier

    Returns:
        True if validation is needed, False otherwise
    """
    # Validate all phase-to-phase transitions
    if target_agent in ["test-thread-manager", "review-thread-manager"]:
        return True
    return False


def main() -> int:
    """
    Main entry point for agent spawn requests.

    Returns:
        Exit code (0 for success, non-zero for error)
    """
    debug_log("main() called")
    # Parse arguments
    if len(sys.argv) < 3:
        debug_log("Insufficient arguments provided", "ERROR")
        print(
            "ERROR: Usage: agent_request_spawn.py <target-agent> <issue-number> [context]",
            file=sys.stderr,
        )
        return 1

    target_agent = sys.argv[1]
    issue_num = sys.argv[2]
    context = sys.argv[3] if len(sys.argv) > 3 else ""
    debug_log(
        f"Parsed args: target_agent={target_agent}, issue_num={issue_num}, context={context!r}"
    )

    # Initialize GHE environment
    ghe_init()
    debug_log("GHE environment initialized")

    # Get repo root and setup paths
    project_root = GHE_REPO_ROOT
    if not project_root:
        debug_log("GHE_REPO_ROOT not set", "ERROR")
        print("ERROR: GHE_REPO_ROOT not set", file=sys.stderr)
        return 1
    debug_log(f"Project root: {project_root}")

    # Internal log (hidden file, not a GHE report)
    ghe_reports_dir = Path(project_root) / "GHE_REPORTS"
    ghe_reports_dir.mkdir(exist_ok=True)
    spawn_log = str(ghe_reports_dir / ".spawn_requests.log")

    # Get timestamp
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Get target agent's display name
    target_name = AGENT_NAMES.get(target_agent, target_agent)

    # Log the spawn request
    debug_log(
        f"Logging spawn request for {target_name} ({target_agent}) on issue #{issue_num}"
    )
    log_request(spawn_log, timestamp, target_name, target_agent, issue_num, context)

    # Get path to spawn-agent script
    script_dir = Path(__file__).parent.resolve()
    spawn_agent_script = script_dir / "spawn_agent.py"

    # Check if target agent is the phase-gate itself (avoid infinite loop)
    if target_agent == "phase-gate":
        debug_log("Target is phase-gate, spawning directly without validation")
        # Direct spawn without validation
        with open(spawn_log, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] Spawning phase-gate for validation...\n")

        result = subprocess.run(
            [sys.executable, str(spawn_agent_script), target_agent, issue_num, context],
            check=False,
        )
        debug_log(f"Phase-gate spawn completed with returncode={result.returncode}")
        return result.returncode

    # Check if this transition needs phase-gate validation
    if needs_validation(target_agent):
        debug_log(f"Transition to {target_agent} requires phase-gate validation")
        # First spawn phase-gate to validate, which will then spawn target if approved
        with open(spawn_log, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] Routing through phase-gate for validation...\n")

        result = subprocess.run(
            [
                sys.executable,
                str(spawn_agent_script),
                "phase-gate",
                issue_num,
                f"Validate spawn of {target_name}: {context}",
            ],
            check=False,
        )
        debug_log(
            f"Phase-gate validation spawn completed with returncode={result.returncode}"
        )
        return result.returncode

    # Direct spawn for non-phase agents
    debug_log(f"Direct spawn of {target_name} (no validation needed)")
    with open(spawn_log, "a", encoding="utf-8") as f:
        f.write(f"[{timestamp}] Direct spawn of {target_name}...\n")

    result = subprocess.run(
        [sys.executable, str(spawn_agent_script), target_agent, issue_num, context],
        check=False,
    )
    debug_log(f"Direct spawn completed with returncode={result.returncode}")

    # Post to issue thread that agent was spawned
    if issue_num and issue_num != "null":
        debug_log(f"Posting spawn notification to issue #{issue_num}")
        try:
            # Get avatar header
            header = avatar_header("Athena")

            # Prepare comment body
            comment_body = f"""{header}
**Agent Spawned**

{target_name} has been spawned to continue work on this issue.

- **Agent**: {target_agent}
- **Context**: {context if context else "Workflow continuation"}
- **Time**: {timestamp}

---
*Spawned by GHE orchestration system*"""

            # Post notification (non-blocking, ignore errors)
            subprocess.Popen(
                ["gh", "issue", "comment", issue_num, "--body", comment_body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=project_root,
            )
        except Exception as e:
            # Silently ignore posting errors
            debug_log(f"Failed to post spawn notification: {e}", "WARNING")
            pass

    debug_log(f"Spawn request processed successfully: {target_name} for #{issue_num}")
    print(f"Spawn request processed: {target_name} for #{issue_num}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
