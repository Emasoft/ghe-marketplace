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

## GitHub Actions Integration (24/7 Automation)

In addition to the local Claude Code plugin, you can install GitHub Actions workflows that run 24/7 on GitHub for automated monitoring and assistance.

### Available Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ghe-stale-monitor.yml` | Daily (cron) | Detect threads inactive >24h |
| `ghe-label-validator.yml` | Label changes | Validate GHE label combinations |
| `ghe-pr-checker.yml` | PR events | Verify PRs link to GHE threads |
| `ghe-ci-opener.yml` | CI failures | Auto-open issues on test failures |
| `ghe-assistant.yml` | @claude mentions | Interactive GHE help in comments |

### Division of Labor

| Capability | GitHub Actions | Local Plugin |
|------------|----------------|--------------|
| 24/7 Monitoring | Yes | No |
| Stale detection | Yes | No |
| Label validation | Yes | No |
| @claude Q&A | Yes (basic) | Yes (full) |
| Claim issues | No | Yes |
| Post checkpoints | No | Yes |
| Transition phases | No | Yes |
| SERENA memory sync | No | Yes |
| Complex code changes | No | Yes |

### Installation

```bash
# Step 1: Install Claude GitHub App (in Claude Code)
/install-github-app

# Step 2: Copy workflows to your repository
mkdir -p .github/workflows
cp examples/github-actions/ghe-*.yml .github/workflows/
```

The `/install-github-app` command authenticates Claude and stores the OAuth token in your repository secrets automatically.

See `examples/github-actions/README.md` for detailed configuration options.

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
stale_threshold_hours: 24
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
| `stale_threshold_hours` | number | 24 | Hours before thread is stale |
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
