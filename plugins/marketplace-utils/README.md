# Marketplace Utils

Portable utility tools for Claude Code plugin marketplaces.

## Skills

### marketplace-release

Release automation for Claude Code plugin marketplaces. Handles version bumping, changelog generation, git tags, and GitHub releases.

**Triggers**: "release", "bump version", "create release", "publish marketplace"

### markdown-toc

Universal Table of Contents generator for markdown files. Supports multiple files, glob patterns, configurable header levels, and various insertion modes.

**Triggers**: "generate toc", "update toc", "table of contents", "add toc to markdown"

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/release.py` | Marketplace release automation |
| `scripts/generate_toc.py` | Markdown TOC generator |

## Installation

```bash
/plugin install marketplace-utils@ghe-marketplace
```

## Usage

After installation, the skills are automatically available. Claude will use them when triggered by relevant keywords.

### Manual Script Usage

```bash
# Release
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" patch "Bug fix"

# TOC generation
python "${CLAUDE_PLUGIN_ROOT}/scripts/generate_toc.py" --dry-run README.md
```

## Portability

Both scripts are fully portable:
- No hardcoded paths or project-specific values
- All configuration read from standard files (marketplace.json, plugin.json)
- Can be copied to any Claude Code marketplace project

## License

MIT
