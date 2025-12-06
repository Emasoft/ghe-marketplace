# GHE Orchestration Architecture

## Overview

GHE uses a **dual-thread architecture** with clear separation between the main conversation and background development work:

1. **Main Thread (FOREGROUND)**: User + Claude conversation, verbatim transcription to GitHub issue
2. **Feature/Bug Threads (BACKGROUND)**: Autonomous development with agents (Athena -> Hephaestus -> Artemis -> Hera)

This architecture ensures the user always has direct access to Claude while complex development tasks run autonomously in background Terminal windows.

## Thread Types

### Main Thread (FOREGROUND)

| Aspect | Description |
|--------|-------------|
| **Participants** | User + Claude ONLY |
| **Purpose** | Conversation, Q&A, coordination |
| **Transcription** | Every exchange posted VERBATIM to GitHub issue |
| **Agents** | **NONE** - no agents spawn here |
| **When active** | User says "work on issue #N" |

```
User: "Let's work on issue #42"
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│                   Main Thread Started                      │
│  - auto-transcribe.sh set-issue 42                        │
│  - current_phase = CONVERSATION                           │
│  - All exchanges posted to Issue #42                      │
│  - NO agents spawned                                      │
└───────────────────────────────────────────────────────────┘
```

### Feature/Bug Threads (BACKGROUND)

| Aspect | Description |
|--------|-------------|
| **Participants** | Agents ONLY (Athena, Hephaestus, Artemis, Hera) |
| **Purpose** | Development, testing, review |
| **First Message** | **REQUIREMENTS by Athena (MANDATORY)** |
| **Agents** | Full agent workflow |
| **When created** | User requests "implement X" or "fix bug Y" |

```
User: "Implement dark mode toggle"
        │
        ▼
┌───────────────────────────────────────────────────────────┐
│              Feature Thread Created                        │
│  - create-feature-thread.sh feature "Dark mode" "..."     │
│  - NEW GitHub issue created                               │
│  - Athena writes REQUIREMENTS (first message)             │
│  - Hephaestus spawned for DEV phase                       │
│  - Tracked in ghe-background-threads.json                 │
└───────────────────────────────────────────────────────────┘
```

## Workflow Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           USER + CLAUDE (Main Thread)                        │
│                                                                             │
│  User types: "Let's work on issue #42"                                      │
│  Claude: Sets current_issue=42, current_phase=CONVERSATION                  │
│  All exchanges are posted VERBATIM to Issue #42                             │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ User: "I need a dark mode toggle for the settings page"             │   │
│  │                          │                                           │   │
│  │                          ▼                                           │   │
│  │ Claude: "I'll create a background thread for that feature"          │   │
│  │                          │                                           │   │
│  │         ┌────────────────┴────────────────┐                         │   │
│  │         │  create-feature-thread.sh       │                         │   │
│  │         │  - Creates Issue #99            │                         │   │
│  │         │  - Links to parent #42          │                         │   │
│  │         └────────────────┬────────────────┘                         │   │
│  └──────────────────────────│──────────────────────────────────────────┘   │
└─────────────────────────────│──────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                     BACKGROUND THREAD (Issue #99)                            │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Phase 1: REQUIREMENTS (Athena)                                     │   │
│  │  - Athena posts requirements as FIRST comment                       │   │
│  │  - Defines acceptance criteria                                      │   │
│  │  - Spawns Hephaestus when done                                      │   │
│  └────────────────────────────│────────────────────────────────────────┘   │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Phase 2: DEV (Hephaestus)                                          │   │
│  │  - Implements the feature                                           │   │
│  │  - Posts progress to Issue #99                                      │   │
│  │  - Requests TEST transition when done                               │   │
│  └────────────────────────────│────────────────────────────────────────┘   │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Phase 3: TEST (Artemis)                                            │   │
│  │  - Runs tests                                                       │   │
│  │  - Fixes simple bugs (or demotes to DEV)                            │   │
│  │  - Requests REVIEW transition when tests pass                       │   │
│  └────────────────────────────│────────────────────────────────────────┘   │
│                               ▼                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  Phase 4: REVIEW (Hera)                                             │   │
│  │  - Conducts code review                                             │   │
│  │  - May request user participation                                   │   │
│  │  - Claude notifies user when ready                                  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Phase Transition Flow

```
┌─────────────┐                ┌─────────────┐                ┌─────────────┐
│ REQUIREMENTS│     AUTO       │     DEV     │     DEV->TEST  │    TEST     │
│   (Athena)  │ ─────────────▶ │ (Hephaestus)│ ─────────────▶ │  (Artemis)  │
└─────────────┘                └─────────────┘                └─────────────┘
                                      ▲                              │
                                      │                              │
                                      │         TEST->DEV            │
                                      │      (test failures)         │
                                      └──────────────────────────────┘
                                                                     │
                                                              TEST->REVIEW
                                                             (tests pass)
                                                                     │
                                                                     ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              ┌─────────────┐                                │
│                              │   REVIEW    │                                │
│                              │   (Hera)    │                                │
│                              └─────────────┘                                │
│                                     │                                       │
│              ┌──────────────────────┼──────────────────────┐               │
│              │                      │                      │                │
│              ▼                      ▼                      ▼                │
│       REVIEW->DEV            APPROVED                  CLOSED               │
│      (needs rework)      (creates PR)            (merged/done)              │
└─────────────────────────────────────────────────────────────────────────────┘
```

## User Notification Flow

When a feature thread reaches REVIEW phase, Claude notifies the user:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Claude (in Main Thread)                                   │
│                                                                             │
│  [Periodically runs: check-review-ready.sh --notify]                        │
│                                                                             │
│  "Feature #99 (Dark mode toggle) is ready for review!                       │
│                                                                             │
│   Hera is conducting the code review and may need your input.               │
│                                                                             │
│   Would you like to:                                                        │
│   1. Temporarily pause our conversation (#42)                               │
│   2. Join the feature thread to participate in the review                   │
│                                                                             │
│   To switch: 'join review for #99'"                                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Scripts

### Main Thread Operations

| Script | Purpose |
|--------|---------|
| `auto-transcribe.sh set-issue N` | Set current issue, enable transcription (NO agents) |
| `auto-transcribe.sh user "msg"` | Post user message to issue |
| `auto-transcribe.sh assistant "msg"` | Post Claude response to issue |
| `auto-transcribe.sh get-issue` | Get current issue number |

### Feature Thread Operations

| Script | Purpose |
|--------|---------|
| `create-feature-thread.sh` | Create new feature/bug thread with Athena requirements |
| `check-review-ready.sh` | Check for threads ready for user review |
| `spawn-agent.sh` | Spawn specific GHE agent with context |
| `agent-request-spawn.sh` | Inter-agent spawning (agent A -> agent B) |
| `phase-transition.sh` | Handle phase transitions (DEV->TEST->REVIEW) |

### Background Agent Support

| Script | Purpose |
|--------|---------|
| `spawn_background.sh` | Opens Terminal in background, starts Claude, pastes prompt |
| `auto_approve.sh` | PreToolUse hook for auto-approving safe operations |
| `post-with-avatar.sh` | Post comments with agent avatar headers |

## Agents (Greek Pantheon)

| Agent | Greek Name | Role | Thread Type |
|-------|------------|------|-------------|
| `github-elements-orchestrator` | Athena | Master orchestrator, writes requirements | Feature Thread |
| `dev-thread-manager` | Hephaestus | DEV phase (implementation) | Feature Thread |
| `test-thread-manager` | Artemis | TEST phase (testing) | Feature Thread |
| `review-thread-manager` | Hera | REVIEW phase (code review) | Feature Thread |
| `phase-gate` | Themis | Validates phase transitions | Both |
| `memory-sync` | Mnemosyne | SERENA memory sync | Both |
| `reporter` | Hermes | Status reports | Both |
| `enforcement` | Ares | Violation detection | Feature Thread |
| `ci-issue-opener` | Chronos | CI failure handling | Feature Thread |
| `pr-checker` | Cerberus | PR validation | Feature Thread |
| `hermes` | Hermes | Message routing | Both |

## User Triggers

### Main Thread Triggers

```
"work on #123"           → set_current_issue(123) → transcription only
"claim issue 45"         → set_current_issue(45)  → transcription only
"lets work on #99"       → set_current_issue(99)  → transcription only
```

### Feature Thread Triggers

```
"implement dark mode"    → create-feature-thread.sh feature "Dark mode" "..."
"add a login page"       → create-feature-thread.sh feature "Login page" "..."
"fix the crash on save"  → create-feature-thread.sh bug "Crash on save" "..."
"there's a bug in auth"  → create-feature-thread.sh bug "Auth bug" "..."
```

### Thread Switch Triggers

```
"join review for #99"    → Switch to feature thread #99
"switch to #123"         → Switch to thread #123
"pause this, join #99"   → Save main thread, switch to #99
"back to #42"            → Return to main thread #42
```

## File Locations

```
plugins/ghe/
├── scripts/
│   ├── auto-transcribe.sh       # Main thread transcription (NO agents)
│   ├── create-feature-thread.sh # Create background feature/bug threads
│   ├── check-review-ready.sh    # Check for review-ready threads
│   ├── spawn_background.sh      # Core: Open background Terminal
│   ├── spawn-agent.sh           # Spawn specific agents
│   ├── agent-request-spawn.sh   # Inter-agent spawning
│   ├── phase-transition.sh      # Phase transition orchestration
│   ├── auto_approve.sh          # PreToolUse auto-approval
│   └── post-with-avatar.sh      # Avatar comment posting
├── hooks/
│   └── hooks.json               # Hook definitions
├── agents/
│   ├── github-elements-orchestrator.md  # Athena
│   ├── dev-thread-manager.md            # Hephaestus
│   ├── test-thread-manager.md           # Artemis
│   ├── review-thread-manager.md         # Hera
│   ├── phase-gate.md                    # Themis
│   └── ...
└── ORCHESTRATION.md             # This file
```

## Configuration

Settings are stored in `.claude/ghe.local.md`:

```yaml
---
enabled: true
current_issue: 42
current_phase: CONVERSATION    # Main thread = CONVERSATION, not DEV/TEST/REVIEW
warnings_before_enforce: 3
violation_count: 0
repo_owner: "username"
serena_sync: true
auto_worktree: true
---
```

### Main Thread vs Feature Thread Phases

| Thread Type | Valid Phases |
|-------------|--------------|
| Main Thread | `CONVERSATION` only |
| Feature Thread | `REQUIREMENTS` -> `DEV` -> `TEST` -> `REVIEW` |

## Background Thread Tracking

Feature/bug threads are tracked in `.claude/ghe-background-threads.json`:

```json
{
  "threads": [
    {
      "issue": 99,
      "type": "feature",
      "title": "Dark mode toggle",
      "parent_issue": 42,
      "phase": "DEV",
      "status": "active",
      "created": "2024-12-05 10:00:00",
      "updated": "2024-12-05 10:30:00"
    }
  ],
  "last_updated": "2024-12-05 10:30:00"
}
```

## GHE_REPORTS (MANDATORY)

**ALL agent reports MUST be posted to BOTH locations:**
1. **GitHub Issue Thread** - Full report text (NOT just a link!)
2. **GHE_REPORTS/** - Same full report text (FLAT structure, no subfolders!)

**Report naming:** `<TIMESTAMP>_<title or description>_(<AGENT>).md`
**Timestamp format:** `YYYYMMDDHHMMSSTimezone`

**ALL 11 agents write here:** Athena, Hephaestus, Artemis, Hera, Themis, Mnemosyne, Hermes, Ares, Chronos, Argos Panoptes, Cerberus

```
GHE_REPORTS/                                              # FLAT structure - NO subfolders!
├── .spawn_log.txt                                        # Internal: spawn events (hidden)
├── .spawn_requests.log                                   # Internal: inter-agent requests (hidden)
├── .transitions.log                                      # Internal: phase transitions (hidden)
├── 20251205150000AEST_issue_99_requirements_(Athena).md  # Athena's requirements for #99
├── 20251205160000AEST_issue_99_dev_complete_(Hephaestus).md  # Hephaestus report for #99
├── 20251205170000AEST_issue_99_tests_complete_(Artemis).md   # Artemis report for #99
└── 20251205180000AEST_issue_99_review_complete_(Hera).md     # Hera report for #99
```

**REQUIREMENTS/** is SEPARATE - permanent design documents, never deleted.

**Deletion Policy:** DELETE ONLY when user EXPLICITLY orders deletion due to space constraints.

## Auto-Approval Security

The `auto_approve.sh` hook ensures background agents can work autonomously:

| Operation | Decision |
|-----------|----------|
| Read, Glob, Grep, LS | ALLOW |
| Write/Edit in project | ALLOW |
| Write/Edit outside project | DENY |
| Safe bash (git, npm, pytest) | ALLOW |
| Dangerous bash (sudo, rm -rf /) | DENY |
| Unknown tools | ASK |

## Troubleshooting

### Main Thread Not Transcribing
1. Check `current_issue` is set: `bash scripts/auto-transcribe.sh get-issue`
2. Verify issue exists: `gh issue view N`
3. Check hooks.json is loading properly

### Feature Thread Not Starting
1. Check user's message triggered the pattern
2. Verify `create-feature-thread.sh` can create issues: `gh issue create --help`
3. Check spawn_log.txt for errors

### Agent Not Spawning
1. Check Terminal.app permissions in System Preferences
2. Verify `claude` CLI is in PATH
3. Check spawn_log.txt for errors
4. Check auto_approve.sh hook log: `cat /tmp/background_agent_hook.log`

### Review Notification Not Appearing
1. Check `check-review-ready.sh` is finding threads
2. Verify threads have correct labels: `gh issue list --label "phase:review"`
3. Check ghe-background-threads.json exists and is valid

### Phase Transition Failing
1. Check transitions.log for validation failures
2. Verify issue has correct labels
3. Ensure phase-gate validates the transition

## Key Design Principles

1. **Main thread is sacred**: User + Claude only, no agents, verbatim transcription
2. **Requirements first**: Every feature thread MUST have Athena's requirements as first message
3. **Autonomous background work**: Agents handle development without blocking user conversation
4. **Clear notification**: User is informed when features are ready for review
5. **Optional participation**: User can join review threads but doesn't have to
6. **No focus stealing**: Background Terminal windows don't steal focus from user's work
