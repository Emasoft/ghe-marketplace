#!/bin/bash
# Quick check if an issue is currently set for transcription
# Returns exit 0 if issue is set, exit 1 if not

CONFIG_FILE=".claude/ghe.local.md"

if [[ -f "$CONFIG_FILE" ]]; then
    ISSUE=$(grep -E "^current_issue:" "$CONFIG_FILE" | head -1 | sed 's/^[^:]*: *//' | tr -d '"' | tr -d "'")
    if [[ -n "$ISSUE" && "$ISSUE" != "null" ]]; then
        echo "TRANSCRIPTION ACTIVE: Issue #$ISSUE"
        exit 0
    fi
fi

echo "TRANSCRIPTION INACTIVE: No issue set"
exit 0  # Exit 0 to not block the hook, just inform
