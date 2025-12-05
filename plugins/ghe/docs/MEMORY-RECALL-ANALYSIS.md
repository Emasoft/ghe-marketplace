# GHE Memory Recall: Complete Flow Analysis

**Date**: 2025-12-04
**Version**: 0.2.1
**Purpose**: Deep analysis of the memory recall mechanism for recovering forgotten information from the GitHub Elements persistent memory system.

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [The Core Problem](#the-core-problem)
3. [Memory Recall Flow - Complete Sequence](#memory-recall-flow---complete-sequence)
4. [Component Analysis](#component-analysis)
5. [Critical Gaps and Issues](#critical-gaps-and-issues)
6. [Edge Cases](#edge-cases)
7. [Recommendations](#recommendations)

---

## Executive Summary

The GHE plugin provides persistent memory through GitHub Issues, surviving Claude's context exhaustion (compaction). The memory recall system has **significant architectural gaps** that could lead to data loss or incomplete recovery.

### Key Findings

| Category | Status | Severity |
|----------|--------|----------|
| SessionStart hook | Partial | HIGH |
| Auto-transcription | Gate-based | MEDIUM |
| Recovery protocol | Manual | HIGH |
| SERENA integration | Optional | MEDIUM |
| User avatar fetching | Working | LOW |

### Critical Issues Identified

1. **No automatic recovery on SessionStart** - New session doesn't auto-fetch last state
2. **Manual recovery burden** - User must know to run recovery commands
3. **SERENA sync is optional** - Memory bank may be out of sync
4. **No checkpoint validation** - Corrupted checkpoints aren't detected
5. **Race conditions** - Multiple sessions could corrupt state

---

## The Core Problem

When Claude's context is exhausted (compaction), a new session starts with **zero memory** of previous work. The GHE plugin solves this by:

1. **WRITING** - Recording all work to GitHub Issues during sessions
2. **RECALLING** - Reading that work back when a new session starts

**The recall is the critical path.** If recall fails or is incomplete, work is lost.

---

## Memory Recall Flow - Complete Sequence

### Scenario: User asks "What were we working on?"

This is the primary recall use case. Here's the complete sequence:

```
USER MESSAGE: "What were we working on?" or "continue where we left off"
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 1: SESSION INITIALIZATION (hooks/hooks.json)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ SessionStart Hook (if enabled)                                          │
│     │                                                                   │
│     ├── check-issue-set.sh executes                                     │
│     │        │                                                          │
│     │        ├── Reads .claude/ghe.local.md                             │
│     │        │        │                                                 │
│     │        │        └── Extracts current_issue value                  │
│     │        │                                                          │
│     │        ├── IF current_issue IS SET:                               │
│     │        │        └── Output: "TRANSCRIPTION ACTIVE: Issue #N"      │
│     │        │                                                          │
│     │        └── IF current_issue IS NULL:                              │
│     │                 └── Output: "TRANSCRIPTION INACTIVE"              │
│     │                                                                   │
│     └── PROBLEM: Hook does NOT fetch issue content!                     │
│         It only tells you IF an issue is set, not WHAT's in it.         │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 2: SKILL ACTIVATION (if user mentions keywords)                   │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ github-elements-tracking skill triggers on:                             │
│   - "track work across sessions"                                        │
│   - "recover from compaction"                                           │
│   - "coordinate multiple agents"                                        │
│   - GitHub Issues as persistent memory                                  │
│                                                                         │
│ BUT: Skill provides INSTRUCTIONS, not AUTOMATION                        │
│      Claude must manually execute recovery commands                     │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 3: MANUAL RECOVERY (per P4-compaction-recovery-walkthrough.md)    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ Step 1: Find Assigned Work                                              │
│         gh issue list --assignee @me --label "in-progress"              │
│              │                                                          │
│              └── Returns list of assigned, in-progress issues           │
│                                                                         │
│ Step 2: Identify Thread Type                                            │
│         Check label: phase:dev, phase:test, or phase:review               │
│              │                                                          │
│              └── CRITICAL: Different thread types have different scope  │
│                                                                         │
│ Step 3: Read Issue Thread                                               │
│         gh issue view $ISSUE --comments                                 │
│              │                                                          │
│              ├── Find LAST "### State Snapshot" section                 │
│              │                                                          │
│              └── Extract:                                               │
│                   - Completed tasks                                     │
│                   - In-progress tasks                                   │
│                   - Pending tasks                                       │
│                   - Files changed                                       │
│                   - Commits made                                        │
│                   - Branch name                                         │
│                   - Next action                                         │
│                                                                         │
│ Step 4: Verify Local State                                              │
│         git checkout <branch>                                           │
│         git log --oneline (verify commits)                              │
│         ls <files from snapshot>                                        │
│              │                                                          │
│              └── CRITICAL: Local state may not match GitHub!            │
│                   - Push may have failed                                │
│                   - Different machine                                   │
│                   - Branch name wrong                                   │
│                                                                         │
│ Step 5: Build TodoWrite                                                 │
│         Create todos from State Snapshot                                │
│              │                                                          │
│              └── Mark completed/in_progress/pending appropriately       │
│                                                                         │
│ Step 6: Post Recovery Comment                                           │
│         Document state inherited and recovery actions                   │
│              │                                                          │
│              └── Creates audit trail in issue thread                    │
│                                                                         │
│ Step 7: Continue Work                                                   │
│         Resume from Next Action in checkpoint                           │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
     │
     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│ PHASE 4: SERENA MEMORY SYNC (optional, if enabled)                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│ IF serena_sync: true in .claude/ghe.local.md:                           │
│     │                                                                   │
│     ├── memory-sync agent (Mnemosyne) is spawned                        │
│     │                                                                   │
│     ├── Reads from .serena/memories/:                                   │
│     │        ├── activeContext.md    (current session focus)            │
│     │        ├── progress.md         (completed work)                   │
│     │        ├── techContext.md      (technical decisions)              │
│     │        ├── dataflow.md         (system interfaces)                │
│     │        └── test_results/       (test execution records)           │
│     │                                                                   │
│     └── PROBLEM: SERENA memory may be STALE if:                         │
│              - Last session didn't sync properly                        │
│              - Memory files weren't committed                           │
│              - Different branch has different memory state              │
│                                                                         │
│ IF serena_sync: false:                                                  │
│     └── SERENA is skipped - GitHub-only mode                            │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Component Analysis

### 1. Hooks (hooks/hooks.json)

**Current State**: The hooks file defines SessionStart behavior.

| Hook Event | Script | What It Does | Gap |
|------------|--------|--------------|-----|
| SessionStart | check-issue-set.sh | Checks if issue is set | Does NOT fetch/display issue content |
| (missing) | - | Auto-fetch last checkpoint | **CRITICAL GAP** |
| (missing) | - | Validate local git state | **CRITICAL GAP** |

**check-issue-set.sh Analysis**:
```bash
# Lines 7-16 - What it does:
if [[ -f "$CONFIG_FILE" ]]; then
    ISSUE=$(grep -E "^current_issue:" "$CONFIG_FILE" ...)
    if [[ -n "$ISSUE" && "$ISSUE" != "null" ]]; then
        echo "TRANSCRIPTION ACTIVE: Issue #$ISSUE"  # <-- Just outputs text
        exit 0
    fi
fi
echo "TRANSCRIPTION INACTIVE: No issue set"
exit 0  # <-- Always exits 0, never blocks
```

**Problem**: This hook only **informs** - it doesn't **act**. The new session doesn't automatically:
- Fetch the issue content
- Display the last checkpoint
- Verify local state matches GitHub

### 2. Scripts (scripts/)

| Script | Purpose | Called By | Issues |
|--------|---------|-----------|--------|
| auto-transcribe.sh | Post messages to GitHub | Hooks (if enabled) | Gate-based, not automatic |
| post-with-avatar.sh | Format comments with avatars | Agents, scripts | Working correctly |
| check-issue-set.sh | Check if issue is set | SessionStart hook | Output only, no action |
| safeguards.sh | Safety checks, recovery | Manual invocation | **Never auto-invoked** |
| parse-settings.sh | Parse .local.md settings | Scripts | Working correctly |

**auto-transcribe.sh Critical Paths**:

```bash
# Line 372-388 - post_user_message():
# Only posts if:
#   1. GitHub repo exists
#   2. enabled == true
#   3. auto_transcribe == true
#   4. current_issue is set
# All 4 conditions must be true!

# Line 237-312 - find_or_create_issue():
# Searches for explicit issue patterns:
#   [Currently discussing issue n.123]
#   [issue #123]
#   working on issue #123
# Falls back to creating new session issue if none found
```

**safeguards.sh Critical Functions**:
```bash
reconcile_ghe_state()     # Fixes state desync - NEVER AUTO-CALLED
pre_flight_check()        # Validates before work - NEVER AUTO-CALLED
recover_from_merge_crash() # Crash recovery - NEVER AUTO-CALLED
```

### 3. Agents

| Agent | Role in Recall | When Invoked |
|-------|----------------|--------------|
| github-elements-orchestrator (Athena) | Coordinates recovery | Manual request |
| memory-sync (Mnemosyne) | Syncs SERENA | After checkpoints, transitions |
| reporter (Hermes) | Status reports | Manual request |

**None are auto-invoked on SessionStart for recovery.**

### 4. Skills

**github-elements-tracking/SKILL.md** provides:
- Instructions for manual recovery
- Playbook references (P1-P10)
- Protocol documentation

**But**: Skills provide knowledge, not automation. Claude must:
1. Recognize recovery is needed
2. Know to invoke the skill
3. Execute commands manually

---

## Critical Gaps and Issues

### GAP 1: No Automatic Recovery on SessionStart (SEVERITY: HIGH)

**Problem**: When a new session starts after compaction, there is no automatic mechanism to:
- Detect that recovery is needed
- Fetch the last checkpoint from GitHub
- Display previous session state

**Current Behavior**:
```
New Session Starts
     │
     ▼
check-issue-set.sh runs (if hook enabled)
     │
     ▼
Outputs "TRANSCRIPTION ACTIVE: Issue #N" (text only)
     │
     ▼
Claude has NO context of what #N contains
     │
     ▼
User must explicitly ask "what were we working on?"
     │
     ▼
Claude must manually run gh issue view #N --comments
```

**Expected Behavior**:
```
New Session Starts
     │
     ▼
SessionStart hook:
  1. Checks if issue is set
  2. IF SET: Auto-fetches last checkpoint
  3. Displays: "Recovering from Issue #N..."
  4. Shows last State Snapshot
  5. Verifies local git state
     │
     ▼
Claude has FULL context immediately
```

### GAP 2: SERENA Sync is Optional and May Be Stale (SEVERITY: MEDIUM)

**Problem**: SERENA memory bank integration is:
- Optional (serena_sync: true/false)
- Only synced on explicit triggers (checkpoint, transition)
- May be out of sync with GitHub state

**Scenario**:
1. Session 1: Works on issue #201, posts checkpoint to GitHub
2. Session 1: Context exhausts BEFORE memory-sync agent runs
3. Session 2: SERENA memory is stale (missing latest checkpoint)
4. Session 2: Reads activeContext.md - shows OLD state
5. Session 2: GitHub has correct state, but SERENA doesn't

### GAP 3: No Checkpoint Validation (SEVERITY: HIGH)

**Problem**: There's no validation that checkpoints are:
- Complete (all required fields present)
- Valid (parseable, not corrupted)
- Consistent (matches local state)

**Scenario**:
1. Agent posts checkpoint but network fails mid-post
2. GitHub has partial/corrupted checkpoint
3. New session reads corrupted checkpoint
4. Recovery fails with unclear error

### GAP 4: Manual Recovery Burden (SEVERITY: HIGH)

**Problem**: The entire recovery protocol (P4-compaction-recovery-walkthrough.md) requires:
- User to know recovery is needed
- Claude to recognize recovery patterns
- Manual execution of 7+ steps
- Technical knowledge of gh CLI

**For non-technical users**: Recovery may be impossible without help.

### GAP 5: Race Conditions with Multiple Sessions (SEVERITY: MEDIUM)

**Problem**: If user opens multiple Claude sessions:
- Both may try to claim same issue
- Both may post conflicting checkpoints
- merge:active lock only protects merges, not claims

**safeguards.sh has protections**, but they're never auto-invoked.

### GAP 6: No CLAUDE.md Auto-Injection on SessionStart (SEVERITY: MEDIUM)

**Problem**: The `inject_claude_md_reminder()` function in auto-transcribe.sh adds:
```markdown
## GHE Active Transcription
**CRITICAL**: All conversation is being transcribed to GitHub.
Currently discussing issue n.${issue_num}
```

But this only runs when `set-issue` is called, NOT on SessionStart.

**Scenario**:
1. Session 1: set-issue 201 called, CLAUDE.md updated
2. Session 1: Context exhausts
3. Session 2: SessionStart hook runs
4. Session 2: CLAUDE.md still has reminder from Session 1
5. BUT: Claude doesn't READ CLAUDE.md automatically on start

The reminder exists but may not be seen.

---

## Edge Cases

### Edge Case 1: Issue Closed Between Sessions

**Scenario**:
1. Session 1: Working on issue #201
2. Session 1: Context exhausts
3. Someone closes issue #201 manually
4. Session 2: Starts, tries to recover from #201
5. #201 is CLOSED - what happens?

**Current Behavior**:
- check-issue-set.sh still shows "Issue #201" (doesn't verify state)
- Recovery may fail with confusing error
- safeguards.sh has `reconcile_ghe_state()` but it's never called

### Edge Case 2: Branch Deleted or Moved

**Scenario**:
1. Session 1: Working on branch `feature/201-jwt-auth`
2. Session 1: Context exhausts
3. Another agent merges and deletes the branch
4. Session 2: Tries to checkout the branch
5. Branch doesn't exist!

**Current Behavior**:
- Recovery protocol says "verify commits exist"
- But there's no automatic detection
- Manual git checkout will fail

### Edge Case 3: Conflicting State in SERENA vs GitHub

**Scenario**:
1. Session 1: Posts checkpoint to GitHub
2. Session 1: Syncs to SERENA
3. Session 1: Posts ANOTHER checkpoint to GitHub
4. Session 1: Context exhausts BEFORE second sync
5. GitHub: Has checkpoint 2
6. SERENA: Has checkpoint 1

**Which source of truth wins?**
- Currently undefined
- No conflict resolution mechanism

### Edge Case 4: Network Failure During Recovery

**Scenario**:
1. Session starts, runs check-issue-set.sh
2. User asks "what were we working on?"
3. Claude runs `gh issue view 201 --comments`
4. Network fails mid-fetch
5. Partial data returned

**Current Behavior**:
- No retry mechanism
- Partial/garbled output possible
- User may think that's all the data

### Edge Case 5: Very Long Issue Thread

**Scenario**:
1. Issue #201 has 500+ comments (months of work)
2. `gh issue view 201 --comments` returns ALL comments
3. Response is too large for Claude's context
4. Claude can't process the full thread

**Current Behavior**:
- No pagination
- No "get only last checkpoint" mechanism
- Must scan entire thread to find last State Snapshot

### Edge Case 6: Checkpoint Without State Snapshot

**Scenario**:
1. Session 1: Posts informal update (not full checkpoint)
2. Session 1: Context exhausts
3. Session 2: Looks for "### State Snapshot"
4. No State Snapshot in last comment

**Current Behavior**:
- Recovery protocol assumes State Snapshot exists
- No fallback for missing structured data
- May need to scan backwards through comments

### Edge Case 7: Different User Context

**Scenario**:
1. User A starts Session 1 on machine A
2. Session 1: Works on issue, context exhausts
3. User B starts Session 2 on machine B
4. Session 2 has different git state (no local commits)

**Current Behavior**:
- Recovery protocol says "verify local state"
- But commits may not be pushed
- User B has no access to User A's local commits

---

## Recommendations

### Recommendation 1: Auto-Recovery SessionStart Hook (HIGH PRIORITY)

Create a new hook script: `session-recovery.sh`

```bash
#!/bin/bash
# session-recovery.sh - Auto-recover on session start

CONFIG_FILE=".claude/ghe.local.md"
RECOVERY_OUTPUT=""

# Get current issue
ISSUE=$(grep -E "^current_issue:" "$CONFIG_FILE" 2>/dev/null | sed 's/^[^:]*: *//' | tr -d '"')

if [[ -n "$ISSUE" && "$ISSUE" != "null" ]]; then
    # Verify issue is still open
    STATE=$(gh issue view "$ISSUE" --json state --jq '.state' 2>/dev/null)

    if [[ "$STATE" != "OPEN" ]]; then
        echo "WARNING: Issue #$ISSUE is $STATE (not OPEN)"
        echo "Run: auto-transcribe.sh clear-issue to reset"
    else
        # Fetch last checkpoint
        echo "## GHE Session Recovery"
        echo ""
        echo "### Active Issue: #$ISSUE"
        echo ""

        # Get issue title
        TITLE=$(gh issue view "$ISSUE" --json title --jq '.title')
        echo "**Title**: $TITLE"
        echo ""

        # Get last comment with State Snapshot
        LAST_CHECKPOINT=$(gh issue view "$ISSUE" --comments --json comments --jq '
            .comments |
            map(select(.body | contains("### State Snapshot"))) |
            last |
            .body // "No checkpoint found"
        ')

        echo "### Last Checkpoint"
        echo "$LAST_CHECKPOINT"
        echo ""

        # Verify git state
        BRANCH=$(echo "$LAST_CHECKPOINT" | grep -A1 "#### Branch" | tail -1 | tr -d '`')
        if [[ -n "$BRANCH" ]]; then
            if git rev-parse --verify "$BRANCH" >/dev/null 2>&1; then
                echo "**Branch**: $BRANCH (verified)"
            else
                echo "**Branch**: $BRANCH (NOT FOUND LOCALLY)"
            fi
        fi
    fi
fi
```

Update hooks.json:
```json
{
  "SessionStart": [
    {
      "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/session-recovery.sh"
    }
  ]
}
```

### Recommendation 2: Checkpoint Validation Schema (HIGH PRIORITY)

Add validation script: `validate-checkpoint.sh`

Required fields:
- `#### Completed` - list of done items
- `#### In Progress` - current work
- `#### Pending` - remaining work
- `#### Branch` - git branch name
- `#### Commits` - commit hashes
- `#### Next Action` - what to do next

### Recommendation 3: Last-Checkpoint-Only Fetch (MEDIUM PRIORITY)

For long issue threads, add:
```bash
# Get only the last checkpoint, not full thread
gh issue view "$ISSUE" --comments --json comments --jq '
    .comments |
    map(select(.body | contains("### State Snapshot"))) |
    last
'
```

### Recommendation 4: Conflict Resolution Protocol (MEDIUM PRIORITY)

When SERENA and GitHub conflict:
1. GitHub is source of truth (persistent, versioned)
2. SERENA is synced FROM GitHub
3. Add `--force-sync-from-github` option to memory-sync agent

### Recommendation 5: Automated Pre-Flight Checks (MEDIUM PRIORITY)

Before any agent claims a thread:
```bash
# Auto-run pre_flight_check()
source safeguards.sh
pre_flight_check $ISSUE_NUM || exit 1
```

### Recommendation 6: Graceful Degradation (LOW PRIORITY)

When recovery fails:
1. Show clear error message
2. Offer manual recovery options
3. Link to documentation
4. Suggest `/ghe:setup` to reconfigure

---

## Summary

The GHE plugin provides a solid foundation for persistent memory through GitHub Issues. However, the **recall mechanism has critical gaps** that put recovery at risk:

| Component | Reliability | Risk |
|-----------|-------------|------|
| Writing (transcription) | Good | Low |
| Storage (GitHub Issues) | Excellent | Very Low |
| **Recall (recovery)** | **Manual** | **HIGH** |
| SERENA sync | Optional | Medium |
| Validation | Missing | High |

**The most critical improvement needed**: Automatic recovery on SessionStart that fetches and displays the last checkpoint without user intervention.

---

*Report generated by Claude Code analysis*
*GHE Plugin v0.2.1*
