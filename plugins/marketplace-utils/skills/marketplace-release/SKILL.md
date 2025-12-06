---
name: marketplace-release
description: Use when creating releases for Claude Code plugin marketplaces. Handles version bumping, changelog generation, git tags, and GitHub releases. Triggered by "release", "bump version", "create release", "publish marketplace".
---

# Marketplace Release Automation

A portable release script for Claude Code plugin marketplaces. Reads all configuration from JSON files - no hardcoded values.

## Prerequisites

1. **GitHub CLI** authenticated: `gh auth status`
2. **Clean git state** (or acknowledge uncommitted changes)
3. **marketplace.json** at `.claude-plugin/marketplace.json`

## Usage

```bash
# Using the plugin script (recommended)
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" <bump-type> "<release-notes>"

# Or copy script to marketplace and run from root
python scripts/release.py <bump-type> "<release-notes>"

# Examples
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" patch "Fix avatar loading issue"
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" minor "Add new agent for code review"
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" major "Breaking: Restructured plugin configuration"
```

## Version Bump Types

| Type | When to Use | Example |
|------|-------------|---------|
| `patch` | Bug fixes, minor improvements | 0.2.5 -> 0.2.6 |
| `minor` | New features, non-breaking changes | 0.2.6 -> 0.3.0 |
| `major` | Breaking changes, major rewrites | 0.3.0 -> 1.0.0 |

## What It Does

1. **Validates prerequisites** - Checks gh CLI, git repo, uncommitted changes
2. **Bumps version** - In marketplace.json and plugin.json
3. **Updates READMEs** - Version badges and release links
4. **Creates commit** - With release message
5. **Creates git tag** - Annotated tag with version
6. **Pushes to remote** - Both commit and tag
7. **Creates GitHub release** - With installation instructions

## Configuration Files

### marketplace.json (required)

```json
{
  "name": "my-marketplace",
  "metadata": {
    "version": "1.0.0-alpha"
  },
  "plugins": [
    {
      "name": "my-plugin",
      "source": "./plugins/my-plugin",
      "version": "1.0.0-alpha"
    }
  ]
}
```

### plugin.json (auto-detected)

Located at `plugins/<name>/.claude-plugin/plugin.json`:

```json
{
  "name": "my-plugin",
  "version": "1.0.0"
}
```

## Version Suffix Handling

The script preserves version suffixes like `-alpha`, `-beta`:

- Input version: `0.2.5-alpha`
- After `patch`: `0.2.6-alpha`
- Suffix preserved in tags: `v0.2.6-alpha`

## Generated Release Body

```markdown
## What's Changed

<your release notes>

## Installation

\`\`\`bash
/plugin marketplace update my-marketplace
/plugin install my-plugin@my-marketplace
\`\`\`

## Full Changelog
https://github.com/owner/repo/compare/v0.2.5-alpha...v0.2.6-alpha
```

## Dry Run

The script prompts for confirmation before making changes:

```
Marketplace: my-marketplace
Plugin: my-plugin
Current version: 0.2.5-alpha
New version: 0.2.6-alpha

Proceed with release v0.2.6-alpha? [y/N]
```

## Troubleshooting

### "marketplace.json not found"
Run from marketplace root directory, not plugin subdirectory.

### "Not authenticated with GitHub CLI"
Run `gh auth login` and authenticate.

### "You have uncommitted changes"
Commit or stash changes, or proceed and include them in the release.

## Portability

This script is fully portable:
- All values read from JSON config files
- GitHub repo info detected via `gh repo view`
- No hardcoded paths, names, or user-specific values
- Can be copied to any Claude Code marketplace project
