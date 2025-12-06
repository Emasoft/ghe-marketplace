#!/bin/bash
# spawn-agent.sh - Spawn a GHE agent in a background Terminal
#
# This script is the orchestration layer that allows:
# 1. Hooks to spawn agents automatically
# 2. Agents to spawn other agents (via agent-request-spawn.sh)
# 3. Workflow automation with context passing
#
# Usage:
#   spawn-agent.sh <agent-name> <issue-number> [additional-context]
#
# Example:
#   spawn-agent.sh dev-thread-manager 123 "Feature: Add dark mode"
#   spawn-agent.sh test-thread-manager 123
#   spawn-agent.sh review-thread-manager 123
#
# Environment:
#   CLAUDE_PLUGIN_ROOT - Set by Claude Code to plugin directory
#   GHE_CONFIG_PATH - Override config path (default: .claude/ghe.local.md)

set -e

# Arguments
AGENT_NAME="${1:-}"
ISSUE_NUM="${2:-}"
CONTEXT="${3:-}"

# Validate required arguments
if [[ -z "$AGENT_NAME" ]]; then
    echo "ERROR: Agent name required"
    echo "Usage: spawn-agent.sh <agent-name> <issue-number> [context]"
    echo ""
    echo "Available agents:"
    echo "  dev-thread-manager     - Hephaestus (DEV phase)"
    echo "  test-thread-manager    - Artemis (TEST phase)"
    echo "  review-thread-manager  - Hera (REVIEW phase)"
    echo "  phase-gate             - Themis (transition validation)"
    echo "  memory-sync            - Mnemosyne (SERENA sync)"
    echo "  reporter               - Hermes (status reports)"
    echo "  enforcement            - Ares (violation detection)"
    echo "  ci-issue-opener        - Chronos (CI failure handling)"
    echo "  pr-checker             - Cerberus (PR validation)"
    echo "  github-elements-orchestrator - Athena (orchestration)"
    exit 1
fi

# Determine working directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$SCRIPT_DIR")}"

# Source shared library
source "${SCRIPT_DIR}/lib/ghe-common.sh"

# Initialize GHE environment
ghe_init

# Use library-provided values
PROJECT_ROOT="${GHE_REPO_ROOT}"
CONFIG_PATH="${GHE_CONFIG_FILE}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Agent metadata - maps agent names to their Greek identities and roles
declare -A AGENT_GREEK_NAME=(
    ["dev-thread-manager"]="Hephaestus"
    ["test-thread-manager"]="Artemis"
    ["review-thread-manager"]="Hera"
    ["phase-gate"]="Themis"
    ["memory-sync"]="Mnemosyne"
    ["reporter"]="Hermes"
    ["enforcement"]="Ares"
    ["ci-issue-opener"]="Chronos"
    ["pr-checker"]="Cerberus"
    ["github-elements-orchestrator"]="Athena"
)

declare -A AGENT_PHASE=(
    ["dev-thread-manager"]="DEV"
    ["test-thread-manager"]="TEST"
    ["review-thread-manager"]="REVIEW"
    ["phase-gate"]="TRANSITION"
    ["memory-sync"]="SYNC"
    ["reporter"]="REPORT"
    ["enforcement"]="AUDIT"
    ["ci-issue-opener"]="CI"
    ["pr-checker"]="PR"
    ["github-elements-orchestrator"]="ORCHESTRATE"
)

# Validate agent name
GREEK_NAME="${AGENT_GREEK_NAME[$AGENT_NAME]:-}"
if [[ -z "$GREEK_NAME" ]]; then
    echo "ERROR: Unknown agent: $AGENT_NAME"
    echo "Run without arguments to see available agents"
    exit 1
fi

PHASE="${AGENT_PHASE[$AGENT_NAME]}"

# Get config values using shared library
REPO_REMOTE=$(ghe_get_setting "repo_remote" "")
REPO_OWNER=$(ghe_get_setting "repo_owner" "")
CURRENT_ISSUE=$(ghe_get_setting "current_issue" "")
CURRENT_PHASE=$(ghe_get_setting "current_phase" "")

# Use provided issue number or current issue
ISSUE_NUM="${ISSUE_NUM:-$CURRENT_ISSUE}"

# Create reports directory
mkdir -p "$PROJECT_ROOT/agents_reports"

# Build agent-specific prompt based on agent type
build_agent_prompt() {
    local agent="$1"
    local issue="$2"
    local ctx="$3"

    # Base context
    local prompt="You are $GREEK_NAME, the GHE ${PHASE} agent.

## Current Context
- **Issue**: #${issue:-NONE}
- **Phase**: ${CURRENT_PHASE:-UNKNOWN}
- **Project**: $PROJECT_ROOT
- **Config**: $CONFIG_PATH
"

    # Add agent-specific instructions
    case "$agent" in
        "dev-thread-manager")
            prompt+="
## Your Task
You have been spawned to manage DEV work on issue #$issue.

1. First, claim the issue:
   \`\`\`bash
   gh issue edit $issue --add-assignee @me --add-label 'phase:dev,in-progress'
   \`\`\`

2. Create a worktree for isolated development:
   \`\`\`bash
   git worktree add ../worktrees/issue-$issue -b issue-$issue-dev
   \`\`\`

3. Read the issue description:
   \`\`\`bash
   gh issue view $issue
   \`\`\`

4. Begin implementation work. Post checkpoints to the issue thread.

5. When DEV is complete, request transition to TEST by calling:
   \`\`\`bash
   bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" phase-gate $issue \"DEV->TEST\"
   \`\`\`

## Context
$ctx

## Output
Save your final report to: agents_reports/dev_${issue}_${TIMESTAMP}.md
"
            ;;

        "test-thread-manager")
            prompt+="
## Your Task
You have been spawned to manage TEST phase for issue #$issue.

1. Update labels:
   \`\`\`bash
   gh issue edit $issue --remove-label 'phase:dev' --add-label 'phase:test'
   \`\`\`

2. Navigate to worktree:
   \`\`\`bash
   cd ../worktrees/issue-$issue
   \`\`\`

3. Run all tests:
   \`\`\`bash
   # Detect test framework and run
   if [[ -f pytest.ini ]] || [[ -f pyproject.toml ]]; then
       uv run pytest -v
   elif [[ -f package.json ]]; then
       npm test
   fi
   \`\`\`

4. If tests pass, request transition to REVIEW:
   \`\`\`bash
   bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" review-thread-manager $issue \"Tests passed\"
   \`\`\`

5. If tests fail, post findings and spawn dev-thread-manager to fix:
   \`\`\`bash
   bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" dev-thread-manager $issue \"Test failures: <summary>\"
   \`\`\`

## Context
$ctx

## Output
Save test results to: agents_reports/test_${issue}_${TIMESTAMP}.md
"
            ;;

        "review-thread-manager")
            prompt+="
## Your Task
You have been spawned to conduct REVIEW for issue #$issue.

1. Update labels:
   \`\`\`bash
   gh issue edit $issue --remove-label 'phase:test' --add-label 'phase:review'
   \`\`\`

2. Review the changes:
   - Code quality
   - Test coverage
   - Documentation
   - Security concerns

3. Post your verdict to the issue thread.

4. If PASS:
   \`\`\`bash
   gh issue edit $issue --add-label 'completed'
   # Create PR if not exists
   gh pr create --fill --head issue-$issue-dev
   \`\`\`

5. If FAIL, demote back to DEV with specific feedback:
   \`\`\`bash
   bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" dev-thread-manager $issue \"Review feedback: <issues>\"
   \`\`\`

## Context
$ctx

## Output
Save review report to: agents_reports/review_${issue}_${TIMESTAMP}.md
"
            ;;

        "phase-gate")
            prompt+="
## Your Task
Validate phase transition request for issue #$issue.

Requested transition: $ctx

1. Check current phase labels on the issue
2. Verify transition is valid (DEV->TEST->REVIEW only, no skipping)
3. Verify criteria are met:
   - DEV->TEST: Code changes exist, basic functionality works
   - TEST->REVIEW: All tests pass
   - REVIEW->MERGE: Review passed

4. If valid, spawn the target phase agent:
   \`\`\`bash
   bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" <target-agent> $issue \"Transition approved\"
   \`\`\`

5. If invalid, post violation warning and notify Ares:
   \`\`\`bash
   bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" enforcement $issue \"Invalid transition: $ctx\"
   \`\`\`

## Output
Save validation report to: agents_reports/transition_${issue}_${TIMESTAMP}.md
"
            ;;

        "memory-sync")
            prompt+="
## Your Task
Synchronize GitHub issue #$issue with SERENA memory bank.

1. Read issue content and comments:
   \`\`\`bash
   gh issue view $issue --comments
   \`\`\`

2. Extract key information (KNOWLEDGE, ACTION, JUDGEMENT elements)

3. Write to SERENA memory:
   - Use mcp__serena__write_memory for new memories
   - Use mcp__serena__edit_memory to update existing

4. Update activeContext.md with current issue state

## Context
$ctx

## Output
Save sync report to: agents_reports/sync_${issue}_${TIMESTAMP}.md
"
            ;;

        "reporter")
            prompt+="
## Your Task
Generate status report for issue #$issue.

1. Gather current state:
   \`\`\`bash
   gh issue view $issue --json state,labels,assignees,comments
   \`\`\`

2. Check worktree status if exists:
   \`\`\`bash
   git -C ../worktrees/issue-$issue status 2>/dev/null || echo 'No worktree'
   \`\`\`

3. Generate comprehensive status report

4. Post summary to issue thread

## Context
$ctx

## Output
Save report to: agents_reports/status_${issue}_${TIMESTAMP}.md
"
            ;;

        "enforcement")
            prompt+="
## Your Task
Investigate potential violation for issue #$issue.

Violation context: $ctx

1. Check issue labels and state:
   \`\`\`bash
   gh issue view $issue --json labels,state,comments
   \`\`\`

2. Determine violation type:
   - Phase skip (DEV->REVIEW without TEST)
   - Multiple threads open
   - Scope violation (wrong work in wrong phase)

3. Check violation history

4. Post warning or block based on progressive enforcement policy

## Output
Save enforcement report to: agents_reports/enforcement_${issue}_${TIMESTAMP}.md
"
            ;;

        "ci-issue-opener")
            prompt+="
## Your Task
Handle CI failure for issue #$issue.

CI context: $ctx

1. Parse CI failure details
2. Create or update issue with failure information
3. Add appropriate labels (ci-failure, source:ci)
4. Link to failing workflow run

## Output
Save CI report to: agents_reports/ci_${issue}_${TIMESTAMP}.md
"
            ;;

        "pr-checker")
            prompt+="
## Your Task
Validate PR requirements for issue #$issue.

1. Find linked PR:
   \`\`\`bash
   gh pr list --search '$issue in:body' --json number,title,state
   \`\`\`

2. Check PR requirements:
   - Has linked issue
   - Passed CI checks
   - Has required reviews
   - Proper phase labels

3. Post validation results to PR

## Context
$ctx

## Output
Save PR check report to: agents_reports/pr_${issue}_${TIMESTAMP}.md
"
            ;;

        "github-elements-orchestrator")
            prompt+="
## Your Task
Orchestrate GHE workflow for issue #$issue.

You are Athena, the master orchestrator. Your role is to:

1. Assess current state of issue #$issue
2. Determine which agents need to be spawned
3. Coordinate the workflow

Available agent commands:
\`\`\`bash
# Spawn DEV agent
bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" dev-thread-manager $issue \"context\"

# Spawn TEST agent
bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" test-thread-manager $issue \"context\"

# Spawn REVIEW agent
bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" review-thread-manager $issue \"context\"
\`\`\`

## Context
$ctx

## Output
Save orchestration report to: agents_reports/orchestrate_${issue}_${TIMESTAMP}.md
"
            ;;

        *)
            prompt+="
## Your Task
Execute agent-specific work for issue #$issue.

## Context
$ctx

## Output
Save report to: agents_reports/${agent}_${issue}_${TIMESTAMP}.md
"
            ;;
    esac

    echo "$prompt"
}

# Build the prompt
FULL_PROMPT=$(build_agent_prompt "$AGENT_NAME" "$ISSUE_NUM" "$CONTEXT")

# Log spawn event
LOG_FILE="$PROJECT_ROOT/agents_reports/spawn_log.txt"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Spawning $GREEK_NAME ($AGENT_NAME) for issue #$ISSUE_NUM" >> "$LOG_FILE"

# Spawn using background script
if [[ -x "$PLUGIN_ROOT/scripts/spawn_background.sh" ]]; then
    bash "$PLUGIN_ROOT/scripts/spawn_background.sh" "$FULL_PROMPT" "$PROJECT_ROOT"
    echo "Spawned $GREEK_NAME ($AGENT_NAME) for issue #$ISSUE_NUM"
else
    echo "ERROR: spawn_background.sh not found or not executable at $PLUGIN_ROOT/scripts/"
    exit 1
fi
