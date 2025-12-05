#!/bin/bash
# detect-duplicate-hooks.sh - Detect duplicate hook configurations
# Part of the GHE Plugin - enforces ONE SOURCE OF TRUTH rule

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(dirname "$(dirname "$0")")}"
DUPLICATES_FOUND=0

echo -e "${CYAN}GHE Hook Duplicate Detector${NC}"
echo "Checking for duplicate hook configurations..."
echo ""

# Function to check a location
check_location() {
    local path="$1"
    local desc="$2"
    local is_canonical="$3"

    if [[ -f "$path" ]]; then
        if [[ "$is_canonical" == "true" ]]; then
            echo -e "${GREEN}[CANONICAL]${NC} $desc"
            echo "            $path"
        else
            echo -e "${RED}[DUPLICATE]${NC} $desc"
            echo "            $path"
            DUPLICATES_FOUND=$((DUPLICATES_FOUND + 1))
        fi
    fi
}

# Function to check settings.json for hooks section
check_settings_json() {
    local path="$1"
    local desc="$2"

    if [[ -f "$path" ]]; then
        if grep -q '"hooks"' "$path" 2>/dev/null; then
            echo -e "${RED}[DUPLICATE]${NC} $desc has hooks section"
            echo "            $path"
            DUPLICATES_FOUND=$((DUPLICATES_FOUND + 1))
        fi
    fi
}

echo "=== Checking Hook Locations ==="
echo ""

# 1. Canonical location - GHE plugin hooks
CANONICAL_HOOK="$PLUGIN_ROOT/hooks/hooks.json"
if [[ -f "$CANONICAL_HOOK" ]]; then
    echo -e "${GREEN}[CANONICAL]${NC} GHE Plugin hooks (the ONE source of truth)"
    echo "            $CANONICAL_HOOK"
else
    echo -e "${YELLOW}[WARNING]${NC} Canonical hook file not found!"
    echo "            Expected: $CANONICAL_HOOK"
fi
echo ""

# 2. Check for project-level hooks in current directory
echo "=== Checking Project-Level Duplicates ==="
if [[ -d ".claude/hooks" ]]; then
    for hook_file in .claude/hooks/*.json .claude/hooks/*.sh; do
        if [[ -f "$hook_file" ]]; then
            echo -e "${RED}[DUPLICATE]${NC} Project-level hook"
            echo "            $(pwd)/$hook_file"
            DUPLICATES_FOUND=$((DUPLICATES_FOUND + 1))
        fi
    done
fi

# Also check for hooks.json directly in .claude/
if [[ -f ".claude/hooks.json" ]]; then
    echo -e "${RED}[DUPLICATE]${NC} Project-level hooks.json"
    echo "            $(pwd)/.claude/hooks.json"
    DUPLICATES_FOUND=$((DUPLICATES_FOUND + 1))
fi
echo ""

# 3. Check global settings
echo "=== Checking Global Duplicates ==="
check_settings_json "$HOME/.claude/settings.json" "Global settings.json"

# Check for global hooks directory
if [[ -d "$HOME/.claude/hooks" ]]; then
    for hook_file in "$HOME/.claude/hooks"/*.json "$HOME/.claude/hooks"/*.sh; do
        if [[ -f "$hook_file" ]]; then
            echo -e "${RED}[DUPLICATE]${NC} Global hook file"
            echo "            $hook_file"
            DUPLICATES_FOUND=$((DUPLICATES_FOUND + 1))
        fi
    done
fi
echo ""

# 4. Check for other plugins with conflicting hooks
echo "=== Checking Other Plugin Conflicts ==="
if [[ -d "$HOME/.claude/plugins" ]]; then
    for plugin_dir in "$HOME/.claude/plugins"/*/; do
        if [[ -d "$plugin_dir" && "$plugin_dir" != *"/ghe/"* ]]; then
            plugin_hooks="$plugin_dir/hooks/hooks.json"
            if [[ -f "$plugin_hooks" ]]; then
                # Check if it has any hooks that conflict with GHE
                if grep -q "auto_approve\|auto-transcribe\|phase-transition" "$plugin_hooks" 2>/dev/null; then
                    echo -e "${YELLOW}[CONFLICT]${NC} Plugin with similar hooks"
                    echo "            $plugin_hooks"
                    DUPLICATES_FOUND=$((DUPLICATES_FOUND + 1))
                fi
            fi
        fi
    done
fi

# Also check plugin cache
if [[ -d "$HOME/.claude/plugins/cache" ]]; then
    for plugin_dir in "$HOME/.claude/plugins/cache"/*/; do
        if [[ -d "$plugin_dir" ]]; then
            # Skip if this is ghe itself
            if [[ "$plugin_dir" == *"ghe"* ]]; then
                continue
            fi
            plugin_hooks="$plugin_dir/hooks/hooks.json"
            if [[ -f "$plugin_hooks" ]]; then
                if grep -q "auto_approve\|auto-transcribe\|phase-transition" "$plugin_hooks" 2>/dev/null; then
                    echo -e "${YELLOW}[CONFLICT]${NC} Cached plugin with similar hooks"
                    echo "            $plugin_hooks"
                    DUPLICATES_FOUND=$((DUPLICATES_FOUND + 1))
                fi
            fi
        fi
    done
fi
echo ""

# Summary
echo "=== Summary ==="
if [[ $DUPLICATES_FOUND -eq 0 ]]; then
    echo -e "${GREEN}No duplicates found. ONE SOURCE OF TRUTH is enforced.${NC}"
    exit 0
else
    echo -e "${RED}Found $DUPLICATES_FOUND duplicate(s)!${NC}"
    echo ""
    echo "To fix, remove all duplicates and keep ONLY the canonical location:"
    echo "  $CANONICAL_HOOK"
    echo ""
    echo "Quick fix commands:"
    echo "  rm -rf .claude/hooks/                    # Remove project-level duplicates"
    echo "  rm -rf ~/.claude/hooks/                  # Remove global duplicates"
    echo "  # Edit ~/.claude/settings.json to remove 'hooks' section"
    exit 1
fi
