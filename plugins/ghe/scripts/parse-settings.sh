#!/bin/bash
# GitHub Elements Settings Parser
# Extracts settings from .claude/ghe.local.md
# Usage: ./parse-settings.sh [field-name]
# Without field-name: outputs all frontmatter
# With field-name: outputs that field's value

set -euo pipefail

# Source shared library
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "${SCRIPT_DIR}/lib/ghe-common.sh"

# Initialize GHE environment
ghe_init

# Default values for all settings
declare -A DEFAULTS=(
  [enabled]="true"
  [enforcement_level]="standard"
  [serena_sync]="true"
  [auto_worktree]="false"
  [checkpoint_interval_minutes]="30"
  [notification_level]="normal"
  [default_reviewer]=""
  [stale_threshold_hours]="24"
  [epic_label_prefix]="parent-epic:"
  [auto_transcribe]="true"
  [auto_create_issue]="true"
  [current_issue]=""
)

# Check if settings file exists
if [[ ! -f "$GHE_CONFIG_FILE" ]]; then
  # Return defaults if no settings file
  if [[ -n "${1:-}" ]]; then
    echo "${DEFAULTS[${1:-}]:-}"
  fi
  exit 0
fi

# Extract frontmatter (everything between --- markers)
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$GHE_CONFIG_FILE")

# If no field specified, output all frontmatter
if [[ -z "${1:-}" ]]; then
  echo "$FRONTMATTER"
  exit 0
fi

FIELD="$1"

# Extract specific field value
VALUE=$(echo "$FRONTMATTER" | grep "^${FIELD}:" | sed "s/${FIELD}: *//" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\\(.*\\)'$/\\1/" || echo "")

# Return value or default
if [[ -z "$VALUE" ]]; then
  echo "${DEFAULTS[${FIELD}]:-}"
else
  echo "$VALUE"
fi

exit 0
