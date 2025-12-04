#!/bin/bash
# GitHub Elements Settings Parser
# Extracts settings from .claude/ghe.local.md
# Usage: ./parse-settings.sh [field-name]
# Without field-name: outputs all frontmatter
# With field-name: outputs that field's value

set -euo pipefail

SETTINGS_FILE=".claude/ghe.local.md"

# Check if settings file exists
if [[ ! -f "$SETTINGS_FILE" ]]; then
  # Return defaults if no settings file
  if [[ -n "${1:-}" ]]; then
    case "$1" in
      enabled) echo "true" ;;
      enforcement_level) echo "standard" ;;
      serena_sync) echo "true" ;;
      auto_worktree) echo "false" ;;
      checkpoint_interval_minutes) echo "30" ;;
      notification_level) echo "normal" ;;
      default_reviewer) echo "" ;;
      stale_threshold_hours) echo "24" ;;
      epic_label_prefix) echo "parent-epic:" ;;
      auto_transcribe) echo "true" ;;
      auto_create_issue) echo "true" ;;
      current_issue) echo "" ;;
      *) echo "" ;;
    esac
  fi
  exit 0
fi

# Extract frontmatter (everything between --- markers)
FRONTMATTER=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$SETTINGS_FILE")

# If no field specified, output all frontmatter
if [[ -z "${1:-}" ]]; then
  echo "$FRONTMATTER"
  exit 0
fi

FIELD="$1"

# Extract specific field value
VALUE=$(echo "$FRONTMATTER" | grep "^${FIELD}:" | sed "s/${FIELD}: *//" | sed 's/^"\(.*\)"$/\1/' | sed "s/^'\\(.*\\)'$/\\1/")

# Return value or default
if [[ -z "$VALUE" ]]; then
  case "$FIELD" in
    enabled) echo "true" ;;
    enforcement_level) echo "standard" ;;
    serena_sync) echo "true" ;;
    auto_worktree) echo "false" ;;
    checkpoint_interval_minutes) echo "30" ;;
    notification_level) echo "normal" ;;
    default_reviewer) echo "" ;;
    stale_threshold_hours) echo "24" ;;
    epic_label_prefix) echo "parent-epic:" ;;
    auto_transcribe) echo "true" ;;
    auto_create_issue) echo "true" ;;
    current_issue) echo "" ;;
    *) echo "" ;;
  esac
else
  echo "$VALUE"
fi

exit 0
