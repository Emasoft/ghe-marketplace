# GitHub Elements Marketplace

A Claude Code plugin marketplace containing the **GitHub Elements** plugin for persistent memory using GitHub Issues.

## Available Plugins

### github-elements v1.0.0

GitHub Issues as **permanent memory** for AI agents. Enables multi-session work tracking, context survival across compaction, and team collaboration.

**Features:**
- 10 specialized agents (DEV, TEST, REVIEW managers, orchestrator, etc.)
- 6 skills (status, claim, checkpoint, transition, report, tracking)
- 1 command (/github-elements:setup)
- 1 hook (SessionStart for context recovery)

**Requirements:**
- GitHub CLI (`gh`) installed and authenticated
- SERENA MCP (optional, for memory bank integration)

## Installation

### Option 1: Install from this marketplace

```bash
# Clone this marketplace
git clone https://github.com/Emasoft/github-elements-marketplace.git ~/.claude/marketplaces/github-elements

# The plugin will be auto-discovered from:
# ~/.claude/marketplaces/github-elements/plugins/github-elements/
```

### Option 2: Install plugin directly

```bash
# Clone directly to plugins directory
git clone https://github.com/Emasoft/github-elements-plugin.git ~/.claude/plugins/github-elements
```

### Option 3: Symlink for development

```bash
# For local development, symlink to your clone
ln -s /path/to/github-elements-plugin ~/.claude/plugins/github-elements
```

## Marketplace Structure

```
github-elements-marketplace/
├── marketplace.json       # Marketplace index
├── README.md              # This file
└── plugins/
    └── github-elements/   # The plugin
        ├── .claude-plugin/
        │   └── plugin.json
        ├── agents/
        ├── skills/
        ├── commands/
        ├── hooks/
        ├── scripts/
        ├── LICENSE
        └── README.md
```

## Usage

After installation, run the setup command:

```
/github-elements:setup
```

This creates `.claude/github-elements.local.md` with your project settings.

## License

Apache-2.0

## Author

Emasoft - https://github.com/Emasoft
