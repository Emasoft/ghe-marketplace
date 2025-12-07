# Marketplace Utils

[![Version](https://img.shields.io/badge/version-1.1.5-blue.svg)](https://github.com/Emasoft/ghe-marketplace/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin-purple.svg)](https://docs.anthropic.com/en/docs/claude-code)

Portable utility tools for Claude Code plugin marketplaces.

## Table of Contents

- [Installation](#installation)
- [Skills](#skills)
  - [marketplace-release](#marketplace-release)
  - [markdown-toc](#markdown-toc)
- [Scripts](#scripts)
  - [release.py](#releasepy)
  - [generate_toc.py](#generate_tocpy)
  - [validate_plugin.py](#validate_pluginpy)
- [Portability](#portability)
- [License](#license)

## Installation

```bash
/plugin install marketplace-utils@ghe-marketplace
```

After installation, the skills are automatically available. Claude will use them when triggered by relevant keywords.

---

## Skills

### marketplace-release

**Triggers**: "release", "bump version", "create release", "publish plugin"

Release automation for Claude Code plugin marketplaces with **independent plugin versioning**. Each plugin in a marketplace can be released separately with its own version.

#### What It Does

1. **Validates prerequisites** - Checks gh CLI, git repo, uncommitted changes
2. **Validates plugin** - Runs `claude plugin validate` before release
3. **Bumps plugin version** - In both marketplace.json and plugin.json
4. **Updates READMEs** - Plugin README badges + marketplace README version table
5. **Creates commit** - With release message
6. **Creates git tag** - Plugin-specific tag: `<plugin-name>-v<version>`
7. **Pushes to remote** - Both commit and tag
8. **Creates GitHub release** - With installation instructions

#### Usage

```bash
# Release a specific plugin
python release.py <bump-type> <plugin-name> "<notes>"

# Examples
python release.py patch ghe "Fix avatar loading issue"
python release.py minor marketplace-utils "Add TOC generator"
python release.py major ghe "Breaking: New API structure"

# List all plugins and versions
python release.py --list
```

#### Version Bump Types

| Type | When to Use | Example |
|------|-------------|---------|
| `patch` | Bug fixes, minor improvements | 0.5.4 -> 0.5.5 |
| `minor` | New features, non-breaking changes | 0.5.5 -> 0.6.0 |
| `major` | Breaking changes, major rewrites | 0.6.0 -> 1.1.5 |

#### Independent Versioning

Each plugin has its own version:
- Tags are plugin-specific: `ghe-v0.5.4`, `marketplace-utils-v1.1.5`
- Only the released plugin's version is bumped
- Other plugins remain unchanged

#### Auto-Generated README Table

The release script maintains a version table in the marketplace README:

```markdown
<!-- PLUGIN-VERSIONS-START -->
## Plugin Versions

| Plugin | Version | Description |
|--------|---------|-------------|
| ghe | 0.5.4 | GHE (GitHub-Elements)... |
| marketplace-utils | 1.1.5 | Portable utility tools... |

*Last updated: 2025-01-15*
<!-- PLUGIN-VERSIONS-END -->
```

---

### markdown-toc

**Triggers**: "generate toc", "update toc", "table of contents", "add toc to markdown"

Universal Table of Contents generator for markdown files. Supports multiple files, glob patterns, configurable header levels, and smart insertion.

#### Quick Start

```bash
# Single file
python generate_toc.py README.md

# Preview without changes
python generate_toc.py --dry-run README.md

# All markdown files in docs/
python generate_toc.py docs/*.md

# Recursive processing
python generate_toc.py --recursive .
```

#### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--dry-run` | false | Preview TOC without modifying files |
| `--min-level N` | 2 | Minimum header level (1-6) |
| `--max-level N` | 3 | Maximum header level (1-6) |
| `--title TEXT` | "Table of Contents" | Custom TOC title |
| `--no-title` | false | Omit TOC title |
| `--recursive, -r` | false | Process .md files recursively |
| `--insert MODE` | auto | Insertion mode: auto, top, marker |
| `--marker TEXT` | `<!-- TOC -->` | Custom marker for marker mode |

#### Insertion Modes

**Auto Mode** (default) - Smart detection:
1. Replace existing `## Table of Contents` section
2. Insert after first `---` separator
3. Insert after YAML frontmatter
4. Insert after first header
5. Insert at top of file

**Top Mode** - Insert at top, respecting YAML frontmatter:
```bash
python generate_toc.py --insert top README.md
```

**Marker Mode** - Insert between marker pairs:
```bash
python generate_toc.py --insert marker README.md
```

In your markdown:
```markdown
<!-- TOC -->
(TOC will be inserted/updated here)
<!-- /TOC -->
```

#### Batch Processing

```bash
# All .md in current directory
python generate_toc.py *.md

# Recursive in docs/
python generate_toc.py --recursive docs/

# Multiple paths
python generate_toc.py README.md CONTRIBUTING.md docs/
```

#### Anchor Generation

GitHub-compatible anchors:
- Lowercase conversion
- Spaces to hyphens
- Special characters removed
- Markdown formatting stripped
- Emoji removed

| Header | Anchor |
|--------|--------|
| `## Getting Started` | `#getting-started` |
| `## **Bold** Header` | `#bold-header` |
| `## Header with \`code\`` | `#header-with-code` |

---

## Scripts

Both scripts are located in `scripts/` and can be run directly or via the plugin path.

### release.py

```bash
# Via plugin
python "${CLAUDE_PLUGIN_ROOT}/scripts/release.py" patch ghe "Bug fix"

# Or copy to marketplace root
python scripts/release.py patch ghe "Bug fix"
```

**Prerequisites:**
- GitHub CLI (`gh`) installed and authenticated
- Run from marketplace root directory
- `.claude-plugin/marketplace.json` must exist

### generate_toc.py

```bash
# Via plugin
python "${CLAUDE_PLUGIN_ROOT}/scripts/generate_toc.py" --dry-run README.md

# Or copy to any project
python scripts/generate_toc.py README.md
```

**Prerequisites:**
- Python 3.6+
- No external dependencies

### validate_plugin.py

Plugin validation tool that wraps `claude plugin validate`:

```bash
# Validate a specific plugin
python "${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin.py" ghe

# Validate all plugins in the marketplace
python "${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin.py" --all

# Show version
python "${CLAUDE_PLUGIN_ROOT}/scripts/validate_plugin.py" --version
```

**Features:**
- Individual plugin validation
- Batch validation with `--all` flag
- Summary report with pass/fail status
- Colored terminal output

**Prerequisites:**
- Claude Code CLI (`claude plugin validate` command)
- Run from marketplace root directory

---

## Portability

All scripts are fully portable:
- **No hardcoded paths** - All paths relative or from config
- **No project-specific values** - Reads from marketplace.json/plugin.json
- **Standard Python** - No external dependencies
- **Copy-friendly** - Can be copied to any Claude Code marketplace

---

## License

MIT License - Copyright (c) 2025 Emasoft
