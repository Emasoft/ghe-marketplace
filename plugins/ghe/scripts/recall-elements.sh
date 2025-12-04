#!/bin/bash
# recall-elements.sh - Element-based memory recall from GitHub Issues
# Part of GitHub Elements (GHE) plugin
#
# Usage:
#   recall-elements.sh --issue NUM --type knowledge|action|judgement [--last N] [--search PATTERN]
#   recall-elements.sh --issue NUM --stats
#   recall-elements.sh --issue NUM --recover
#   recall-elements.sh --issue NUM --compound "knowledge+action"
#
# Element Types:
#   knowledge - Requirements, specs, design, algorithms, explanations
#   action    - Code, diffs, implementations, file changes
#   judgement - Bugs, reviews, feedback, issues, verdicts

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
ORANGE='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Badge patterns for searching
PATTERN_KNOWLEDGE="element-knowledge"
PATTERN_ACTION="element-action"
PATTERN_JUDGEMENT="element-judgement"

# Default values
ISSUE=""
TYPE=""
LAST_N=0
SEARCH_PATTERN=""
STATS_MODE=false
RECOVER_MODE=false
COMPOUND=""

# Print usage
usage() {
    cat <<'EOF'
recall-elements.sh - Element-based memory recall from GitHub Issues

USAGE:
  recall-elements.sh --issue NUM --type TYPE [OPTIONS]
  recall-elements.sh --issue NUM --stats
  recall-elements.sh --issue NUM --recover
  recall-elements.sh --issue NUM --compound "type1+type2"

ELEMENT TYPES:
  knowledge   Requirements, specs, design, algorithms, explanations (blue)
  action      Code, diffs, implementations, file changes (green)
  judgement   Bugs, reviews, feedback, issues, verdicts (orange)

OPTIONS:
  --issue NUM       Issue number to query (required)
  --type TYPE       Element type to recall (knowledge|action|judgement)
  --last N          Return only the last N elements of the type
  --search PATTERN  Filter elements containing PATTERN (case-insensitive)
  --stats           Show element distribution statistics
  --recover         Smart recovery mode - show context for resuming work
  --compound TYPE   Get elements with multiple badges (e.g., "knowledge+action")
  --help, -h        Show this help message

EXAMPLES:
  # Get all KNOWLEDGE elements from issue #201
  recall-elements.sh --issue 201 --type knowledge

  # Get last 5 ACTION elements
  recall-elements.sh --issue 201 --type action --last 5

  # Search for JWT-related JUDGEMENT elements
  recall-elements.sh --issue 201 --type judgement --search "jwt"

  # Show element statistics
  recall-elements.sh --issue 201 --stats

  # Smart recovery for resuming work
  recall-elements.sh --issue 201 --recover

  # Get compound elements (both knowledge and action)
  recall-elements.sh --issue 201 --compound "knowledge+action"

RECALL DECISION GUIDE:
  "What code did we write?"        → --type action
  "What were the requirements?"    → --type knowledge
  "What bugs did we find?"         → --type judgement
  "What issues remain?"            → --type judgement
  "What was the design?"           → --type knowledge
  "Show implementation"            → --type action
  "What feedback was given?"       → --type judgement
  "Full context"                   → --recover
EOF
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --issue)
                ISSUE="$2"
                shift 2
                ;;
            --type)
                TYPE="$2"
                shift 2
                ;;
            --last)
                LAST_N="$2"
                shift 2
                ;;
            --search)
                SEARCH_PATTERN="$2"
                shift 2
                ;;
            --stats)
                STATS_MODE=true
                shift
                ;;
            --recover)
                RECOVER_MODE=true
                shift
                ;;
            --compound)
                COMPOUND="$2"
                shift 2
                ;;
            --help|-h)
                usage
                exit 0
                ;;
            *)
                echo -e "${RED}Error: Unknown option $1${NC}" >&2
                usage
                exit 1
                ;;
        esac
    done
}

# Validate arguments
validate_args() {
    if [[ -z "$ISSUE" ]]; then
        echo -e "${RED}Error: --issue is required${NC}" >&2
        usage
        exit 1
    fi

    if [[ ! "$ISSUE" =~ ^[0-9]+$ ]]; then
        echo -e "${RED}Error: Issue must be a number${NC}" >&2
        exit 1
    fi

    if [[ -n "$TYPE" ]] && [[ ! "$TYPE" =~ ^(knowledge|action|judgement)$ ]]; then
        echo -e "${RED}Error: Invalid type. Use: knowledge, action, or judgement${NC}" >&2
        exit 1
    fi

    # Check that at least one mode is specified
    if [[ -z "$TYPE" ]] && [[ "$STATS_MODE" != "true" ]] && [[ "$RECOVER_MODE" != "true" ]] && [[ -z "$COMPOUND" ]]; then
        echo -e "${RED}Error: Specify --type, --stats, --recover, or --compound${NC}" >&2
        usage
        exit 1
    fi
}

# Get pattern for element type
get_pattern() {
    local type="$1"
    case "$type" in
        knowledge) echo "$PATTERN_KNOWLEDGE" ;;
        action) echo "$PATTERN_ACTION" ;;
        judgement) echo "$PATTERN_JUDGEMENT" ;;
    esac
}

# Get color for element type
get_color() {
    local type="$1"
    case "$type" in
        knowledge) echo "$BLUE" ;;
        action) echo "$GREEN" ;;
        judgement) echo "$ORANGE" ;;
        *) echo "$NC" ;;
    esac
}

# Show element statistics
show_stats() {
    echo -e "${BOLD}${CYAN}GitHub Elements Statistics: Issue #${ISSUE}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    local stats
    stats=$(gh issue view "$ISSUE" --comments --json comments --jq '
        {
            total: .comments | length,
            knowledge: [.comments[] | select(.body | contains("element-knowledge"))] | length,
            action: [.comments[] | select(.body | contains("element-action"))] | length,
            judgement: [.comments[] | select(.body | contains("element-judgement"))] | length,
            compound: [.comments[] | select(
                ((.body | contains("element-knowledge")) and (.body | contains("element-action"))) or
                ((.body | contains("element-knowledge")) and (.body | contains("element-judgement"))) or
                ((.body | contains("element-action")) and (.body | contains("element-judgement")))
            )] | length
        }
    ')

    local total knowledge action judgement compound
    total=$(echo "$stats" | jq -r '.total')
    knowledge=$(echo "$stats" | jq -r '.knowledge')
    action=$(echo "$stats" | jq -r '.action')
    judgement=$(echo "$stats" | jq -r '.judgement')
    compound=$(echo "$stats" | jq -r '.compound')

    # Calculate percentages
    local k_pct a_pct j_pct
    if [[ "$total" -gt 0 ]]; then
        k_pct=$((knowledge * 100 / total))
        a_pct=$((action * 100 / total))
        j_pct=$((judgement * 100 / total))
    else
        k_pct=0
        a_pct=0
        j_pct=0
    fi

    # Display counts with visual bars
    echo -e "${BOLD}Element Distribution:${NC}"
    echo ""
    printf "  ${BLUE}KNOWLEDGE${NC}  %-3s " "$knowledge"
    printf "${BLUE}"
    for ((i=0; i<k_pct/5; i++)); do printf "█"; done
    printf "${NC}"
    for ((i=k_pct/5; i<20; i++)); do printf "░"; done
    printf " %d%%\n" "$k_pct"

    printf "  ${GREEN}ACTION${NC}     %-3s " "$action"
    printf "${GREEN}"
    for ((i=0; i<a_pct/5; i++)); do printf "█"; done
    printf "${NC}"
    for ((i=a_pct/5; i<20; i++)); do printf "░"; done
    printf " %d%%\n" "$a_pct"

    printf "  ${ORANGE}JUDGEMENT${NC}  %-3s " "$judgement"
    printf "${ORANGE}"
    for ((i=0; i<j_pct/5; i++)); do printf "█"; done
    printf "${NC}"
    for ((i=j_pct/5; i<20; i++)); do printf "░"; done
    printf " %d%%\n" "$j_pct"

    echo ""
    echo -e "${BOLD}Summary:${NC}"
    echo -e "  Total comments:    $total"
    echo -e "  Compound elements: $compound (multi-badge)"
    echo ""
}

# Query elements by type
query_by_type() {
    local type="$1"
    local pattern
    pattern=$(get_pattern "$type")
    local color
    color=$(get_color "$type")

    echo -e "${BOLD}${color}Recalling ${type^^} elements from Issue #${ISSUE}${NC}"
    echo -e "${color}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    local jq_filter

    # Build jq filter
    if [[ -n "$SEARCH_PATTERN" ]]; then
        # Case-insensitive search within element type
        jq_filter="[.comments[] | select(.body | contains(\"$pattern\")) | select(.body | ascii_downcase | contains(\"$(echo "$SEARCH_PATTERN" | tr '[:upper:]' '[:lower:]')\"))]"
    else
        jq_filter="[.comments[] | select(.body | contains(\"$pattern\"))]"
    fi

    # Add sorting and limiting
    jq_filter="$jq_filter | sort_by(.createdAt)"

    if [[ "$LAST_N" -gt 0 ]]; then
        jq_filter="$jq_filter | .[-${LAST_N}:]"
    fi

    # Format output
    jq_filter="$jq_filter | .[] | {date: .createdAt, author: .author.login, body: .body}"

    local results
    results=$(gh issue view "$ISSUE" --comments --json comments --jq "$jq_filter")

    if [[ -z "$results" ]]; then
        echo -e "${YELLOW}No ${type} elements found${NC}"
        if [[ -n "$SEARCH_PATTERN" ]]; then
            echo -e "${YELLOW}(searched for: \"$SEARCH_PATTERN\")${NC}"
        fi
        return
    fi

    # Parse and display results
    echo "$results" | jq -r '
        "┌──────────────────────────────────────────────────────────────┐",
        "│ \(.date | split("T")[0]) │ @\(.author)",
        "├──────────────────────────────────────────────────────────────┤",
        (.body | split("\n")[0:15] | .[] | "│ \(.)"),
        "└──────────────────────────────────────────────────────────────┘",
        ""
    '
}

# Query compound elements (multiple badges)
query_compound() {
    local types="$1"

    echo -e "${BOLD}${CYAN}Recalling COMPOUND elements (${types}) from Issue #${ISSUE}${NC}"
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""

    # Parse compound type
    local conditions=""
    if [[ "$types" == *"knowledge"* ]]; then
        conditions="(.body | contains(\"$PATTERN_KNOWLEDGE\"))"
    fi
    if [[ "$types" == *"action"* ]]; then
        if [[ -n "$conditions" ]]; then
            conditions="$conditions and (.body | contains(\"$PATTERN_ACTION\"))"
        else
            conditions="(.body | contains(\"$PATTERN_ACTION\"))"
        fi
    fi
    if [[ "$types" == *"judgement"* ]]; then
        if [[ -n "$conditions" ]]; then
            conditions="$conditions and (.body | contains(\"$PATTERN_JUDGEMENT\"))"
        else
            conditions="(.body | contains(\"$PATTERN_JUDGEMENT\"))"
        fi
    fi

    local jq_filter="[.comments[] | select($conditions)] | sort_by(.createdAt)"

    if [[ "$LAST_N" -gt 0 ]]; then
        jq_filter="$jq_filter | .[-${LAST_N}:]"
    fi

    jq_filter="$jq_filter | .[] | {date: .createdAt, author: .author.login, body: .body}"

    local results
    results=$(gh issue view "$ISSUE" --comments --json comments --jq "$jq_filter")

    if [[ -z "$results" ]]; then
        echo -e "${YELLOW}No compound elements found matching: $types${NC}"
        return
    fi

    echo "$results" | jq -r '
        "┌──────────────────────────────────────────────────────────────┐",
        "│ \(.date | split("T")[0]) │ @\(.author)",
        "├──────────────────────────────────────────────────────────────┤",
        (.body | split("\n")[0:15] | .[] | "│ \(.)"),
        "└──────────────────────────────────────────────────────────────┘",
        ""
    '
}

# Smart recovery mode
smart_recover() {
    echo -e "${BOLD}${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BOLD}${CYAN}║         GHE SMART RECOVERY: Issue #${ISSUE}                         ║${NC}"
    echo -e "${BOLD}${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""

    # 1. Show statistics first
    show_stats

    # 2. Get first KNOWLEDGE (original context)
    echo -e "${BOLD}${BLUE}═══ ORIGINAL CONTEXT (First Knowledge Element) ═══${NC}"
    echo ""

    local first_knowledge
    first_knowledge=$(gh issue view "$ISSUE" --comments --json comments --jq '
        [.comments[] | select(.body | contains("element-knowledge"))] |
        first |
        if . then
            "Date: \(.createdAt | split("T")[0])\nAuthor: @\(.author.login)\n\n\(.body | split("\n")[0:20] | join("\n"))"
        else
            "No knowledge elements found"
        end
    ')

    if [[ -n "$first_knowledge" && "$first_knowledge" != "null" ]]; then
        echo -e "${BLUE}$first_knowledge${NC}"
    else
        echo -e "${YELLOW}No knowledge elements found${NC}"
    fi
    echo ""

    # 3. Get last ACTION (current state)
    echo -e "${BOLD}${GREEN}═══ CURRENT STATE (Last Action Element) ═══${NC}"
    echo ""

    local last_action
    last_action=$(gh issue view "$ISSUE" --comments --json comments --jq '
        [.comments[] | select(.body | contains("element-action"))] |
        last |
        if . then
            "Date: \(.createdAt | split("T")[0])\nAuthor: @\(.author.login)\n\n\(.body | split("\n")[0:25] | join("\n"))"
        else
            "No action elements found"
        end
    ')

    if [[ -n "$last_action" && "$last_action" != "null" ]]; then
        echo -e "${GREEN}$last_action${NC}"
    else
        echo -e "${YELLOW}No action elements found${NC}"
    fi
    echo ""

    # 4. Get recent JUDGEMENT (open issues)
    echo -e "${BOLD}${ORANGE}═══ OPEN ISSUES (Recent Judgement Elements) ═══${NC}"
    echo ""

    local recent_judgements
    recent_judgements=$(gh issue view "$ISSUE" --comments --json comments --jq '
        [.comments[] | select(.body | contains("element-judgement"))] |
        .[-3:] |
        .[] |
        "┌─ \(.createdAt | split("T")[0]) │ @\(.author.login)\n\(.body | split("\n")[0:10] | .[] | "│ \(.)")\n└─────────────────────────────────"
    ')

    if [[ -n "$recent_judgements" ]]; then
        echo -e "${ORANGE}$recent_judgements${NC}"
    else
        echo -e "${YELLOW}No judgement elements found${NC}"
    fi
    echo ""

    # 5. Recommended next action
    echo -e "${BOLD}${CYAN}═══ RECOMMENDED NEXT ACTION ═══${NC}"
    echo ""

    # Analyze what to do next based on elements
    local action_count knowledge_count judgement_count
    action_count=$(gh issue view "$ISSUE" --comments --json comments --jq '[.comments[] | select(.body | contains("element-action"))] | length')
    knowledge_count=$(gh issue view "$ISSUE" --comments --json comments --jq '[.comments[] | select(.body | contains("element-knowledge"))] | length')
    judgement_count=$(gh issue view "$ISSUE" --comments --json comments --jq '[.comments[] | select(.body | contains("element-judgement"))] | length')

    if [[ "$judgement_count" -gt 0 ]]; then
        echo -e "1. ${ORANGE}Address recent judgements${NC} - There are $judgement_count issues/feedback to review"
    fi

    if [[ "$action_count" -gt 0 ]]; then
        echo -e "2. ${GREEN}Continue from last action${NC} - Resume development from last checkpoint"
    fi

    if [[ "$knowledge_count" -gt 0 && "$action_count" -eq 0 ]]; then
        echo -e "1. ${BLUE}Start implementation${NC} - Knowledge exists but no actions yet"
    fi

    if [[ "$knowledge_count" -eq 0 && "$action_count" -eq 0 && "$judgement_count" -eq 0 ]]; then
        echo -e "${YELLOW}No elements found. This issue may not be using GHE element tracking.${NC}"
    fi

    echo ""
    echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}Recovery complete. Use --type to drill into specific elements.${NC}"
}

# Main execution
main() {
    parse_args "$@"
    validate_args

    if [[ "$STATS_MODE" == "true" ]]; then
        show_stats
    elif [[ "$RECOVER_MODE" == "true" ]]; then
        smart_recover
    elif [[ -n "$COMPOUND" ]]; then
        query_compound "$COMPOUND"
    elif [[ -n "$TYPE" ]]; then
        query_by_type "$TYPE"
    fi
}

main "$@"
