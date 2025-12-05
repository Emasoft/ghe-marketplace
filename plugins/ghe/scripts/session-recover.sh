#!/bin/bash
# GHE Session Recovery - Check for active issue and recover context
# Called by SessionStart hook

CONFIG=".claude/ghe.local.md"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"

if [[ -f "$CONFIG" ]]; then
    # Extract current_issue from config (handle various formats)
    ISSUE=$(grep -E "^current_issue:" "$CONFIG" 2>/dev/null | head -1 | sed 's/^[^:]*: *//' | tr -d '"' | tr -d "'" | tr -d ' ')

    if [[ -n "$ISSUE" && "$ISSUE" != "null" ]]; then
        echo "GHE: Recovering context from Issue #$ISSUE..."
        bash "${PLUGIN_ROOT}/scripts/recall-elements.sh" --issue "$ISSUE" --recover 2>/dev/null || \
            echo "Element recall not available - run manually: recall-elements.sh --issue $ISSUE --recover"
    fi
fi
