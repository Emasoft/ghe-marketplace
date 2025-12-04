# GitHub Elements - GitHub Actions Integration

These GitHub Actions workflows provide **24/7 automated maintenance** for the GitHub Elements workflow tracking system. They complement the local Claude Code plugin by running monitoring and validation tasks continuously on GitHub.

## Overview

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ghe-stale-monitor.yml` | Scheduled (daily) | Detect threads with no activity >24h |
| `ghe-label-validator.yml` | Label changes | Validate GHE label combinations |
| `ghe-pr-checker.yml` | PR events | Verify PRs link to valid GHE threads |
| `ghe-ci-opener.yml` | CI failures | Auto-open issues on workflow failures |
| `ghe-assistant.yml` | @claude mentions | Interactive GHE queries in comments |

## Prerequisites

1. **Authentication**: Install the Claude GitHub App (recommended) OR use an API key
2. **Repository Permissions**: Enable GitHub Actions with write access to issues and PRs

## Installation

### Step 1: Authenticate Claude

**Option A: Install Claude GitHub App (Recommended)**

In Claude Code, run:
```
/install-github-app
```

This installs the official Claude GitHub App and stores the OAuth token as `CLAUDE_CODE_OAUTH_TOKEN` in your repository secrets automatically.

**Option B: Use API Key (Alternative)**

If you prefer using an API key directly:
1. Go to **Settings > Secrets and variables > Actions**
2. Add secret: `ANTHROPIC_API_KEY` with your Anthropic API key

### Step 2: Copy Workflow Files

```bash
# Copy all GHE workflows to your repository
mkdir -p .github/workflows
cp ghe-*.yml .github/workflows/
```

Or download via GitHub CLI:
```bash
curl -o .github/workflows/ghe-stale-monitor.yml \
  https://raw.githubusercontent.com/Emasoft/claude-code-plugins/main/github-elements-plugin/examples/github-actions/ghe-stale-monitor.yml
```

### Step 3: Update Authentication in Workflows

The workflows default to using OAuth token. If using API key instead, edit each workflow:

```yaml
# For GitHub App (default - recommended):
claude_code_oauth_token: ${{ secrets.CLAUDE_CODE_OAUTH_TOKEN }}

# For API key (alternative):
# anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
```

## Configuration

### Authentication Options

| Method | Secret Name | How to Set Up |
|--------|-------------|---------------|
| **GitHub App** (recommended) | `CLAUDE_CODE_OAUTH_TOKEN` | Run `/install-github-app` in Claude Code |
| API Key | `ANTHROPIC_API_KEY` | Add manually in repository secrets |

### Customization

Each workflow has configurable parameters in the `env` section:

```yaml
env:
  STALE_HOURS: 24        # Hours before thread is considered stale
  EPIC_LABEL: "epic:"    # Prefix for epic labels
  PHASE_LABELS: "dev,test,review"
```

## Workflow Details

### 1. Stale Thread Monitor (`ghe-stale-monitor.yml`)

**Runs**: Daily at 9 AM UTC (configurable)

**What it does**:
- Scans all issues with `in-progress` label
- Checks if last activity was more than 24 hours ago
- Posts warning comment on stale threads
- Creates summary issue if multiple stale threads found

**Prompt logic**:
```
Find all open issues with "in-progress" label.
For each, check if last comment/event was >24h ago.
Post warning on stale threads.
```

### 2. Label Validator (`ghe-label-validator.yml`)

**Runs**: On any label change to issues

**What it does**:
- Validates GHE label combinations are valid
- Checks only one phase label exists (dev/test/review)
- Verifies status labels are consistent
- Posts corrective comment if invalid combination detected

**Valid combinations**:
- `dev` + `dev` + `in-progress`
- `test` + `test` + `ready`
- etc.

**Invalid combinations** (will warn):
- `dev` + `test` (multiple phases)
- `in-progress` without assignee
- `review` without linked PR

### 3. PR Thread Checker (`ghe-pr-checker.yml`)

**Runs**: On PR opened, synchronized, or edited

**What it does**:
- Checks PR description for GHE issue link (`Closes #N`, `Fixes #N`)
- Validates linked issue has correct GHE labels
- Checks branch naming convention (`feature/epic-name-*`)
- Posts warning if PR is not properly linked

### 4. CI Failure Issue Opener (`ghe-ci-opener.yml`)

**Runs**: When any workflow completes with failure

**What it does**:
- Detects workflow failures
- Extracts failure details from logs (if `actions: read` enabled)
- Opens issue with failure summary
- Links to failed workflow run
- Tags relevant epic if identifiable from branch name

### 5. GHE Assistant (`ghe-assistant.yml`)

**Runs**: When @claude is mentioned in issue/PR comments

**What it does**:
- Responds to GHE-related questions
- Provides current thread status
- Explains workflow phases
- Lists available work
- **Does NOT perform actions** (claim, checkpoint, transition)

**Example queries**:
- "@claude what's the status of this thread?"
- "@claude explain the GHE workflow"
- "@claude what work is available?"

## Integration with Local Plugin

These GitHub Actions **complement** the local Claude Code plugin:

| Responsibility | GitHub Actions | Local Plugin |
|----------------|----------------|--------------|
| 24/7 Monitoring | Yes | No |
| Stale detection | Yes | No |
| Label validation | Yes | No |
| Claim issues | No | Yes (ghe-claim) |
| Post checkpoints | No | Yes (ghe-checkpoint) |
| Transition phases | No | Yes (ghe-transition) |
| SERENA memory sync | No | Yes (memory-sync agent) |
| Complex code changes | No | Yes (thread managers) |

The GitHub Actions handle **passive monitoring**, while the local plugin handles **active operations**.

## Cost Considerations

GitHub Claude Actions use your Anthropic API key. To control costs:

1. **Limit turns**: Each workflow uses `--max-turns` to cap API calls
2. **Use smaller models**: Workflows default to `claude-sonnet` (cheaper)
3. **Reduce frequency**: Adjust cron schedules as needed
4. **Scope carefully**: Use path filters to limit triggers

Example cost control:
```yaml
claude_args: |
  --max-turns 5
  --model claude-sonnet-4-20250514
```

## Troubleshooting

### Workflow not triggering
- Check workflow is in `.github/workflows/`
- Verify workflow is enabled in Actions tab
- Check trigger conditions match your events

### Authentication errors
- If using GitHub App: Verify `CLAUDE_CODE_OAUTH_TOKEN` secret exists (run `/install-github-app` in Claude Code)
- If using API key: Verify `ANTHROPIC_API_KEY` secret is set
- Check credentials are not expired
- Ensure sufficient API quota

### Claude not responding
- Check workflow logs in Actions tab
- Verify permissions are correctly set
- Check `max-turns` is not too restrictive

## Security Notes

1. **API Key**: Store only in GitHub Secrets, never in workflow files
2. **Permissions**: Workflows request minimal permissions needed
3. **Branch protection**: Consider protecting main branch from direct Claude commits
4. **Review before merge**: Always review Claude's PRs before merging

## Further Reading

- [GitHub Claude Action Documentation](https://github.com/anthropics/claude-code-action)
- [GitHub Elements Plugin Documentation](../README.md)
- [Claude Code Plugin Development](https://docs.anthropic.com/en/docs/claude-code/plugins)
