# GHE Safeguards Integration

## Overview

The GHE safeguards system provides comprehensive error prevention and recovery functions. All agents MUST use these safeguards before performing critical operations.

## Available Functions

| Function | Purpose |
|----------|---------|
| `pre_flight_check(issue_num)` | All safety checks before work |
| `verify_worktree_health(path)` | Check worktree is valid |
| `safe_worktree_cleanup(path)` | Remove worktree safely |
| `acquire_merge_lock_safe(issue_num)` | Get merge lock with TTL |
| `release_merge_lock_safe(issue_num)` | Release merge lock |
| `atomic_commit_push(branch, msg, files)` | Commit+push with rollback |
| `reconcile_ghe_state()` | Fix state desync |
| `validate_with_retry(script, file)` | Validation with retries |
| `recover_from_merge_crash(issue_num)` | Recovery after crash |

## Usage in Python Scripts

```python
#!/usr/bin/env python3
"""Example script using GHE safeguards."""
import sys
sys.path.insert(0, os.environ.get('CLAUDE_PLUGIN_ROOT', '.') + '/scripts')

from safeguards import (
    pre_flight_check,
    verify_worktree_health,
    recover_from_merge_crash,
)

# Pre-flight check before any work
issue_num = 42
if not pre_flight_check(issue_num):
    print("Pre-flight check failed. Resolve issues before proceeding.")
    sys.exit(1)

# Verify worktree health
worktree_path = f"../ghe-worktrees/issue-{issue_num}"
if not verify_worktree_health(worktree_path):
    print("Worktree health check failed. Cannot proceed.")
    sys.exit(1)
```

## CLI Usage

```bash
# Pre-flight check
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" --pre-flight "$ISSUE_NUM"

# Recover from crash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" --recover "$ISSUE_NUM"

# Verify worktree health
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/safeguards.py" --verify-worktree "$WORKTREE_PATH"
```

## Pre-Flight Check Details

The pre-flight check verifies:
1. Git repo is clean (no uncommitted changes)
2. Worktree exists and is healthy
3. No merge locks held by other processes
4. Branch is correct for the issue
5. Remote is reachable

## Recovery Protocol

If a previous operation crashed or was interrupted:

```python
from safeguards import recover_from_merge_crash

# Attempt recovery
if recover_from_merge_crash(issue_num):
    print("Recovery successful")
else:
    print("Recovery failed - manual intervention required")
```

## Error Handling

All safeguard functions return boolean (True/False) for success/failure. They also print detailed error messages to stderr for debugging.

**CRITICAL**: Never ignore safeguard failures. If a check fails, stop and investigate.
