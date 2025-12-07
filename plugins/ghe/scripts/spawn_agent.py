#!/usr/bin/env python3
"""spawn_agent.py - Spawn a GHE agent in a background Terminal

This script is the orchestration layer that allows:
1. Hooks to spawn agents automatically
2. Agents to spawn other agents (via agent_request_spawn.py)
3. Workflow automation with context passing

Usage:
    spawn_agent.py <agent-name> <issue-number> [additional-context]

Example:
    spawn_agent.py dev-thread-manager 123 "Feature: Add dark mode"
    spawn_agent.py test-thread-manager 123
    spawn_agent.py review-thread-manager 123

Environment:
    CLAUDE_PLUGIN_ROOT - Set by Claude Code to plugin directory
    GHE_CONFIG_PATH - Override config path (default: .claude/ghe.local.md)
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Import from ghe_common
from ghe_common import ghe_init, ghe_get_setting, ghe_get_repo_path, GHE_PLUGIN_ROOT


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [spawn_agent] - {message}\n")
    except Exception:
        pass


# Agent metadata - maps agent names to their Greek identities and roles
AGENT_GREEK_NAME = {
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

AGENT_PHASE = {
    "dev-thread-manager": "DEV",
    "test-thread-manager": "TEST",
    "review-thread-manager": "REVIEW",
    "phase-gate": "TRANSITION",
    "memory-sync": "SYNC",
    "reporter": "REPORT",
    "enforcement": "AUDIT",
    "ci-issue-opener": "CI",
    "pr-checker": "PR",
    "github-elements-orchestrator": "ORCHESTRATE",
}


def show_usage() -> None:
    """Display usage information with all available agents."""
    debug_log("show_usage() called - no agent name provided", "WARN")
    print("ERROR: Agent name required")
    print("Usage: spawn_agent.py <agent-name> <issue-number> [context]")
    print()
    print("Available agents:")
    print("  dev-thread-manager     - Hephaestus (DEV phase)")
    print("  test-thread-manager    - Artemis (TEST phase)")
    print("  review-thread-manager  - Hera (REVIEW phase)")
    print("  phase-gate             - Themis (transition validation)")
    print("  memory-sync            - Mnemosyne (SERENA sync)")
    print("  reporter               - Hermes (status reports)")
    print("  enforcement            - Ares (violation detection)")
    print("  ci-issue-opener        - Chronos (CI failure handling)")
    print("  pr-checker             - Cerberus (PR validation)")
    print("  github-elements-orchestrator - Athena (orchestration)")


def build_agent_prompt(
    agent_name: str,
    issue_num: str,
    context: str,
    greek_name: str,
    phase: str,
    current_phase: str,
    project_root: str,
    config_path: str,
    plugin_root: str,
    timestamp: str,
) -> str:
    """Build agent-specific prompt based on agent type.

    Args:
        agent_name: Name of the agent (e.g., "dev-thread-manager")
        issue_num: GitHub issue number
        context: Additional context string
        greek_name: Greek god name for the agent
        phase: Agent's phase
        current_phase: Current project phase
        project_root: Project root directory
        config_path: GHE config file path
        plugin_root: Plugin root directory
        timestamp: Brisbane timezone timestamp string

    Returns:
        Complete prompt string for the agent
    """
    debug_log(
        f"build_agent_prompt() called for {greek_name} ({agent_name}), issue #{issue_num}"
    )
    # Base context
    prompt = f"""You are {greek_name}, the GHE {phase} agent.

## Current Context
- **Issue**: #{issue_num or "NONE"}
- **Phase**: {current_phase or "UNKNOWN"}
- **Project**: {project_root}
- **Config**: {config_path}
"""

    # Add agent-specific instructions
    if agent_name == "dev-thread-manager":
        prompt += f"""
## Your Task
You have been spawned to manage DEV work on issue #{issue_num}.

1. First, claim the issue:
   ```bash
   gh issue edit {issue_num} --add-assignee @me --add-label 'phase:dev,in-progress'
   ```

2. Create a worktree for isolated development:
   ```bash
   git worktree add ../worktrees/issue-{issue_num} -b issue-{issue_num}-dev
   ```

3. Read the issue description:
   ```bash
   gh issue view {issue_num}
   ```

4. Begin implementation work. Post checkpoints to the issue thread.

5. When DEV is complete, request transition to TEST by calling:
   ```bash
   bash "{plugin_root}/scripts/agent_request_spawn.py" phase-gate {issue_num} "DEV->TEST"
   ```

## Context
{context}

## Output
Save your final report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_dev_complete_(Hephaestus).md
"""

    elif agent_name == "test-thread-manager":
        prompt += f"""
## Your Task
You have been spawned to manage TEST phase for issue #{issue_num}.

1. Update labels:
   ```bash
   gh issue edit {issue_num} --remove-label 'phase:dev' --add-label 'phase:test'
   ```

2. Navigate to worktree:
   ```bash
   cd ../worktrees/issue-{issue_num}
   ```

3. Run all tests:
   ```bash
   # Detect test framework and run
   if [[ -f pytest.ini ]] || [[ -f pyproject.toml ]]; then
       uv run pytest -v
   elif [[ -f package.json ]]; then
       npm test
   fi
   ```

4. If tests pass, request transition to REVIEW:
   ```bash
   bash "{plugin_root}/scripts/agent_request_spawn.py" review-thread-manager {issue_num} "Tests passed"
   ```

5. If tests fail, post findings and spawn dev-thread-manager to fix:
   ```bash
   bash "{plugin_root}/scripts/agent_request_spawn.py" dev-thread-manager {issue_num} "Test failures: <summary>"
   ```

## Context
{context}

## Output
Save test results to: GHE_REPORTS/{timestamp}_issue_{issue_num}_tests_complete_(Artemis).md
"""

    elif agent_name == "review-thread-manager":
        prompt += f"""
## Your Task
You have been spawned to conduct REVIEW for issue #{issue_num}.

1. Update labels:
   ```bash
   gh issue edit {issue_num} --remove-label 'phase:test' --add-label 'phase:review'
   ```

2. Review the changes:
   - Code quality
   - Test coverage
   - Documentation
   - Security concerns

3. Post your verdict to the issue thread.

4. If PASS:
   ```bash
   gh issue edit {issue_num} --add-label 'completed'
   # Create PR if not exists
   gh pr create --fill --head issue-{issue_num}-dev
   ```

5. If FAIL, demote back to DEV with specific feedback:
   ```bash
   bash "{plugin_root}/scripts/agent_request_spawn.py" dev-thread-manager {issue_num} "Review feedback: <issues>"
   ```

## Context
{context}

## Output
Save review report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_review_complete_(Hera).md
"""

    elif agent_name == "phase-gate":
        prompt += f"""
## Your Task
Validate phase transition request for issue #{issue_num}.

Requested transition: {context}

1. Check current phase labels on the issue
2. Verify transition is valid (DEV->TEST->REVIEW only, no skipping)
3. Verify criteria are met:
   - DEV->TEST: Code changes exist, basic functionality works
   - TEST->REVIEW: All tests pass
   - REVIEW->MERGE: Review passed

4. If valid, spawn the target phase agent:
   ```bash
   bash "{plugin_root}/scripts/agent_request_spawn.py" <target-agent> {issue_num} "Transition approved"
   ```

5. If invalid, post violation warning and notify Ares:
   ```bash
   bash "{plugin_root}/scripts/agent_request_spawn.py" enforcement {issue_num} "Invalid transition: {context}"
   ```

## Output
Save validation report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_transition_(Themis).md
"""

    elif agent_name == "memory-sync":
        prompt += f"""
## Your Task
Synchronize GitHub issue #{issue_num} with SERENA memory bank.

1. Read issue content and comments:
   ```bash
   gh issue view {issue_num} --comments
   ```

2. Extract key information (KNOWLEDGE, ACTION, JUDGEMENT elements)

3. Write to SERENA memory:
   - Use mcp__serena__write_memory for new memories
   - Use mcp__serena__edit_memory to update existing

4. Update activeContext.md with current issue state

## Context
{context}

## Output
Save sync report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_memory_sync_(Mnemosyne).md
"""

    elif agent_name == "reporter":
        prompt += f"""
## Your Task
Generate status report for issue #{issue_num}.

1. Gather current state:
   ```bash
   gh issue view {issue_num} --json state,labels,assignees,comments
   ```

2. Check worktree status if exists:
   ```bash
   git -C ../worktrees/issue-{issue_num} status 2>/dev/null || echo 'No worktree'
   ```

3. Generate comprehensive status report

4. Post summary to issue thread

## Context
{context}

## Output
Save report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_status_report_(Hermes).md
"""

    elif agent_name == "enforcement":
        prompt += f"""
## Your Task
Investigate potential violation for issue #{issue_num}.

Violation context: {context}

1. Check issue labels and state:
   ```bash
   gh issue view {issue_num} --json labels,state,comments
   ```

2. Determine violation type:
   - Phase skip (DEV->REVIEW without TEST)
   - Multiple threads open
   - Scope violation (wrong work in wrong phase)

3. Check violation history

4. Post warning or block based on progressive enforcement policy

## Output
Save enforcement report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_enforcement_(Ares).md
"""

    elif agent_name == "ci-issue-opener":
        prompt += f"""
## Your Task
Handle CI failure for issue #{issue_num}.

CI context: {context}

1. Parse CI failure details
2. Create or update issue with failure information
3. Add appropriate labels (ci-failure, source:ci)
4. Link to failing workflow run

## Output
Save CI report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_ci_failure_(Chronos).md
"""

    elif agent_name == "pr-checker":
        prompt += f"""
## Your Task
Validate PR requirements for issue #{issue_num}.

1. Find linked PR:
   ```bash
   gh pr list --search '{issue_num} in:body' --json number,title,state
   ```

2. Check PR requirements:
   - Has linked issue
   - Passed CI checks
   - Has required reviews
   - Proper phase labels

3. Post validation results to PR

## Context
{context}

## Output
Save PR check report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_pr_check_(Cerberus).md
"""

    elif agent_name == "github-elements-orchestrator":
        prompt += f"""
## Your Task
Orchestrate GHE workflow for issue #{issue_num}.

You are Athena, the master orchestrator. Your role is to:

1. Assess current state of issue #{issue_num}
2. Determine which agents need to be spawned
3. Coordinate the workflow

Available agent commands:
```bash
# Spawn DEV agent
bash "{plugin_root}/scripts/agent_request_spawn.py" dev-thread-manager {issue_num} "context"

# Spawn TEST agent
bash "{plugin_root}/scripts/agent_request_spawn.py" test-thread-manager {issue_num} "context"

# Spawn REVIEW agent
bash "{plugin_root}/scripts/agent_request_spawn.py" review-thread-manager {issue_num} "context"
```

## Context
{context}

## Output
Save orchestration report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_orchestration_(Athena).md
"""

    else:
        prompt += f"""
## Your Task
Execute agent-specific work for issue #{issue_num}.

## Context
{context}

## Output
Save report to: GHE_REPORTS/{timestamp}_issue_{issue_num}_{agent_name}_({greek_name}).md
"""

    return prompt


def main() -> None:
    """Main entry point for spawn_agent.py"""
    debug_log("main() entry")
    debug_log(f"sys.argv={sys.argv}")
    # Parse arguments
    if len(sys.argv) < 2:
        show_usage()
        sys.exit(1)

    agent_name = sys.argv[1]
    issue_num = sys.argv[2] if len(sys.argv) > 2 else ""
    context = sys.argv[3] if len(sys.argv) > 3 else ""
    debug_log(
        f"Parsed args: agent_name={agent_name}, issue_num={issue_num}, context={context[:50] if context else ''}"
    )

    # Validate agent name
    greek_name = AGENT_GREEK_NAME.get(agent_name)
    if not greek_name:
        debug_log(f"Unknown agent: {agent_name}", "ERROR")
        print(f"ERROR: Unknown agent: {agent_name}")
        print("Run without arguments to see available agents")
        sys.exit(1)

    phase = AGENT_PHASE[agent_name]
    debug_log(f"Agent validated: {greek_name} ({agent_name}), phase={phase}")

    # Initialize GHE environment
    debug_log("Calling ghe_init()")
    ghe_init()

    # Get config values
    project_root = ghe_get_repo_path()
    config_path = ghe_get_setting("_config_file", "")
    repo_remote = ghe_get_setting("repo_remote", "")
    repo_owner = ghe_get_setting("repo_owner", "")
    current_issue = ghe_get_setting("current_issue", "")
    current_phase = ghe_get_setting("current_phase", "")
    debug_log(f"Config loaded: project_root={project_root}, config_path={config_path}")
    debug_log(f"Repo info: repo_remote={repo_remote}, repo_owner={repo_owner}")
    debug_log(
        f"Issue info: current_issue={current_issue}, current_phase={current_phase}"
    )

    # Use provided issue number or current issue
    if not issue_num:
        debug_log(f"No issue_num provided, using current_issue={current_issue}")
        issue_num = current_issue

    # Create GHE_REPORTS directory (FLAT structure - no subfolders!)
    reports_dir = Path(project_root) / "GHE_REPORTS"
    reports_dir.mkdir(exist_ok=True)
    debug_log(f"Reports directory: {reports_dir}")

    # Generate timestamp in Brisbane timezone (YYYYMMDDHHMMSSTimezone)
    brisbane_tz = ZoneInfo("Australia/Brisbane")
    now = datetime.now(brisbane_tz)
    timestamp = now.strftime("%Y%m%d%H%M%S%Z")
    debug_log(f"Generated timestamp: {timestamp}")

    # Build the prompt
    debug_log("Building agent prompt")
    full_prompt = build_agent_prompt(
        agent_name=agent_name,
        issue_num=issue_num,
        context=context,
        greek_name=greek_name,
        phase=phase,
        current_phase=current_phase,
        project_root=project_root,
        config_path=config_path,
        plugin_root=GHE_PLUGIN_ROOT,
        timestamp=timestamp,
    )

    # Log spawn event (internal log, not a GHE report)
    log_file = reports_dir / ".spawn_log.txt"
    log_timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, "a") as f:
        f.write(
            f"[{log_timestamp}] Spawning {greek_name} ({agent_name}) for issue #{issue_num}\n"
        )
    debug_log(f"Wrote to spawn log: {log_file}")

    # Spawn using background script
    spawn_script = Path(GHE_PLUGIN_ROOT) / "scripts" / "spawn_background.py"
    debug_log(f"Spawn script path: {spawn_script}")
    if not spawn_script.exists():
        debug_log(f"spawn_background.py not found at {spawn_script}", "ERROR")
        print(f"ERROR: spawn_background.py not found at {spawn_script}")
        sys.exit(1)

    if not spawn_script.stat().st_mode & 0o111:
        debug_log(f"spawn_background.py not executable at {spawn_script}", "ERROR")
        print(f"ERROR: spawn_background.py not executable at {spawn_script}")
        sys.exit(1)

    # Execute spawn_background.py using sys.executable for portability
    debug_log(f"Executing: {sys.executable} {spawn_script} <prompt> {project_root}")
    try:
        subprocess.run(
            [sys.executable, str(spawn_script), full_prompt, project_root], check=True
        )
        debug_log(
            f"Successfully spawned {greek_name} ({agent_name}) for issue #{issue_num}"
        )
        print(f"Spawned {greek_name} ({agent_name}) for issue #{issue_num}")
    except subprocess.CalledProcessError as e:
        debug_log(f"Failed to spawn agent: {e}", "ERROR")
        print(f"ERROR: Failed to spawn agent: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
