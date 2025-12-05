#!/bin/bash
# create-feature-thread.sh - Create a new feature/bug thread and spawn agents
#
# This script handles the creation of BACKGROUND feature/bug development threads.
# These are SEPARATE from the main conversation thread (user + Claude).
#
# Flow:
# 1. Create new GitHub issue for the feature/bug
# 2. Athena posts REQUIREMENTS as the FIRST comment
# 3. Spawn Hephaestus (DEV) to start implementation
# 4. Track the thread in background_threads.json
# 5. Return thread info to main conversation
#
# Usage:
#   create-feature-thread.sh feature "Title" "Description" [parent-issue]
#   create-feature-thread.sh bug "Title" "Description" [parent-issue]
#
# Example:
#   create-feature-thread.sh feature "Add dark mode" "User requested dark mode toggle" 42

set -e

THREAD_TYPE="${1:-feature}"  # feature or bug
TITLE="${2:-}"
DESCRIPTION="${3:-}"
PARENT_ISSUE="${4:-}"  # The main conversation issue

if [[ -z "$TITLE" ]]; then
    echo "ERROR: Title required"
    echo "Usage: create-feature-thread.sh <feature|bug> \"Title\" \"Description\" [parent-issue]"
    exit 1
fi

# Paths
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
CONFIG_PATH="$PROJECT_ROOT/.claude/ghe.local.md"
THREADS_FILE="$PROJECT_ROOT/.claude/ghe-background-threads.json"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
TIMESTAMP_SHORT=$(date +%Y%m%d_%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Config helpers
get_config() {
    local key="$1"
    local default="$2"
    if [[ -f "$CONFIG_PATH" ]]; then
        local value=$(sed -n '/^---$/,/^---$/p' "$CONFIG_PATH" | grep "^${key}:" | head -1 | sed 's/^[^:]*: *//' | tr -d '"' | tr -d "'")
        echo "${value:-$default}"
    else
        echo "$default"
    fi
}

# Ensure threads tracking file exists
ensure_threads_file() {
    if [[ ! -f "$THREADS_FILE" ]]; then
        echo '{"threads": [], "last_updated": ""}' > "$THREADS_FILE"
    fi
}

# Add thread to tracking
add_thread() {
    local issue_num="$1"
    local thread_type="$2"
    local title="$3"
    local parent="$4"
    local phase="$5"

    ensure_threads_file

    # Use jq to add thread
    local tmp_file=$(mktemp)
    jq --arg num "$issue_num" \
       --arg type "$thread_type" \
       --arg title "$title" \
       --arg parent "$parent" \
       --arg phase "$phase" \
       --arg time "$TIMESTAMP" \
       '.threads += [{
           "issue": ($num | tonumber),
           "type": $type,
           "title": $title,
           "parent_issue": (if $parent == "" then null else ($parent | tonumber) end),
           "phase": $phase,
           "status": "active",
           "created": $time,
           "updated": $time
       }] | .last_updated = $time' "$THREADS_FILE" > "$tmp_file"
    mv "$tmp_file" "$THREADS_FILE"
}

# Update thread status
update_thread() {
    local issue_num="$1"
    local phase="$2"
    local status="${3:-active}"

    ensure_threads_file

    local tmp_file=$(mktemp)
    jq --arg num "$issue_num" \
       --arg phase "$phase" \
       --arg status "$status" \
       --arg time "$TIMESTAMP" \
       '(.threads[] | select(.issue == ($num | tonumber))) |= . + {
           "phase": $phase,
           "status": $status,
           "updated": $time
       } | .last_updated = $time' "$THREADS_FILE" > "$tmp_file"
    mv "$tmp_file" "$THREADS_FILE"
}

# Get active threads
get_active_threads() {
    ensure_threads_file
    jq -r '.threads[] | select(.status == "active") | "Issue #\(.issue): \(.title) [\(.phase)]"' "$THREADS_FILE"
}

echo -e "${CYAN}Creating $THREAD_TYPE thread: $TITLE${NC}"

# Determine label based on type
case "$THREAD_TYPE" in
    "feature"|"enhancement")
        TYPE_LABEL="enhancement"
        ;;
    "bug"|"fix")
        TYPE_LABEL="bug"
        ;;
    *)
        TYPE_LABEL="enhancement"
        ;;
esac

# Create the GitHub issue
echo "Creating GitHub issue..."

# Build body with link to parent if exists
BODY="## Overview

$DESCRIPTION

---
**Thread Type**: $THREAD_TYPE
**Created**: $TIMESTAMP
"

if [[ -n "$PARENT_ISSUE" ]]; then
    BODY+="**Parent Conversation**: #$PARENT_ISSUE
"
fi

BODY+="
---
*This is a background development thread managed by GHE agents.*
*Requirements will be posted by Athena below.*"

# Create issue
NEW_ISSUE=$(gh issue create \
    --title "$TITLE" \
    --body "$BODY" \
    --label "$TYPE_LABEL" \
    --label "phase:dev" \
    --json number \
    --jq '.number' 2>/dev/null)

if [[ -z "$NEW_ISSUE" ]]; then
    echo -e "${RED}ERROR: Failed to create GitHub issue${NC}"
    exit 1
fi

echo -e "${GREEN}Created issue #$NEW_ISSUE${NC}"

# Add to tracking
add_thread "$NEW_ISSUE" "$THREAD_TYPE" "$TITLE" "$PARENT_ISSUE" "REQUIREMENTS"

# Create worktree for the feature
WORKTREE_BASE="../ghe-worktrees"
WORKTREE_PATH="$WORKTREE_BASE/issue-$NEW_ISSUE"
BRANCH_NAME="issue-$NEW_ISSUE-dev"

echo "Creating worktree..."
mkdir -p "$WORKTREE_BASE"

if git show-ref --verify --quiet "refs/heads/$BRANCH_NAME" 2>/dev/null; then
    git worktree add "$WORKTREE_PATH" "$BRANCH_NAME" 2>/dev/null || true
else
    local base_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
    git worktree add "$WORKTREE_PATH" -b "$BRANCH_NAME" "$base_branch" 2>/dev/null || true
fi

if [[ -d "$WORKTREE_PATH" ]]; then
    echo -e "${GREEN}Worktree created: $WORKTREE_PATH${NC}"
fi

# Post Athena's requirements as FIRST comment
echo "Spawning Athena to write requirements..."

# Build Athena's prompt for requirements generation
ATHENA_PROMPT="You are Athena, the GHE orchestrator.

## CRITICAL TASK: Write Requirements

You MUST write the REQUIREMENTS for issue #$NEW_ISSUE as the FIRST substantive comment.

**Issue**: #$NEW_ISSUE
**Type**: $THREAD_TYPE
**Title**: $TITLE
**Description**: $DESCRIPTION
**Parent Conversation**: ${PARENT_ISSUE:-none}

## Requirements Format

Post a comment to issue #$NEW_ISSUE with this structure:

\`\`\`bash
# Load avatar helper
source \"${PLUGIN_ROOT}/scripts/post-with-avatar.sh\"

# Get header
HEADER=\$(avatar_header \"Athena\")

# Post requirements
gh issue comment $NEW_ISSUE --body \"\${HEADER}
## Requirements for: $TITLE

### 1. Overview
[Brief description of what this $THREAD_TYPE will accomplish]

### 2. User Story
**As a** [user type], **I want** [goal], **so that** [benefit].

### 3. Acceptance Criteria
- [ ] **AC-1**: [First criterion]
- [ ] **AC-2**: [Second criterion]
- [ ] **AC-3**: [Third criterion]

### 4. Technical Requirements
#### 4.1 Functional
- **FR-1**: [Functional requirement]

#### 4.2 Non-Functional
- **NFR-1**: [Non-functional requirement]

### 5. Scope
#### In Scope
- [What IS included]

#### Out of Scope
- [What is NOT included]

### 6. Dependencies
- [List any dependencies]

### 7. Test Requirements
- **TEST-1**: [What must be tested]

---
*Requirements written by Athena (Orchestrator)*
*Hephaestus will begin DEV phase after requirements are posted.*
\"
\`\`\`

After posting requirements, call:
\`\`\`bash
bash \"${PLUGIN_ROOT}/scripts/agent-request-spawn.sh\" dev-thread-manager $NEW_ISSUE \"Requirements complete, begin DEV\"
\`\`\`

## Output
Save your work to: agents_reports/requirements_${NEW_ISSUE}_${TIMESTAMP_SHORT}.md"

# Spawn Athena in background
bash "$SCRIPT_DIR/spawn_background.sh" "$ATHENA_PROMPT" "$PROJECT_ROOT"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Feature Thread Created!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "Issue:       ${CYAN}#$NEW_ISSUE${NC}"
echo -e "Title:       $TITLE"
echo -e "Type:        $THREAD_TYPE"
echo -e "Worktree:    $WORKTREE_PATH"
echo -e "Branch:      $BRANCH_NAME"
echo ""
echo "Workflow:"
echo "  1. Athena is writing requirements (spawned)"
echo "  2. Hephaestus will begin DEV after requirements"
echo "  3. Artemis will run TEST after DEV"
echo "  4. Hera will conduct REVIEW after TEST"
echo ""
if [[ -n "$PARENT_ISSUE" ]]; then
    echo -e "Linked to conversation: ${CYAN}#$PARENT_ISSUE${NC}"
fi
echo ""
echo "Track progress: gh issue view $NEW_ISSUE --comments"
echo ""

# Output JSON for programmatic use
echo "{\"issue\": $NEW_ISSUE, \"title\": \"$TITLE\", \"type\": \"$THREAD_TYPE\", \"worktree\": \"$WORKTREE_PATH\", \"branch\": \"$BRANCH_NAME\"}"
