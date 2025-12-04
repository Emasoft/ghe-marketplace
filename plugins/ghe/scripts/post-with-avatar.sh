#!/bin/bash
# post-with-avatar.sh - Helper for posting GitHub comments with avatar banners
# Usage: source this file, then call post_comment or get_avatar_url

# Avatar URLs - hosted locally in plugin assets (served via raw GitHub)
# Local path: plugins/ghe/assets/avatars/{name}.png
AVATAR_BASE="https://raw.githubusercontent.com/Emasoft/ghe-marketplace/main/plugins/ghe/assets/avatars"
declare -A AVATAR_URLS=(
    ["Emasoft"]="${AVATAR_BASE}/emasoft.png"
    ["Claude"]="${AVATAR_BASE}/claude.png"
    ["Hephaestus"]="${AVATAR_BASE}/hephaestus.png"
    ["Artemis"]="${AVATAR_BASE}/artemis.png"
    ["Hera"]="${AVATAR_BASE}/hera.png"
    ["Athena"]="${AVATAR_BASE}/athena.png"
    ["Themis"]="${AVATAR_BASE}/themis.png"
    ["Mnemosyne"]="${AVATAR_BASE}/mnemosyne.png"
    ["Ares"]="${AVATAR_BASE}/ares.png"
    ["Hermes"]="${AVATAR_BASE}/hermes.png"
    ["Chronos"]="${AVATAR_BASE}/chronos.png"
    ["Cerberus"]="${AVATAR_BASE}/cerberus.png"
    ["Argos"]="${AVATAR_BASE}/argos.png"
)

# Agent name to display name mapping
declare -A AGENT_NAMES=(
    ["ghe:dev-thread-manager"]="Hephaestus"
    ["ghe:test-thread-manager"]="Artemis"
    ["ghe:review-thread-manager"]="Hera"
    ["ghe:github-elements-orchestrator"]="Athena"
    ["ghe:phase-gate"]="Themis"
    ["ghe:memory-sync"]="Mnemosyne"
    ["ghe:enforcement"]="Ares"
    ["ghe:reporter"]="Hermes"
    ["ghe:ci-issue-opener"]="Chronos"
    ["ghe:pr-checker"]="Cerberus"
)

# Get avatar URL for an agent name
# Usage: get_avatar_url "Hera" or get_avatar_url "ghe:review-thread-manager"
get_avatar_url() {
    local name="$1"

    # If it's an agent ID, convert to display name
    if [[ "$name" == ghe:* ]]; then
        name="${AGENT_NAMES[$name]:-$name}"
    fi

    # Fallback to base URL with lowercase name (all avatars should be pre-downloaded)
    echo "${AVATAR_URLS[$name]:-${AVATAR_BASE}/$(echo $name | tr '[:upper:]' '[:lower:]').png}"
}

# Get display name for an agent
# Usage: get_display_name "ghe:review-thread-manager" -> "Hera"
get_display_name() {
    local agent_id="$1"
    echo "${AGENT_NAMES[$agent_id]:-$agent_id}"
}

# Format a comment with avatar banner
# Usage: format_comment "Hera" "Content here"
# Returns: Formatted markdown string
format_comment() {
    local name="$1"
    local content="$2"
    local avatar_url

    # If it's an agent ID, convert to display name
    if [[ "$name" == ghe:* ]]; then
        name="${AGENT_NAMES[$name]:-$name}"
    fi

    avatar_url=$(get_avatar_url "$name")

    cat <<EOF
<img src="${avatar_url}" width="77" align="left"/>

**${name} said:**
<br><br>

${content}
EOF
}

# Post a comment to a GitHub issue with avatar banner
# Usage: post_issue_comment ISSUE_NUM AGENT_NAME "Content"
post_issue_comment() {
    local issue_num="$1"
    local agent_name="$2"
    local content="$3"
    local formatted

    formatted=$(format_comment "$agent_name" "$content")
    gh issue comment "$issue_num" --body "$formatted"
}

# Post a comment to a GitHub PR with avatar banner
# Usage: post_pr_comment PR_NUM AGENT_NAME "Content"
post_pr_comment() {
    local pr_num="$1"
    local agent_name="$2"
    local content="$3"
    local formatted

    formatted=$(format_comment "$agent_name" "$content")
    gh pr comment "$pr_num" --body "$formatted"
}

# Generate the avatar header only (for complex comments built separately)
# Usage: avatar_header "Hera"
avatar_header() {
    local name="$1"
    local avatar_url

    # If it's an agent ID, convert to display name
    if [[ "$name" == ghe:* ]]; then
        name="${AGENT_NAMES[$name]:-$name}"
    fi

    avatar_url=$(get_avatar_url "$name")

    cat <<EOF
<img src="${avatar_url}" width="77" align="left"/>

**${name} said:**
<br><br>

EOF
}

# Show help
if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    cat <<'HELP'
post-with-avatar.sh - Helper for posting GitHub comments with avatar banners

USAGE:
  source plugins/ghe/scripts/post-with-avatar.sh

FUNCTIONS:
  get_avatar_url NAME          Get avatar URL for agent name or ID
  get_display_name AGENT_ID    Convert agent ID to display name
  format_comment NAME CONTENT  Format content with avatar header
  post_issue_comment NUM NAME CONTENT  Post to issue with avatar
  post_pr_comment NUM NAME CONTENT     Post to PR with avatar
  avatar_header NAME           Get just the avatar header

EXAMPLES:
  # Post as Hera to issue #5
  post_issue_comment 5 "Hera" "Review complete. PASS."

  # Post using agent ID
  post_issue_comment 5 "ghe:review-thread-manager" "Review complete."

  # Get formatted comment for complex posts
  HEADER=$(avatar_header "Hera")
  gh issue comment 5 --body "${HEADER}
## Review Results
- Test 1: PASS
- Test 2: PASS"

AGENT NAMES:
  Hephaestus  - DEV thread manager (builds and shapes)
  Artemis     - TEST thread manager (hunts bugs)
  Hera        - REVIEW thread manager (evaluates quality)
  Athena      - Orchestrator (coordinates workflow)
  Themis      - Phase gate (enforces transitions)
  Mnemosyne   - Memory sync (SERENA integration)
  Ares        - Enforcement (violations)
  Hermes      - Reporter (status reports)
  Chronos     - CI issue opener (time-based)
  Cerberus    - PR checker (guards merges)
HELP
fi
