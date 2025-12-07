# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**GHE (GitHub-Elements)** is a Claude Code plugin marketplace that transforms GitHub Issues into a persistent memory system for AI-assisted development. It provides:
- Multi-session continuity through GitHub Issue threads
- Automated workflow management (DEV → TEST → REVIEW phases)
- 10 specialized agents themed after Greek mythology
- SERENA memory bank integration

**Current Versions:**
- GHE Plugin: v0.6.34
- Marketplace Utils: v1.1.6

## Common Commands

### Validation

```bash
# Full plugin validation
python3 validation_scripts/plugin-validator.py

# Validate specific plugin
python3 validation_scripts/validate_plugin.py ghe
python3 validation_scripts/validate_plugin.py marketplace-utils
python3 validation_scripts/validate_plugin.py --all

# Component validation
bash validation_scripts/validate-agent.sh <agent-file>
python3 validation_scripts/validate-skill.py <skill-file>
bash validation_scripts/hook-linter.sh
bash validation_scripts/validate-settings.sh
```

### Release

```bash
# Release with version bump (patch/minor/major)
python scripts/release.py patch ghe "Fix description"
python scripts/release.py minor marketplace-utils "New feature"
python scripts/release.py major ghe "Breaking change"

# List all plugin versions
python scripts/release.py --list

# Generate/update TOC
python scripts/generate_toc.py README.md
python scripts/generate_toc.py --dry-run README.md
python scripts/generate_toc.py --recursive docs/
```

### Setup

```bash
# Add marketplace and install plugins
/plugin marketplace add Emasoft/ghe-marketplace
/plugin install ghe@ghe-marketplace
/plugin install marketplace-utils@ghe-marketplace

# Configure for a project
/ghe:setup
```

## Architecture

### Directory Structure

```
ghe-marketplace/
├── .claude-plugin/marketplace.json    # Marketplace registry for both plugins
├── .github/workflows/                 # Argos Panoptes (7 GitHub Actions workflows)
├── plugins/
│   ├── ghe/                           # Main plugin (v0.6.34)
│   │   ├── agents/                    # 10 specialized agents + references/
│   │   ├── commands/                  # User commands (/ghe:setup, /ghe:spawn-agent)
│   │   ├── skills/                    # 10 skills (ghe-status, ghe-claim, etc.)
│   │   ├── hooks/hooks.json           # 5 lifecycle hooks
│   │   ├── scripts/                   # 28 Python scripts (~9100 LOC)
│   │   ├── assets/avatars/            # 10 agent avatar images
│   │   └── templates/                 # Markdown templates
│   └── marketplace-utils/             # Utility plugin (v1.1.6)
│       ├── skills/                    # marketplace-release, markdown-toc
│       └── scripts/                   # release.py, generate_toc.py
├── validation_scripts/                # Plugin validators and linters
├── scripts/                           # Marketplace-level scripts
└── GHE_REPORTS/                       # Agent-generated reports
```

### The Element System

Everything in GHE is an **Element** - a single message/reply to a GitHub Issue:
- **Element of Knowledge**: Plans, specifications, architecture decisions
- **Element of Action**: Code, assets, configuration (tangible artifacts)
- **Element of Judgement**: Bug reports, code reviews, test results

### Phase-Gated Workflow

```
DEV (Hephaestus) ──► TEST (Artemis) ──► REVIEW (Hera)
                                            │
                                            └──► Themis (Phase Gate)
                                                    │
                                                    ├─► PASS → merge to main
                                                    └─► FAIL → back to DEV
```

Phase transitions require the `pending-promotion` label. Themis validates and promotes or rejects.

### Agent Roster

| Agent | ID | Role | Model |
|-------|-----|------|-------|
| Athena | `ghe:github-elements-orchestrator` | Central coordinator | Opus 4.5 |
| Hephaestus | `ghe:dev-thread-manager` | DEV phase | Opus 4.5 |
| Artemis | `ghe:test-thread-manager` | TEST phase | Sonnet 4 |
| Hera | `ghe:review-thread-manager` | REVIEW phase | Sonnet 4 |
| Themis | `ghe:phase-gate` | Phase transitions | Sonnet 4 |
| Mnemosyne | `ghe:memory-sync` | SERENA memory sync | Haiku 4 |
| Ares | `ghe:enforcement` | Rule enforcement | Haiku 4 |
| Hermes | `ghe:reporter` | Status reports | Haiku 4 |
| Chronos | `ghe:ci-issue-opener` | CI failure detection | Haiku 4 |
| Cerberus | `ghe:pr-checker` | PR validation | Haiku 4 |

### Hook System

5 lifecycle hooks in `plugins/ghe/hooks/hooks.json`:
1. **SessionStart**: Initialize session, auto-transcribe check, resume last active issue
2. **UserPromptSubmit**: Store prompt for transcription, check issue context
3. **Stop**: Store response for transcription, verify completion
4. **PreToolUse** (Bash): Transcribe reminder
5. **PostToolUse** (Bash): Detect issue changes

### Argos Panoptes (24/7 Guardian)

Separate from local agents - runs as GitHub Actions powered by Claude GitHub App:
- 7 workflows: PR review, bug triage, feature triage, moderation, spam detection, security alerts, CI failures
- Always identifies as "Argos Panoptes (The All-Seeing)"
- Conservative by default: creates URGENT issues vs. false positives

## Key Technical Decisions

1. **GitHub Issues as Database**: All memory stored in threads, survives context exhaustion
2. **Independent Versioning**: Each plugin versioned separately with its own git tag
3. **No External Dependencies**: Python scripts use only standard library
4. **Fail-Fast Approach**: No error handling/fallbacks, failures propagate for visibility
5. **No Backward Compatibility**: Single version of code only

## Plugin Manifest Locations

- Marketplace: `.claude-plugin/marketplace.json`
- GHE: `plugins/ghe/.claude-plugin/plugin.json`
- Marketplace Utils: `plugins/marketplace-utils/.claude-plugin/plugin.json`

## Working with Agents

Agent files are in `plugins/ghe/agents/`. Each agent has:
- YAML frontmatter with name, description, model, tools
- Markdown body with system prompt and instructions
- References in `agents/references/` for shared documentation

The largest agent is `review-thread-manager.md` (Hera) at ~65KB.

## Working with Skills

Skills are in `plugins/ghe/skills/` and `plugins/marketplace-utils/skills/`. Each skill:
- Has its own directory with `skill.md`
- Uses YAML frontmatter for metadata
- Provides triggers and usage instructions

## Working with Hooks

Hook scripts are in `plugins/ghe/scripts/`. Key scripts:
- `ghe_init.py`: Session initialization
- `auto_transcribe.py`: Auto-save work to issues
- `session_recover.py`: Resume last active issue
- `transcription_enforcer.py`: Store/verify transcription state
- `transcription_notify.py`: Notify user of memory bank status
- `check_issue_set.py`: Verify current issue context
- `transcribe_reminder.py`: Reminder before bash commands
- `detect_issue_changes.py`: Monitor issue updates after bash
- `safeguards.py`: Safety checks before operations
- `thread_manager.py`: GitHub thread operations
- `phase_transition.py`: Phase promotion logic

## Per-Project Configuration

Project settings stored in `.claude/ghe.local.md` (gitignored). Created by `/ghe:setup` command. Contains:
- Repository info (owner/repo)
- Enforcement level
- SERENA integration settings
- Auto worktree creation
- Notification preferences
