#!/bin/bash
# agent-request-spawn.sh - Request spawning another GHE agent
#
# This script allows agents to spawn other agents, creating the
# inter-agent communication mechanism for GHE workflow automation.
#
# When an agent completes its work and needs to trigger the next phase,
# it calls this script to spawn the appropriate agent.
#
# Usage:
#   agent-request-spawn.sh <target-agent> <issue-number> [context-message]
#
# Examples:
#   # DEV agent requesting transition to TEST
#   agent-request-spawn.sh test-thread-manager 123 "DEV complete, ready for testing"
#
#   # TEST agent passing to REVIEW after tests pass
#   agent-request-spawn.sh review-thread-manager 123 "All tests passed"
#
#   # REVIEW agent demoting back to DEV
#   agent-request-spawn.sh dev-thread-manager 123 "Review failed: missing error handling"
#
#   # Any agent requesting transition validation
#   agent-request-spawn.sh phase-gate 123 "DEV->TEST"
#
# This script:
# 1. Validates the spawn request
# 2. Logs the request for audit trail
# 3. Optionally validates transition via phase-gate
# 4. Spawns the target agent via spawn-agent.sh

set -e

TARGET_AGENT="${1:-}"
ISSUE_NUM="${2:-}"
CONTEXT="${3:-}"

if [[ -z "$TARGET_AGENT" ]] || [[ -z "$ISSUE_NUM" ]]; then
    echo "ERROR: Usage: agent-request-spawn.sh <target-agent> <issue-number> [context]"
    exit 1
fi

# Determine paths
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$SCRIPT_DIR")}"

# Find project root
find_project_root() {
    local dir="$(pwd)"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/.claude/ghe.local.md" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    echo "$(pwd)"
}

PROJECT_ROOT="$(find_project_root)"
SPAWN_LOG="$PROJECT_ROOT/agents_reports/spawn_requests.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# Ensure log directory exists
mkdir -p "$(dirname "$SPAWN_LOG")"

# Agent Greek names for logging
declare -A AGENT_NAMES=(
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

TARGET_NAME="${AGENT_NAMES[$TARGET_AGENT]:-$TARGET_AGENT}"

# Log the spawn request
log_request() {
    echo "[$TIMESTAMP] SPAWN REQUEST: $TARGET_NAME ($TARGET_AGENT) for #$ISSUE_NUM" >> "$SPAWN_LOG"
    echo "  Context: ${CONTEXT:-none}" >> "$SPAWN_LOG"
    echo "  Caller: $$" >> "$SPAWN_LOG"
}

log_request

# Phase transitions that should go through phase-gate validation
# Format: "source->target"
GATED_TRANSITIONS=(
    "dev-thread-manager->test-thread-manager"    # DEV -> TEST
    "test-thread-manager->review-thread-manager" # TEST -> REVIEW
)

# Determine if this spawn needs phase-gate validation
needs_validation() {
    local caller_phase=""
    local target_phase=""

    # Try to determine caller from context or environment
    # In practice, the calling agent would pass its identity

    # For now, we validate all phase-to-phase transitions
    case "$TARGET_AGENT" in
        "test-thread-manager"|"review-thread-manager")
            return 0  # Needs validation
            ;;
        *)
            return 1  # No validation needed
            ;;
    esac
}

# Check if target agent is the phase-gate itself (avoid infinite loop)
if [[ "$TARGET_AGENT" == "phase-gate" ]]; then
    # Direct spawn without validation
    echo "[$TIMESTAMP] Spawning phase-gate for validation..." >> "$SPAWN_LOG"
    bash "$SCRIPT_DIR/spawn-agent.sh" "$TARGET_AGENT" "$ISSUE_NUM" "$CONTEXT"
    exit $?
fi

# Check if this transition needs phase-gate validation
if needs_validation; then
    # First spawn phase-gate to validate, which will then spawn target if approved
    echo "[$TIMESTAMP] Routing through phase-gate for validation..." >> "$SPAWN_LOG"
    bash "$SCRIPT_DIR/spawn-agent.sh" "phase-gate" "$ISSUE_NUM" "Validate spawn of $TARGET_NAME: $CONTEXT"
    exit $?
fi

# Direct spawn for non-phase agents
echo "[$TIMESTAMP] Direct spawn of $TARGET_NAME..." >> "$SPAWN_LOG"
bash "$SCRIPT_DIR/spawn-agent.sh" "$TARGET_AGENT" "$ISSUE_NUM" "$CONTEXT"

# Post to issue thread that agent was spawned
if [[ -n "$ISSUE_NUM" ]] && [[ "$ISSUE_NUM" != "null" ]]; then
    # Load avatar helper if available
    if [[ -f "$SCRIPT_DIR/post-with-avatar.sh" ]]; then
        source "$SCRIPT_DIR/post-with-avatar.sh"
        HEADER=$(avatar_header "Athena")
    else
        HEADER=""
    fi

    # Post notification (non-blocking, ignore errors)
    gh issue comment "$ISSUE_NUM" --body "${HEADER}
**Agent Spawned**

$TARGET_NAME has been spawned to continue work on this issue.

- **Agent**: $TARGET_AGENT
- **Context**: ${CONTEXT:-Workflow continuation}
- **Time**: $TIMESTAMP

---
*Spawned by GHE orchestration system*" 2>/dev/null &
fi

echo "Spawn request processed: $TARGET_NAME for #$ISSUE_NUM"
