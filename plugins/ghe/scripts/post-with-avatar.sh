#!/bin/bash
# post-with-avatar.sh - Helper for posting GitHub comments with avatar banners
# Usage: source this file, then call post_comment or get_avatar_url

# Avatar URLs for each agent
declare -A AVATAR_URLS=(
    ["Emasoft"]="https://avatars.githubusercontent.com/u/713559?v=4&s=77"
    ["Claude"]="https://robohash.org/claude-code-orchestrator.png?size=77x77&set=set3"
    ["Hephaestus"]="https://robohash.org/hephaestus.png?size=77x77&set=set3"
    ["Artemis"]="https://robohash.org/artemis.png?size=77x77&set=set3"
    ["Hera"]="https://robohash.org/hera.png?size=77x77&set=set3"
    ["Athena"]="https://robohash.org/athena.png?size=77x77&set=set3"
    ["Themis"]="https://robohash.org/themis.png?size=77x77&set=set3"
    ["Mnemosyne"]="https://robohash.org/mnemosyne.png?size=77x77&set=set3"
    ["Ares"]="https://robohash.org/ares.png?size=77x77&set=set3"
    ["Hermes"]="https://robohash.org/hermes.png?size=77x77&set=set3"
    ["Chronos"]="https://robohash.org/chronos.png?size=77x77&set=set3"
    ["Cerberus"]="https://robohash.org/cerberus.png?size=77x77&set=set3"
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

    echo "${AVATAR_URLS[$name]:-https://robohash.org/${name}.png?size=77x77&set=set3}"
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
