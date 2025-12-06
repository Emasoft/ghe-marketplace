# Epic Management Reference

This reference covers epic phases, branch management, and epic lifecycle.

## Epic vs Regular Threads

**CRITICAL**: Understand the distinction between epic threads and regular threads.

### Two Levels of Work

| Level | Thread Labels | Scope | Managed By |
|-------|---------------|-------|------------|
| **Regular** | `phase:dev`, `phase:test`, `phase:review` | Single issue | Hephaestus, Artemis, Hera |
| **Epic** | `epic` + `dev`, `epic` + `test`, `epic` + `review` | Group of issues | **ATHENA ONLY** |

### CRITICAL: Athena Owns ALL Epic Phases

**Epic threads are ONLY managed by Athena**, regardless of phase:

| Phase | Regular Thread | Epic Thread |
|-------|---------------|-------------|
| DEV | Hephaestus (actual coding) | **Athena** (planning what to code) |
| TEST | Artemis (actual testing) | **Athena** (planning what to test) |
| REVIEW | Hera (actual reviewing) | **Athena** (setting review standards) |

**WHY?** Epic threads are about **PLANNING**, not **EXECUTION**:
- `epic` + `dev`: Planning WHAT features to develop, breaking into issues, organizing into WAVES
- `epic` + `test`: Planning WHAT tests to create/execute, test coverage strategy
- `epic` + `review`: Setting review expectations, quality standards, acceptance criteria

### When to Use Epics (Meta-Level)

Epics are **META threads** that plan and coordinate **groups of issues**:

| Epic Type | Example | Child Issues |
|-----------|---------|--------------|
| `epic-feature` | User authentication system | Login, logout, password reset, 2FA, session management |
| `epic-refactoring` | Migrate to async/await | 15 files need refactoring |
| `epic-migration` | Database schema v2 | Schema changes, data migration, rollback plan |
| `epic-addons` | Plugin system | Plugin loader, API, sandbox, registry |
| `epic-webserver` | REST API overhaul | Endpoints, auth middleware, rate limiting |

### Epic Phase Flow (META-LEVEL)

Epic phases are **fundamentally different** from regular thread phases. They are META-level operations:

```
epic+dev ─────────────► epic+test ───────────────► epic+review ──► epic+complete
     │                       │                          │
     │                       │                          │
     ▼                       ▼                          ▼
 Athena creates          BETA RELEASE              RC RELEASE
 waves + requirements    Public testing            External reviews
     │                       │                          │
     │                       │                          │
     ▼                       ▼                          ▼
 All waves complete      All beta bugs fixed      User approves
 (normal flow)           (normal bug flow)        (external verdicts)

ONLY ONE EPIC CAN BE IN epic+test OR epic+review AT A TIME!
```

### Epic Labels - META Meanings

| Phase Label | What It Means | What Happens |
|-------------|---------------|--------------|
| `epic` + `dev` | Planning: create waves, write requirements | Athena creates issues, waves execute via normal flow |
| `epic` + `test` | **BETA RELEASE**: Public testing phase | Beta version released, users test, bugs routed to epic |
| `epic` + `review` | **RC RELEASE**: External review phase | Release Candidate released, external reviews collected |

---

## Epic DEV Phase: Wave Planning (Normal Flow)

When an epic has `epic` + `dev` labels:
1. Athena writes requirements for each wave
2. Athena starts waves (creates issues with `dev` label)
3. Issues go through normal DEV → TEST → REVIEW flow
4. Themis notifies Athena when each wave completes
5. When ALL waves are complete, Athena requests transition to `epic` + `test`

---

## Epic TEST Phase: Beta Release (META Testing)

**CRITICAL**: `epic` + `test` does NOT mean Athena is testing. It means the epic feature is ready for PUBLIC BETA TESTING.

### What Happens When Epic Enters TEST Phase

```
1. Orchestrator informs user: "Epic feature ready for beta testing"
     │
     ▼
2. BETA RELEASE created on GitHub (from beta branch)
     │
     ▼
3. Users download and test the beta
     │
     ▼
4. Bug reports from users are posted to GitHub Issues
     │
     ▼
5. Hermes routes bug reports to the epic thread
   (tagged with parent-epic:NNN for traceability)
     │
     ▼
6. Bugs are triaged and fixed via NORMAL bug flow
   (code is from beta branch of this epic)
     │
     ▼
7. User decides to close beta testing
     │
     ▼
8. Themis posts to epic thread: "Beta phase complete, all bugs fixed"
     │
     ▼
9. Athena requests Themis to promote to `epic` + `review`
```

### Beta Testing Rules

| Rule | Description |
|------|-------------|
| **One at a time** | Only ONE epic can have `epic` + `test` labels at any time |
| **Bug routing** | Hermes routes all beta bug reports to the epic thread |
| **Normal flow** | Bugs are fixed via normal DEV → TEST → REVIEW cycle |
| **Beta branch** | All bug fixes are on the beta branch for this epic |
| **User control** | User decides when to close beta testing |

### Epic TEST Phase Demotion Protocol (Rare)

In rare cases, critical issues during beta testing may require demoting the entire epic back to DEV phase:

**When to Demote TEST → DEV Phase**:
- Fundamental architectural flaw discovered
- Security vulnerability requiring redesign
- Core requirements changed mid-beta
- Beta testing reveals missing essential functionality

**Demotion Process**:

```bash
EPIC_ISSUE=<epic issue number>

# Source avatar helper
source "${CLAUDE_PLUGIN_ROOT}/scripts/post-with-avatar.sh"

# Step 1: Request demotion (Athena to Themis)
HEADER=$(avatar_header "Athena")
gh issue comment $EPIC_ISSUE --body "${HEADER}
## Requesting Epic Demotion: TEST → DEV Phase

### Critical Issues Found
[Describe the fundamental issues discovered during beta testing]

### Why Demotion is Necessary
- [ ] Cannot be fixed with normal bug fix cycle
- [ ] Requires structural changes to the epic design
- [ ] User has approved demotion

### Affected Areas
- [List components/features that need rework]

### Proposed New Wave
Will create a new wave to address these issues after demotion."

# Step 2: Spawn Themis to validate and execute (epic phase labels are Themis-only)
# DO NOT manipulate epic/dev/test/review labels directly - only Themis can do this
echo "SPAWN phase-gate: Validate and execute epic demotion TEST → DEV phase for epic #${EPIC_ISSUE}"

# Themis will:
# 1. Validate demotion criteria
# 2. Remove test label, add dev label (epic label stays)
# 3. Update epic title
# 4. Post demotion notification

### Next Steps (after Themis completes)
1. Athena will create new wave with requirements for the rework
2. Normal DEV → TEST → REVIEW cycle for new issues
3. When all new wave issues complete, Athena may request TEST phase again"
```

**What Happens After Demotion**:
1. Beta release is suspended (users notified)
2. Beta branch is preserved (not deleted)
3. Athena creates new wave to address issues
4. Existing unfixed beta bugs remain tracked
5. When new wave completes, epic can re-enter TEST phase

---

### Hermes: Bug Report Router

**Hermes** (the messenger) routes bug reports from beta testers to the correct epic thread:

```bash
# When a new bug report is filed during beta testing:
ACTIVE_BETA_EPIC=$(gh issue list --label "epic" --label "phase:test" --state open --json number --jq '.[0].number')

if [ -n "$ACTIVE_BETA_EPIC" ]; then
  # Route to the active beta epic
  gh issue edit $BUG_ISSUE --add-label "parent-epic:${ACTIVE_BETA_EPIC}"
  gh issue edit $BUG_ISSUE --add-label "beta-bug"

  # Post notification to epic thread
  HEADER=$(avatar_header "Hermes")
  gh issue comment $ACTIVE_BETA_EPIC --body "${HEADER}
## Beta Bug Report Received

A new bug report has been filed during beta testing.

### Bug Issue
#${BUG_ISSUE}

### Status
Routing to normal bug triage flow (DEV → TEST → REVIEW)."
fi
```

---

## Epic REVIEW Phase: Release Candidate (META Review)

**CRITICAL**: `epic` + `review` does NOT mean Athena is reviewing. It means the epic feature is ready for EXTERNAL REVIEW as a Release Candidate.

### What Happens When Epic Enters REVIEW Phase

```
1. Orchestrator informs user: "Epic feature ready for RC release"
     │
     ▼
2. RELEASE CANDIDATE (RC) created on GitHub (from review branch)
     │
     ▼
3. User asks external reviewers to test and evaluate
     │
     ▼
4. External reviews posted to GitHub Issues
   (tagged with: external-review)
     │
     ▼
5. Athena collects external feedback (does NOT respond to issues)
     │
     ▼
6. User reviews external feedback and makes decision
     │
     ▼
7. User approves → Themis adds complete label + merge to main
   User rejects → Themis removes review, adds dev label with feedback
```

### RC Review Rules

| Rule | Description |
|------|-------------|
| **One at a time** | Only ONE epic can have `epic` + `review` labels at any time |
| **External label** | External reviews tagged `external-review` |
| **User decision** | User (not Athena) decides PASS/FAIL |
| **Review branch** | RC is built from review branch |
| **No mixing** | External reviews distinct from normal review phases |

### External Review Label

```bash
# External reviewers' issues are marked distinctly
gh issue edit $EXTERNAL_REVIEW_ISSUE --add-label "external-review"
gh issue edit $EXTERNAL_REVIEW_ISSUE --add-label "parent-epic:${EPIC_ISSUE}"
```

---

## Epic Phase Summary

| Phase | Athena's Role | Release Type | Who Acts |
|-------|---------------|--------------|----------|
| `epic` + `dev` | **ACTIVE**: Creates requirements, starts waves | None | Normal agents for issues |
| `epic` + `test` | **PASSIVE**: Waits for beta bugs to be fixed | BETA | Users test, Hermes routes bugs |
| `epic` + `review` | **PASSIVE**: Collects external feedback | RC | External reviewers, User decides |
| `epic` + `complete` | Done | PRODUCTION | Merge to main |

### Epic Naming Convention

```
Epic thread title format:
[EPIC] [DEV] <epic-type>: <description>
[EPIC] [TEST] <epic-type>: <description>
[EPIC] [REVIEW] <epic-type>: <description>

Examples:
[EPIC] [DEV] epic-feature: User Authentication System
[EPIC] [TEST] epic-migration: Database Schema v2
[EPIC] [REVIEW] epic-refactoring: Async/Await Migration
```

---

## Branch Management Strategy

### Branch Types

| Branch Type | Pattern | Purpose | Lifespan |
|-------------|---------|---------|----------|
| **Main** | `main` | Production-ready code | Permanent |
| **Issue branches** | `issue-<N>` | Individual issue work | Until merged |
| **Epic beta** | `epic-<N>-beta` | Beta release during epic TEST phase | Until RC |
| **Epic RC** | `epic-<N>-rc` | Release Candidate during epic REVIEW phase | Until main merge |

### Branch Flow During Epic Lifecycle

```
main ◄─────────────────────────────────────────────────┐
  │                                                    │
  ├── issue-101 (wave 1 issue) ──► merged to epic-N-beta
  │                                    │
  ├── issue-102 (wave 1 issue) ──► merged to epic-N-beta
  │                                    │
  ├── issue-103 (wave 2 issue) ──► merged to epic-N-beta
  │                                    │
  │                               epic-N-beta (epic TEST phase)
  │                                    │
  │                               Beta bugs fixed on issue branches
  │                               then merged to epic-N-beta
  │                                    │
  │                               epic-N-rc (epic REVIEW phase)
  │                                    │
  │                               RC issues fixed on issue branches
  │                               then merged to epic-N-rc
  │                                    │
  └───────────────────────────────────┘ (epic+complete → merge to main)
```

### Phase-Specific Branch Rules

#### Epic DEV Phase

```bash
# Each issue gets its own worktree and branch
git worktree add ../ghe-worktrees/issue-${ISSUE_NUM} -b issue-${ISSUE_NUM} main

# Work happens in issue branch
# When DEV → TEST → REVIEW passes, issue merges to beta branch
git checkout epic-${EPIC_NUM}-beta
git merge issue-${ISSUE_NUM}
```

#### Epic TEST Phase (Beta)

```bash
EPIC_NUM=<epic issue number>

# Create beta branch from main (once, when entering TEST phase)
git checkout main
git checkout -b epic-${EPIC_NUM}-beta

# Beta bugs get NEW issue branches
git worktree add ../ghe-worktrees/issue-${BUG_ISSUE} -b issue-${BUG_ISSUE} epic-${EPIC_NUM}-beta

# After bug DEV → TEST → REVIEW passes, merge to beta branch
git checkout epic-${EPIC_NUM}-beta
git merge issue-${BUG_ISSUE}
```

#### Epic REVIEW Phase (RC)

```bash
EPIC_NUM=<epic issue number>

# Create RC branch from beta (once, when entering REVIEW phase)
git checkout epic-${EPIC_NUM}-beta
git checkout -b epic-${EPIC_NUM}-rc

# Critical fixes get NEW issue branches (should be rare)
git worktree add ../ghe-worktrees/issue-${FIX_ISSUE} -b issue-${FIX_ISSUE} epic-${EPIC_NUM}-rc

# After fix DEV → TEST → REVIEW passes, merge to rc branch
git checkout epic-${EPIC_NUM}-rc
git merge issue-${FIX_ISSUE}
```

#### Epic Complete Phase (Merge to Main)

```bash
EPIC_NUM=<epic issue number>

# User has approved the RC
# Merge rc branch to main
git checkout main
git merge epic-${EPIC_NUM}-rc

# Tag the release
git tag -a "v1.0.0-epic-${EPIC_NUM}" -m "Epic ${EPIC_NUM} release"

# Clean up epic branches
git branch -d epic-${EPIC_NUM}-beta
git branch -d epic-${EPIC_NUM}-rc
```

### Key Rules

| Rule | Description |
|------|-------------|
| **Never work on main** | All work happens on issue branches |
| **One issue = One branch** | Even beta bugs get their own branches |
| **Merge target varies** | Issue branches merge to beta/rc during epic, to main otherwise |
| **Beta is cumulative** | Beta branch accumulates all wave merges + bug fixes |
| **RC is frozen** | Only critical fixes should touch RC branch |
| **Clean up after epic** | Delete beta and rc branches after merge to main |
