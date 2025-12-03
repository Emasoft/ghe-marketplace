# GHE Marketplace

> **ALPHA** - This plugin is in early development. APIs and workflows may change.

**GHE** = **G**it**H**ub-**E**lements

Automated project management for Claude Code using GitHub Issues as persistent memory.

## What is GHE?

GHE is a Claude Code plugin that turns GitHub Issues into a **persistent memory system** for AI agents. It enables:

- **Multi-session work tracking** - Continue where you left off after context compaction
- **Automated workflow management** - DEV → TEST → REVIEW phase cycle
- **Team collaboration** - Multiple agents working on the same project
- **Context survival** - Your work history persists in GitHub Issues

## Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/Emasoft/ghe-marketplace.git ~/.claude/marketplaces/ghe-marketplace
```

Restart Claude Code. The plugin auto-discovers.

### Alternative: Plugin Only

```bash
git clone https://github.com/Emasoft/ghe-marketplace.git /tmp/ghe-temp
cp -r /tmp/ghe-temp/plugins/ghe ~/.claude/plugins/
rm -rf /tmp/ghe-temp
```

### Development (Symlink)

```bash
git clone https://github.com/Emasoft/ghe-marketplace.git ~/Code/ghe-marketplace
ln -s ~/Code/ghe-marketplace ~/.claude/marketplaces/ghe-marketplace
```

## Post-Installation

Run the setup command:

```
/ghe:setup
```

This creates `.claude/ghe.local.md` with your project settings.

## Requirements

- **GitHub CLI** (`gh`) - Install and authenticate:
  ```bash
  brew install gh    # macOS
  gh auth login
  ```

- **SERENA MCP** (Optional) - For memory bank integration

## Plugin Contents

### GHE v0.1.0-alpha

| Component | Count | Description |
|-----------|-------|-------------|
| Agents | 10 | DEV/TEST/REVIEW managers, orchestrator, enforcement |
| Skills | 6 | ghe-status, ghe-claim, ghe-checkpoint, ghe-transition, ghe-report |
| Commands | 1 | `/ghe:setup` |
| Hooks | 1 | SessionStart for context recovery |

### Agents

| Agent | Purpose |
|-------|---------|
| `dev-thread-manager` | Manages DEV phase work |
| `test-thread-manager` | Manages TEST phase work |
| `review-thread-manager` | Manages REVIEW phase, bug triage |
| `ghe-orchestrator` | Coordinates workflow |
| `phase-gate` | Validates phase transitions |
| `memory-sync` | Syncs to SERENA memory bank |
| `enforcement` | Audits workflow compliance |
| `reporter` | Generates status reports |
| `ci-issue-opener` | Creates issues from CI failures |
| `pr-checker` | Validates PRs against workflow |

### Skills

| Skill | Usage |
|-------|-------|
| `ghe-status` | Quick workflow overview |
| `ghe-claim` | Claim an issue to work on |
| `ghe-checkpoint` | Post progress checkpoint |
| `ghe-transition` | Change phases (DEV→TEST→REVIEW) |
| `ghe-report` | Detailed metrics and reports |
| `github-elements-tracking` | Full workflow documentation |

## Workflow

```
DEV ──► TEST ──► REVIEW ──► DEV ...
                    │
                    └──► PASS? → merge to main
```

- **DEV**: Write code and tests
- **TEST**: Run tests, fix simple bugs
- **REVIEW**: Evaluate quality, render verdict

## Structure

```
ghe-marketplace/
├── marketplace.json
├── README.md
├── LICENSE
└── plugins/
    └── ghe/
        ├── .claude-plugin/plugin.json
        ├── agents/
        ├── skills/
        ├── commands/
        ├── hooks/
        ├── scripts/
        └── examples/
```

## Updating

```bash
cd ~/.claude/marketplaces/ghe-marketplace
git pull
```

## Uninstalling

```bash
rm -rf ~/.claude/marketplaces/ghe-marketplace
```

## License

MIT License - Copyright (c) 2025 Emasoft

## Author

[Emasoft](https://github.com/Emasoft)
