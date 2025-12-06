#!/bin/bash
# check-review-ready.sh - Check for background threads ready for user review
#
# This script is called by Claude to check if any background feature/bug
# threads have reached the REVIEW phase and are waiting for user participation.
#
# When a thread is ready, Claude should ask the user if they want to:
# 1. Temporarily pause the main conversation
# 2. Join the feature thread to participate in review with Hera
#
# Usage:
#   check-review-ready.sh           # List all review-ready threads
#   check-review-ready.sh --json    # Output as JSON
#   check-review-ready.sh --notify  # Generate notification message

set -e

MODE="${1:-list}"

# Source shared library
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/ghe-common.sh"

# Initialize GHE environment
ghe_init

# Use library-provided directories and colors
THREADS_FILE="${GHE_REPO_ROOT}/.claude/ghe-background-threads.json"
GREEN="${GHE_GREEN}"
YELLOW="${GHE_YELLOW}"
CYAN='\033[0;36m'
NC="${GHE_NC}"

# Check threads file
if [[ ! -f "$THREADS_FILE" ]]; then
    if [[ "$MODE" == "--json" ]]; then
        echo '{"review_ready": [], "count": 0}'
    else
        echo "No background threads tracked."
    fi
    exit 0
fi

# Find threads in REVIEW phase
REVIEW_THREADS=$(jq -r '.threads[] | select(.status == "active" and .phase == "REVIEW")' "$THREADS_FILE" 2>/dev/null)

if [[ -z "$REVIEW_THREADS" ]]; then
    # Also check GitHub directly for phase:review labels
    REVIEW_ISSUES=$(gh issue list --label "phase:review" --state open --json number,title 2>/dev/null || echo "[]")
    REVIEW_COUNT=$(echo "$REVIEW_ISSUES" | jq 'length')

    if [[ "$REVIEW_COUNT" -eq 0 ]]; then
        if [[ "$MODE" == "--json" ]]; then
            echo '{"review_ready": [], "count": 0}'
        else
            echo "No threads ready for review."
        fi
        exit 0
    fi

    # Use GitHub data
    if [[ "$MODE" == "--json" ]]; then
        echo "$REVIEW_ISSUES" | jq '{review_ready: ., count: length}'
    elif [[ "$MODE" == "--notify" ]]; then
        MAIN_ISSUE=$(ghe_get_setting "current_issue" "")
        echo ""
        echo -e "${YELLOW}========================================${NC}"
        echo -e "${YELLOW}   FEATURE(S) READY FOR REVIEW!${NC}"
        echo -e "${YELLOW}========================================${NC}"
        echo ""
        echo "$REVIEW_ISSUES" | jq -r '.[] | "  Issue #\(.number): \(.title)"'
        echo ""
        echo "These features have completed DEV and TEST phases."
        echo "Hera is conducting the review and may need your input."
        echo ""
        echo "Would you like to:"
        echo "  1. Temporarily pause our conversation (#$MAIN_ISSUE)"
        echo "  2. Join a feature thread to participate in the review"
        echo ""
        echo "To switch: \"join review for #<issue-number>\""
        echo ""
    else
        echo -e "${GREEN}Threads ready for review:${NC}"
        echo "$REVIEW_ISSUES" | jq -r '.[] | "  #\(.number): \(.title)"'
    fi
    exit 0
fi

# Process from threads file
REVIEW_COUNT=$(echo "$REVIEW_THREADS" | jq -s 'length')

case "$MODE" in
    "--json")
        echo "$REVIEW_THREADS" | jq -s '{review_ready: ., count: length}'
        ;;

    "--notify")
        MAIN_ISSUE=$(ghe_get_setting "current_issue" "")
        echo ""
        echo -e "${YELLOW}========================================${NC}"
        echo -e "${YELLOW}   FEATURE(S) READY FOR REVIEW!${NC}"
        echo -e "${YELLOW}========================================${NC}"
        echo ""
        echo "$REVIEW_THREADS" | jq -r '"  Issue #\(.issue): \(.title)"'
        echo ""
        echo "These features have completed DEV and TEST phases."
        echo "Hera is conducting the review and may need your input."
        echo ""
        if [[ -n "$MAIN_ISSUE" && "$MAIN_ISSUE" != "null" ]]; then
            echo "Currently in main conversation: #$MAIN_ISSUE"
            echo ""
            echo "Would you like to:"
            echo "  1. Temporarily pause our conversation"
            echo "  2. Join a feature thread to participate in the review"
            echo ""
        fi
        echo "To switch: \"join review for #<issue-number>\""
        echo ""
        ;;

    *)
        echo -e "${GREEN}Threads ready for review:${NC}"
        echo "$REVIEW_THREADS" | jq -r '"  #\(.issue): \(.title) (parent: #\(.parent_issue // "none"))"'
        echo ""
        echo "Total: $REVIEW_COUNT thread(s)"
        ;;
esac
