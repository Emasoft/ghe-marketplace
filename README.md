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

## The Element

<p align="center">
  <img src="plugins/ghe/assets/element-triangle.svg" alt="The Element Triangle" width="400"/>
</p>

An **Element** is a unit of information stored as a single message/reply to a GitHub Issue in the issue tracker. Every piece of information in GHE is an Element.

**The power of this system**: GitHub threads allow you to **isolate and preserve the context of each task**. Human developers and AI agents can discuss progress while keeping the conversation focused and on track, instead of mixing different issues together.

At any moment, you can tell Claude: *"Let's switch to working on issue #42"* - and Claude instantly gets up to speed by reading that issue's thread. It spawns a subagent to read and summarize the thread, so it won't waste your tokens or context memory. Each issue is a self-contained knowledge base for its task.

There are **3 types of Elements**:

### Element of Knowledge

A message describing **objective information ABOUT the code**:
- Files, signatures, incompatibilities, errors, results
- Algorithm pseudocode, quotes from papers, ideas
- Architectures, design, requirements, formats
- APIs, features, functionalities, data structures
- Configurations, databases, dev stack, compilers, dependencies

### Element of Action

A message containing or linking **actual source code**:
- Code snippets showing an issue in the codebase
- Proposed patches or fixes
- Summarized changes with diffs
- Contributions to the project (linked PRs, forks)
- Proposed variations to parts of the code

> Must be actual code, not pseudocode - a snippet, diff, or patch.

### Element of Judgement

A message containing **criticism or evaluation** about the code:
- Bug reports and descriptions
- Performance issues
- Incompatibilities, security issues
- Code quality assessments
- Any positive or negative evaluation of code or program behavior

## Core Features

### 1. ON TRACK - Always Focused on the Current Task

Each GitHub Issue thread keeps Claude focused on **one task at a time**. No more context drift or mixing different problems together. When you say *"Let's work on issue #42"*, Claude reads that specific thread and stays on track.

### 2. ALIGNED TEAM WORK - Seamless Collaboration

Other collaborators who have installed the GHE plugin can **collaborate effortlessly**. Everyone stays up to date by following the thread and commenting in it. Human developers and AI agents work together in the same conversation, with full visibility of each other's progress.

### 3. PERFECT MEMORY - Nothing Gets Lost

Both Claude and the user have **all information stored in the thread**. No word will be forgotten, even across multiple sessions. Specialized agents retrieve any information from the thread history and provide it to Claude or the user on demand. Context compaction? No problem - the thread is your permanent record.

### 4. EPIC THREADS - Big Plans, Organized Execution

Not just single issues - **large implementation plans** are conducted via Epic threads. When a set of changes is defined, the Epic thread automatically launches a **WAVE**. A WAVE is composed of many new threads, each one focusing on developing a specific functionality. This enables orchestrated, parallel development of complex features while keeping the big picture in the Epic.

```
EPIC THREAD: "Implement Authentication System"
    │
    └── WAVE 1
        ├── Issue #101: User registration
        ├── Issue #102: Login/logout flow
        ├── Issue #103: Password reset
        └── Issue #104: Session management
    │
    └── WAVE 2
        ├── Issue #105: OAuth integration
        ├── Issue #106: Two-factor auth
        └── Issue #107: API tokens
```

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
