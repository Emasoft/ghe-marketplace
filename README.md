<div align="center">

# GHE

### **G**it**H**ub-**E**lements

**Persistent Memory for Claude Code**

[![Version](https://img.shields.io/badge/version-0.1.0--alpha-blue.svg)](https://github.com/Emasoft/ghe-marketplace)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin-purple.svg)](https://claude.ai/code)

*Turn GitHub Issues into a persistent memory system for AI agents.*

</div>

---

> **ALPHA** - This plugin is in early development. APIs and workflows may change.

## What is GHE?

GHE is a Claude Code plugin that transforms GitHub Issues into a **persistent memory system** for AI-assisted development. Your work survives context compaction, your team stays synchronized, and nothing gets lost.

<table>
<tr>
<td>

**Multi-session continuity**<br/>
<sub>Continue where you left off</sub>

</td>
<td>

**Automated workflow**<br/>
<sub>DEV &rarr; TEST &rarr; REVIEW</sub>

</td>
<td>

**Team collaboration**<br/>
<sub>Humans + AI in sync</sub>

</td>
<td>

**Perfect recall**<br/>
<sub>Every detail preserved</sub>

</td>
</tr>
</table>

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

---

## Why GHE?

<table>
<tr>
<td width="80" align="center">
<img src="https://img.icons8.com/fluency/96/synchronize.png" width="48"/>
</td>
<td>

### SESSION CONTINUITY

**Never lose information again.**

No more losing information and details every time the session is **COMPACTED**. A hook and a team of agents will automatically align Claude with the thread on GitHub where all developments, ideas, data, files, progress, information, results, problems, reports, actions, logs, changes to the code are stored in their original chronological flow of events.

</td>
</tr>
<tr>
<td width="80" align="center">
<img src="https://img.icons8.com/fluency/96/goal.png" width="48"/>
</td>
<td>

### ON TRACK

**Always focused on the current task.**

Each GitHub Issue thread keeps Claude **always focused on the current task**. No more context drift or mixing different problems together.

</td>
</tr>
<tr>
<td width="80" align="center">
<img src="https://img.icons8.com/fluency/96/conference-call.png" width="48"/>
</td>
<td>

### ALIGNED TEAM WORK

**Easy collaboration across humans and AI.**

Other collaborators that have installed the GHE plugin will be able to **collaborate easily and be always up to date** following the thread and commenting in it.

</td>
</tr>
<tr>
<td width="80" align="center">
<img src="https://img.icons8.com/fluency/96/brain.png" width="48"/>
</td>
<td>

### PERFECT MEMORY

**Nothing gets forgotten.**

Both Claude and the user will have **all the information stored in the thread**. No word will be forgotten. Specialized agents will find any information from the thread and will provide it to Claude or the user.

</td>
</tr>
<tr>
<td width="80" align="center">
<img src="https://img.icons8.com/fluency/96/parallel-tasks.png" width="48"/>
</td>
<td>

### EPIC THREADS

**Big implementation plans with WAVES.**

Not only single issues, but **big implementation plans** will be conducted via Epic threads. Every time a set of changes is defined, the Epic thread will launch automatically a **WAVE**. A WAVE will be composed by many new threads, each one focusing on developing a functionality.

</td>
</tr>
</table>

<details>
<summary><b>Example: Epic Thread with Waves</b></summary>

```
EPIC THREAD: "Implement Authentication System"
    │
    ├── WAVE 1
    │   ├── Issue #101: User registration
    │   ├── Issue #102: Login/logout flow
    │   ├── Issue #103: Password reset
    │   └── Issue #104: Session management
    │
    └── WAVE 2
        ├── Issue #105: OAuth integration
        ├── Issue #106: Two-factor auth
        └── Issue #107: API tokens
```

</details>

---

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
