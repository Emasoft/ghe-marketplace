#!/bin/bash
# Auto-approve PreToolUse hook for background Claude sessions
# Works WITHOUT --dangerously-skip-permissions flag!
#
# Philosophy: Allow operations that TARGET the project directory.
# - Reading from anywhere is fine (system libs, etc.)
# - Writing/modifying/deleting MUST target allowed directories
#
# Allowed write directories:
#   - Project folder (and subfolders)
#   - /tmp/ (macOS/Linux) or %TEMP% (Windows)
#   - ~/.claude/ (Claude Code config)
#
# Permission decisions:
#   - "allow" = auto-approve (no user prompt)
#   - "deny"  = block operation
#   - "ask"   = prompt user for approval

# Optional logging (comment out in production)
LOG_FILE="${BACKGROUND_AGENT_LOG:-/tmp/background_agent_hook.log}"

# Source shared library to get registered repo path
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "${SCRIPT_DIR}/lib/ghe-common.sh" ]]; then
    source "${SCRIPT_DIR}/lib/ghe-common.sh"
    # Get the registered repo_path from config (SOURCE OF TRUTH from /ghe:setup)
    REGISTERED_REPO=$(ghe_get_repo_path 2>/dev/null || echo "")
fi

# Read JSON input from Claude
INPUT=$(cat)

# Extract tool information
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

# Get project root from current working directory
# Remove trailing slash for consistent comparison
PROJECT_ROOT="${CWD:-$(pwd)}"
PROJECT_ROOT="${PROJECT_ROOT%/}"

# Also track additional allowed directories from CLAUDE_PROJECT_DIRS env var
# Format: colon-separated paths like /path/one:/path/two
# IMPORTANT: Also include the registered repo from GHE config if different from CWD
EXTRA_PROJECT_DIRS="${CLAUDE_PROJECT_DIRS:-}"

# Add registered repo as allowed directory if it exists and differs from PROJECT_ROOT
if [[ -n "$REGISTERED_REPO" && "$REGISTERED_REPO" != "$PROJECT_ROOT" ]]; then
    if [[ -n "$EXTRA_PROJECT_DIRS" ]]; then
        EXTRA_PROJECT_DIRS="${EXTRA_PROJECT_DIRS}:${REGISTERED_REPO}"
    else
        EXTRA_PROJECT_DIRS="${REGISTERED_REPO}"
    fi
    [[ -n "$LOG_FILE" ]] && echo "[$(date)] Added registered repo to allowed dirs: $REGISTERED_REPO" >> "$LOG_FILE"
fi

# === PLATFORM DETECTION ===
# Detect OS and set platform-specific paths

detect_platform() {
    case "$(uname -s)" in
        Darwin*)
            PLATFORM="macos"
            TEMP_DIR="/tmp"
            CLAUDE_DIR="$HOME/.claude"
            ;;
        Linux*)
            PLATFORM="linux"
            TEMP_DIR="/tmp"
            CLAUDE_DIR="$HOME/.claude"
            ;;
        MINGW*|MSYS*|CYGWIN*)
            PLATFORM="windows"
            # Windows Git Bash - use Windows temp
            TEMP_DIR="${TEMP:-${TMP:-/tmp}}"
            CLAUDE_DIR="$HOME/.claude"
            ;;
        *)
            PLATFORM="unknown"
            TEMP_DIR="/tmp"
            CLAUDE_DIR="$HOME/.claude"
            ;;
    esac
}

detect_platform

# Log if enabled
if [[ -n "$LOG_FILE" ]]; then
    echo "[$(date)] Platform: $PLATFORM, Tool: $TOOL_NAME, Path: $FILE_PATH, Cmd: ${COMMAND:0:80}" >> "$LOG_FILE"
fi

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

# Normalize a path for comparison (remove trailing slash, resolve . and ..)
normalize_path() {
    local P="$1"
    # Remove trailing slashes
    P="${P%/}"
    # If we have realpath, use it for canonical form (but don't require file to exist)
    if command -v realpath &>/dev/null; then
        # -m: don't require file to exist, -s: no symlink resolution (faster)
        realpath -ms "$P" 2>/dev/null || echo "$P"
    else
        echo "$P"
    fi
}

# Check if path P starts with prefix DIR (proper directory containment check)
path_starts_with() {
    local P="$1"
    local DIR="$2"

    # Empty dir matches nothing
    [[ -z "$DIR" ]] && return 1

    # Exact match
    [[ "$P" == "$DIR" ]] && return 0

    # P is under DIR (ensure we match directory boundary, not just string prefix)
    # e.g., /home/user/project should match, but /home/user/project2 should not
    [[ "$P" == "$DIR/"* ]] && return 0

    return 1
}

# Check if a path is within allowed write directories
is_allowed_write_path() {
    local P="$1"
    [[ -z "$P" ]] && return 0

    # /dev/null is always safe (common redirect target)
    [[ "$P" == "/dev/null" ]] && return 0

    # Relative paths are inside project (allowed)
    [[ "$P" != "/"* ]] && [[ "$P" != [A-Za-z]:* ]] && return 0

    # Normalize the path for consistent comparison
    local NP
    NP=$(normalize_path "$P")

    # Log the comparison for debugging
    [[ -n "$LOG_FILE" ]] && echo "[$(date)] PATH CHECK: '$NP' against PROJECT_ROOT='$PROJECT_ROOT'" >> "$LOG_FILE"

    # Project directory (and subfolders) - use proper containment check
    if path_starts_with "$NP" "$PROJECT_ROOT"; then
        [[ -n "$LOG_FILE" ]] && echo "[$(date)] PATH ALLOWED: in PROJECT_ROOT" >> "$LOG_FILE"
        return 0
    fi

    # Check extra project directories (colon-separated)
    if [[ -n "$EXTRA_PROJECT_DIRS" ]]; then
        IFS=':' read -ra DIRS <<< "$EXTRA_PROJECT_DIRS"
        for DIR in "${DIRS[@]}"; do
            DIR=$(normalize_path "$DIR")
            if path_starts_with "$NP" "$DIR"; then
                [[ -n "$LOG_FILE" ]] && echo "[$(date)] PATH ALLOWED: in EXTRA_PROJECT_DIRS ($DIR)" >> "$LOG_FILE"
                return 0
            fi
        done
    fi

    # Temp directory - platform specific
    # macOS/Linux: /tmp or /private/tmp
    path_starts_with "$NP" "/tmp" && return 0
    path_starts_with "$NP" "/private/tmp" && return 0
    # Windows: various temp locations
    [[ -n "$TEMP" ]] && path_starts_with "$NP" "$TEMP" && return 0
    [[ -n "$TMP" ]] && path_starts_with "$NP" "$TMP" && return 0

    # Claude config directory (~/.claude/)
    # macOS: /Users/<user>/.claude/
    # Linux: /home/<user>/.claude/
    # Windows: C:\Users\<user>\.claude\ (via $HOME)
    path_starts_with "$NP" "$CLAUDE_DIR" && return 0
    path_starts_with "$NP" "$HOME/.claude" && return 0

    # Claude plugins cache (installed plugins)
    path_starts_with "$NP" "$HOME/.claude/plugins" && return 0

    # Not in allowed directories
    [[ -n "$LOG_FILE" ]] && echo "[$(date)] PATH DENIED: '$NP' not in any allowed directory" >> "$LOG_FILE"
    return 1
}

# Resolve a path (handle relative paths)
resolve_path() {
    local P="$1"
    # Handle Windows-style paths in Git Bash
    if [[ "$P" == [A-Za-z]:* ]]; then
        echo "$P"
    elif [[ "$P" != "/"* ]]; then
        # Relative path - prepend project root
        echo "$PROJECT_ROOT/$P"
    else
        echo "$P"
    fi
}

# Check if command contains catastrophic system operations
# Only blocks truly destructive SYSTEM-level operations
# External drives (USB, etc.) are allowed - user's choice
is_catastrophic() {
    local CMD="$1"

    # Privilege escalation - always block
    [[ "$CMD" == *"sudo "* ]] && return 0

    # Root filesystem destruction
    [[ "$CMD" == *"rm -rf /"* ]] && return 0
    [[ "$CMD" == *"rm -rf ~"* ]] && return 0
    [[ "$CMD" == *"rm -rf \$HOME"* ]] && return 0

    # Writing to system devices (not external drives)
    # Block: /dev/sda (Linux system), /dev/disk0 /dev/disk1 (macOS system)
    # Allow: /dev/sdb, /dev/sdc, /dev/disk2+ (external drives)
    [[ "$CMD" == *"> /dev/null"* ]] && return 1  # /dev/null is safe
    [[ "$CMD" == *"> /dev/sda"* ]] && return 0
    [[ "$CMD" == *"> /dev/nvme0"* ]] && return 0
    [[ "$CMD" == *"of=/dev/sda"* ]] && return 0
    [[ "$CMD" == *"of=/dev/nvme0"* ]] && return 0
    [[ "$CMD" == *"of=/dev/disk0"* ]] && return 0
    [[ "$CMD" == *"of=/dev/disk1"* ]] && return 0

    # System drive formatting only
    # macOS: diskutil on disk0/disk1 (system drives)
    [[ "$CMD" == *"diskutil"*"/dev/disk0"* ]] && return 0
    [[ "$CMD" == *"diskutil"*"/dev/disk1"* ]] && return 0
    # Linux: mkfs on sda/nvme0 (system drives)
    [[ "$CMD" == *"mkfs"*"/dev/sda"* ]] && return 0
    [[ "$CMD" == *"mkfs"*"/dev/nvme0"* ]] && return 0
    # Windows: format C: (system drive)
    [[ "$CMD" == *"format "*"C:"* ]] && return 0
    [[ "$CMD" == *"format "*"c:"* ]] && return 0

    # Fork bomb
    [[ "$CMD" == *":(){:|:&};:"* ]] && return 0

    # System control - always block
    [[ "$CMD" == *"shutdown"* ]] && return 0
    [[ "$CMD" == *"reboot"* ]] && return 0
    [[ "$CMD" == *"init 0"* ]] && return 0
    [[ "$CMD" == *"init 6"* ]] && return 0

    # Windows system destruction
    [[ "$CMD" == *"del /f /s /q C:\\"* ]] && return 0
    [[ "$CMD" == *"rd /s /q C:\\"* ]] && return 0

    return 1
}

# Extract WRITE targets from a command
# Returns paths that the command would write/modify/delete
get_write_targets() {
    local CMD="$1"
    local TARGETS=""

    # Output redirections: > >> 2> 2>> &>
    local REDIRECTS
    REDIRECTS=$(echo "$CMD" | grep -oE '(>|>>|2>|2>>|&>)\s*[^ ]+' | sed 's/^[0-9]*>>\? *//' || true)
    TARGETS="$TARGETS $REDIRECTS"

    # rm targets (everything after rm and flags)
    if [[ "$CMD" =~ ^rm[[:space:]] ]] || [[ "$CMD" == *" rm "* ]]; then
        local RM_TARGETS
        RM_TARGETS=$(echo "$CMD" | sed -n 's/.*\brm\s\+\(-[^ ]*\s\+\)*//p' || true)
        TARGETS="$TARGETS $RM_TARGETS"
    fi

    # mv destination (last argument)
    if [[ "$CMD" =~ ^mv[[:space:]] ]] || [[ "$CMD" == *" mv "* ]]; then
        local MV_DEST
        MV_DEST=$(echo "$CMD" | sed -n 's/.*\bmv\s.*\s\+\([^ ]*\)\s*$/\1/p' || true)
        TARGETS="$TARGETS $MV_DEST"
    fi

    # cp destination (last argument)
    if [[ "$CMD" =~ ^cp[[:space:]] ]] || [[ "$CMD" == *" cp "* ]]; then
        local CP_DEST
        CP_DEST=$(echo "$CMD" | sed -n 's/.*\bcp\s.*\s\+\([^ ]*\)\s*$/\1/p' || true)
        TARGETS="$TARGETS $CP_DEST"
    fi

    # touch, mkdir targets
    if [[ "$CMD" =~ ^(touch|mkdir)[[:space:]] ]] || [[ "$CMD" == *" touch "* ]] || [[ "$CMD" == *" mkdir "* ]]; then
        local CREATE_TARGETS
        CREATE_TARGETS=$(echo "$CMD" | sed -n 's/.*\b\(touch\|mkdir\)\s\+\(-[^ ]*\s\+\)*//p' || true)
        TARGETS="$TARGETS $CREATE_TARGETS"
    fi

    # chmod, chown targets
    if [[ "$CMD" =~ ^(chmod|chown)[[:space:]] ]] || [[ "$CMD" == *" chmod "* ]] || [[ "$CMD" == *" chown "* ]]; then
        local PERM_TARGETS
        PERM_TARGETS=$(echo "$CMD" | sed -n 's/.*\b\(chmod\|chown\)\s\+[^ ]*\s\+//p' || true)
        TARGETS="$TARGETS $PERM_TARGETS"
    fi

    # tee writes to files
    if [[ "$CMD" == *"| tee "* ]] || [[ "$CMD" == *"|tee "* ]]; then
        local TEE_TARGETS
        TEE_TARGETS=$(echo "$CMD" | sed -n 's/.*|\s*tee\s\+\(-[^ ]*\s\+\)*//p' || true)
        TARGETS="$TARGETS $TEE_TARGETS"
    fi

    echo "$TARGETS"
}

# Check if all write targets are in allowed directories
all_writes_allowed() {
    local CMD="$1"
    local TARGETS
    TARGETS=$(get_write_targets "$CMD")

    # No write targets detected = safe (read-only command)
    [[ -z "${TARGETS// /}" ]] && return 0

    for TARGET in $TARGETS; do
        # Skip empty
        [[ -z "$TARGET" ]] && continue
        # Skip flags
        [[ "$TARGET" == -* ]] && continue

        # Resolve and check
        local RESOLVED
        RESOLVED=$(resolve_path "$TARGET")

        if ! is_allowed_write_path "$RESOLVED"; then
            [[ -n "$LOG_FILE" ]] && echo "[$(date)] BLOCKED TARGET: $TARGET -> $RESOLVED" >> "$LOG_FILE"
            return 1
        fi
    done

    return 0
}

# === MAIN DECISION LOGIC ===

case "$TOOL_NAME" in
    # Read-only tools - always safe
    "Read"|"Glob"|"Grep"|"LS"|"Task"|"WebFetch"|"WebSearch"|"TodoWrite"|"TodoRead"|"ListMcpResourcesTool"|"ReadMcpResourceTool")
        approve "Safe read-only tool"
        ;;

    # Write tools - check path is in allowed directories
    "Write"|"Edit"|"MultiEdit"|"NotebookEdit")
        if is_allowed_write_path "$FILE_PATH"; then
            approve "Write targets allowed directory"
        else
            deny_it "Write targets outside allowed directories: $FILE_PATH"
        fi
        ;;

    # Bash commands - check write targets
    "Bash")
        # First, check for catastrophic commands
        if is_catastrophic "$COMMAND"; then
            deny_it "Catastrophic system command blocked"
        # Then check if all write targets are in allowed directories
        elif all_writes_allowed "$COMMAND"; then
            approve "All write targets in allowed directories"
        else
            deny_it "Command writes outside allowed directories"
        fi
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
