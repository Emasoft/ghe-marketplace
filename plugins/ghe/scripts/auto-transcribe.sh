#!/bin/bash
# GHE Auto-Transcribe System
# Posts every conversation exchange to GitHub issues with element classification

set -e

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"
CONFIG_FILE=".claude/ghe.local.md"
GITHUB_USER="${GITHUB_OWNER:-Emasoft}"

# Colors for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Avatar URLs
declare -A AVATARS=(
    ["Emasoft"]="https://avatars.githubusercontent.com/u/713559?v=4&s=77"
    ["Athena"]="https://robohash.org/athena.png?size=77x77&set=set3"
    ["Hephaestus"]="https://robohash.org/hephaestus.png?size=77x77&set=set3"
    ["Artemis"]="https://robohash.org/artemis.png?size=77x77&set=set3"
    ["Hera"]="https://robohash.org/hera.png?size=77x77&set=set3"
    ["Themis"]="https://robohash.org/themis.png?size=77x77&set=set3"
    ["Hermes"]="https://robohash.org/hermes.png?size=77x77&set=set3"
    ["Ares"]="https://robohash.org/ares.png?size=77x77&set=set3"
    ["Chronos"]="https://robohash.org/chronos.png?size=77x77&set=set3"
    ["Mnemosyne"]="https://robohash.org/mnemosyne.png?size=77x77&set=set3"
)

# Element type badges (GitHub-friendly markdown)
BADGE_KNOWLEDGE="![knowledge](https://img.shields.io/badge/element-knowledge-blue)"
BADGE_ACTION="![action](https://img.shields.io/badge/element-action-green)"
BADGE_JUDGEMENT="![judgement](https://img.shields.io/badge/element-judgement-orange)"

#######################################
# Check if we have a GitHub repo
#######################################
check_github_repo() {
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        echo "Not a git repository" >&2
        return 1
    fi

    local remote=$(git remote get-url origin 2>/dev/null || echo "")
    if [[ -z "$remote" ]] || [[ ! "$remote" =~ github\.com ]]; then
        echo "No GitHub remote found" >&2
        return 1
    fi

    # Verify gh is authenticated
    if ! gh auth status > /dev/null 2>&1; then
        echo "GitHub CLI not authenticated" >&2
        return 1
    fi

    return 0
}

#######################################
# Get or create config file
#######################################
ensure_config() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
        mkdir -p "$(dirname "$CONFIG_FILE")"
        cat > "$CONFIG_FILE" << 'YAML'
---
enabled: true
auto_transcribe: true
current_issue: null
current_phase: null
session_id: null
---

# GHE Auto-Transcribe Configuration

Auto-transcription is enabled. All conversations will be recorded to GitHub issues.
YAML
    fi
}

#######################################
# Read config value
#######################################
get_config() {
    local key="$1"
    local default="$2"

    if [[ -f "$CONFIG_FILE" ]]; then
        local value=$(grep -E "^${key}:" "$CONFIG_FILE" | head -1 | sed 's/^[^:]*: *//' | tr -d '"' | tr -d "'")
        if [[ -n "$value" && "$value" != "null" ]]; then
            echo "$value"
            return
        fi
    fi
    echo "$default"
}

#######################################
# Update config value
#######################################
set_config() {
    local key="$1"
    local value="$2"

    if [[ -f "$CONFIG_FILE" ]]; then
        if grep -q "^${key}:" "$CONFIG_FILE"; then
            # Update existing
            sed -i.bak "s/^${key}:.*/${key}: ${value}/" "$CONFIG_FILE" && rm -f "${CONFIG_FILE}.bak"
        else
            # Add after frontmatter opening
            sed -i.bak "s/^---$/---\n${key}: ${value}/" "$CONFIG_FILE" && rm -f "${CONFIG_FILE}.bak"
        fi
    fi
}

#######################################
# Redact sensitive data
#######################################
redact_sensitive() {
    local text="$1"

    # Redact API keys
    text=$(echo "$text" | sed -E 's/sk-ant-[a-zA-Z0-9_-]+/[REDACTED_API_KEY]/g')
    text=$(echo "$text" | sed -E 's/sk-[a-zA-Z0-9]{20,}/[REDACTED_KEY]/g')
    text=$(echo "$text" | sed -E 's/ghp_[a-zA-Z0-9]{36}/[REDACTED_GH_TOKEN]/g')
    text=$(echo "$text" | sed -E 's/gho_[a-zA-Z0-9]{36}/[REDACTED_GH_TOKEN]/g')

    # Redact passwords in common patterns
    text=$(echo "$text" | sed -E 's/(password|passwd|pwd|secret|token|key)(["\x27]?\s*[:=]\s*["\x27]?)[^"\x27\s]+/\1\2[REDACTED]/gi')

    # Redact user home paths (keep structure visible)
    text=$(echo "$text" | sed -E 's|/Users/[^/]+/|/Users/[USER]/|g')
    text=$(echo "$text" | sed -E 's|/home/[^/]+/|/home/[USER]/|g')

    # Redact email addresses (except noreply)
    text=$(echo "$text" | sed -E 's/[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}/[REDACTED_EMAIL]/g')
    text=$(echo "$text" | sed -E 's/\[REDACTED_EMAIL\](@users\.noreply\.github\.com)/\1/g')

    echo "$text"
}

#######################################
# Classify content into element types
#######################################
classify_element() {
    local content="$1"
    local badges=""

    # Check for KNOWLEDGE indicators
    if echo "$content" | grep -qiE '(spec|requirement|design|algorithm|api|schema|architecture|protocol|format|structure|definition|concept|theory|documentation|how.*(work|function)|explain|what is|overview)'; then
        badges="$BADGE_KNOWLEDGE"
    fi

    # Check for ACTION indicators (code, implementation)
    if echo "$content" | grep -qE '(```|diff|patch|function |class |def |const |let |var |import |export |<[a-z]+>|\.py|\.js|\.ts|\.md|\.yml|\.yaml|\.json|create|implement|write|add|modify|edit|fix|update|refactor)'; then
        if [[ -n "$badges" ]]; then
            badges="$badges $BADGE_ACTION"
        else
            badges="$BADGE_ACTION"
        fi
    fi

    # Check for JUDGEMENT indicators
    if echo "$content" | grep -qiE '(bug|error|issue|problem|fail|broken|wrong|missing|review|feedback|test|should|must|need|improve|concern|question|why|critique|evaluate|assess|verdict|pass|reject)'; then
        if [[ -n "$badges" ]]; then
            badges="$badges $BADGE_JUDGEMENT"
        else
            badges="$BADGE_JUDGEMENT"
        fi
    fi

    # Default to knowledge if no classification
    if [[ -z "$badges" ]]; then
        badges="$BADGE_KNOWLEDGE"
    fi

    echo "$badges"
}

#######################################
# Find or create issue for conversation
#######################################
find_or_create_issue() {
    local topic="$1"
    local current_issue=$(get_config "current_issue" "")

    # If we have an active issue, use it
    if [[ -n "$current_issue" && "$current_issue" != "null" ]]; then
        # Verify it still exists and is open
        if gh issue view "$current_issue" --json state --jq '.state' 2>/dev/null | grep -q "OPEN"; then
            echo "$current_issue"
            return 0
        fi
    fi

    # Try to find an existing open issue matching the topic
    local keywords=$(echo "$topic" | tr '[:upper:]' '[:lower:]' | grep -oE '[a-z]{4,}' | head -5 | tr '\n' ' ')

    if [[ -n "$keywords" ]]; then
        local found_issue=$(gh issue list --state open --limit 10 --json number,title,body | \
            jq -r --arg kw "$keywords" '.[] | select((.title + " " + .body) | ascii_downcase | contains($kw | split(" ")[0])) | .number' | head -1)

        if [[ -n "$found_issue" ]]; then
            set_config "current_issue" "$found_issue"
            echo "$found_issue"
            return 0
        fi
    fi

    # Create a new session issue
    local session_id=$(date +%Y%m%d_%H%M%S)
    local title="[SESSION] Development Session $session_id"

    # Create issue and capture the URL, then extract issue number
    local issue_url=$(gh issue create \
        --title "$title" \
        --label "session" \
        --body "## Development Session

**Started**: $(date -u +"%Y-%m-%d %H:%M:%S UTC")
**Session ID**: $session_id

This issue tracks the conversation and work done during this development session.

---

### Element Types

- ${BADGE_KNOWLEDGE} - Specs, requirements, design, algorithms, documentation
- ${BADGE_ACTION} - Code, implementations, file changes, assets
- ${BADGE_JUDGEMENT} - Reviews, feedback, bug reports, evaluations

---
")
    # Extract issue number from URL (format: https://github.com/owner/repo/issues/N)
    local new_issue=$(echo "$issue_url" | grep -oE '[0-9]+$')

    if [[ -n "$new_issue" ]]; then
        set_config "current_issue" "$new_issue"
        set_config "session_id" "$session_id"
        echo "$new_issue"
        return 0
    fi

    return 1
}

#######################################
# Post message to issue
#######################################
post_to_issue() {
    local issue_num="$1"
    local speaker="$2"
    local message="$3"
    local is_user="${4:-false}"

    # Get avatar
    local avatar_url="${AVATARS[$speaker]:-${AVATARS[Athena]}}"

    # Redact sensitive data
    local safe_message=$(redact_sensitive "$message")

    # Classify element
    local badges=$(classify_element "$safe_message")

    # Format the comment
    local comment
    if [[ "$is_user" == "true" ]]; then
        comment="<img src=\"${avatar_url}\" width=\"77\" align=\"left\"/>

**${speaker} said:**
<br><br>

${safe_message}

---
${badges}"
    else
        comment="<img src=\"${avatar_url}\" width=\"77\" align=\"left\"/>

**${speaker} said:**
<br><br>

${safe_message}

---
${badges}"
    fi

    # Post to GitHub
    gh issue comment "$issue_num" --body "$comment"
}

#######################################
# Main: Post user message
#######################################
post_user_message() {
    local message="$1"

    if ! check_github_repo; then
        return 1
    fi

    ensure_config

    # Check if enabled
    if [[ "$(get_config 'enabled' 'true')" != "true" ]]; then
        return 0
    fi

    if [[ "$(get_config 'auto_transcribe' 'true')" != "true" ]]; then
        return 0
    fi

    # Get or create issue
    local issue=$(find_or_create_issue "$message")

    if [[ -n "$issue" ]]; then
        post_to_issue "$issue" "$GITHUB_USER" "$message" "true"
        echo "Posted to issue #$issue"
    fi
}

#######################################
# Main: Post assistant message
#######################################
post_assistant_message() {
    local message="$1"
    local agent="${2:-Athena}"

    if ! check_github_repo; then
        return 1
    fi

    ensure_config

    # Check if enabled
    if [[ "$(get_config 'enabled' 'true')" != "true" ]]; then
        return 0
    fi

    if [[ "$(get_config 'auto_transcribe' 'true')" != "true" ]]; then
        return 0
    fi

    local issue=$(get_config "current_issue" "")

    if [[ -n "$issue" && "$issue" != "null" ]]; then
        post_to_issue "$issue" "$agent" "$message" "false"
        echo "Posted to issue #$issue"
    fi
}

#######################################
# CLI interface
#######################################
case "${1:-}" in
    "user")
        post_user_message "$2"
        ;;
    "assistant")
        post_assistant_message "$2" "${3:-Athena}"
        ;;
    "find-issue")
        find_or_create_issue "$2"
        ;;
    "check")
        check_github_repo && echo "GitHub repo OK" || echo "No GitHub repo"
        ;;
    *)
        echo "Usage: $0 {user|assistant|find-issue|check} [message] [agent]"
        exit 1
        ;;
esac
