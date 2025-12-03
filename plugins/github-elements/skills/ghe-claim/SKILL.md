---
name: ghe-claim
description: |
  CLAIM a specific GitHub issue to START working on it. Requires an issue number. Performs validation, atomic claim, posts claim comment, and sets up worktree.

  USE THIS SKILL WHEN:
  - User says "claim issue #N" or "claim #N"
  - User says "start working on issue #N" or "take issue #N"
  - User says "I'll work on #N" or "pick up #N"
  - User wants to BEGIN work on a specific issue number
  - User selected an issue from available work and wants to claim it

  REQUIRED: An issue number must be specified or identifiable from context.

  DO NOT USE THIS SKILL WHEN:
  - User just wants to SEE status (use ghe-status)
  - User is ALREADY working and wants to post update (use ghe-checkpoint)
  - User wants to CHANGE phases (use ghe-transition)
  - User wants reports (use ghe-report)
  - No specific issue number is mentioned

  EXAMPLES:
  <example>
  Context: User wants to start work on a specific issue
  user: "Claim issue #201"
  assistant: "I'll use ghe-claim to claim issue #201 with the full protocol"
  </example>
  <example>
  Context: User picks from available work
  user: "I'll take issue #205"
  assistant: "I'll use ghe-claim to claim issue #205"
  </example>
  <example>
  Context: User wants to start on specific feature
  user: "Start working on #312"
  assistant: "I'll use ghe-claim to claim and set up issue #312"
  </example>
---

## Settings Awareness

Respects `.claude/github-elements.local.md`:
- `enabled`: If false, skip claim operation
- `enforcement_level`: Affects phase-gate strictness
- `auto_worktree`: If true, auto-create git worktree
- `serena_sync`: If false, skip SERENA memory bank update

---

# GitHub Elements Claim

**Purpose**: Claim a specific issue to START working on it. Modifies issue state.

## Required Input

- **Issue number**: Must be specified (e.g., #201, issue 201)

## When to Use

- Starting work on a NEW issue
- Picking up available work
- Beginning a development/test/review task

## How to Execute

### Step 1: Validate with phase-gate

Spawn **phase-gate** agent to check:
- Issue has "ready" label
- Issue is not already assigned
- Phase order is correct (DEV closed before TEST, etc.)
- No other threads open for same epic

### Step 2: Execute claim

Spawn appropriate thread manager based on issue labels:
- `type:dev` label → **dev-thread-manager**
- `type:test` label → **test-thread-manager**
- `type:review` label → **review-thread-manager**

The thread manager will:
1. Assign issue to @me (atomic claim)
2. Add "in-progress" label
3. Remove "ready" label
4. Post claim comment with session header
5. Create worktree (for DEV)

### Step 3: Sync memory

Spawn **memory-sync** agent to:
- Add to activeContext.md
- Record claim event

## Output

Confirmation including:
- Phase validation result
- Issue assigned and labeled
- Claim comment posted
- Worktree created (if DEV)
- Memory bank updated

## Key Differentiator

This skill STARTS new work. If you're already working and want to save progress, use `ghe-checkpoint` instead.
