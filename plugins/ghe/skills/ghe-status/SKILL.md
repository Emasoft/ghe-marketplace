---
name: ghe-status
description: |
  READ-ONLY quick overview of GitHub Elements workflow state. Shows active threads, phase distribution, and workflow health at a glance.

  USE THIS SKILL WHEN:
  - User asks "what's the status" or "show me the status"
  - User asks "what threads are active" or "what am I working on"
  - User asks "show me the workflow state" or "what's happening"
  - User wants a quick overview before starting work
  - Starting a session and need context

  DO NOT USE THIS SKILL WHEN:
  - User wants to CLAIM an issue (use ghe-claim)
  - User wants to POST a checkpoint (use ghe-checkpoint)
  - User wants to TRANSITION phases (use ghe-transition)
  - User wants DETAILED metrics/health reports (use ghe-report)

  EXAMPLES:
  <example>
  Context: User starting a session wants to see current state
  user: "What's the github elements status?"
  assistant: "I'll use ghe-status to show you the current workflow state"
  </example>
  <example>
  Context: User wants to know what work is available
  user: "Show me what threads are active"
  assistant: "I'll use ghe-status to display active and available threads"
  </example>
  <example>
  Context: Quick check before doing work
  user: "What am I currently working on?"
  assistant: "I'll use ghe-status to find your in-progress threads"
  </example>
---

## Settings Awareness

Respects `.claude/ghe.local.md`:
- `enabled`: If false, return minimal status
- `notification_level`: Affects output verbosity

---

# GitHub Elements Status (Quick Overview)

**Purpose**: Read-only quick overview of workflow state. Does NOT modify anything.

## When to Use

- Quick status check
- See active threads
- Check what's available
- Session start context

## How to Execute

Spawn the **reporter** agent with report type "status".

The reporter will:
1. Query all threads with GitHub Elements labels
2. Show active threads (DEV, TEST, REVIEW)
3. Display phase distribution
4. List recent completions
5. Show workflow health indicators
6. Flag any violations or warnings

## Output Format

```markdown
## GitHub Elements Status Report

### Active Threads
| Issue | Type | Phase | Epic | Assignee | Last Activity |
|-------|------|-------|------|----------|---------------|

### Phase Distribution
DEV: N active | TEST: N active | REVIEW: N active

### Available Work
[Ready issues not yet claimed]

### Workflow Health
- Violations: N
- Checkpoint frequency: N%
```

## Key Differentiator

This is a **READ-ONLY** quick overview. For detailed metrics, health checks, or epic-specific reports, use `ghe-report` instead.
