# GitHub Elements Plugin

A Claude Code plugin for using GitHub Issues as persistent memory with orchestrated DEV/TEST/REVIEW workflow management.

## Overview

GitHub Elements provides a complete system for:
- **Persistent Memory**: GitHub Issues survive context exhaustion
- **Workflow Orchestration**: Automated DEV -> TEST -> REVIEW lifecycle
- **Agent Coordination**: Specialized agents for each workflow phase
- **Memory Integration**: Syncs with SERENA memory bank

## Installation

### From Dev Marketplace

```bash
# Add to your project's .claude/settings.json
{
  "plugins": [
    {
      "name": "github-elements",
      "marketplace": "skill-factory-dev",
      "path": "github-elements-plugin"
    }
  ]
}
```

## Features

### The Circular Phase Order

```
        +--------------------------------------------+
        |                                            |
        v                                            |
    DEV --------> TEST --------> REVIEW -------------+
     |             |               |                 |
     |             |               v                 |
     |             |         PASS? -> merge to main  |
     |             |               |                 |
     |             |         FAIL? ------------------+
     |        Bug fixes ONLY       (to DEV, never TEST)
     |
 Development work
 (code + tests)
```

### Specialized Agents

> **"Enforce no Time, Only Order"**

| Agent | Model | Purpose |
|-------|-------|---------|
| `github-elements-orchestrator` | opus | Central coordinator |
| `dev-thread-manager` | opus | DEV thread lifecycle |
| `test-thread-manager` | sonnet | TEST thread lifecycle |
| `review-thread-manager` | sonnet | REVIEW thread lifecycle |
| `phase-gate` | sonnet | Transition validation |
| `memory-sync` | haiku | SERENA memory sync |
| `enforcement` | haiku | Violation detection |
| `ci-issue-opener` | haiku | CI failure issues |
| `pr-checker` | haiku | PR requirements |
| `reporter` | haiku | Status reports |

---

## Argos Panoptes - The All-Seeing Guardian

> *"Argos Panoptes"* (Ancient Greek: Ἄργος Πανόπτης, "All-seeing Argos") was a giant with a hundred eyes in Greek mythology. He was a faithful guardian who never slept, as some of his eyes were always awake.

### What is Argos Panoptes?

**Argos Panoptes is NOT a Claude Code agent.** It is powered by the **Claude GitHub App** and runs as GitHub Actions workflows that monitor your repository 24/7, even when you are offline.

While the specialized agents (Hera, Hephaestus, Ares, Chronos) are local Claude Code subagents that require you to be online with an active Claude Code session, Argos Panoptes operates autonomously through GitHub's infrastructure.

### What Argos Does

Argos Panoptes serves as your repository's tireless sentinel:

1. **Monitors Events 24/7**: Watches for PRs, issues, comments, security alerts, and CI failures
2. **Triages Incoming Work**: Validates submissions, asks for missing information, applies labels
3. **Queues Work for Specialists**: Prepares issues for the appropriate agent to handle when you're online
4. **Maintains Order**: Prevents spam, flags policy violations, tracks CI health
5. **Never Impersonates**: Always identifies itself as "Argos Panoptes (The All-Seeing)" and clearly states which specialist agent will handle the work

### How Argos Differs from Local Agents

| Aspect | Argos Panoptes | Local Agents (Hera, Hephaestus, etc.) |
|--------|----------------|---------------------------------------|
| **Powered by** | Claude GitHub App | Claude Code CLI |
| **Runs when** | 24/7 (GitHub Actions) | Only during active sessions |
| **Can do** | Triage, label, comment, queue | Full development, testing, review |
| **Identity** | Own avatar and banner | Own avatars and banners |
| **Autonomy** | High (automated) | Supervised (you're online) |

### Installing Argos Panoptes

Argos requires the Claude GitHub App to be installed on your repository.

#### Step 1: Install the Claude GitHub App

Run this command in Claude Code:

```
/install-github-app
```

This command will:
- Guide you through GitHub OAuth authentication
- Create a pull request to add the Claude workflow to your repository
- Automatically configure the `CLAUDE_CODE_OAUTH_TOKEN` secret based on your subscription

**Note**: Only the repository owner can run this command. The setup varies based on your Anthropic subscription (Max Pro flat-rate, usage-based credits, etc.).

#### Step 2: Copy the GHE Workflow Files

After the Claude GitHub App is installed, copy the Argos workflows to your repository:

```bash
# From your repository root
mkdir -p .github/workflows
cp path/to/ghe-plugin/examples/github-actions/ghe-*.yml .github/workflows/
```

Or manually copy each workflow file from the `examples/github-actions/` directory.

#### Step 3: Verify Installation

Create a test issue with the `bug` label to verify Argos responds. You should see a comment from Claude with the Argos Panoptes avatar asking for bug report details or confirming the issue is ready for review.

### Events Argos Reacts To

When you're offline, Argos automatically processes these events and queues work for your next session:

| Event | Trigger | What Argos Does | Queued For |
|-------|---------|-----------------|------------|
| **A: PR Opened** | Someone opens a pull request | Creates a REVIEW issue linking to the PR, adds `review` and `source:pr` labels, comments on the PR with the queue issue link | Hera |
| **B: Bug Report** | Someone opens an issue with `bug` label | Validates the bug report template (description, steps to reproduce, expected vs actual behavior, environment). If complete: adds `review` and `ready` labels. If incomplete: adds `needs-info` label and politely asks for missing details | Hera |
| **C: Feature Request** | Someone opens an issue with `enhancement` or `feature` label | Validates the feature request (description, use case). If complete: adds `dev` and `ready` labels. If incomplete: adds `needs-info` label and asks for clarification | Hephaestus |
| **D: Policy Violation** | Someone posts a comment with harassment, threats, spam, or discrimination | Issues a warning (maximum 3 warnings per user). After 3 warnings: adds `needs-moderation` label for human review. Very conservative - when uncertain, does nothing | Ares |
| **E: SPAM Detected** | Someone posts obvious spam (requires 3+ indicators) | Closes the issue with `spam` label. Extremely conservative - only acts on obvious spam (new account + no activity + promotional links + crypto/gambling content). False positives are unacceptable | - |
| **F: Security Alert** | GitHub detects a Dependabot alert, code scanning alert, or secret scanning alert | Creates an URGENT issue with `dev`, `urgent`, and `security` labels. If critical severity: also adds `blocked` label. Never dismisses alerts | Hephaestus |
| **G: CI/CD Failure** | A workflow fails (excluding GHE workflows to prevent loops) | Creates or updates a CI failure issue with `review`, `ci-failure`, and `source:ci` labels. Tracks consecutive failures and adds `urgent` label after 3+ failures | Chronos |

### Argos Design Principles

1. **Conservative by Default**: When uncertain, Argos creates an URGENT issue and waits for human decision rather than taking autonomous action
2. **No False Positives**: Especially for SPAM and moderation - better to miss spam than block a legitimate user
3. **Respect User Autonomy**: Only the repository owner makes final decisions. Argos never bans, deletes, or takes irreversible actions
4. **Prevent Infinite Loops**: Argos workflows exclude bot actors and other GHE workflows to prevent cascading triggers
5. **No Deletions**: Issues are closed and labeled, never deleted (preserves complete audit trail)
6. **Clear Identity**: Always signs as "Argos Panoptes (The All-Seeing)" and explains which specialist will handle the work

### What Argos Does NOT Flag as Violations

To avoid false positives, these are explicitly NOT considered violations:

- Mentioning other tools or projects positively
- Technical disagreements (even heated ones)
- Asking questions repeatedly
- Non-English comments
- Sarcasm or humor
- Respectful criticism of the project

### Argos Workflow Files

| Workflow | Event | Purpose |
|----------|-------|---------|
| `ghe-pr-review.yml` | A | Queue PRs for review |
| `ghe-bug-triage.yml` | B | Validate and triage bug reports |
| `ghe-feature-triage.yml` | C | Validate and triage feature requests |
| `ghe-moderation.yml` | D | Detect policy violations |
| `ghe-spam-detection.yml` | E | Conservative spam detection |
| `ghe-security-alert.yml` | F | Security vulnerability handling |
| `ghe-ci-failure.yml` | G | CI/CD failure tracking |

### Division of Labor: Argos vs Local Plugin

| Capability | Argos (GitHub Actions) | Local Plugin (Claude Code) |
|------------|------------------------|----------------------------|
| 24/7 Monitoring | Yes | No |
| Triage new issues/PRs | Yes | No |
| Validate templates | Yes | No |
| Apply labels | Yes | Yes |
| @claude mentions (basic Q&A) | Yes | Yes (full) |
| Claim issues | No | Yes |
| Post checkpoints | No | Yes |
| Transition phases | No | Yes |
| SERENA memory sync | No | Yes |
| Write/modify code | No | Yes |
| Run tests | No | Yes |
| Create PRs | No | Yes |

---

### Natural Language Operations

Just tell Claude what you want. These operation skills are discoverable:

| Say | Skill Activated | What Happens |
|-----|-----------------|--------------|
| "Show me the workflow status" | `ghe-status` | Spawns reporter agent |
| "Claim issue #201" | `ghe-claim` | Validates and claims with protocol |
| "Post a checkpoint" | `ghe-checkpoint` | Records state to active thread |
| "Transition to TEST" | `ghe-transition` | Validates and executes transition |
| "Give me a metrics report" | `ghe-report` | Generates detailed report |

### SessionStart Hook

Automatically loads active thread context when a session starts:
- Finds in-progress issues assigned to you
- Loads the last checkpoint state
- Activates the skill
- Syncs with SERENA memory bank

## Workflow Rules

### One Thread At A Time

For any feature/epic, only ONE thread can be open at a time:
- DEV -> close DEV, open TEST
- TEST -> close TEST, open REVIEW
- REVIEW PASS -> close REVIEW, merge
- REVIEW FAIL -> close REVIEW, reopen DEV

### Phase Responsibilities

| Phase | Can Do | Cannot Do |
|-------|--------|-----------|
| **DEV** | Write code, write tests, structural changes | Render verdicts |
| **TEST** | Run tests, fix simple bugs | Write new tests, structural changes |
| **REVIEW** | Evaluate, render verdicts | Write code, demote to TEST |

### Demotion Rules

- **REVIEW -> DEV**: Always (for any fixes)
- **TEST -> DEV**: When structural changes needed
- **REVIEW -> TEST**: NEVER (must go to DEV)

## Memory Integration

### Three-Tier Storage

```
Tier 1: TodoWrite         (Session - transient)
        |
        v
Tier 2: GitHub Elements   (Persistent - 64KB limit)
        |
        v
Tier 3: SERENA Memory     (Archive - unlimited)
```

### SERENA Memory Structure

```
.serena/memories/
├── activeContext.md    # Current session focus
├── progress.md         # Completed work
├── techContext.md      # Technical decisions
├── dataflow.md         # System interfaces
├── projectBrief.md     # Project overview
└── test_results/       # Test execution records
```

## Usage Examples

### Start Work on a Feature

```
User: "Show me the workflow status"
Claude: [Spawns reporter, shows active/available work]

User: "Claim issue #201"
Claude: [Validates phase order, claims issue, posts comment, sets up worktree]

... do development work ...

User: "Post a checkpoint"
Claude: [Gathers state, posts checkpoint to issue, syncs memory]

User: "I'm done with DEV, transition to TEST"
Claude: [Validates transition, closes DEV, opens TEST thread]
```

### Run Maintenance Cycle

```
User: "Run a maintenance cycle on the github elements workflow"

Claude: [Spawns orchestrator which:
  1. Spawns reporter for status
  2. Checks each thread with phase-gate
  3. Executes any needed transitions
  4. Syncs memory bank
  5. Checks for violations
  6. Reports summary back]
```

## Plugin Structure

```
github-elements-plugin/
├── .claude-plugin/
│   ├── plugin.json           # Plugin manifest
│   └── marketplace.json      # Dev marketplace config
├── skills/
│   ├── github-elements-tracking/
│   │   ├── SKILL.md          # Main skill
│   │   └── references/       # Playbooks (P1-P9)
│   ├── ghe-status/           # Status operation skill
│   ├── ghe-claim/            # Claim operation skill
│   ├── ghe-checkpoint/       # Checkpoint operation skill
│   ├── ghe-transition/       # Transition operation skill
│   └── ghe-report/           # Report operation skill
├── agents/
│   ├── github-elements-orchestrator.md
│   ├── dev-thread-manager.md
│   ├── test-thread-manager.md
│   ├── review-thread-manager.md
│   ├── phase-gate.md
│   ├── memory-sync.md
│   ├── enforcement.md
│   ├── ci-issue-opener.md
│   ├── pr-checker.md
│   └── reporter.md
├── hooks/
│   └── hooks.json
├── examples/
│   └── github-actions/       # 24/7 automation workflows
└── README.md
```

## Configuration

GitHub Elements supports per-project configuration via `.claude/github-elements.local.md`.

### Quick Setup

Run the setup command to configure interactively:

```
/github-elements:setup
```

This prompts for your preferences and creates the settings file.

### Manual Configuration

Create `.claude/github-elements.local.md` in your project:

```markdown
---
enabled: true
enforcement_level: standard
serena_sync: true
auto_worktree: false
checkpoint_interval_minutes: 30
notification_level: normal
default_reviewer: "your-github-username"
epic_label_prefix: "epic:"
---

# GitHub Elements Configuration

Your custom notes and context here.
```

### Settings Reference

| Setting | Values | Default | Description |
|---------|--------|---------|-------------|
| `enabled` | true/false | true | Enable/disable plugin entirely |
| `enforcement_level` | strict/standard/lenient | standard | Rule strictness |
| `serena_sync` | true/false | true | Sync with SERENA memory bank |
| `auto_worktree` | true/false | false | Auto-create git worktree on claim |
| `checkpoint_interval_minutes` | 0/15/30/60 | 30 | Reminder interval (0=disabled) |
| `notification_level` | verbose/normal/quiet | normal | Output verbosity |
| `default_reviewer` | string | "" | Default GitHub reviewer username |
| `epic_label_prefix` | string | "epic:" | Prefix for epic labels |

### Enforcement Levels

- **strict**: Block violations, require all criteria, no exceptions
- **standard**: Warn on first violation, block on repeat, allow override with reason
- **lenient**: Advisory only, log but don't block

### Gitignore

Settings files are user-local and should not be committed:

```gitignore
# Add to .gitignore
.claude/*.local.md
```

### Changing Settings

After editing `.claude/github-elements.local.md`, restart Claude Code for changes to take effect. Hooks cannot be hot-swapped within a session.

## Prerequisites

- GitHub CLI (`gh`) installed and authenticated
- Git repository with GitHub remote
- (Optional) SERENA MCP for memory bank integration

## License

Apache 2.0

## Author

Emasoft
