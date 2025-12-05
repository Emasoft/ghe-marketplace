#!/bin/bash
# thread-manager.sh - Phase-based thread management for GHE
# Manages thread lifecycle with proper manager assignment and changelog tracking

set -e

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"
source "$PLUGIN_ROOT/scripts/post-with-avatar.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Phase to Manager mapping
declare -A PHASE_MANAGERS=(
    ["dev"]="Hephaestus"
    ["test"]="Artemis"
    ["review"]="Hera"
    ["epic"]="Athena"
)

# Manager descriptions
declare -A MANAGER_ROLES=(
    ["Hephaestus"]="DEV Phase Manager - Builds and shapes the implementation"
    ["Artemis"]="TEST Phase Manager - Hunts bugs and verifies quality"
    ["Hera"]="REVIEW Phase Manager - Evaluates and renders final verdict"
    ["Athena"]="EPIC Manager - Coordinates design and plans waves"
)

#######################################
# Get manager for a phase
#######################################
get_phase_manager() {
    local phase="$1"
    phase=$(echo "$phase" | tr '[:upper:]' '[:lower:]')
    echo "${PHASE_MANAGERS[$phase]:-Hephaestus}"
}

#######################################
# Check if issue is an EPIC
#######################################
is_epic_issue() {
    local issue_num="$1"
    local labels=$(gh issue view "$issue_num" --json labels --jq '.labels[].name' 2>/dev/null)

    if echo "$labels" | grep -qi "epic"; then
        return 0
    fi
    return 1
}

#######################################
# Get current phase from issue labels
#######################################
get_issue_phase() {
    local issue_num="$1"
    local labels=$(gh issue view "$issue_num" --json labels --jq '.labels[].name' 2>/dev/null)

    if echo "$labels" | grep -q "phase:review"; then
        echo "review"
    elif echo "$labels" | grep -q "phase:test"; then
        echo "test"
    elif echo "$labels" | grep -q "phase:dev"; then
        echo "dev"
    else
        echo "dev"  # Default to dev
    fi
}

#######################################
# Create first post template
#######################################
create_first_post() {
    local issue_num="$1"
    local phase="$2"
    local requirements="$3"
    local manager=$(get_phase_manager "$phase")
    local avatar_url=$(get_avatar_url "$manager")
    local role="${MANAGER_ROLES[$manager]}"

    local template="<img src=\"${avatar_url}\" width=\"77\" align=\"left\"/>

**${manager}** - ${role}
<br><br>

## Requirements

${requirements}

---

## Changelog (DEV)

_No entries yet_

---

## Test Log (TEST)

_Phase not started_

---

## Review Log (REVIEW)

_Phase not started_

---

_Last updated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")_"

    echo "$template"
}

#######################################
# Update first post with new manager (phase transition)
#######################################
update_first_post_manager() {
    local issue_num="$1"
    local new_phase="$2"
    local new_manager=$(get_phase_manager "$new_phase")
    local avatar_url=$(get_avatar_url "$new_manager")
    local role="${MANAGER_ROLES[$new_manager]}"

    # Get current first post (issue body)
    local current_body=$(gh issue view "$issue_num" --json body --jq '.body')

    # Replace avatar and manager name in first line
    # Pattern: <img src="..." .../>
    local new_header="<img src=\"${avatar_url}\" width=\"77\" align=\"left\"/>

**${new_manager}** - ${role}
<br><br>"

    # Extract everything after the header (from ## Requirements onwards)
    local content_after_header=$(echo "$current_body" | sed -n '/^## Requirements/,$p')

    # Combine new header with existing content
    local new_body="${new_header}

${content_after_header}"

    # Update the issue body
    gh issue edit "$issue_num" --body "$new_body"

    echo -e "${GREEN}Updated thread manager to ${new_manager} for issue #${issue_num}${NC}"
}

#######################################
# Add changelog entry
#######################################
add_changelog_entry() {
    local issue_num="$1"
    local entry="$2"
    local comment_id="$3"  # Optional link to comment

    local timestamp=$(date -u +"%Y-%m-%d %H:%M")
    local link_text=""

    if [[ -n "$comment_id" ]]; then
        local repo=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
        link_text=" → [details](https://github.com/${repo}/issues/${issue_num}#issuecomment-${comment_id})"
    fi

    local new_entry="- [${timestamp}] ${entry}${link_text}"

    # Get current body
    local current_body=$(gh issue view "$issue_num" --json body --jq '.body')

    # Insert entry after "## Changelog (DEV)" line, before the next ---
    # Replace "_No entries yet_" if present
    if echo "$current_body" | grep -q "_No entries yet_"; then
        current_body=$(echo "$current_body" | sed "s/_No entries yet_/${new_entry}/")
    else
        # Add after existing entries in changelog section
        current_body=$(echo "$current_body" | sed "/^## Changelog (DEV)/,/^---/{
            /^---/i\\
${new_entry}
        }")
    fi

    # Update timestamp
    current_body=$(echo "$current_body" | sed "s/_Last updated:.*/_Last updated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")_/")

    gh issue edit "$issue_num" --body "$current_body"
    echo "Added changelog entry to issue #${issue_num}"
}

#######################################
# Add test log entry
#######################################
add_testlog_entry() {
    local issue_num="$1"
    local entry="$2"
    local comment_id="$3"

    local timestamp=$(date -u +"%Y-%m-%d %H:%M")
    local link_text=""

    if [[ -n "$comment_id" ]]; then
        local repo=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
        link_text=" → [details](https://github.com/${repo}/issues/${issue_num}#issuecomment-${comment_id})"
    fi

    local new_entry="- [${timestamp}] ${entry}${link_text}"

    local current_body=$(gh issue view "$issue_num" --json body --jq '.body')

    # Replace "_Phase not started_" in test section
    if echo "$current_body" | grep -A1 "## Test Log" | grep -q "_Phase not started_"; then
        current_body=$(echo "$current_body" | sed "/## Test Log/,/^---/{s/_Phase not started_/${new_entry}/}")
    else
        current_body=$(echo "$current_body" | sed "/^## Test Log (TEST)/,/^---/{
            /^---/i\\
${new_entry}
        }")
    fi

    current_body=$(echo "$current_body" | sed "s/_Last updated:.*/_Last updated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")_/")

    gh issue edit "$issue_num" --body "$current_body"
    echo "Added test log entry to issue #${issue_num}"
}

#######################################
# Add review log entry
#######################################
add_reviewlog_entry() {
    local issue_num="$1"
    local entry="$2"
    local comment_id="$3"

    local timestamp=$(date -u +"%Y-%m-%d %H:%M")
    local link_text=""

    if [[ -n "$comment_id" ]]; then
        local repo=$(gh repo view --json nameWithOwner --jq '.nameWithOwner')
        link_text=" → [details](https://github.com/${repo}/issues/${issue_num}#issuecomment-${comment_id})"
    fi

    local new_entry="- [${timestamp}] ${entry}${link_text}"

    local current_body=$(gh issue view "$issue_num" --json body --jq '.body')

    if echo "$current_body" | grep -A1 "## Review Log" | grep -q "_Phase not started_"; then
        current_body=$(echo "$current_body" | sed "/## Review Log/,/^---/{s/_Phase not started_/${new_entry}/}")
    else
        current_body=$(echo "$current_body" | sed "/^## Review Log (REVIEW)/,/^---/{
            /^---/i\\
${new_entry}
        }")
    fi

    current_body=$(echo "$current_body" | sed "s/_Last updated:.*/_Last updated: $(date -u +"%Y-%m-%d %H:%M:%S UTC")_/")

    gh issue edit "$issue_num" --body "$current_body"
    echo "Added review log entry to issue #${issue_num}"
}

#######################################
# Initialize thread with first post
#######################################
init_thread() {
    local issue_num="$1"
    local requirements="${2:-No requirements specified}"

    # Check if epic
    if is_epic_issue "$issue_num"; then
        local phase="epic"
    else
        local phase=$(get_issue_phase "$issue_num")
    fi

    local first_post=$(create_first_post "$issue_num" "$phase" "$requirements")

    # Update the issue body with the first post template
    gh issue edit "$issue_num" --body "$first_post"

    local manager=$(get_phase_manager "$phase")
    echo -e "${GREEN}Initialized thread #${issue_num} with ${manager} as manager${NC}"
}

#######################################
# Transition phase and update manager
#######################################
transition_phase() {
    local issue_num="$1"
    local new_phase="$2"

    # Update labels
    local old_phase=$(get_issue_phase "$issue_num")
    gh issue edit "$issue_num" --remove-label "phase:${old_phase}" 2>/dev/null || true
    gh issue edit "$issue_num" --add-label "phase:${new_phase}"

    # Update first post manager
    update_first_post_manager "$issue_num" "$new_phase"

    local new_manager=$(get_phase_manager "$new_phase")
    echo -e "${GREEN}Transitioned issue #${issue_num} from ${old_phase} to ${new_phase}${NC}"
    echo -e "${GREEN}New thread manager: ${new_manager}${NC}"
}

#######################################
# Get appropriate agent for posting based on phase
# Athena ONLY for epic threads
#######################################
get_posting_agent() {
    local issue_num="$1"

    if is_epic_issue "$issue_num"; then
        echo "Athena"
    else
        local phase=$(get_issue_phase "$issue_num")
        get_phase_manager "$phase"
    fi
}

#######################################
# CLI interface
#######################################
case "${1:-}" in
    "init")
        init_thread "$2" "$3"
        ;;
    "transition")
        transition_phase "$2" "$3"
        ;;
    "add-changelog")
        add_changelog_entry "$2" "$3" "$4"
        ;;
    "add-testlog")
        add_testlog_entry "$2" "$3" "$4"
        ;;
    "add-reviewlog")
        add_reviewlog_entry "$2" "$3" "$4"
        ;;
    "get-manager")
        get_phase_manager "$2"
        ;;
    "get-posting-agent")
        get_posting_agent "$2"
        ;;
    "is-epic")
        if is_epic_issue "$2"; then
            echo "true"
        else
            echo "false"
        fi
        ;;
    "update-manager")
        update_first_post_manager "$2" "$3"
        ;;
    *)
        echo "Usage: $0 {init|transition|add-changelog|add-testlog|add-reviewlog|get-manager|get-posting-agent|is-epic|update-manager}"
        echo ""
        echo "Commands:"
        echo "  init <issue> [requirements]     Initialize thread with first post template"
        echo "  transition <issue> <phase>      Transition to new phase (dev/test/review)"
        echo "  add-changelog <issue> <entry> [comment_id]   Add changelog entry"
        echo "  add-testlog <issue> <entry> [comment_id]     Add test log entry"
        echo "  add-reviewlog <issue> <entry> [comment_id]   Add review log entry"
        echo "  get-manager <phase>             Get manager name for phase"
        echo "  get-posting-agent <issue>       Get appropriate agent for posting"
        echo "  is-epic <issue>                 Check if issue is an epic"
        echo "  update-manager <issue> <phase>  Update first post manager avatar"
        echo ""
        echo "Phase managers:"
        echo "  dev    -> Hephaestus (builds and shapes)"
        echo "  test   -> Artemis (hunts bugs)"
        echo "  review -> Hera (evaluates quality)"
        echo "  epic   -> Athena (coordinates design)"
        exit 1
        ;;
esac
