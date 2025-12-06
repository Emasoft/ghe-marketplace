#!/bin/bash
# Quick check if an issue is currently set for transcription
# Returns exit 0 if issue is set, exit 1 if not

# Source shared library
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/ghe-common.sh"

# Initialize GHE environment
ghe_init

# Check if a current issue is set
ISSUE=$(ghe_get_setting "current_issue" "")
if [[ -n "$ISSUE" && "$ISSUE" != "null" ]]; then
    ghe_info "TRANSCRIPTION ACTIVE: Issue #$ISSUE"
    exit 0
fi

ghe_info "TRANSCRIPTION INACTIVE: No issue set"
exit 0  # Exit 0 to not block the hook, just inform
