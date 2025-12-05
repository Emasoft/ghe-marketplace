#!/bin/bash
# Auto-approve PreToolUse hook for background Claude sessions
# Works WITHOUT --dangerously-skip-permissions flag!
#
# This hook auto-approves safe operations within the project directory,
# allowing background agents to work autonomously.
#
# Permission decisions:
#   - "allow" = auto-approve (no user prompt)
#   - "deny"  = block operation
#   - "ask"   = prompt user for approval

# Optional logging (comment out in production)
LOG_FILE="${BACKGROUND_AGENT_LOG:-/tmp/background_agent_hook.log}"

# Read JSON input from Claude
INPUT=$(cat)

# Extract tool information
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

# Log if enabled
if [[ -n "$LOG_FILE" ]]; then
    echo "[$(date)] Tool: $TOOL_NAME, Path: $FILE_PATH, Cmd: ${COMMAND:0:50}" >> "$LOG_FILE"
fi

# Get project root from current working directory
PROJECT_ROOT="${CWD:-$(pwd)}"

# === PERMISSION DECISION FUNCTIONS ===

approve() {
    local REASON="${1:-Auto-approved by background-agents hook}"
    [[ -n "$LOG_FILE" ]] && echo "[$(date)] ALLOW: $REASON" >> "$LOG_FILE"
    cat << EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"$REASON"}}
EOF
    exit 0
}

deny_it() {
    local REASON="${1:-Denied by background-agents hook}"
    [[ -n "$LOG_FILE" ]] && echo "[$(date)] DENY: $REASON" >> "$LOG_FILE"
    cat << EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"$REASON"}}
EOF
    exit 0
}

ask_user() {
    local REASON="${1:-Requires user approval}"
    [[ -n "$LOG_FILE" ]] && echo "[$(date)] ASK: $REASON" >> "$LOG_FILE"
    cat << EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"$REASON"}}
EOF
    exit 0
}

# === PATH SAFETY CHECKS ===

is_safe_path() {
    local P="$1"
    # Empty path is safe (some tools don't have paths)
    [[ -z "$P" ]] && return 0
    # Relative paths are safe (within project)
    [[ "$P" != "/"* ]] && return 0
    # Paths within project directory are safe
    [[ "$P" == "$PROJECT_ROOT"* ]] && return 0
    # /tmp is safe for temporary files
    [[ "$P" == "/tmp"* ]] && return 0
    # Everything else is unsafe
    return 1
}

# === MAIN DECISION LOGIC ===

case "$TOOL_NAME" in
    # Read-only tools - always safe
    "Read"|"Glob"|"Grep"|"LS"|"Task"|"WebFetch"|"WebSearch"|"TodoWrite"|"TodoRead"|"ListMcpResourcesTool"|"ReadMcpResourceTool")
        approve "Safe read-only tool"
        ;;

    # Write tools - check path is within project
    "Write"|"Edit"|"MultiEdit"|"NotebookEdit")
        if is_safe_path "$FILE_PATH"; then
            approve "Write within project directory"
        else
            deny_it "Write outside project: $FILE_PATH"
        fi
        ;;

    # Bash commands - whitelist safe commands
    "Bash")
        case "$COMMAND" in
            # Git operations
            git\ *|gh\ *)
                approve "Git/GitHub command" ;;
            
            # File inspection (read-only)
            ls\ *|cat\ *|head\ *|tail\ *|wc\ *|file\ *|stat\ *|find\ *|grep\ *|which\ *)
                approve "Safe read command" ;;
            
            # Development tools
            python*|uv\ *|node\ *|npm\ *|pnpm\ *|yarn\ *|cargo\ *|go\ *)
                approve "Development runtime" ;;
            
            # Linters and formatters
            ruff\ *|pytest*|mypy\ *|eslint\ *|prettier\ *|tsc\ *|rustfmt\ *)
                approve "Linter/formatter" ;;
            
            # Safe utilities
            echo\ *|printf\ *|mkdir\ *|touch\ *|cp\ *|mv\ *|chmod\ *|date*|pwd*|cd\ *|sleep\ *)
                approve "Safe utility" ;;
            
            # Build tools
            make\ *|cmake\ *|ninja\ *)
                approve "Build tool" ;;
            
            # Dangerous commands - always deny
            *"sudo "*|*"rm -rf /"*|*"chmod 777 "*|*"> /dev/"*|*"dd if="*)
                deny_it "Dangerous command blocked" ;;
            
            # Unknown commands - ask user
            *)
                ask_user "Unknown bash command"
                ;;
        esac
        ;;

    # MCP tools - generally safe (they have their own auth)
    mcp__*)
        approve "MCP tool"
        ;;

    # Skill/SlashCommand execution - safe
    "Skill"|"SlashCommand")
        approve "Skill/command execution"
        ;;

    # Unknown tools - ask user
    *)
        ask_user "Unknown tool: $TOOL_NAME"
        ;;
esac
