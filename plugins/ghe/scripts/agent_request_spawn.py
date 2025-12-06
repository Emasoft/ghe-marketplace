#!/usr/bin/env python3
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
from typing import Optional

# Import from local GHE library
from ghe_common import ghe_init, ghe_gh, GHE_REPO_ROOT
from post_with_avatar import avatar_header


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


def log_request(spawn_log: str, timestamp: str, target_name: str,
                target_agent: str, issue_num: str, context: str) -> None:
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
    with open(spawn_log, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] SPAWN REQUEST: {target_name} ({target_agent}) for #{issue_num}\n")
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
    # Parse arguments
    if len(sys.argv) < 3:
        print("ERROR: Usage: agent_request_spawn.py <target-agent> <issue-number> [context]",
              file=sys.stderr)
        return 1

    target_agent = sys.argv[1]
    issue_num = sys.argv[2]
    context = sys.argv[3] if len(sys.argv) > 3 else ""

    # Initialize GHE environment
    ghe_init()

    # Get repo root and setup paths
    project_root = GHE_REPO_ROOT
    if not project_root:
        print("ERROR: GHE_REPO_ROOT not set", file=sys.stderr)
        return 1

    # Internal log (hidden file, not a GHE report)
    ghe_reports_dir = Path(project_root) / "GHE_REPORTS"
    ghe_reports_dir.mkdir(exist_ok=True)
    spawn_log = str(ghe_reports_dir / ".spawn_requests.log")

    # Get timestamp
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Get target agent's display name
    target_name = AGENT_NAMES.get(target_agent, target_agent)

    # Log the spawn request
    log_request(spawn_log, timestamp, target_name, target_agent, issue_num, context)

    # Get path to spawn-agent script
    script_dir = Path(__file__).parent.resolve()
    spawn_agent_script = script_dir / "spawn_agent.py"

    # Check if target agent is the phase-gate itself (avoid infinite loop)
    if target_agent == "phase-gate":
        # Direct spawn without validation
        with open(spawn_log, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] Spawning phase-gate for validation...\n")

        result = subprocess.run(
            [sys.executable, str(spawn_agent_script), target_agent, issue_num, context],
            check=False
        )
        return result.returncode

    # Check if this transition needs phase-gate validation
    if needs_validation(target_agent):
        # First spawn phase-gate to validate, which will then spawn target if approved
        with open(spawn_log, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] Routing through phase-gate for validation...\n")

        result = subprocess.run(
            [sys.executable, str(spawn_agent_script), "phase-gate", issue_num,
             f"Validate spawn of {target_name}: {context}"],
            check=False
        )
        return result.returncode

    # Direct spawn for non-phase agents
    with open(spawn_log, 'a', encoding='utf-8') as f:
        f.write(f"[{timestamp}] Direct spawn of {target_name}...\n")

    result = subprocess.run(
        [sys.executable, str(spawn_agent_script), target_agent, issue_num, context],
        check=False
    )

    # Post to issue thread that agent was spawned
    if issue_num and issue_num != "null":
        try:
            # Get avatar header
            header = avatar_header("Athena")

            # Prepare comment body
            comment_body = f"""{header}
**Agent Spawned**

{target_name} has been spawned to continue work on this issue.

- **Agent**: {target_agent}
- **Context**: {context if context else 'Workflow continuation'}
- **Time**: {timestamp}

---
*Spawned by GHE orchestration system*"""

            # Post notification (non-blocking, ignore errors)
            subprocess.Popen(
                ["gh", "issue", "comment", issue_num, "--body", comment_body],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                cwd=project_root
            )
        except Exception:
            # Silently ignore posting errors
            pass

    print(f"Spawn request processed: {target_name} for #{issue_num}")
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
