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

### Recommended: Use `/install-github-app` Command

The easiest and most reliable way to set up Claude GitHub Action:

```
/install-github-app https://github.com/<owner>/<repo>
```

This command (run by the user in Claude Code chat):
1. Guides through GitHub App authentication
2. Creates optimized workflow files automatically
3. Configures secrets based on your Claude subscription
4. Creates a PR for you to review and merge

**Benefits over manual setup:**

| Feature | Manual | `/install-github-app` |
|---------|--------|----------------------|
| Secret handling | Manual `ANTHROPIC_API_KEY` | Auto `CLAUDE_CODE_OAUTH_TOKEN` |
| Permissions | Broad write access | Minimal read-only (more secure) |
| PR reviews | Not included | Auto review workflow included |
| Subscription | Manual configuration | Auto-detected from your plan |

### What the Command Creates

**1. `.github/workflows/claude.yml`** - Interactive mode (responds to @claude)

```yaml
name: Claude Code

on:
  issue_comment:
    types: [created]
  pull_request_review_comment:
    types: [created]
  issues:
    types: [opened, assigned]
  pull_request_review:
    types: [submitted]

jobs:
  claude:
    if: |
      (github.event_name == 'issue_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review_comment' && contains(github.event.comment.body, '@claude')) ||
      (github.event_name == 'pull_request_review' && contains(github.event.review.body, '@claude')) ||
      (github.event_name == 'issues' && (contains(github.event.issue.body, '@claude') || contains(github.event.issue.title, '@claude')))
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
      issues: read
      id-token: write
      actions: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 1

      - uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          additional_permissions: |
            actions: read
```

**2. `.github/workflows/claude-code-review.yml`** - Auto PR reviews

```yaml
name: Claude Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  claude-review:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: read
      issues: read
      id-token: write

    steps:
      - uses: actions/checkout@v4
      - uses: anthropics/claude-code-action@v1
        with:
          claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}
          prompt: |
            Please review this pull request and provide feedback on:
            - Code quality and best practices
            - Potential bugs or issues
            - Performance considerations
            - Security concerns
            - Test coverage
```

### Alternative: Manual Setup

If you prefer manual configuration, add to **Settings → Secrets → Actions**:

| Secret | Description |
|--------|-------------|
| `ANTHROPIC_API_KEY` | Your API key (sk-ant-...) |

Then create workflow files manually (see above examples, but use `anthropic_api_key` instead of `claude_code_oauth_token`).

### Plugin Location

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
2. Verify secret is set:
   - `CLAUDE_CODE_OAUTH_TOKEN` (if used `/install-github-app`)
   - `ANTHROPIC_API_KEY` (if manual setup)
3. Confirm @claude mention is in the comment
4. Check for workflow errors in run logs

### OIDC Token Error

If you see "Could not fetch an OIDC token" error:
- Ensure `id-token: write` permission is in workflow
- Verify the PR from `/install-github-app` was merged

### Plugin Not Loading

1. Verify plugin path: `plugins: ./plugins/ghe`
2. Check plugin structure has `.claude-plugin/plugin.json`
3. Review workflow logs for plugin load errors

### Agents Not Available

1. Confirm agents are in `plugins/ghe/agents/`
2. Check agent frontmatter is valid YAML
3. Verify plugin.json includes agents directory

### Re-running Setup

If you need to reconfigure Claude GitHub Action:

```
/install-github-app https://github.com/<owner>/<repo>
```

This creates a new PR that updates existing workflow files.

## References

- [Claude GitHub Action](https://github.com/anthropics/claude-code-action)
- [Anthropic Docs](https://docs.anthropic.com/claude-code/github-actions)
- [GHE Plugin Documentation](../README.md)
