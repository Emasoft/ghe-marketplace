#!/bin/bash
# release.sh - Automate version bump, tag, and GitHub release
# Usage: ./release.sh [patch|minor|major] "Release notes"
# Example: ./release.sh patch "Fix avatar loading issue"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_DIR="$(dirname "$SCRIPT_DIR")"
PLUGIN_JSON="$PLUGIN_DIR/.claude-plugin/plugin.json"
README="$PLUGIN_DIR/README.md"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; exit 1; }

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    command -v gh >/dev/null 2>&1 || error "GitHub CLI (gh) is not installed"
    command -v jq >/dev/null 2>&1 || error "jq is not installed"
    command -v zip >/dev/null 2>&1 || error "zip is not installed"

    # Check gh auth status
    gh auth status >/dev/null 2>&1 || error "Not authenticated with GitHub CLI. Run 'gh auth login'"

    # Check we're in a git repo
    git rev-parse --git-dir >/dev/null 2>&1 || error "Not in a git repository"

    # Check for uncommitted changes
    if [[ -n $(git status --porcelain) ]]; then
        warn "You have uncommitted changes. They will be included in this release."
        read -p "Continue? [y/N] " -n 1 -r
        echo
        [[ $REPLY =~ ^[Yy]$ ]] || exit 1
    fi

    success "Prerequisites check passed"
}

# Get current version from plugin.json
get_current_version() {
    jq -r '.version' "$PLUGIN_JSON"
}

# Bump version based on type (patch/minor/major)
bump_version() {
    local current="$1"
    local bump_type="$2"

    IFS='.' read -r major minor patch <<< "$current"

    case "$bump_type" in
        major)
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        minor)
            minor=$((minor + 1))
            patch=0
            ;;
        patch)
            patch=$((patch + 1))
            ;;
        *)
            error "Invalid bump type: $bump_type. Use patch, minor, or major."
            ;;
    esac

    echo "$major.$minor.$patch"
}

# Update version in plugin.json
update_plugin_json() {
    local new_version="$1"
    local tmp_file=$(mktemp)

    jq --arg v "$new_version" '.version = $v' "$PLUGIN_JSON" > "$tmp_file"
    mv "$tmp_file" "$PLUGIN_JSON"

    success "Updated plugin.json to version $new_version"
}

# Update version in README.md
update_readme() {
    local new_version="$1"

    # Update the version badge at the top of README
    sed -i '' "s/\*\*Version: [0-9]*\.[0-9]*\.[0-9]*\*\*/**Version: $new_version**/" "$README"

    success "Updated README.md version badge"
}

# Create git commit
create_commit() {
    local version="$1"
    local notes="$2"

    git add -A
    git commit -m "Release v$version

$notes"

    success "Created commit for v$version"
}

# Create and push git tag
create_tag() {
    local version="$1"
    local notes="$2"

    git tag -a "v$version" -m "Release v$version - $notes"
    git push origin main
    git push origin "v$version"

    success "Created and pushed tag v$version"
}

# Create zip file
create_zip() {
    local version="$1"
    local zip_name="ghe-v$version.zip"
    local repo_root="$(git rev-parse --show-toplevel)"

    cd "$repo_root"
    zip -r "$zip_name" plugins/ghe -x "*.DS_Store" -x "*__pycache__*" -x "*.pyc"

    echo "$repo_root/$zip_name"
}

# Create GitHub release
create_release() {
    local version="$1"
    local notes="$2"
    local zip_path="$3"

    local release_body="## What's Changed in v$version

$notes

### Installation

**Via Claude Code CLI (recommended):**
\`\`\`bash
claude plugin add Emasoft/ghe-marketplace
\`\`\`

**Manual installation:**
1. Download \`ghe-v$version.zip\` below
2. Extract to \`~/.claude/plugins/ghe/\`
3. Restart Claude Code

### Full Changelog
https://github.com/Emasoft/ghe-marketplace/compare/v$(get_previous_tag)...v$version"

    gh release create "v$version" \
        --title "GHE v$version" \
        --notes "$release_body" \
        "$zip_path"

    success "Created GitHub release v$version"
}

# Get previous tag for changelog link
get_previous_tag() {
    git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo "0.0.0"
}

# Clean up zip file
cleanup() {
    local zip_path="$1"
    rm -f "$zip_path"
    success "Cleaned up temporary files"
}

# Show usage
usage() {
    cat << EOF
Usage: $0 <bump_type> "<release_notes>"

Arguments:
  bump_type     Version bump type: patch, minor, or major
  release_notes Brief description of changes (in quotes)

Examples:
  $0 patch "Fix avatar loading issue"
  $0 minor "Add new agent personas"
  $0 major "Breaking API changes"

Current version: $(get_current_version)
EOF
    exit 1
}

# Main
main() {
    if [[ $# -lt 2 ]]; then
        usage
    fi

    local bump_type="$1"
    local release_notes="$2"

    info "Starting release process..."
    echo

    check_prerequisites

    local current_version=$(get_current_version)
    local new_version=$(bump_version "$current_version" "$bump_type")

    info "Current version: $current_version"
    info "New version: $new_version"
    echo

    read -p "Proceed with release v$new_version? [y/N] " -n 1 -r
    echo
    [[ $REPLY =~ ^[Yy]$ ]] || exit 1

    echo
    info "Step 1/6: Updating plugin.json..."
    update_plugin_json "$new_version"

    info "Step 2/6: Updating README.md..."
    update_readme "$new_version"

    info "Step 3/6: Creating commit..."
    create_commit "$new_version" "$release_notes"

    info "Step 4/6: Creating and pushing tag..."
    create_tag "$new_version" "$release_notes"

    info "Step 5/6: Creating zip file..."
    local zip_path=$(create_zip "$new_version")
    info "Created: $zip_path"

    info "Step 6/6: Creating GitHub release..."
    create_release "$new_version" "$release_notes" "$zip_path"

    info "Cleaning up..."
    cleanup "$zip_path"

    echo
    success "Release v$new_version complete!"
    echo
    info "Release URL: https://github.com/Emasoft/ghe-marketplace/releases/tag/v$new_version"
}

main "$@"
