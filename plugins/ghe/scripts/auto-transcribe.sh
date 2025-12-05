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

# Avatar URLs - Agent avatars are hosted locally in plugin assets
# User avatars are fetched dynamically from GitHub
AVATAR_BASE="https://raw.githubusercontent.com/Emasoft/ghe-marketplace/main/plugins/ghe/assets/avatars"

# Agent avatars (bundled with plugin)
declare -A AVATARS=(
    ["Athena"]="${AVATAR_BASE}/athena.png"
    ["Hephaestus"]="${AVATAR_BASE}/hephaestus.png"
    ["Artemis"]="${AVATAR_BASE}/artemis.png"
    ["Hera"]="${AVATAR_BASE}/hera.png"
    ["Themis"]="${AVATAR_BASE}/themis.png"
    ["Hermes"]="${AVATAR_BASE}/hermes.png"
    ["Ares"]="${AVATAR_BASE}/ares.png"
    ["Chronos"]="${AVATAR_BASE}/chronos.png"
    ["Mnemosyne"]="${AVATAR_BASE}/mnemosyne.png"
    ["Cerberus"]="${AVATAR_BASE}/cerberus.png"
    ["Argos"]="${AVATAR_BASE}/argos.png"
)

# Get avatar for a GitHub user (dynamically fetched)
get_user_avatar() {
    local username="$1"
    local size="${2:-77}"
    # GitHub provides avatars at: https://avatars.githubusercontent.com/{username}?s={size}
    echo "https://avatars.githubusercontent.com/${username}?s=${size}"
}

# Get avatar URL - checks agents first, then falls back to GitHub user avatar
get_avatar_url() {
    local name="$1"
    # Check if it's a known agent
    if [[ -n "${AVATARS[$name]}" ]]; then
        echo "${AVATARS[$name]}"
    else
        # Assume it's a GitHub username, fetch their avatar dynamically
        get_user_avatar "$name" 77
    fi
}

# Element type badges (GitHub-friendly markdown) - no alt text, just badges
BADGE_KNOWLEDGE="![](https://img.shields.io/badge/element-knowledge-blue)"
BADGE_ACTION="![](https://img.shields.io/badge/element-action-green)"
BADGE_JUDGEMENT="![](https://img.shields.io/badge/element-judgement-orange)"

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

    # Check for ACTION indicators (code, assets, any concrete project artifacts)
    # ACTION = tangible changes to the project: code, images, sounds, video, 3D, stylesheets, configs
    if echo "$content" | grep -qE '(```|diff|patch|function |class |def |const |let |var |import |export |<[a-z]+>)'; then
        if [[ -n "$badges" ]]; then
            badges="$badges $BADGE_ACTION"
        else
            badges="$BADGE_ACTION"
        fi
    # Code/config file extensions
    elif echo "$content" | grep -qiE '\.(py|js|ts|jsx|tsx|md|yml|yaml|json|xml|html|css|scss|sass|less|sh|bash|zsh|rb|go|rs|java|kt|swift|c|cpp|h|hpp)'; then
        if [[ -n "$badges" ]]; then
            badges="$badges $BADGE_ACTION"
        else
            badges="$BADGE_ACTION"
        fi
    # Asset file extensions (images, audio, video, 3D, fonts)
    elif echo "$content" | grep -qiE '\.(png|jpg|jpeg|gif|svg|ico|webp|avif|bmp|tiff|mp3|wav|ogg|flac|aac|m4a|mp4|webm|avi|mov|mkv|glb|gltf|obj|fbx|blend|dae|3ds|ttf|otf|woff|woff2|eot)'; then
        if [[ -n "$badges" ]]; then
            badges="$badges $BADGE_ACTION"
        else
            badges="$BADGE_ACTION"
        fi
    # URLs to raw files/assets (GitHub raw, CDN, etc.)
    elif echo "$content" | grep -qiE '(raw\.githubusercontent\.com|github\.com/.*/blob/|cdn\.|assets/|images/|sprites/|textures/|sounds/|audio/|video/|models/|fonts/)'; then
        if [[ -n "$badges" ]]; then
            badges="$badges $BADGE_ACTION"
        else
            badges="$BADGE_ACTION"
        fi
    # Action verbs indicating concrete changes
    elif echo "$content" | grep -qiE '(create[d]?|implement|writ(e|ten)|add(ed)?|modif(y|ied)|edit(ed)?|fix(ed)?|update[d]?|refactor|upload(ed)?|commit(ted)?|push(ed)?|deploy(ed)?|built|generat(e|ed)|render(ed)?|compil(e|ed)|export(ed)?|import(ed)?)'; then
        if [[ -n "$badges" ]]; then
            badges="$badges $BADGE_ACTION"
        else
            badges="$BADGE_ACTION"
        fi
    # Asset-related keywords
    elif echo "$content" | grep -qiE '(asset[s]?|sprite[s]?|icon[s]?|graphic[s]?|image[s]?|texture[s]?|sound[s]?|audio|video|model[s]?|animation[s]?|stylesheet|font[s]?|avatar[s]?|logo|banner|thumbnail|screenshot)'; then
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
# Extract explicit issue number from text
# Patterns expanded to recognize:
#   - Context marker: [Currently discussing issue n.123]
#   - Bracketed: [issue #123], [Issue #123]
#   - GitHub URLs: https://github.com/OWNER/REPO/issues/123
#   - Action words with #: work on #123, claim #123, fix #123
#   - Action words without #: work on issue 123, claim 123
#   - Simple: issue 123, Issue 123
#   - Standalone hash: #123 (word boundary)
#######################################
extract_explicit_issue() {
    local text="$1"
    local issue_num=""

    # Pattern 1: [Currently discussing issue n.123] - context marker
    if [[ "$text" =~ \[Currently\ discussing\ issue\ n\.([0-9]+)\] ]]; then
        issue_num="${BASH_REMATCH[1]}"

    # Pattern 2: [issue #123] or [Issue #123] - bracketed format
    elif [[ "$text" =~ \[[Ii]ssue\ \#([0-9]+)\] ]]; then
        issue_num="${BASH_REMATCH[1]}"

    # Pattern 3: GitHub URL - https://github.com/OWNER/REPO/issues/123
    elif [[ "$text" =~ github\.com/[^/]+/[^/]+/issues/([0-9]+) ]]; then
        issue_num="${BASH_REMATCH[1]}"

    # Pattern 4: Action words with # - work on #123, working on issue #123
    elif [[ "$text" =~ [Ww]ork(ing)?\ on\ (issue\ )?\#([0-9]+) ]]; then
        issue_num="${BASH_REMATCH[3]}"

    # Pattern 5: Action words with # - lets work on #123
    elif [[ "$text" =~ [Ll]ets?\ work\ on\ (issue\ )?\#([0-9]+) ]]; then
        issue_num="${BASH_REMATCH[2]}"

    # Pattern 6: claim/fix/resume/close/check with # - claim #123, fix #123
    elif [[ "$text" =~ ([Cc]laim|[Ff]ix|[Rr]esume|[Cc]lose|[Cc]heck)\ (issue\ )?\#([0-9]+) ]]; then
        issue_num="${BASH_REMATCH[3]}"

    # Pattern 7: Action words WITHOUT # - work on issue 123, work on 123
    elif [[ "$text" =~ [Ww]ork(ing)?\ on\ (issue\ )?([0-9]+) ]]; then
        issue_num="${BASH_REMATCH[3]}"

    # Pattern 8: lets work on issue 123 or lets work on 123
    elif [[ "$text" =~ [Ll]ets?\ work\ on\ (issue\ )?([0-9]+) ]]; then
        issue_num="${BASH_REMATCH[2]}"

    # Pattern 9: claim/fix/resume/close/check WITHOUT # - claim 123, fix issue 123
    elif [[ "$text" =~ ([Cc]laim|[Ff]ix|[Rr]esume|[Cc]lose|[Cc]heck)\ (issue\ )?([0-9]+) ]]; then
        issue_num="${BASH_REMATCH[3]}"

    # Pattern 10: Simple "issue 123" or "Issue 123" (case insensitive)
    elif [[ "$text" =~ [Ii]ssue\ ([0-9]+) ]]; then
        issue_num="${BASH_REMATCH[1]}"

    # Pattern 11: Standalone #123 at word boundary (not part of other text)
    # Must be at start, after space, or end of string
    elif [[ "$text" =~ (^|[[:space:]])\#([0-9]+)($|[[:space:]]) ]]; then
        issue_num="${BASH_REMATCH[2]}"
    fi

    echo "$issue_num"
}

#######################################
# Find or create issue for conversation
#######################################
find_or_create_issue() {
    local topic="$1"

    # FIRST: Check for explicit issue mention in the message
    local explicit_issue=$(extract_explicit_issue "$topic")
    if [[ -n "$explicit_issue" ]]; then
        # Verify it exists (open or closed - we can still post to closed issues)
        if gh issue view "$explicit_issue" --json number --jq '.number' 2>/dev/null | grep -q "$explicit_issue"; then
            set_config "current_issue" "$explicit_issue"
            echo "$explicit_issue"
            return 0
        fi
    fi

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

--- ${BADGE_KNOWLEDGE} ${BADGE_ACTION} ${BADGE_JUDGEMENT}

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
# Transform local references to GitHub links for better traceability
# NOTE: Uses printf to avoid issues with special characters in content
#######################################
linkify_content() {
    local CONTENT="$1"
    local REPO=$(gh repo view --json nameWithOwner --jq '.nameWithOwner' 2>/dev/null)

    # If no repo or content is empty, return as-is
    if [ -z "$REPO" ] || [ -z "$CONTENT" ]; then
        printf '%s' "$CONTENT"
        return
    fi

    # Use a temp file to avoid sed issues with special characters
    local TMPFILE=$(mktemp)
    printf '%s' "$CONTENT" > "$TMPFILE"

    # Transform file:line references (e.g., `file.py:42`) - use @ as delimiter
    sed -i.bak -E "s@\`([a-zA-Z0-9_/.-]+\.(py|js|ts|md|yaml|yml|json|sh)):([0-9]+)\`@[\`\1:\3\`](https://github.com/$REPO/blob/main/\1#L\3)@g" "$TMPFILE" 2>/dev/null || true

    # Transform REQUIREMENTS references
    sed -i.bak -E "s@\bREQUIREMENTS/([^[:space:])\"]+\.md)@[REQUIREMENTS/\1](https://github.com/$REPO/blob/main/REQUIREMENTS/\1)@g" "$TMPFILE" 2>/dev/null || true

    # Transform REQ-XXX references to search links
    sed -i.bak -E "s@\b(REQ-[0-9]{3})\b@[\1](https://github.com/$REPO/search?q=\1)@g" "$TMPFILE" 2>/dev/null || true

    # Transform issue references if not already linked (avoid double-linking)
    # Pattern: non-bracket char + # + digits + non-bracket char
    sed -i.bak -E "s@([^[])#([0-9]+)([^]])@\1[#\2](https://github.com/$REPO/issues/\2)\3@g" "$TMPFILE" 2>/dev/null || true

    # Output result and cleanup
    cat "$TMPFILE"
    rm -f "$TMPFILE" "${TMPFILE}.bak"
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

    # Linkify content (convert local paths to GitHub links)
    local linkified_message=$(linkify_content "$safe_message")

    # Classify element
    local badges=$(classify_element "$linkified_message")

    # Format the comment - badges on same line as ---
    local comment
    comment="<img src=\"${avatar_url}\" width=\"77\" align=\"left\"/>

**${speaker} said:**
<br><br>

${linkified_message}

--- ${badges}"

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
# Inject issue reminder into project CLAUDE.md
#######################################
inject_claude_md_reminder() {
    local issue_num="$1"
    local claude_md="CLAUDE.md"
    local marker="<!-- GHE-CURRENT-ISSUE -->"
    local instruction="\n${marker}\n## GHE Active Transcription\n\n**CRITICAL**: All conversation is being transcribed to GitHub.\n\n\`\`\`\nCurrently discussing issue n.${issue_num}\n\`\`\`\n\n**You MUST include this line in your responses when referencing the current work.**\n${marker}\n"

    if [[ -f "$claude_md" ]]; then
        # Remove any existing GHE section
        if grep -q "$marker" "$claude_md"; then
            # Remove existing block (between markers)
            sed -i.bak "/${marker}/,/${marker}/d" "$claude_md" && rm -f "${claude_md}.bak"
        fi

        # Append new instruction at the end
        echo -e "$instruction" >> "$claude_md"
        echo "Injected issue reminder into CLAUDE.md"
    else
        # Create minimal CLAUDE.md with instruction
        echo -e "# Project Instructions\n$instruction" > "$claude_md"
        echo "Created CLAUDE.md with issue reminder"
    fi
}

#######################################
# Remove issue reminder from CLAUDE.md
#######################################
remove_claude_md_reminder() {
    local claude_md="CLAUDE.md"
    local marker="<!-- GHE-CURRENT-ISSUE -->"

    if [[ -f "$claude_md" ]] && grep -q "$marker" "$claude_md"; then
        sed -i.bak "/${marker}/,/${marker}/d" "$claude_md" && rm -f "${claude_md}.bak"
        echo "Removed issue reminder from CLAUDE.md"
    fi
}

#######################################
# Set current issue for MAIN THREAD transcription
#
# This is for the FOREGROUND conversation between USER and CLAUDE.
# It only enables transcription - NO agents are spawned here.
# The main thread is just Claude posting verbatim exchanges.
#
# For feature/bug DEVELOPMENT threads (with agents), use:
#   create-feature-thread.sh
#######################################
set_current_issue() {
    local issue_num="$1"

    if ! check_github_repo; then
        return 1
    fi

    ensure_config

    # Verify issue exists
    if ! gh issue view "$issue_num" --json number --jq '.number' 2>/dev/null | grep -q "$issue_num"; then
        echo "Issue #$issue_num not found" >&2
        return 1
    fi

    # SAVE the previous issue BEFORE switching (for resume functionality)
    local previous=$(get_config "current_issue" "")
    if [[ -n "$previous" && "$previous" != "null" && "$previous" != "$issue_num" ]]; then
        save_last_active_issue "$previous"
        echo -e "${YELLOW}Saved previous issue #$previous${NC}"
    fi

    echo -e "${GREEN}Setting main conversation thread to issue #$issue_num${NC}"

    # Update config - this is the MAIN thread (user + Claude conversation)
    set_config "current_issue" "$issue_num"
    set_config "current_phase" "CONVERSATION"  # Special phase for main thread

    # Inject reminder into CLAUDE.md
    inject_claude_md_reminder "$issue_num"

    # Mark issue as active conversation (NOT phase:dev - that's for feature threads)
    gh issue edit "$issue_num" --add-label "conversation" 2>/dev/null || true
    gh issue edit "$issue_num" --add-label "in-progress" 2>/dev/null || true

    echo ""
    echo -e "${GREEN}Issue #$issue_num is now the MAIN CONVERSATION THREAD${NC}"
    echo ""
    echo "TRANSCRIPTION IS NOW ACTIVE"
    echo "All exchanges between you and Claude will be posted VERBATIM to issue #$issue_num"
    echo ""
    echo "This is the foreground thread - NO agents will be spawned here."
    echo "To develop a feature/fix a bug, ask Claude and a BACKGROUND thread will be created."
    echo ""
    echo "Include in your responses:"
    echo "  Currently discussing issue n.$issue_num"
    return 0
}

#######################################
# Get current issue
#######################################
get_current_issue() {
    ensure_config
    local issue=$(get_config "current_issue" "")
    if [[ -n "$issue" && "$issue" != "null" ]]; then
        echo -e "${GREEN}TRANSCRIPTION ACTIVE${NC}"
        echo "Current issue: #$issue"
        echo ""
        echo "Include in responses: Currently discussing issue n.$issue"
    else
        echo -e "${YELLOW}TRANSCRIPTION INACTIVE${NC}"
        echo "No current issue set"
        echo ""
        echo "To activate: set-issue <NUMBER>"
    fi
}

#######################################
# Save current issue to last_active_issue.json
# This enables "resume last issue" functionality
#######################################
save_last_active_issue() {
    local issue_num="$1"
    local last_active_file=".claude/last_active_issue.json"

    # Only save if we have a valid issue number
    if [[ -z "$issue_num" || "$issue_num" == "null" ]]; then
        return 0
    fi

    # Get issue title from GitHub
    local title=$(gh issue view "$issue_num" --json title --jq '.title' 2>/dev/null || echo "Unknown")
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Ensure .claude directory exists
    mkdir -p .claude

    # Save to JSON file
    cat > "$last_active_file" << EOF
{
  "issue": $issue_num,
  "title": "$title",
  "last_active": "$timestamp"
}
EOF

    echo "Saved last active issue: #$issue_num"
}

#######################################
# Get last active issue from JSON file
#######################################
get_last_active_issue() {
    local last_active_file=".claude/last_active_issue.json"

    if [[ ! -f "$last_active_file" ]]; then
        echo -e "${YELLOW}No last active issue found${NC}"
        echo ""
        echo "No previous session recorded in .claude/last_active_issue.json"
        return 1
    fi

    local issue=$(jq -r '.issue' "$last_active_file" 2>/dev/null)
    local title=$(jq -r '.title' "$last_active_file" 2>/dev/null)
    local last_active=$(jq -r '.last_active' "$last_active_file" 2>/dev/null)

    if [[ -z "$issue" || "$issue" == "null" ]]; then
        echo -e "${YELLOW}Invalid last active issue file${NC}"
        return 1
    fi

    echo -e "${GREEN}Last Active Issue Found${NC}"
    echo ""
    echo "  Issue:       #$issue"
    echo "  Title:       $title"
    echo "  Last Active: $last_active"
    echo ""
    echo "To resume: set-issue $issue"

    # Return just the issue number for scripting use
    return 0
}

#######################################
# Get last issue number only (for scripting)
#######################################
get_last_issue_number() {
    local last_active_file=".claude/last_active_issue.json"

    if [[ -f "$last_active_file" ]]; then
        jq -r '.issue' "$last_active_file" 2>/dev/null
    fi
}

#######################################
# Clear current issue (stop transcription)
#######################################
clear_current_issue() {
    ensure_config

    # SAVE the current issue BEFORE clearing (for resume functionality)
    local current=$(get_config "current_issue" "")
    if [[ -n "$current" && "$current" != "null" ]]; then
        save_last_active_issue "$current"
    fi

    # Remove from config
    set_config "current_issue" "null"

    # Remove CLAUDE.md reminder
    remove_claude_md_reminder

    echo -e "${YELLOW}TRANSCRIPTION STOPPED${NC}"
    echo "No issue is now active for transcription"

    if [[ -n "$current" && "$current" != "null" ]]; then
        echo ""
        echo "Previous issue #$current has been saved."
        echo "To resume later: get-last-issue"
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
    "set-issue")
        set_current_issue "$2"
        ;;
    "get-issue")
        get_current_issue
        ;;
    "clear-issue")
        clear_current_issue
        ;;
    "get-last-issue")
        get_last_active_issue
        ;;
    "last-issue-number")
        # Returns ONLY the issue number (for scripting/piping)
        get_last_issue_number
        ;;
    "resume")
        # Convenience: Resume the last active issue
        LAST=$(get_last_issue_number)
        if [[ -n "$LAST" && "$LAST" != "null" ]]; then
            set_current_issue "$LAST"
        else
            echo "No previous issue to resume"
            exit 1
        fi
        ;;
    "check")
        check_github_repo && echo "GitHub repo OK" || echo "No GitHub repo"
        ;;
    *)
        echo "Usage: $0 {user|assistant|find-issue|set-issue|get-issue|clear-issue|get-last-issue|resume|check} [message] [agent]"
        echo ""
        echo "Commands:"
        echo "  user <message>              Post user message to current issue"
        echo "  assistant <message> [agent] Post assistant message (default: Athena)"
        echo "  find-issue <topic>          Find or create issue for topic"
        echo "  set-issue <number>          Set current issue and activate transcription"
        echo "  get-issue                   Show current issue status"
        echo "  clear-issue                 Stop transcription and clear current issue"
        echo "  get-last-issue              Show the last active issue (from previous session)"
        echo "  last-issue-number           Get only the issue number (for scripting)"
        echo "  resume                      Resume transcription to the last active issue"
        echo "  check                       Verify GitHub repo is configured"
        echo ""
        echo "IMPORTANT: Transcription only happens AFTER set-issue is called!"
        echo ""
        echo "Issue patterns recognized in messages:"
        echo "  [Currently discussing issue n.123]"
        echo "  [issue #123]"
        echo "  working on issue #123"
        echo "  lets work on #123"
        echo "  claim #123"
        echo ""
        echo "Resume workflow:"
        echo "  1. User says: 'what were we working on?' or 'resume last issue'"
        echo "  2. Claude checks: auto-transcribe.sh get-last-issue"
        echo "  3. Claude resumes: auto-transcribe.sh resume (or set-issue N)"
        exit 1
        ;;
esac
