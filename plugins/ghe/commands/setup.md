---
description: "Configure GitHub Elements plugin for this project"
allowed-tools: ["Write", "Read", "AskUserQuestion", "Bash"]
---

# GitHub Elements Setup Command

This command creates `.claude/ghe.local.md` with user preferences.

## Step 1: Check Existing Configuration

First check if `.claude/ghe.local.md` already exists:
- If exists, read current settings and offer to modify
- If not, create new configuration

## Step 2: Gather User Preferences

Use AskUserQuestion to collect configuration in multiple batches:

### Batch 1: Core Settings

```json
{
  "questions": [
    {
      "question": "Enable GitHub Elements tracking for this project?",
      "header": "Enable",
      "multiSelect": false,
      "options": [
        {"label": "Yes", "description": "Activate GHE workflow tracking"},
        {"label": "No", "description": "Disable plugin for this project"}
      ]
    },
    {
      "question": "Which workflow enforcement level?",
      "header": "Enforcement",
      "multiSelect": false,
      "options": [
        {"label": "Strict", "description": "Block violations, require all criteria"},
        {"label": "Standard", "description": "Warn on violations, allow override"},
        {"label": "Lenient", "description": "Minimal checks, advisory only"}
      ]
    },
    {
      "question": "Enable SERENA memory bank integration?",
      "header": "SERENA Sync",
      "multiSelect": false,
      "options": [
        {"label": "Yes", "description": "Auto-sync checkpoints to .serena/memories/"},
        {"label": "No", "description": "Use GitHub Issues only"}
      ]
    }
  ]
}
```

### Batch 2: Automation Settings

```json
{
  "questions": [
    {
      "question": "Auto-create git worktree when claiming issues?",
      "header": "Auto Worktree",
      "multiSelect": false,
      "options": [
        {"label": "Yes", "description": "Create isolated worktree per issue"},
        {"label": "No", "description": "Work in main repo directory"}
      ]
    },
    {
      "question": "Checkpoint reminder interval?",
      "header": "Reminders",
      "multiSelect": false,
      "options": [
        {"label": "15 minutes", "description": "Frequent reminders"},
        {"label": "30 minutes", "description": "Standard interval (recommended)"},
        {"label": "60 minutes", "description": "Infrequent reminders"},
        {"label": "Disabled", "description": "No automatic reminders"}
      ]
    },
    {
      "question": "How verbose should notifications be?",
      "header": "Verbosity",
      "multiSelect": false,
      "options": [
        {"label": "Verbose", "description": "All details and status updates"},
        {"label": "Normal", "description": "Important updates only"},
        {"label": "Quiet", "description": "Errors and warnings only"}
      ]
    }
  ]
}
```

### Batch 3: GitHub Settings

```json
{
  "questions": [
    {
      "question": "Default reviewer for REVIEW phase? (GitHub username)",
      "header": "Reviewer",
      "multiSelect": false,
      "options": [
        {"label": "Self", "description": "Assign yourself as reviewer"},
        {"label": "Team Lead", "description": "Use configured team lead"},
        {"label": "Custom", "description": "Specify a GitHub username"}
      ]
    },
    {
      "question": "Stale thread threshold (hours inactive)?",
      "header": "Stale Threshold",
      "multiSelect": false,
      "options": [
        {"label": "12 hours", "description": "Quick detection"},
        {"label": "24 hours", "description": "Standard (recommended)"},
        {"label": "48 hours", "description": "Lenient threshold"},
        {"label": "72 hours", "description": "Extended threshold"}
      ]
    }
  ]
}
```

## Step 3: Parse Answers and Create Settings

Convert user answers to settings values:

| Answer | Setting | Value |
|--------|---------|-------|
| Enable: Yes | enabled | true |
| Enable: No | enabled | false |
| Enforcement: Strict | enforcement_level | strict |
| Enforcement: Standard | enforcement_level | standard |
| Enforcement: Lenient | enforcement_level | lenient |
| SERENA Sync: Yes | serena_sync | true |
| SERENA Sync: No | serena_sync | false |
| Auto Worktree: Yes | auto_worktree | true |
| Auto Worktree: No | auto_worktree | false |
| Reminders: 15 min | checkpoint_interval_minutes | 15 |
| Reminders: 30 min | checkpoint_interval_minutes | 30 |
| Reminders: 60 min | checkpoint_interval_minutes | 60 |
| Reminders: Disabled | checkpoint_interval_minutes | 0 |
| Verbosity: Verbose | notification_level | verbose |
| Verbosity: Normal | notification_level | normal |
| Verbosity: Quiet | notification_level | quiet |
| Reviewer: Self | default_reviewer | (get from gh api user) |
| Reviewer: Team Lead | default_reviewer | (ask for username) |
| Reviewer: Custom | default_reviewer | (ask for username) |
| Stale: 12h | stale_threshold_hours | 12 |
| Stale: 24h | stale_threshold_hours | 24 |
| Stale: 48h | stale_threshold_hours | 48 |
| Stale: 72h | stale_threshold_hours | 72 |

## Step 4: Get GitHub Username (if needed)

If reviewer is "Self", get current GitHub user:

```bash
gh api user --jq '.login'
```

If reviewer is "Team Lead" or "Custom", ask:

```json
{
  "questions": [
    {
      "question": "Enter the GitHub username for the default reviewer:",
      "header": "Username",
      "multiSelect": false,
      "options": [
        {"label": "Type username", "description": "Enter in the text field"}
      ]
    }
  ]
}
```

## Step 5: Create Settings File

Ensure `.claude/` directory exists:

```bash
mkdir -p .claude
```

Write settings file using Write tool to `.claude/ghe.local.md`:

```markdown
---
enabled: <true/false>
enforcement_level: <strict/standard/lenient>
serena_sync: <true/false>
auto_worktree: <true/false>
checkpoint_interval_minutes: <0/15/30/60>
notification_level: <verbose/normal/quiet>
default_reviewer: "<github-username>"
stale_threshold_hours: <12/24/48/72>
epic_label_prefix: "epic:"
current_issue: null
auto_transcribe: true
---

# GHE Configuration

This project is configured for GHE (GitHub-Elements) workflow tracking.

## Current Settings

- **Enforcement Level**: <level>
- **SERENA Integration**: <yes/no>
- **Auto Worktree**: <yes/no>
- **Checkpoint Reminders**: Every <N> minutes (or disabled)
- **Notification Level**: <level>
- **Default Reviewer**: @<username>
- **Stale Threshold**: <N> hours

## Active Issue Tracking

- **Current Issue**: None (say "lets work on issue #N" to activate)
- **Auto Transcribe**: Yes (all exchanges posted to issue thread)

## Trigger Phrases

To start/resume issue tracking, say:
- "lets work on this new issue" - Creates a new issue
- "lets work on issue #123" - Activates existing issue
- "lets resume working on issue #123" - Resumes existing issue

## Modifying Settings

Edit this file manually and restart Claude Code for changes to take effect.

## Disabling Plugin

Set `enabled: false` in the frontmatter above.
```

## Step 6: Create Required GitHub Labels

Create all labels required by GitHub Elements:

```bash
# Create type labels
gh label create "type:dev" --color "0E8A16" --description "Development thread" --force
gh label create "type:test" --color "FBCA04" --description "Testing thread" --force
gh label create "type:review" --color "1D76DB" --description "Review thread" --force

# Create status labels
gh label create "ready" --color "C2E0C6" --description "Available for claiming" --force
gh label create "in-progress" --color "FEF2C0" --description "Work in progress" --force
gh label create "blocked" --color "D93F0B" --description "Has blocker" --force
gh label create "needs-input" --color "D4C5F9" --description "Waiting for input" --force
gh label create "review-needed" --color "BFDADC" --description "Ready for review" --force

# Create gate labels
gh label create "gate:passed" --color "0E8A16" --description "Review passed" --force
gh label create "gate:failed" --color "D93F0B" --description "Review failed" --force

# Create violation labels
gh label create "violation:phase" --color "B60205" --description "Phase order violation" --force
gh label create "violation:scope" --color "B60205" --description "Scope violation" --force

# Create CI labels
gh label create "ci-failure" --color "D93F0B" --description "CI/CD failure" --force
gh label create "source:ci" --color "C5DEF5" --description "Auto-created from CI" --force

# Create priority labels (for CI failures only)
gh label create "priority:critical" --color "B60205" --description "Blocking main branch" --force

# Create stale label
gh label create "stale" --color "E4E669" --description "No activity for threshold period" --force

echo "All GitHub Elements labels created."
```

## Step 7: Update .gitignore

Ensure settings file is gitignored:

```bash
# Check if .gitignore exists and has the pattern
if ! grep -q ".claude/*.local.md" .gitignore 2>/dev/null; then
  echo "" >> .gitignore
  echo "# GHE plugin settings (user-local)" >> .gitignore
  echo ".claude/*.local.md" >> .gitignore
fi
```

## Step 8: Confirm to User

Tell the user:

1. Settings file created at `.claude/ghe.local.md`
2. All required GitHub labels created (type:, status, gate:, violation:, etc.)
3. Summary of configured settings
4. Reminder that changes require Claude Code restart
5. How to re-run setup: `/ghe:setup`
6. Settings are gitignored (personal to this machine)

## Implementation Notes

- Always create `.claude/` directory if it doesn't exist
- Validate GitHub usernames with `gh api users/<username>` before saving
- If user cancels mid-setup, don't create partial settings file
- If file exists, load current values as defaults for questions
