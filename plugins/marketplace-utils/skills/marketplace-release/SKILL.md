---
name: marketplace-release
description: Use when creating releases for Claude Code plugin marketplaces. Supports independent plugin versioning - each plugin can be released separately. Triggered by "release", "bump version", "create release", "publish plugin".
---

# Marketplace Release Automation

A portable release script for Claude Code plugin marketplaces with **independent plugin versioning**. Each plugin in a marketplace maintains its own version and can be released separately.

## Prerequisites

1. **GitHub CLI** authenticated: `gh auth status`
2. **Clean git state** (or acknowledge uncommitted changes)
3. **marketplace.json** at `.claude-plugin/marketplace.json`
4. Run from the **marketplace root directory**

## Usage

```bash
# Release a specific plugin
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" <bump-type> <plugin-name> "<release-notes>"

# List all plugins and their versions
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" --list

# Or copy script to marketplace and run from root
python scripts/release.py <bump-type> <plugin-name> "<release-notes>"
```

## Examples

```bash
# Patch release for ghe plugin
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" patch ghe "Fix avatar loading issue"

# Minor release for marketplace-utils
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" minor marketplace-utils "Add TOC generator"

# Major release with breaking changes
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" major ghe "Breaking: New API structure"

# View all plugins and current versions
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" --list
```

## Version Bump Types

| Type | When to Use | Example |
|------|-------------|---------|
| `patch` | Bug fixes, minor improvements | 0.5.4 -> 0.5.5 |
| `minor` | New features, non-breaking changes | 0.5.5 -> 0.6.0 |
| `major` | Breaking changes, major rewrites | 0.6.0 -> 1.0.0 |

## What It Does

1. **Validates prerequisites** - Checks gh CLI, git repo, uncommitted changes
2. **Bumps plugin version** - In both marketplace.json and the plugin's plugin.json
3. **Updates README** - Version badges and release links (plugin-specific)
4. **Creates commit** - With release message
5. **Creates git tag** - Plugin-specific tag: `<plugin-name>-v<version>`
6. **Pushes to remote** - Both commit and tag
7. **Creates GitHub release** - With installation instructions

## Independent Versioning

Each plugin has its own version tracked in marketplace.json:

```json
{
  "name": "my-marketplace",
  "plugins": [
    {
      "name": "ghe",
      "source": "./plugins/ghe",
      "version": "0.5.4"
    },
    {
      "name": "marketplace-utils",
      "source": "./plugins/marketplace-utils",
      "version": "1.0.0"
    }
  ]
}
```

When you release a plugin:
- **Only that plugin's version** is bumped
- Tags are plugin-specific: `ghe-v0.5.4`, `marketplace-utils-v1.0.0`
- Other plugins remain unchanged

## Configuration Files

### marketplace.json (required)

Located at `.claude-plugin/marketplace.json`:

```json
{
  "name": "my-marketplace",
  "plugins": [
    {
      "name": "plugin-a",
      "source": "./plugins/plugin-a",
      "version": "1.0.0"
    },
    {
      "name": "plugin-b",
      "source": "./plugins/plugin-b",
      "version": "2.3.1"
    }
  ]
}
```

### plugin.json (auto-detected)

Located at `plugins/<name>/.claude-plugin/plugin.json`:

```json
{
  "name": "plugin-a",
  "version": "1.0.0"
}
```

Both files are updated when releasing that specific plugin.

## Version Suffix Handling

The script preserves version suffixes like `-alpha`, `-beta`:

- Input version: `0.2.5-alpha`
- After `patch`: `0.2.6-alpha`
- Tag created: `ghe-v0.2.6-alpha`

## Generated Release Body

```markdown
## What's Changed

<your release notes>

## Installation

```bash
/plugin marketplace update my-marketplace
/plugin install ghe@my-marketplace
```

## Full Changelog
https://github.com/owner/repo/compare/ghe-v0.5.3...ghe-v0.5.4
```

## Confirmation Prompt

The script prompts for confirmation before making changes:

```
Marketplace: my-marketplace
Plugin: ghe
Current version: 0.5.3
New version: 0.5.4

Proceed with release ghe-v0.5.4? [y/N]
```

## List Plugins Command

Use `--list` to see all plugins and their current versions:

```bash
$ python release.py --list

Marketplace: my-marketplace

Plugin                    Version         Source
----------------------------------------------------------------------
ghe                       0.5.4           ./plugins/ghe
marketplace-utils         1.0.0           ./plugins/marketplace-utils
```

## Troubleshooting

### "marketplace.json not found"
Run from marketplace root directory, not plugin subdirectory.

### "Unknown plugin: xyz"
Check plugin name matches exactly what's in marketplace.json. Use `--list` to see available plugins.

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
