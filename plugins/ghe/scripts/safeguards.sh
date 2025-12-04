#!/bin/bash
# GHE Safeguards - Comprehensive error prevention and recovery
# Source this file to use safeguard functions in your scripts
#
# Usage: source safeguards.sh
#
# Functions provided:
#   - verify_worktree_health <path>
#   - safe_worktree_cleanup <path> [force]
#   - acquire_merge_lock_safe <issue_num>
#   - release_merge_lock_safe <issue_num>
#   - heartbeat_merge_lock <issue_num>
#   - atomic_commit_push <branch> <message> <files...>
#   - reconcile_ghe_state
#   - validate_with_retry <script> <file>
#   - pre_flight_check <issue_num>

set -euo pipefail

# Configuration
LOCK_TTL=${LOCK_TTL:-900}           # 15 minutes default
HEARTBEAT_INTERVAL=${HEARTBEAT_INTERVAL:-60}  # 1 minute
MAX_RETRIES=${MAX_RETRIES:-3}
RETRY_DELAY=${RETRY_DELAY:-2}
GHE_WORKTREES_DIR=${GHE_WORKTREES_DIR:-"../ghe-worktrees"}

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_error() { echo -e "${RED}ERROR: $*${NC}" >&2; }
log_warn() { echo -e "${YELLOW}WARNING: $*${NC}" >&2; }
log_ok() { echo -e "${GREEN}OK: $*${NC}"; }
log_info() { echo "INFO: $*"; }

#=============================================================================
# WORKTREE SAFEGUARDS
#=============================================================================

# Verify worktree is healthy and usable
# Returns 0 if healthy, 1 if not
verify_worktree_health() {
    local worktree_path="$1"

    log_info "Verifying worktree health: $worktree_path"

    # Check 1: Directory exists
    if [ ! -d "$worktree_path" ]; then
        log_error "Worktree directory does not exist: $worktree_path"
        return 1
    fi

    # Check 2: .git file exists (worktrees have .git file, not directory)
    if [ ! -f "$worktree_path/.git" ]; then
        log_error "Not a valid worktree (missing .git file): $worktree_path"
        return 1
    fi

    # Check 3: .git file points to valid location
    local git_dir=$(cat "$worktree_path/.git" | sed 's/gitdir: //')
    if [ ! -d "$git_dir" ]; then
        log_error "Worktree .git file points to non-existent directory: $git_dir"
        return 1
    fi

    # Check 4: Git recognizes it as worktree
    if ! git worktree list 2>/dev/null | grep -q "$(realpath "$worktree_path")"; then
        log_warn "Git does not recognize worktree: $worktree_path"
        log_info "Attempting repair with: git worktree prune"
        git worktree prune

        # Re-check after prune
        if ! git worktree list 2>/dev/null | grep -q "$(realpath "$worktree_path")"; then
            log_error "Worktree still not recognized after prune"
            return 1
        fi
    fi

    # Check 5: Branch exists and is checked out
    local branch
    branch=$(cd "$worktree_path" && git branch --show-current 2>/dev/null) || true
    if [ -z "$branch" ]; then
        log_error "Worktree has no branch checked out (detached HEAD or corrupted)"
        return 1
    fi

    # Check 6: No uncommitted changes that would block operations
    local git_status_output
    git_status_output=$(cd "$worktree_path" && git status --porcelain 2>/dev/null) || true
    if [ -n "$git_status_output" ]; then
        log_warn "Worktree has uncommitted changes"
        # Not a failure, just a warning
    fi

    log_ok "Worktree health verified: $worktree_path (branch: $branch)"
    return 0
}

# Safely clean up a worktree, handling all edge cases
# Usage: safe_worktree_cleanup <path> [force]
safe_worktree_cleanup() {
    local worktree_path="$1"
    local force="${2:-false}"

    log_info "Cleaning up worktree: $worktree_path (force=$force)"

    # Step 1: Check if directory exists at all
    if [ ! -d "$worktree_path" ]; then
        log_info "Worktree directory already removed: $worktree_path"
        git worktree prune 2>/dev/null || true
        return 0
    fi

    # Step 2: Check for uncommitted changes
    if [ -f "$worktree_path/.git" ]; then
        local git_status_output
        git_status_output=$(cd "$worktree_path" && git status --porcelain 2>/dev/null) || true
        if [ -n "$git_status_output" ] && [ "$force" != "true" ]; then
            log_error "Worktree has uncommitted changes. Use force=true to override."
            log_info "Changes:"
            echo "$git_status_output"
            return 1
        fi
    fi

    # Step 3: Try normal removal first
    if git worktree remove "$worktree_path" 2>/dev/null; then
        log_ok "Worktree removed successfully: $worktree_path"
        return 0
    fi

    # Step 4: If normal removal failed and force=true, do manual cleanup
    if [ "$force" = "true" ]; then
        log_warn "Normal removal failed, forcing cleanup..."

        # Remove .git file to unlink from main repo
        rm -f "$worktree_path/.git" 2>/dev/null || true

        # Prune stale worktrees from git's tracking
        git worktree prune 2>/dev/null || true

        # Remove directory
        rm -rf "$worktree_path"

        log_ok "Worktree force-removed: $worktree_path"
        return 0
    fi

    log_error "Could not remove worktree. Use force=true to override."
    return 1
}

#=============================================================================
# MERGE LOCK SAFEGUARDS
#=============================================================================

# Acquire merge lock with race condition detection and TTL enforcement
# Returns 0 if lock acquired, 1 if not
acquire_merge_lock_safe() {
    local issue_num="$1"
    local lock_label="merge:active"

    log_info "Attempting to acquire merge lock for issue #$issue_num"

    # Check for existing lock
    local existing_lock
    existing_lock=$(gh issue list --label "$lock_label" --state open --json number,updatedAt 2>/dev/null) || true

    if [ -n "$existing_lock" ] && [ "$existing_lock" != "[]" ]; then
        local lock_issue
        lock_issue=$(echo "$existing_lock" | jq -r '.[0].number')
        local lock_time
        lock_time=$(echo "$existing_lock" | jq -r '.[0].updatedAt')

        # Calculate lock age (cross-platform)
        local now_epoch
        now_epoch=$(date +%s)
        local lock_epoch
        # Try GNU date first, fall back to BSD date
        lock_epoch=$(date -d "$lock_time" +%s 2>/dev/null || date -j -f "%Y-%m-%dT%H:%M:%SZ" "$lock_time" +%s 2>/dev/null || echo "0")

        if [ "$lock_epoch" != "0" ]; then
            local lock_age=$((now_epoch - lock_epoch))

            if [ $lock_age -gt $LOCK_TTL ]; then
                log_warn "Stale lock detected on issue #$lock_issue (age: ${lock_age}s > TTL: ${LOCK_TTL}s)"
                log_info "Force-releasing stale lock..."
                gh issue edit "$lock_issue" --remove-label "$lock_label" 2>/dev/null || true
            else
                log_warn "Lock held by issue #$lock_issue (age: ${lock_age}s, TTL: ${LOCK_TTL}s)"
                log_info "Wait for lock release or TTL expiry"
                return 1
            fi
        else
            log_warn "Could not parse lock timestamp, assuming stale"
            gh issue edit "$lock_issue" --remove-label "$lock_label" 2>/dev/null || true
        fi
    fi

    # Acquire lock
    if ! gh issue edit "$issue_num" --add-label "$lock_label" 2>/dev/null; then
        log_error "Failed to add merge lock label"
        return 1
    fi

    # Brief pause to detect race conditions
    sleep 2

    # Verify we're the only lock holder (race condition check)
    local holders
    holders=$(gh issue list --label "$lock_label" --state open --json number 2>/dev/null | jq '. | length') || holders=0

    if [ "$holders" -gt 1 ]; then
        log_error "Race condition detected - multiple lock holders!"
        log_info "Releasing our lock to avoid deadlock..."
        gh issue edit "$issue_num" --remove-label "$lock_label" 2>/dev/null || true
        return 1
    fi

    log_ok "Merge lock acquired for issue #$issue_num"
    return 0
}

# Release merge lock
release_merge_lock_safe() {
    local issue_num="$1"
    local lock_label="merge:active"

    log_info "Releasing merge lock for issue #$issue_num"

    # Remove lock label (ignore errors - lock might already be released)
    gh issue edit "$issue_num" --remove-label "$lock_label" 2>/dev/null || true

    log_ok "Merge lock released for issue #$issue_num"
}

# Send heartbeat to keep lock alive during long operations
heartbeat_merge_lock() {
    local issue_num="$1"

    # Update issue to refresh updatedAt timestamp
    # Use a hidden comment to minimize noise
    gh issue comment "$issue_num" --body "<!-- ghe-merge-heartbeat: $(date -u +%Y-%m-%dT%H:%M:%SZ) -->" 2>/dev/null || true
}

# Wait for merge lock with timeout
wait_for_merge_lock() {
    local issue_num="$1"
    local timeout="${2:-$LOCK_TTL}"
    local start_time
    start_time=$(date +%s)

    log_info "Waiting for merge lock (timeout: ${timeout}s)..."

    while true; do
        if acquire_merge_lock_safe "$issue_num"; then
            return 0
        fi

        local elapsed=$(($(date +%s) - start_time))
        if [ $elapsed -gt $timeout ]; then
            log_error "Timeout waiting for merge lock (${elapsed}s > ${timeout}s)"
            return 1
        fi

        log_info "Lock busy, waiting... (${elapsed}s / ${timeout}s)"
        sleep 30
    done
}

#=============================================================================
# ATOMIC GIT OPERATIONS
#=============================================================================

# Perform atomic commit and push with rollback on failure
# Usage: atomic_commit_push <branch> <message> <files...>
atomic_commit_push() {
    local branch="$1"
    local message="$2"
    shift 2
    local files=("$@")

    log_info "Atomic commit-push: ${#files[@]} files to branch $branch"

    # Create savepoint
    local savepoint
    savepoint=$(git rev-parse HEAD)
    log_info "Savepoint: $savepoint"

    # Stage files
    for file in "${files[@]}"; do
        if [ ! -e "$file" ]; then
            log_error "File does not exist: $file"
            git reset HEAD 2>/dev/null || true
            return 1
        fi

        if ! git add "$file"; then
            log_error "Failed to stage: $file"
            git reset HEAD 2>/dev/null || true
            return 1
        fi
    done

    # Check if there's anything to commit
    if git diff --cached --quiet; then
        log_warn "No changes to commit"
        return 0
    fi

    # Commit
    if ! git commit -m "$message"; then
        log_error "Commit failed, rolling back staged changes"
        git reset HEAD 2>/dev/null || true
        return 1
    fi

    local commit_hash
    commit_hash=$(git rev-parse HEAD)
    log_info "Committed: $commit_hash"

    # Push
    if ! git push origin "$branch"; then
        log_error "Push failed, rolling back commit"
        git reset --hard "$savepoint"
        return 1
    fi

    log_ok "Atomic commit-push completed: $commit_hash"
    return 0
}

#=============================================================================
# STATE RECONCILIATION
#=============================================================================

# Reconcile ghe.local.md state with actual GitHub state
reconcile_ghe_state() {
    local config_file="${1:-.claude/ghe.local.md}"

    log_info "Reconciling GHE state..."

    if [ ! -f "$config_file" ]; then
        log_warn "Config file not found: $config_file"
        return 0
    fi

    # Read current state from config
    local config_issue
    config_issue=$(grep '^current_issue:' "$config_file" | sed 's/current_issue: *//' | tr -d '"') || true

    # Check if referenced issue is still open
    if [ -n "$config_issue" ] && [ "$config_issue" != "null" ]; then
        local issue_state
        issue_state=$(gh issue view "$config_issue" --json state --jq '.state' 2>/dev/null) || issue_state="UNKNOWN"

        if [ "$issue_state" = "CLOSED" ]; then
            log_warn "ghe.local.md references closed issue #$config_issue"
            log_info "Resetting state to null..."

            # Use sed to update (cross-platform)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                sed -i '' 's/^current_issue: .*/current_issue: null/' "$config_file"
                sed -i '' 's/^current_phase: .*/current_phase: null/' "$config_file"
            else
                sed -i 's/^current_issue: .*/current_issue: null/' "$config_file"
                sed -i 's/^current_phase: .*/current_phase: null/' "$config_file"
            fi
        fi
    fi

    # Check for orphaned worktrees
    if [ -d "$GHE_WORKTREES_DIR" ]; then
        for wt in "$GHE_WORKTREES_DIR"/issue-*/; do
            if [ -d "$wt" ]; then
                local issue_num
                issue_num=$(basename "$wt" | sed 's/issue-//')

                local issue_state
                issue_state=$(gh issue view "$issue_num" --json state --jq '.state' 2>/dev/null) || issue_state="UNKNOWN"

                if [ "$issue_state" = "CLOSED" ]; then
                    log_warn "Orphaned worktree found for closed issue #$issue_num: $wt"
                    log_info "Cleaning up orphaned worktree..."
                    safe_worktree_cleanup "$wt" true
                fi
            fi
        done
    fi

    # Prune any stale worktrees
    git worktree prune 2>/dev/null || true

    log_ok "State reconciliation complete"
}

#=============================================================================
# VALIDATION WITH RETRIES
#=============================================================================

# Run validation script with retries for transient failures
# Usage: validate_with_retry <script> <file>
validate_with_retry() {
    local script="$1"
    local file="$2"

    log_info "Validating: $file (max $MAX_RETRIES attempts)"

    for ((i=1; i<=MAX_RETRIES; i++)); do
        if "$script" "$file"; then
            log_ok "Validation passed on attempt $i"
            return 0
        fi

        if [ $i -lt $MAX_RETRIES ]; then
            log_warn "Validation failed (attempt $i/$MAX_RETRIES), retrying in ${RETRY_DELAY}s..."
            sleep $RETRY_DELAY
        fi
    done

    log_error "Validation failed after $MAX_RETRIES attempts"
    return 1
}

#=============================================================================
# PRE-FLIGHT CHECK
#=============================================================================

# Run all safety checks before starting work on an issue
# Usage: pre_flight_check <issue_num>
pre_flight_check() {
    local issue_num="$1"
    local worktree_path="$GHE_WORKTREES_DIR/issue-$issue_num"
    local errors=0

    log_info "Running pre-flight checks for issue #$issue_num"
    echo "=================================================="

    # Check 1: Issue exists and is open
    echo -n "[1/6] Issue #$issue_num status: "
    local issue_state
    issue_state=$(gh issue view "$issue_num" --json state --jq '.state' 2>/dev/null) || issue_state="NOT_FOUND"

    if [ "$issue_state" = "OPEN" ]; then
        echo -e "${GREEN}OPEN${NC}"
    else
        echo -e "${RED}$issue_state${NC}"
        ((errors++))
    fi

    # Check 2: Worktree exists
    echo -n "[2/6] Worktree exists: "
    if [ -d "$worktree_path" ]; then
        echo -e "${GREEN}YES${NC}"
    else
        echo -e "${YELLOW}NO (will be created)${NC}"
    fi

    # Check 3: Worktree health (if exists)
    echo -n "[3/6] Worktree health: "
    if [ -d "$worktree_path" ]; then
        if verify_worktree_health "$worktree_path" >/dev/null 2>&1; then
            echo -e "${GREEN}HEALTHY${NC}"
        else
            echo -e "${RED}UNHEALTHY${NC}"
            ((errors++))
        fi
    else
        echo -e "${YELLOW}N/A${NC}"
    fi

    # Check 4: Not on main branch (if in worktree)
    echo -n "[4/6] Branch check: "
    if [ -d "$worktree_path" ]; then
        local current_branch
        current_branch=$(cd "$worktree_path" && git branch --show-current 2>/dev/null) || current_branch=""

        if [ "$current_branch" = "main" ]; then
            echo -e "${RED}ON MAIN (FORBIDDEN)${NC}"
            ((errors++))
        elif [ -n "$current_branch" ]; then
            echo -e "${GREEN}$current_branch${NC}"
        else
            echo -e "${RED}DETACHED HEAD${NC}"
            ((errors++))
        fi
    else
        echo -e "${YELLOW}N/A${NC}"
    fi

    # Check 5: No active merge lock (unless it's ours)
    echo -n "[5/6] Merge lock: "
    local lock_holder
    lock_holder=$(gh issue list --label "merge:active" --state open --json number --jq '.[0].number' 2>/dev/null) || lock_holder=""

    if [ -z "$lock_holder" ]; then
        echo -e "${GREEN}FREE${NC}"
    elif [ "$lock_holder" = "$issue_num" ]; then
        echo -e "${YELLOW}HELD BY US${NC}"
    else
        echo -e "${YELLOW}HELD BY #$lock_holder${NC}"
    fi

    # Check 6: GitHub CLI authenticated
    echo -n "[6/6] GitHub auth: "
    if gh auth status >/dev/null 2>&1; then
        echo -e "${GREEN}OK${NC}"
    else
        echo -e "${RED}NOT AUTHENTICATED${NC}"
        ((errors++))
    fi

    echo "=================================================="

    if [ $errors -gt 0 ]; then
        log_error "Pre-flight check failed with $errors error(s)"
        return 1
    fi

    log_ok "All pre-flight checks passed"
    return 0
}

#=============================================================================
# RECOVERY PROCEDURES
#=============================================================================

# Recover from a crashed/interrupted merge operation
recover_from_merge_crash() {
    local issue_num="$1"

    log_info "Attempting recovery from merge crash for issue #$issue_num"

    # Step 1: Release any held locks
    release_merge_lock_safe "$issue_num"

    # Step 2: Check worktree state
    local worktree_path="$GHE_WORKTREES_DIR/issue-$issue_num"

    if [ -d "$worktree_path" ]; then
        # Check for in-progress rebase
        if [ -d "$worktree_path/.git/rebase-merge" ] || [ -d "$worktree_path/.git/rebase-apply" ]; then
            log_warn "Found in-progress rebase, aborting..."
            (cd "$worktree_path" && git rebase --abort 2>/dev/null) || true
        fi

        # Check for merge in progress
        if [ -f "$worktree_path/.git/MERGE_HEAD" ]; then
            log_warn "Found in-progress merge, aborting..."
            (cd "$worktree_path" && git merge --abort 2>/dev/null) || true
        fi
    fi

    # Step 3: Reconcile state
    reconcile_ghe_state

    log_ok "Recovery complete for issue #$issue_num"
}

# Print usage/help
print_safeguards_help() {
    cat << 'EOF'
GHE Safeguards - Available Functions

WORKTREE OPERATIONS:
  verify_worktree_health <path>     - Check if worktree is healthy
  safe_worktree_cleanup <path> [force] - Safely remove worktree

MERGE LOCK OPERATIONS:
  acquire_merge_lock_safe <issue>   - Acquire lock with TTL enforcement
  release_merge_lock_safe <issue>   - Release merge lock
  wait_for_merge_lock <issue> [timeout] - Wait for lock with timeout
  heartbeat_merge_lock <issue>      - Send heartbeat to keep lock alive

GIT OPERATIONS:
  atomic_commit_push <branch> <msg> <files...> - Atomic commit+push

STATE MANAGEMENT:
  reconcile_ghe_state [config_file] - Fix state desync
  pre_flight_check <issue>          - Run all safety checks
  recover_from_merge_crash <issue>  - Recover from crash

VALIDATION:
  validate_with_retry <script> <file> - Validate with retries

CONFIGURATION (environment variables):
  LOCK_TTL=900              - Lock timeout in seconds (default: 15 min)
  MAX_RETRIES=3             - Retry attempts for validation
  RETRY_DELAY=2             - Delay between retries in seconds
  GHE_WORKTREES_DIR=../ghe-worktrees - Worktrees directory

EOF
}

# If script is run directly (not sourced), show help
if [[ "${BASH_SOURCE[0]:-}" == "${0}" ]]; then
    print_safeguards_help
fi
