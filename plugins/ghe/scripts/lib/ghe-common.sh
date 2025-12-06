#!/bin/bash
# GHE Common Library
# Shared functions for all GHE scripts
# Source this file: source "${SCRIPT_DIR}/lib/ghe-common.sh"

# Determine plugin root if not already set
# Library is at plugins/ghe/scripts/lib/, so go up 2 levels to get to plugins/ghe/
GHE_PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"

#######################################
# Find config file - try multiple locations
# Priority: 1) Plugin-relative path, 2) Git root, 3) Current directory
#######################################
ghe_find_config_file() {
    # Try plugin-relative first (plugin is at REPO/plugins/ghe/)
    local plugin_repo="$(cd "$GHE_PLUGIN_ROOT/../.." 2>/dev/null && pwd)"
    if [[ -f "${plugin_repo}/.claude/ghe.local.md" ]]; then
        echo "${plugin_repo}/.claude/ghe.local.md"
        return 0
    fi

    # Try git root
    local git_root=$(git rev-parse --show-toplevel 2>/dev/null)
    if [[ -n "$git_root" && -f "${git_root}/.claude/ghe.local.md" ]]; then
        echo "${git_root}/.claude/ghe.local.md"
        return 0
    fi

    # Try current directory
    if [[ -f ".claude/ghe.local.md" ]]; then
        echo "$(pwd)/.claude/ghe.local.md"
        return 0
    fi

    return 1
}

#######################################
# Read repo_path from config - SOURCE OF TRUTH from /ghe:setup
# This ensures we always use the exact repo the user selected
#######################################
ghe_get_repo_path() {
    local config_file="${1:-$(ghe_find_config_file)}"

    if [[ -f "$config_file" ]]; then
        # Extract repo_path from YAML frontmatter
        local path=$(grep '^repo_path:' "$config_file" 2>/dev/null | sed 's/repo_path: *//' | tr -d '"' | tr -d "'")
        if [[ -n "$path" && -d "$path" ]]; then
            echo "$path"
            return 0
        fi
    fi

    # Fallback to plugin-relative path
    echo "$(cd "$GHE_PLUGIN_ROOT/../.." 2>/dev/null && pwd)"
}

#######################################
# Read a setting from config frontmatter
# Usage: ghe_get_setting "key_name" [default_value]
#######################################
ghe_get_setting() {
    local key="$1"
    local default="${2:-}"
    local config_file="${GHE_CONFIG_FILE:-$(ghe_find_config_file)}"

    if [[ -f "$config_file" ]]; then
        local value=$(grep "^${key}:" "$config_file" 2>/dev/null | sed "s/${key}: *//" | tr -d '"' | tr -d "'")
        if [[ -n "$value" ]]; then
            echo "$value"
            return 0
        fi
    fi

    echo "$default"
}

#######################################
# Run gh commands from the correct repo directory
# Usage: ghe_gh issue view 123
#######################################
ghe_gh() {
    local repo_root="${GHE_REPO_ROOT:-$(ghe_get_repo_path)}"
    (cd "$repo_root" && gh "$@")
}

#######################################
# Run git commands on the correct repo
# Usage: ghe_git status
#######################################
ghe_git() {
    local repo_root="${GHE_REPO_ROOT:-$(ghe_get_repo_path)}"
    git -C "$repo_root" "$@"
}

#######################################
# Initialize GHE environment variables
# Call this at the start of each script
#######################################
ghe_init() {
    export GHE_CONFIG_FILE="${GHE_CONFIG_FILE:-$(ghe_find_config_file)}"
    export GHE_REPO_ROOT="${GHE_REPO_ROOT:-$(ghe_get_repo_path "$GHE_CONFIG_FILE")}"
    export GHE_ENABLED=$(ghe_get_setting "enabled" "false")
    export GHE_CURRENT_ISSUE=$(ghe_get_setting "current_issue" "")
    export GHE_CURRENT_PHASE=$(ghe_get_setting "current_phase" "")
    export GHE_AUTO_TRANSCRIBE=$(ghe_get_setting "auto_transcribe" "false")
}

# Colors for terminal output
GHE_RED='\033[0;31m'
GHE_GREEN='\033[0;32m'
GHE_YELLOW='\033[1;33m'
GHE_NC='\033[0m'

#######################################
# Log functions
#######################################
ghe_info() {
    echo -e "${GHE_GREEN}[GHE]${GHE_NC} $*"
}

ghe_warn() {
    echo -e "${GHE_YELLOW}[GHE]${GHE_NC} $*" >&2
}

ghe_error() {
    echo -e "${GHE_RED}[GHE]${GHE_NC} $*" >&2
}
