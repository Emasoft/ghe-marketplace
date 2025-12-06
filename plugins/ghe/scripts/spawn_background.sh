#!/bin/bash
# Spawn a Claude session in a BACKGROUND Terminal window (macOS only)
# Terminal window stays in background - NEVER steals focus!
#
# WINDOW IDENTITY GUARANTEE:
# The prompt is piped directly to Claude as part of the command that creates the window.
# This is ATOMIC - there is NO separate "send to window" step, NO keystroke routing.
# It is PHYSICALLY IMPOSSIBLE for the prompt to go to a different window.
#
# Usage: spawn_background.sh "Your prompt here" [working_dir]
#
# Environment variables:
#   BACKGROUND_AGENT_LOG - Log file path (default: /tmp/background_agent_hook.log)

set -e

PROMPT="${1:-Hello! Please run git status and create a summary.}"
WORKING_DIR="${2:-$(pwd)}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
AGENT_UUID=$(uuidgen 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null || echo "$$-$RANDOM")
AGENT_ID="GHE-AGENT-${AGENT_UUID}"
LOG_FILE="${BACKGROUND_AGENT_LOG:-/tmp/background_agent_hook.log}"

# Ensure we have an absolute path
if [[ "$WORKING_DIR" != "/"* ]]; then
    WORKING_DIR="$(cd "$WORKING_DIR" && pwd)"
fi

# Get parent directory (for sub-git projects)
PARENT_DIR="$(dirname "$WORKING_DIR")"

# Create GHE_REPORTS directory (FLAT structure - no subfolders!)
mkdir -p "$WORKING_DIR/GHE_REPORTS"

# Detect OS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: This script only works on macOS (requires Terminal.app)"
    echo "For Linux, consider using tmux or screen instead."
    exit 1
fi

# Write prompt to temp file (avoids shell escaping issues entirely)
PROMPT_FILE=$(mktemp /tmp/claude_prompt_XXXXXX.txt)

# Add security prefix with agent guidelines
cat > "$PROMPT_FILE" << SECURITY_EOF
[AGENT GUIDELINES]
You are a background agent. Execute your task with these boundaries:
- Project directory: $WORKING_DIR
- Parent directory (if sub-git): $PARENT_DIR
- Allowed write locations: project dir, parent dir, ~/.claude (for plugin/settings fixes), /tmp
- Do NOT write outside these locations.

REPORT POSTING (MANDATORY):
- ALL reports MUST be posted to BOTH locations:
  1. GitHub Issue Thread - Full report text (NOT just a link!)
  2. GHE_REPORTS/ folder - Same full report text (FLAT structure, no subfolders!)
- Report naming: <TIMESTAMP>_<title or description>_(<AGENT>).md
  Example: 20251206143022GMT+01_issue_42_dev_complete_(Hephaestus).md
  Timestamp format: YYYYMMDDHHMMSSTimezone
- REQUIREMENTS/ is SEPARATE - permanent design docs, never deleted
- REDACT before posting: API keys, passwords, emails, user paths → ✕✕REDACTED✕✕

[TASK]
$PROMPT
SECURITY_EOF

# Log spawn event
log_msg() {
    local msg="$1"
    local ts=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[$ts] [$AGENT_ID] $msg" >> "$LOG_FILE"
}

log_msg "=========================================="
log_msg "Spawning agent: $AGENT_ID"
log_msg "Directory: $WORKING_DIR"
log_msg "Prompt: ${PROMPT:0:100}..."

# THE IRONCLAD GUARANTEE:
# This entire command runs ATOMICALLY in a single Terminal tab.
# The prompt is piped directly to Claude - there is NO separate send step.
# It is PHYSICALLY IMPOSSIBLE for the prompt to go to a different window.
FULL_CMD="cd '$WORKING_DIR' && cat '$PROMPT_FILE' | claude --dangerously-skip-permissions; rm -f '$PROMPT_FILE'"

# Create Terminal window in background (no activation, no focus stealing)
# The do script command passes the full command to the new tab at creation time
RESULT=$(osascript << EOF
tell application "Terminal"
    -- ATOMIC: Command is bound to this tab at creation time
    set newTab to do script "$FULL_CMD"
    set newWindow to first window whose tabs contains newTab
    set custom title of newTab to "$AGENT_ID"
    return (id of newWindow as text) & "|" & (tty of newTab)
end tell
EOF
)

# Parse window info
WINDOW_ID=$(echo "$RESULT" | cut -d'|' -f1)
TTY_PATH=$(echo "$RESULT" | cut -d'|' -f2)

# Log completion
log_msg "Window ID: $WINDOW_ID, TTY: $TTY_PATH"
log_msg "Spawn complete"

echo ""
echo "=============================================="
echo "Background Agent Spawned"
echo "=============================================="
echo "Agent ID:   $AGENT_ID"
echo "Window ID:  $WINDOW_ID"
echo "TTY:        $TTY_PATH"
echo "Directory:  $WORKING_DIR"
echo "Prompt:     ${PROMPT:0:60}..."
echo ""
echo "WINDOW IDENTITY: 100% GUARANTEED"
echo "  Prompt piped directly to Claude (atomic, no keystrokes)"
echo "  Physically impossible for prompt to go elsewhere"
echo ""
echo "Working in background - no interruptions!"
echo "Check GHE_REPORTS/ for output."
echo "=============================================="
