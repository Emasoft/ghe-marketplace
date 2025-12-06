#!/bin/bash
# GHE Session Recovery - Check for active issue and recover context
# Called by SessionStart hook

# Source shared library
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/ghe-common.sh"

# Initialize GHE environment
ghe_init

if [[ -n "$GHE_CURRENT_ISSUE" && "$GHE_CURRENT_ISSUE" != "null" ]]; then
    ghe_info "Recovering context from Issue #$GHE_CURRENT_ISSUE..."
    bash "${GHE_PLUGIN_ROOT}/scripts/recall-elements.sh" --issue "$GHE_CURRENT_ISSUE" --recover 2>/dev/null || \
        ghe_warn "Element recall not available - run manually: recall-elements.sh --issue $GHE_CURRENT_ISSUE --recover"
fi
