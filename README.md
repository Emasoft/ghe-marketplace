# GitHub Elements Marketplace

A Claude Code plugin marketplace containing the **GitHub Elements** plugin for persistent memory using GitHub Issues.

## Installation

### Quick Install (Recommended)

```bash
# Clone this marketplace to Claude Code's marketplaces directory
git clone https://github.com/Emasoft/github-elements-marketplace.git ~/.claude/marketplaces/github-elements-marketplace
```

After cloning, restart Claude Code. The plugin will be auto-discovered.

### Alternative: Install Plugin Only

If you only want the plugin without the marketplace structure:

```bash
# Clone the plugin directly
git clone https://github.com/Emasoft/github-elements-marketplace.git /tmp/ghe-temp
cp -r /tmp/ghe-temp/plugins/github-elements ~/.claude/plugins/
rm -rf /tmp/ghe-temp
```

### For Development (Symlink)

```bash
# Clone to your preferred location
git clone https://github.com/Emasoft/github-elements-marketplace.git ~/Code/github-elements-marketplace

# Symlink to Claude Code
ln -s ~/Code/github-elements-marketplace ~/.claude/marketplaces/github-elements-marketplace
```

## Post-Installation Setup

After installation, run the setup command in Claude Code:

```
/github-elements:setup
```

This creates `.claude/github-elements.local.md` with your project-specific settings.

## Requirements

- **GitHub CLI** (`gh`) - Must be installed and authenticated
  ```bash
  # Install
  brew install gh  # macOS

  # Authenticate
  gh auth login
  ```

- **SERENA MCP** (Optional) - For memory bank integration with project-level context

## Available Plugin

### github-elements v1.0.0

GitHub Issues as **permanent memory** for AI agents. Enables multi-session work tracking, context survival across compaction, and team collaboration.

| Component | Count | Description |
|-----------|-------|-------------|
| Agents | 10 | DEV/TEST/REVIEW managers, orchestrator, enforcement, etc. |
| Skills | 6 | status, claim, checkpoint, transition, report, tracking |
| Commands | 1 | `/github-elements:setup` for project configuration |
| Hooks | 1 | SessionStart for automatic context recovery |

### Core Features

- **Persistent Memory**: GitHub Issues survive context compaction
- **Multi-Session Tracking**: Continue work across Claude Code sessions
- **Team Collaboration**: Multiple agents can work on same project
- **Phase Workflow**: DEV → TEST → REVIEW circular development cycle
- **SERENA Integration**: Optional memory bank for large documents

## Marketplace Structure

```
github-elements-marketplace/
├── marketplace.json       # Plugin index with metadata
├── README.md              # This file
├── LICENSE                # MIT License
└── plugins/
    └── github-elements/   # The complete plugin
        ├── .claude-plugin/
        │   └── plugin.json
        ├── agents/        # 10 specialized agents
        ├── skills/        # 6 workflow skills
        ├── commands/      # Setup command
        ├── hooks/         # SessionStart hook
        ├── scripts/       # Helper scripts
        ├── examples/      # GitHub Actions examples
        └── README.md      # Plugin documentation
```

## Updating

```bash
cd ~/.claude/marketplaces/github-elements-marketplace
git pull
```

## Uninstalling

```bash
rm -rf ~/.claude/marketplaces/github-elements-marketplace
```

## License

MIT License - Copyright (c) 2025 Emasoft

## Author

[Emasoft](https://github.com/Emasoft)

## Links

- [Plugin Documentation](plugins/github-elements/README.md)
- [GitHub Actions Examples](plugins/github-elements/examples/github-actions/)
- [Issue Tracker](https://github.com/Emasoft/github-elements-marketplace/issues)
