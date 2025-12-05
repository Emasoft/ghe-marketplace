<div align="center">

# GHE

### **G**it**H**ub-**E**lements

**Persistent Memory for Claude Code**

[![Version](https://img.shields.io/badge/version-0.2.3--alpha-blue.svg)](https://github.com/Emasoft/ghe-marketplace/releases/tag/v0.2.3-alpha)
[![Release](https://img.shields.io/github/v/release/Emasoft/ghe-marketplace?include_prereleases&label=release)](https://github.com/Emasoft/ghe-marketplace/releases)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Claude Code](https://img.shields.io/badge/Claude%20Code-Plugin-purple.svg)](https://docs.anthropic.com/en/docs/claude-code)
[![GitHub Issues](https://img.shields.io/github/issues/Emasoft/ghe-marketplace)](https://github.com/Emasoft/ghe-marketplace/issues)
[![Status](https://img.shields.io/badge/status-alpha-orange.svg)](https://github.com/Emasoft/ghe-marketplace)

*Turn GitHub Issues into a persistent memory system for AI agents.*

</div>

---

> **ALPHA** - This plugin is in early development. APIs and workflows may change.

## What is GHE?

GHE is a Claude Code plugin that transforms GitHub Issues into a **persistent memory system** for AI-assisted development. Your work survives context compaction, your team stays synchronized, and nothing gets lost.

| Multi-session continuity | Automated workflow | Team collaboration | Perfect recall |
|:---:|:---:|:---:|:---:|
| Continue where you left off | DEV &rarr; TEST &rarr; REVIEW | Humans + AI in sync | Every detail preserved |

---

## The Element

<p align="center">
  <img src="assets/element-triangle.svg" alt="The Element Triangle" width="400"/>
</p>

An **Element** is a unit of information stored as a single message/reply to a GitHub Issue in the issue tracker. Every piece of information in GHE is an Element.

<p align="center">
  <img src="assets/element-classification.svg" alt="Element Classification System" width="900"/>
</p>

**The power of this system**: GitHub threads allow you to **isolate and preserve the context of each task**. Human developers and AI agents can discuss progress while keeping the conversation focused and on track, instead of mixing different issues together.

At any moment, you can tell Claude: *"Let's switch to working on issue #42"* - and Claude instantly gets up to speed by reading that issue's thread. It spawns a subagent to read and summarize the thread, so it won't waste your tokens or context memory. Each issue is a self-contained knowledge base for its task.

There are **3 types of Elements**:

### Element of Knowledge

A message describing **plans, ideas, and theory** - discussion that informs but doesn't change the project:
- Requirements, specifications, design documents
- Architecture decisions, algorithms, protocols
- APIs, data structures, formats
- Explanations, documentation, theory

> "The Talk" - Plans and ideas before they become reality.

### Element of Action

A message containing or linking **tangible project artifacts** - the only element type that actually changes the project:

**CODE:**
- Code snippets, patches, diffs
- Functions, classes, scripts
- Configuration files

**ASSETS:**
- Images, sprites, icons, graphics
- Audio, sound effects, music
- Video, animations
- 3D models, textures
- Stylesheets, fonts

> "The Reality" - If it ships with the project, it's an ACTION.

### Element of Judgement

A message containing **evaluation and feedback** - assessment of what exists:
- Bug reports, error descriptions
- Code reviews, test results
- Performance issues, security concerns
- Quality assessments, critiques
- Any analysis of code or behavior

> "The Verdict" - Evaluation of the work done.

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

### How WAVES Work

An **Epic Thread** is a master issue that describes a large feature or milestone. Instead of cramming everything into one issue, the Epic orchestrates work through **WAVES**:

1. **WAVE 1** - The Epic spawns the first set of sub-issues, each tackling a specific piece of the feature
2. Each sub-issue goes through the DEV &rarr; TEST &rarr; REVIEW cycle independently
3. When WAVE 1 completes, results are summarized back to the Epic
4. **WAVE 2** - Based on WAVE 1 results, the next set of sub-issues is spawned
5. This continues until the Epic is complete

**Benefits:**
- Parallel development across multiple sub-issues
- Clear dependencies between waves
- Progress visible at both Epic and sub-issue level
- Easy to pause/resume large features
- Natural checkpoints for review

```
EPIC THREAD: "Implement Authentication System"
    │
    ├── WAVE 1 (Foundation)
    │   ├── Issue #101: User registration
    │   ├── Issue #102: Login/logout flow
    │   ├── Issue #103: Password reset
    │   └── Issue #104: Session management
    │
    └── WAVE 2 (Advanced Features)
        ├── Issue #105: OAuth integration
        ├── Issue #106: Two-factor auth
        └── Issue #107: API tokens
```

---

## Installation

### Option 1: Add Marketplace (Recommended)

```bash
/plugin marketplace add Emasoft/ghe-marketplace
```

Then install the plugin:

```bash
/plugin install ghe@ghe-marketplace
```

Restart Claude Code. Done!

### Option 2: Manual Clone

```bash
git clone https://github.com/Emasoft/ghe-marketplace.git ~/ghe-marketplace
```

Then add as local marketplace:

```bash
/plugin marketplace add ~/ghe-marketplace
/plugin install ghe@ghe-marketplace
```

---

## Post-Installation

Run the setup command in your project:

```
/ghe:setup
```

This interactive menu will ask you about:
- Enable/disable plugin for this project
- Enforcement level (strict/standard/lenient)
- SERENA memory bank integration
- Auto worktree creation
- Checkpoint reminder intervals
- Notification verbosity
- Default reviewer
- Stale threshold

Settings are saved to `.claude/ghe.local.md`.

---

## Prerequisites

### 1. Claude Code

GHE is a plugin for **Claude Code**, Anthropic's official AI coding assistant.

| | |
|:---:|:---|
| <a href="https://www.anthropic.com"><img src="https://img.icons8.com/fluency/96/artificial-intelligence.png" width="48"/></a> | **Anthropic** - The company behind Claude<br/>https://www.anthropic.com |
| <a href="https://docs.anthropic.com/en/docs/claude-code"><img src="https://img.icons8.com/fluency/96/console.png" width="48"/></a> | **Claude Code Documentation**<br/>https://docs.anthropic.com/en/docs/claude-code |
| <a href="https://www.npmjs.com/package/@anthropic-ai/claude-code"><img src="https://cdn.jsdelivr.net/gh/devicons/devicon/icons/npm/npm-original-wordmark.svg" width="48"/></a> | **Install Claude Code**<br/>`npm install -g @anthropic-ai/claude-code` |

### 2. GitHub CLI

GHE uses the GitHub CLI (`gh`) to interact with your repositories.

```bash
# macOS
brew install gh

# Windows
winget install GitHub.cli

# Linux
sudo apt install gh
```

Then authenticate:
```bash
gh auth login
```

---

## Plugin Contents

### GHE v0.2.3-alpha

| Component | Count | Description |
|-----------|-------|-------------|
| Agents | 10 | DEV/TEST/REVIEW managers, orchestrator, enforcement, reporting |
| Skills | 6 | ghe-status, ghe-claim, ghe-checkpoint, ghe-transition, ghe-report |
| Commands | 1 | `/ghe:setup` |
| Hooks | 1 | SessionStart for context recovery |

### Agents

| Avatar | Name | Agent ID | Purpose |
|:------:|:----:|----------|---------|
| <img src="plugins/ghe/assets/avatars/hephaestus.png" width="77"/> | **Hephaestus** | `ghe:dev-thread-manager` | Builds and shapes the work (DEV phase) |
| <img src="plugins/ghe/assets/avatars/artemis.png" width="77"/> | **Artemis** | `ghe:test-thread-manager` | Hunts down bugs and verifies behavior (TEST phase) |
| <img src="plugins/ghe/assets/avatars/hera.png" width="77"/> | **Hera** | `ghe:review-thread-manager` | Evaluates quality and provides feedback (REVIEW phase) |
| <img src="plugins/ghe/assets/avatars/athena.png" width="77"/> | **Athena** | `ghe:github-elements-orchestrator` | Strategist coordinating the workflow |
| <img src="plugins/ghe/assets/avatars/themis.png" width="77"/> | **Themis** | `ghe:phase-gate` | Upholds rules and judges phase transitions |
| <img src="plugins/ghe/assets/avatars/mnemosyne.png" width="77"/> | **Mnemosyne** | `ghe:memory-sync` | Records and preserves knowledge |
| <img src="plugins/ghe/assets/avatars/ares.png" width="77"/> | **Ares** | `ghe:enforcement` | Enforces workflow rules, can suspend or block |
| <img src="plugins/ghe/assets/avatars/hermes.png" width="77"/> | **Hermes** | `ghe:reporter` | Messenger delivering status reports and metrics |
| <img src="plugins/ghe/assets/avatars/chronos.png" width="77"/> | **Chronos** | `ghe:ci-issue-opener` | Sounds the alarm when CI fails |
| <img src="plugins/ghe/assets/avatars/cerberus.png" width="77"/> | **Cerberus** | `ghe:pr-checker` | Guards the gates, validates PRs |

### Argos Panoptes - The All-Seeing Guardian

<table>
<tr>
<td width="100" align="center">
<img src="plugins/ghe/assets/avatars/argos.png" width="77"/>
</td>
<td>

**Argos Panoptes** is the foremost guardian and first responder to all GitHub events. Unlike the agents above, Argos is **NOT** a Claude Code plugin agent - it's a **GitHub Action** that runs 24/7 on GitHub's infrastructure.

</td>
</tr>
</table>

#### Why Argos is Different

| Plugin Agents | Argos Panoptes |
|---------------|----------------|
| Run locally in Claude Code | Runs on GitHub's servers |
| Active only during your session | Active 24/7, even when you sleep |
| Respond when you invoke them | Responds automatically to events |
| Installed via `/plugin install` | Installed by copying workflow files |

**Argos never sleeps.** When a bug report comes in at 3 AM, Argos validates it. When a PR is opened, Argos queues it for review. When CI fails, Argos documents it. The other agents (Hera, Hephaestus, etc.) handle the work when you're online - Argos ensures nothing is missed while you're away.

#### Events Argos Responds To

| Event | Trigger | What Argos Does |
|-------|---------|-----------------|
| **PR Opened** | `pull_request: [opened, ready_for_review]` | Creates REVIEW issue for Hera, queues PR for review |
| **Bug Report** | `issues: [opened, edited]` with `bug` label | Validates bug report, adds phase labels, requests missing info |
| **Feature Request** | `issues: [opened, edited]` with `enhancement`/`feature` label | Validates feature request, queues for Hephaestus |
| **Comment Posted** | `issue_comment: [created]` | Monitors for policy violations, warns or flags for Ares |
| **Possible SPAM** | `issues: [opened]` | Conservative spam detection (requires 3+ indicators) |
| **CI Failure** | `workflow_run: [completed]` with failure | Creates/updates CI failure issue for Chronos |
| **Security Alert** | Security events (Dependabot, CodeQL, secrets) | Creates URGENT issue for Hephaestus |

#### Installing Argos Panoptes

Argos requires **manual installation** in your repository. Copy the workflow files from `.github/workflows/`:

```bash
# From the ghe-marketplace repository, copy all ghe-*.yml files to your repo
cp .github/workflows/ghe-*.yml /path/to/your-repo/.github/workflows/
```

**Required secrets** in your repository:
- `CLAUDE_CODE_OAUTH_TOKEN` - For the Claude Code Action to authenticate

After installation, Argos will automatically respond to events in your repository. All comments from Argos are signed as "**Argos Panoptes (The All-Seeing)**" and use the argos.png avatar.

### Skills

| Skill | Usage |
|-------|-------|
| `github-elements-tracking` | Full workflow documentation |

---

## Workflow

```
DEV ──► TEST ──► REVIEW ──► DEV ...
                    │
                    └──► PASS? → merge to main
```

- **DEV**: Write code and tests
- **TEST**: Run tests, fix simple bugs
- **REVIEW**: Evaluate quality, render verdict

---

## Troubleshooting

**Something not working? Don't worry! Let's fix it together.**

### Claude doesn't see the plugin

**What happened?** Claude Code didn't find the plugin in your folders.

**Let's check:**
1. Open your terminal
2. Type this and press Enter:
   ```bash
   /plugin marketplace list
   ```
3. Do you see `ghe-marketplace`? Great! Now check:
   ```bash
   /plugin
   ```
4. Look for `ghe` in the list. If not there, run:
   ```bash
   /plugin install ghe@ghe-marketplace
   ```
5. Restart Claude Code.

### GitHub CLI says "not logged in"

**What happened?** The `gh` tool doesn't know who you are yet.

**Let's fix it:**
1. Open your terminal
2. Type this and press Enter:
   ```bash
   gh auth login
   ```
3. Follow the steps on screen. Pick "GitHub.com" and "HTTPS".
4. It will open your browser. Click "Authorize".
5. Done! Now `gh` knows you.

### The /ghe:setup command doesn't work

**What happened?** Claude Code can't find the command.

**Let's check:**
1. Did you restart Claude Code after installing? (Close it completely, then open again)
2. Is the plugin installed? Run `/plugin` and look for `ghe`
3. Still not working? Try reinstalling:
   ```bash
   /plugin marketplace update ghe-marketplace
   /plugin install ghe@ghe-marketplace
   ```

### Claude forgets everything after compaction

**What happened?** The SessionStart hook might not be running.

**Let's check:**
1. Do you have a GitHub Issue for your project? GHE needs one to save your work.
2. Did you run `/ghe:setup` in your project? This tells GHE which repo to use.
3. Check the settings file exists: `.claude/ghe.local.md`

### I see errors about "permission denied"

**What happened?** Some files need permission to run.

**Let's fix it:**
```bash
chmod +x ~/.claude/plugins/cache/ghe-marketplace/plugins/ghe/scripts/*.sh 2>/dev/null
chmod +x ~/.claude/plugins/cache/ghe-marketplace/plugins/ghe/hooks/scripts/*.sh 2>/dev/null
```

Now try again!

### Still stuck?

**That's okay!** Here's what to do:

1. **Check the GitHub Issues**: Maybe someone had the same problem.
   - Go to: https://github.com/Emasoft/ghe-marketplace/issues

2. **Ask for help**: Open a new issue and tell us:
   - What you tried to do
   - What happened instead
   - Copy any error messages you see

We'll help you figure it out!

---

## Updating

```bash
/plugin marketplace update ghe-marketplace
```

---

## Uninstalling

```bash
/plugin uninstall ghe
/plugin marketplace remove ghe-marketplace
```

---

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

- **Issues**: https://github.com/Emasoft/ghe-marketplace/issues
- **Discussions**: https://github.com/Emasoft/ghe-marketplace/discussions

## Acknowledgments

- [Anthropic](https://www.anthropic.com) for creating Claude and Claude Code
- The Claude Code community for inspiration and feedback

---

## License

MIT License - Copyright (c) 2025 Emasoft

See [LICENSE](LICENSE) for details.

---

<div align="center">

**Made with Claude Code**

[Emasoft](https://github.com/Emasoft) | [Report Bug](https://github.com/Emasoft/ghe-marketplace/issues) | [Request Feature](https://github.com/Emasoft/ghe-marketplace/issues)

</div>
