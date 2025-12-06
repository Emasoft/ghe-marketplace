# GHE Scripts Reference

Complete reference for all GHE Python scripts. Use these instead of embedding inline code.

## Script Categories

| Category | Scripts | Purpose |
|----------|---------|---------|
| **Core** | `ghe_common.py`, `ghe_init.py` | Shared utilities, initialization |
| **Thread Mgmt** | `thread_manager.py`, `phase_transition.py` | Thread lifecycle |
| **Safety** | `safeguards.py` | Error prevention, recovery |
| **Communication** | `post_with_avatar.py` | GitHub comments with avatars |
| **Session** | `session_context.py`, `session_recover.py` | Context management |
| **Transcription** | `auto_transcribe.py`, `transcribe_*.py` | Issue transcription |

---

## thread_manager.py

Thread lifecycle management for DEV/TEST/REVIEW threads.

### CLI Usage

```bash
# Initialize a new thread
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/thread_manager.py" init --issue 42 --requirements "REQ-001"

# Transition phase
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/thread_manager.py" transition --issue 42 --phase test

# Get current phase
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/thread_manager.py" get-phase --issue 42

# Check if epic
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/thread_manager.py" is-epic --issue 42
```

### Python Module Usage

```python
from thread_manager import (
    is_epic_issue,
    get_issue_phase,
    transition_phase,
    init_thread,
    get_phase_manager,
)

# Check if issue is an epic
if is_epic_issue(42):
    print("This is an epic thread")

# Get current phase
phase = get_issue_phase(42)  # Returns: "dev", "test", "review", or None

# Transition to next phase
transition_phase(42, "test")

# Get phase manager agent
manager = get_phase_manager("dev")  # Returns: "Hephaestus"
```

---

## phase_transition.py

Phase validation and transition execution.

### CLI Usage

```bash
# Validate a transition
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/phase_transition.py" validate --from dev --to test --issue 42

# Execute a transition
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/phase_transition.py" execute --phase test --issue 42

# Demote to DEV
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/phase_transition.py" demote --issue 42 --reason "Tests failing"
```

### Python Module Usage

```python
from phase_transition import (
    is_valid_transition,
    get_issue_phase,
    execute_transition,
    demote_to_dev,
)

# Validate transition
if is_valid_transition("dev", "test"):
    execute_transition("test", issue=42)

# Demote with reason
demote_to_dev(issue=42, reason="Critical bugs found")
```

---

## safeguards.py

Error prevention and recovery system.

### CLI Usage

```bash
# Pre-flight check (run before any work)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" preflight --issue 42

# Verify worktree health
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" verify-worktree --path "../ghe-worktrees/issue-42"

# Recover from crash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" recover --issue 42

# Reconcile GHE state
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" reconcile

# Acquire merge lock
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" acquire-lock --issue 42

# Release merge lock
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" release-lock --issue 42
```

### Python Module Usage

```python
from safeguards import (
    pre_flight_check,
    verify_worktree_health,
    recover_from_merge_crash,
    acquire_merge_lock_safe,
    release_merge_lock_safe,
    atomic_commit_push,
)

# Pre-flight check
if not pre_flight_check("42"):
    print("Pre-flight failed!")
    sys.exit(1)

# Verify worktree
if verify_worktree_health("../ghe-worktrees/issue-42"):
    print("Worktree healthy")

# Atomic commit with rollback on failure
if atomic_commit_push("issue-42", "Fix bug", ["src/main.py"]):
    print("Commit successful")
```

---

## post_with_avatar.py

GitHub comments with avatar banners.

### CLI Usage

```bash
# Get avatar header for an agent
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/post_with_avatar.py" --header-only "Hera"

# Test all avatars
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/post_with_avatar.py" --test
```

### Python Module Usage

```python
from post_with_avatar import (
    post_issue_comment,
    format_comment,
    get_avatar_header,
)

# Post a comment with avatar
post_issue_comment(42, "Hera", "Review complete. Verdict: PASS")

# Get just the header for manual formatting
header = get_avatar_header("Hera")
body = f"{header}\n## My Section\nContent here..."

# Format a full comment
formatted = format_comment("Athena", "Epic checkpoint posted.")
```

### Agent Names

| Agent ID | Display Name |
|----------|--------------|
| ghe:dev-thread-manager | Hephaestus |
| ghe:test-thread-manager | Artemis |
| ghe:review-thread-manager | Hera |
| ghe:github-elements-orchestrator | Athena |
| ghe:phase-gate | Themis |
| ghe:memory-sync | Mnemosyne |
| ghe:enforcement | Ares |
| ghe:reporter | Hermes |
| ghe:ci-issue-opener | Chronos |
| ghe:pr-checker | Cerberus |

---

## session_context.py

Session state and context management.

### Python Module Usage

```python
from session_context import (
    get_session_context,
    save_session_context,
    clear_session_context,
)

# Get current context
ctx = get_session_context()
print(f"Current issue: {ctx.get('issue')}")

# Save context
save_session_context({"issue": 42, "phase": "dev"})
```

---

## check_issue_set.py

Validate issue sets for epics.

### CLI Usage

```bash
# Check if issue set is complete
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_issue_set.py" --epic 10
```

---

## check_review_ready.py

Verify review readiness.

### CLI Usage

```bash
# Check if ready for review
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/check_review_ready.py" --issue 42
```

---

## Best Practices

1. **Always use scripts instead of inline bash** - Scripts are tested and maintained
2. **Import as Python modules when possible** - Cleaner, better error handling
3. **Use CLI for simple operations** - Quick one-off commands
4. **Check script help** - `python3 script.py --help` for latest options
5. **Use CLAUDE_PLUGIN_ROOT** - Never hardcode paths
