# Claude GitHub Action Integration with GHE Plugin

This document explains how the GitHub Elements (GHE) plugin integrates with [Claude GitHub Action](https://github.com/anthropics/claude-code-action) - Anthropic's official action for AI-assisted development.

## Overview

When Claude GitHub Action runs with the GHE plugin installed, it gains access to:

1. **All GHE Agents** - The complete pantheon of specialized agents
2. **GitHub Elements Skill** - Phase tracking, checkpoints, memory synchronization
3. **Hooks** - Avatar banners, auto-transcription, safeguards
4. **Commands** - Setup and maintenance slash commands

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     GitHub Repository                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Issue/PR Comment: "@claude help me..."                         │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │           .github/workflows/claude.yml                   │   │
│  │                                                          │   │
│  │  triggers: issue_comment, pull_request_review_comment,  │   │
│  │            pull_request_review, issues, pull_request    │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │        anthropics/claude-code-action@v1                  │   │
│  │                                                          │   │
│  │  plugins: ./plugins/ghe  ◄── Loads GHE plugin           │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   GHE Plugin                             │   │
│  │                                                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │   │
│  │  │   Agents    │  │   Skills    │  │   Hooks     │     │   │
│  │  │             │  │             │  │             │     │   │
│  │  │ - Athena    │  │ github-     │  │ - Avatar    │     │   │
│  │  │ - Hephaestus│  │   elements- │  │   banners   │     │   │
│  │  │ - Artemis   │  │   tracking  │  │ - Trans-    │     │   │
│  │  │ - Hera      │  │             │  │   cription  │     │   │
│  │  │ - etc.      │  │             │  │ - Safety    │     │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘     │   │
│  └─────────────────────────────────────────────────────────┘   │
│           │                                                      │
│           ▼                                                      │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              GitHub Issue/PR Response                    │   │
│  │                                                          │   │
│  │  <avatar banner>                                         │   │
│  │  Response from Claude with GHE context                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Agent Availability

When Claude GitHub Action runs with the GHE plugin, these agents can be invoked:

| Agent | Identity | Purpose |
|-------|----------|---------|
| github-elements-orchestrator | Athena | Central workflow coordinator |
| dev-thread-manager | Hephaestus | DEV phase management |
| test-thread-manager | Artemis | TEST phase execution |
| review-thread-manager | Hera | REVIEW evaluation |
| phase-gate | Themis | Transition validation |
| enforcement | Nemesis | Violation detection |
| reporter | Hermes | Status reports |
| memory-sync | Mnemosyne | SERENA synchronization |
| pr-checker | Cerberus | PR validation |
| ci-issue-opener | Chronos | CI failure reporting |

### Example Invocations

```markdown
@claude use the reporter agent to give me a status report

@claude analyze this PR with pr-checker

@claude create a DEV thread for this feature using dev-thread-manager

@claude what phase is epic:auth-system in? use github-elements-orchestrator
```

## Interactive vs Automation Mode

### Interactive Mode (Default)

Claude responds to @claude mentions in:
- Issue comments
- PR comments
- PR reviews

```yaml
# Triggered automatically when @claude is mentioned
if: contains(github.event.comment.body, '@claude')
```

### Automation Mode

Add a `prompt` input for automated workflows:

```yaml
- uses: anthropics/claude-code-action@v1
  with:
    anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
    plugins: ./plugins/ghe
    prompt: |
      You are assisting with GitHub Elements workflow.
      Analyze this issue and determine:
      1. Which epic it belongs to
      2. What phase it should start in
      3. Which agent should handle it
```

## Workflow Triggers

The standard GHE workflow triggers on:

| Event | Type | Purpose |
|-------|------|---------|
| `issue_comment` | created | Respond to @claude in issues |
| `pull_request_review_comment` | created | Respond to @claude in PR comments |
| `pull_request_review` | submitted | Respond to @claude in reviews |
| `issues` | opened, edited | Auto-triage new issues |
| `pull_request` | opened, synchronize | Auto-review PRs |

## Permissions

Required permissions for full GHE functionality:

```yaml
permissions:
  contents: write       # Create branches, commit changes
  pull-requests: write  # Create PRs, post comments
  issues: write         # Create issues, post comments
  actions: read         # Read CI status for context
```

## Hooks Integration

GHE hooks are active when Claude GitHub Action runs:

### Avatar Banners
All responses include the appropriate agent avatar banner.

### Transcription
User interactions are logged to the active issue thread.

### Safeguards
Phase transition rules and one-thread-at-a-time enforcement remain active.

## Setup Requirements

### 1. Repository Secret

Add to **Settings → Secrets and variables → Actions**:

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Your API key (sk-ant-...) |

### 2. Workflow File

Create `.github/workflows/claude.yml`:

```yaml
name: Claude Code

on:
  issue_comment:
    types: [created]
  issues:
    types: [opened, edited]
  pull_request_review_comment:
    types: [created]
  pull_request_review:
    types: [submitted]
  pull_request:
    types: [opened, synchronize]

jobs:
  claude:
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review' && contains(github.event.review.body, '@claude')) ||
      (github.event_name == 'issues' && github.event.action == 'opened') ||
      (github.event_name == 'pull_request' && github.event.action == 'opened')

    runs-on: ubuntu-latest

    permissions:
      contents: write
      pull-requests: write
      issues: write
      actions: read

    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - uses: anthropics/claude-code-action@v1
        with:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          plugins: ./plugins/ghe
          timeout_minutes: 30
```

### 3. Plugin Location

The GHE plugin must be at `./plugins/ghe` relative to repository root.

## Capabilities and Limitations

### What Claude Can Do (with GHE)
- Create/modify issues using GHE workflow
- Create branches and commits
- Open pull requests
- Post comments with avatar banners
- Manage phase transitions
- Run GHE agents
- Access repository context

### What Claude Cannot Do
- Bypass branch protection rules
- Approve PRs without required reviewers
- Access secrets directly (only via approved MCP tools)
- Push to protected branches without passing checks

## Security Considerations

1. **Audit Trail**: All Claude actions create commits with clear authorship
2. **Branch Protection**: Claude respects required reviews and status checks
3. **Secret Isolation**: API key is only used for Claude auth, not exposed to code
4. **Prompt Injection**: Claude GitHub Action has built-in protections against malicious prompts

## Troubleshooting

### Claude Not Responding

1. Check workflow is triggered (Actions tab)
2. Verify `ANTHROPIC_API_KEY` secret is set
3. Confirm @claude mention is in the comment
4. Check for workflow errors in run logs

### Plugin Not Loading

1. Verify plugin path: `plugins: ./plugins/ghe`
2. Check plugin structure has `.claude-plugin/plugin.json`
3. Review workflow logs for plugin load errors

### Agents Not Available

1. Confirm agents are in `plugins/ghe/agents/`
2. Check agent frontmatter is valid YAML
3. Verify plugin.json includes agents directory

## References

- [Claude GitHub Action](https://github.com/anthropics/claude-code-action)
- [Anthropic Docs](https://docs.anthropic.com/claude-code/github-actions)
- [GHE Plugin Documentation](../README.md)
