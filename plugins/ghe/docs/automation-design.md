# GHE Automation System Design

## Overview

This document outlines the automated workflow system for GHE plugin repositories.
The system handles 7 event types, routing them to the appropriate GHE agents for processing.

## Design Principles

1. **Conservative by Default**: When in doubt, create an URGENT issue and wait for human intervention
2. **No False Positives**: Especially for SPAM/moderation - better to miss spam than block legitimate users
3. **Respect User Autonomy**: Only the repo owner makes final decisions
4. **Prevent Infinite Loops**: Bot actions must not trigger other bot actions
5. **Idempotent Operations**: Same event should not create duplicate issues
6. **Graceful Degradation**: Failures should be logged, not cause cascading errors

## Event Types and Agent Routing

| Event | Trigger | Tag(s) | Agent | Priority |
|-------|---------|--------|-------|----------|
| A: PR Opened | `pull_request: opened` | `phase:review` | Hera | Normal |
| B: Bug Report | `issues: opened` + bug template | `phase:review` | Hera | Normal |
| C: Feature Request | `issues: opened` + feature template | `phase:dev` | Hephaestus | Normal |
| D: Policy Violation | `issue_comment: created` | `needs-moderation` | Ares | Normal |
| E: SPAM Detected | `issues/comments` | (close/delete) | (auto) | Low |
| F: Security Alert | `dependabot/code_scanning` | `phase:dev`, `urgent` | Hephaestus | URGENT |
| G: CI/CD Failure | `workflow_run: completed` (failure) | `phase:review`, `ci-failure` | Chronos | High |

## Critical Edge Cases

### Loop Prevention

**Problem**: Bot creates issue → triggers issue workflow → creates another issue...

**Solution**:
```yaml
# Every workflow MUST have this check
if: |
  github.actor != 'github-actions[bot]' &&
  github.actor != 'dependabot[bot]' &&
  !contains(github.event.*.user.login, '[bot]')
```

### Duplicate Prevention

**Problem**: Same PR/alert creates multiple review issues

**Solution**:
```bash
# Check for existing linked issue before creating
existing=$(gh issue list --label "pr:$PR_NUMBER" --json number --jq '.[0].number')
if [ -n "$existing" ]; then
  echo "Issue #$existing already exists for PR #$PR_NUMBER"
  exit 0
fi
```

### Rate Limiting

**Problem**: Burst of events exhausts API quota

**Solution**:
- Use `concurrency` groups to limit parallel runs
- Add delays between API calls
- Batch operations where possible

```yaml
concurrency:
  group: ghe-automation-${{ github.event.issue.number || github.event.pull_request.number }}
  cancel-in-progress: false
```

### Permission Boundaries

**Problem**: Claude action has write access but should respect repo rules

**Solution**:
- Use minimal permissions per workflow
- Never force-push or bypass branch protection
- Never delete issues (only close)
- Always comment, never edit user content

## Detailed Event Specifications

### Event A: PR Opened → REVIEW Issue

**Trigger Conditions**:
- `pull_request: [opened]`
- NOT from bot
- NOT a draft PR (wait until ready)

**Actions**:
1. Check if review issue already exists for this PR
2. If exists, skip
3. Create issue with:
   - Title: `[REVIEW] PR #X: <PR title>`
   - Label: `phase:review`, `source:pr`
   - Body: Link to PR, summary of changes, file list
4. Comment on PR linking to review issue

**Edge Cases**:
- Draft PR → Skip, will trigger when marked ready
- Bot PR (Dependabot) → Still create review issue but add `bot-pr` label
- PR from owner → Still create review issue (for Hera to process)
- PR with linked issue → Add cross-reference, don't duplicate

---

### Event B: Bug Report → Validate + REVIEW

**Trigger Conditions**:
- `issues: [opened]`
- Has `bug` label OR matches bug template

**Template Validation**:
Required fields:
- [ ] Description of the bug
- [ ] Steps to reproduce
- [ ] Expected behavior
- [ ] Actual behavior
- [ ] Version/environment

**Actions**:
1. Check if template is properly filled
2. If incomplete:
   - Comment explaining what's missing
   - Add `needs-info` label
   - Do NOT add `phase:review` yet
3. If complete:
   - Add `phase:review` label
   - Add `ready` label
   - Comment confirming issue is queued for Hera

**Edge Cases**:
- User edits issue to complete template → Should trigger revalidation (separate workflow)
- Issue has both bug and feature labels → Treat as bug (more urgent)
- Issue from owner → Same treatment (consistency)

---

### Event C: Feature Request → Validate + DEV

**Trigger Conditions**:
- `issues: [opened]`
- Has `enhancement` label OR matches feature template

**Template Validation**:
Required fields:
- [ ] Feature description
- [ ] Use case / problem solved
- [ ] Proposed solution (optional but encouraged)

**Actions**:
1. Check if template is properly filled
2. If incomplete:
   - Comment explaining what's missing
   - Add `needs-info` label
   - Do NOT add `phase:dev` yet
3. If complete:
   - Add `phase:dev` label
   - Add `ready` label
   - Comment confirming issue is queued for Hephaestus

**Edge Cases**:
- Duplicate feature request → Comment linking to existing, add `duplicate` label
- Very vague request → Ask for clarification, add `needs-info`
- Feature that's already implemented → Comment, close with `wontfix`

---

### Event D: Comment Policy Violation

**Trigger Conditions**:
- `issue_comment: [created]`
- NOT from owner
- NOT from bot

**Policy Violations** (checked in order):
1. **Harassment/Abuse**: Personal attacks, threats, discriminatory language
2. **Spam Links**: Multiple promotional links, crypto/gambling
3. **Off-Topic Derailing**: Completely unrelated to issue topic
4. **Excessive Self-Promotion**: Pushing own products repeatedly

**NOT Violations**:
- Mentioning other tools/projects positively
- Disagreeing with decisions (respectfully)
- Asking questions (even if repeated)
- Suggesting alternatives

**Actions**:
1. Analyze comment content
2. If clear violation:
   - Reply with warning (max 3 per user per issue)
   - If 3rd warning: add `needs-moderation` label
3. If borderline:
   - Do nothing, let human review
4. Track warnings in issue comments (not external)

**Edge Cases**:
- Non-English comments → Be conservative, don't flag
- Sarcasm/humor → Be conservative, don't flag
- Technical disagreements → Never flag, this is healthy
- User responding to warning → Don't count as another violation

---

### Event E: SPAM Detection

**Trigger Conditions**:
- `issues: [opened]`
- `issue_comment: [created]`
- NOT from repo collaborators

**SPAM Indicators** (need multiple to confirm):
- [ ] Account created very recently (< 7 days)
- [ ] No other GitHub activity
- [ ] Multiple external links in first post
- [ ] Generic greeting + promotion pattern
- [ ] Known spam domains
- [ ] Cryptocurrency/gambling/adult content

**NOT SPAM**:
- Links to documentation
- Links to related projects
- Links to bug reproductions
- New users with legitimate questions
- Mentions of competitor tools

**Actions**:
1. Calculate spam score (need 3+ indicators)
2. If HIGH confidence spam (5+ indicators):
   - Close issue with "spam" label
   - Do NOT delete (preserve audit trail)
   - Log to workflow summary
3. If MEDIUM confidence (3-4 indicators):
   - Add `possible-spam` label
   - Comment asking user to verify they're human
   - Wait for human review
4. If LOW confidence:
   - Do nothing

**Edge Cases**:
- False positive → User can reopen issue, remove label
- Sophisticated spam → Will slip through, human catches later
- Spam in comments → Only add label, never delete

---

### Event F: Security Alert → URGENT DEV

**Trigger Conditions**:
- `dependabot_alert: [created]`
- `code_scanning_alert: [created, reopened]`
- `secret_scanning_alert: [created]`

**Actions**:
1. Check if issue already exists for this alert
2. If exists, update existing issue
3. If new:
   - Create issue with:
     - Title: `[SECURITY] <alert title>`
     - Labels: `phase:dev`, `urgent`, `security`
     - Body: Full alert details, severity, remediation steps
4. If CRITICAL severity:
   - Also add `blocked` label (nothing else should proceed)

**Edge Cases**:
- Low severity alert → Still create issue, just not marked `urgent`
- Alert for dev dependency → Create issue, add `dev-dependency` label
- Duplicate alert → Update existing issue, don't create new
- Alert dismissed as false positive → Close corresponding issue

---

### Event G: CI/CD Failure → REVIEW + CI/CD

**Trigger Conditions**:
- `workflow_run: [completed]`
- conclusion: failure

**Actions**:
1. Check if this is a known flaky test (from issue labels)
2. Check if issue already exists for this workflow failure
3. If exists and same error:
   - Add comment with new failure details
   - Increment failure count
4. If new failure:
   - Create issue with:
     - Title: `[CI] <workflow name> failed`
     - Labels: `phase:review`, `ci-failure`, `source:ci`
     - Body: Workflow link, error summary, affected files
5. If same workflow fails 3+ times:
   - Add `urgent` label

**Edge Cases**:
- Failure due to GitHub outage → Check status.github.com, don't create issue
- Failure in PR (not main) → Create issue but link to PR
- Cancelled workflow → Ignore (not a failure)
- Timed out → Create issue with `timeout` label

## Concurrency and Ordering

All workflows use concurrency groups to prevent race conditions:

```yaml
concurrency:
  group: ghe-${{ github.event_name }}-${{ github.event.*.number || github.run_id }}
  cancel-in-progress: false  # Complete current, queue next
```

## Required Labels

These labels must exist in the repository (created by /ghe:setup):

| Label | Color | Description |
|-------|-------|-------------|
| `phase:dev` | #0E8A16 | DEV phase |
| `phase:review` | #1D76DB | REVIEW phase |
| `urgent` | #B60205 | Needs immediate attention |
| `needs-info` | #D4C5F9 | Waiting for more information |
| `needs-moderation` | #D93F0B | Needs human moderation review |
| `ci-failure` | #D93F0B | CI/CD failure |
| `security` | #B60205 | Security issue |
| `source:pr` | #C5DEF5 | Auto-created from PR |
| `source:ci` | #C5DEF5 | Auto-created from CI |
| `possible-spam` | #FBCA04 | Potential spam, needs review |
| `bot-pr` | #BFD4F2 | PR from bot (Dependabot, etc.) |

## Permissions Matrix

| Workflow | contents | issues | pull-requests | security-events |
|----------|----------|--------|---------------|-----------------|
| A: PR Review | read | write | read | - |
| B: Bug Report | read | write | - | - |
| C: Feature Request | read | write | - | - |
| D: Moderation | read | write | - | - |
| E: SPAM | read | write | - | - |
| F: Security | read | write | - | read |
| G: CI/CD | read | write | read | - |

## Failure Handling

All workflows should:
1. Use `continue-on-error: false` for critical steps
2. Log failures to workflow summary
3. On unhandled error: Create URGENT issue for human review

```yaml
- name: Handle unexpected error
  if: failure()
  run: |
    gh issue create \
      --title "[URGENT] Automation failure in ${{ github.workflow }}" \
      --label "urgent,needs-moderation" \
      --body "Workflow ${{ github.workflow }} failed unexpectedly.

      Run: ${{ github.server_url }}/${{ github.repository }}/actions/runs/${{ github.run_id }}

      Please investigate."
```
