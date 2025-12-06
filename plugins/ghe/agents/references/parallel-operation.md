# Parallel Operation Reference

This reference covers multi-issue coordination, concurrent agent spawning, workload balancing, priority queue algorithm, conflict prevention, autonomous dispatch loop, and progress monitoring.

## Parallel Issue Handling Protocol

**Athena coordinates multiple concurrent development streams without user intervention.**

### Autonomous Operation Mode

When enabled, the orchestrator can manage multiple issues in parallel:

```bash
# Check autonomous mode setting
AUTONOMOUS=$(grep "autonomous_mode:" .claude/ghe.local.md | awk '{print $2}')

if [ "$AUTONOMOUS" = "true" ]; then
  echo "Autonomous mode enabled - parallel processing active"
fi
```

### Multi-Issue Coordination

#### Issue Pool Management

```bash
# Get all ready issues by phase
get_ready_issues() {
  local PHASE=$1
  gh issue list --label "phase:$PHASE" --label "ready" --state open --json number,title,labels
}

# Distribute work to available agents
DEV_READY=$(get_ready_issues "dev")
TEST_READY=$(get_ready_issues "test")
REVIEW_READY=$(get_ready_issues "review")

echo "Issue Pool Status:"
echo "- DEV ready: $(echo "$DEV_READY" | jq 'length')"
echo "- TEST ready: $(echo "$TEST_READY" | jq 'length')"
echo "- REVIEW ready: $(echo "$REVIEW_READY" | jq 'length')"
```

#### Concurrent Agent Spawning

**Spawning Protocol**

When multiple issues are ready, spawn agents in priority order:

1. **REVIEW first** - Unblock completed work
2. **TEST second** - Verify before more DEV
3. **DEV last** - New work after queue cleared

**Spawn Commands**

For each ready issue (up to MAX_CONCURRENT):

- **DEV**: SPAWN dev-thread-manager: Claim and develop issue #N following TDD
- **TEST**: SPAWN test-thread-manager: Claim and verify issue #N with strict testing
- **REVIEW**: SPAWN review-thread-manager: Claim and review issue #N against requirements

### Workload Balancing

```bash
# Maximum concurrent issues per phase
MAX_DEV=3
MAX_TEST=2
MAX_REVIEW=2

# Check current workload
get_phase_workload() {
  local PHASE=$1
  gh issue list --label "phase:$PHASE" --label "in-progress" --state open --json number | jq 'length'
}

CURRENT_DEV=$(get_phase_workload "dev")
CURRENT_TEST=$(get_phase_workload "test")
CURRENT_REVIEW=$(get_phase_workload "review")

# Calculate available slots
SLOTS_DEV=$((MAX_DEV - CURRENT_DEV))
SLOTS_TEST=$((MAX_TEST - CURRENT_TEST))
SLOTS_REVIEW=$((MAX_REVIEW - CURRENT_REVIEW))

echo "Available slots: DEV=$SLOTS_DEV, TEST=$SLOTS_TEST, REVIEW=$SLOTS_REVIEW"
```

### Priority Queue Algorithm

```bash
# Calculate issue priority
calculate_priority() {
  local ISSUE=$1
  local PRIORITY=0

  LABELS=$(gh issue view "$ISSUE" --json labels --jq '.labels[].name')

  # Priority modifiers
  echo "$LABELS" | grep -q "urgent" && PRIORITY=$((PRIORITY + 100))
  echo "$LABELS" | grep -q "blocking" && PRIORITY=$((PRIORITY + 50))
  echo "$LABELS" | grep -q "bug" && PRIORITY=$((PRIORITY + 30))
  echo "$LABELS" | grep -q "security" && PRIORITY=$((PRIORITY + 80))

  # Age modifier (older = higher priority)
  CREATED=$(gh issue view "$ISSUE" --json createdAt --jq '.createdAt')
  AGE_DAYS=$(( ($(date +%s) - $(date -d "$CREATED" +%s)) / 86400 ))
  PRIORITY=$((PRIORITY + AGE_DAYS))

  echo "$PRIORITY"
}

# Sort issues by priority
sort_by_priority() {
  local ISSUES=$1
  echo "$ISSUES" | jq -r '.[].number' | while read issue; do
    PRIORITY=$(calculate_priority "$issue")
    echo "$PRIORITY $issue"
  done | sort -rn | awk '{print $2}'
}
```

### Conflict Prevention

```bash
# Prevent conflicting operations
check_conflicts() {
  local ISSUE=$1
  local PHASE=$2

  # Get epic
  EPIC=$(gh issue view "$ISSUE" --json labels --jq '.labels[] | select(.name | startswith("epic:")) | .name | split(":")[1]')

  # Check if another issue in same epic is in conflicting phase
  case $PHASE in
    "dev")
      # Only one DEV at a time per epic (unless explicitly parallel)
      CONFLICTS=$(gh issue list --label "epic:$EPIC" --label "phase:dev" --label "in-progress" --json number | jq 'length')
      ;;
    "test")
      # TEST can run in parallel
      CONFLICTS=0
      ;;
    "review")
      # Only one REVIEW at a time per epic
      CONFLICTS=$(gh issue list --label "epic:$EPIC" --label "phase:review" --label "in-progress" --json number | jq 'length')
      ;;
  esac

  if [ "$CONFLICTS" -gt 0 ]; then
    echo "CONFLICT: Another $PHASE in progress for epic $EPIC"
    return 1
  fi
  return 0
}
```

### Autonomous Dispatch Loop

```bash
# Main dispatch loop (runs periodically)
dispatch_work() {
  echo "=== Dispatch Cycle $(date) ==="

  # 1. Check for promotable threads
  PENDING=$(gh issue list --label "pending-promotion" --state open --json number)
  if [ "$(echo "$PENDING" | jq 'length')" -gt 0 ]; then
    echo "Found pending promotions - spawning Themis"
    # SPAWN phase-gate: Evaluate pending promotions
  fi

  # 2. Fill available slots
  for phase in review test dev; do
    SLOTS=$(eval echo "\$SLOTS_$(echo $phase | tr '[:lower:]' '[:upper:]')")

    if [ "$SLOTS" -gt 0 ]; then
      READY=$(get_ready_issues "$phase" | jq -r '.[].number' | head -$SLOTS)

      for issue in $READY; do
        if check_conflicts "$issue" "$phase"; then
          echo "Dispatching $phase agent for #$issue"
          # SPAWN ${phase}-thread-manager: Claim and process issue #$issue
        fi
      done
    fi
  done

  echo "=== Dispatch Complete ==="
}
```

### Progress Monitoring

```bash
# Monitor all active threads
monitor_progress() {
  echo "## Active Thread Status"
  echo ""

  for phase in dev test review; do
    echo "### Phase: $(echo $phase | tr '[:lower:]' '[:upper:]')"
    gh issue list --label "phase:$phase" --label "in-progress" --state open \
      --json number,title,assignees,updatedAt \
      --template '{{range .}}#{{.number}} {{.title}} (@{{range .assignees}}{{.login}}{{end}}) - Updated: {{.updatedAt}}
{{end}}'
    echo ""
  done
}
```

### Stale Thread Detection

```bash
# Detect and handle stale threads
check_stale_threads() {
  local STALE_HOURS=24

  STALE=$(gh issue list --label "in-progress" --state open --json number,updatedAt | \
    jq --arg cutoff "$(date -d "-$STALE_HOURS hours" --iso-8601=seconds)" \
    '[.[] | select(.updatedAt < $cutoff)]')

  if [ "$(echo "$STALE" | jq 'length')" -gt 0 ]; then
    echo "## STALE THREADS DETECTED"
    echo ""
    echo "$STALE" | jq -r '.[] | "- #\(.number) (last update: \(.updatedAt))"'
    echo ""
    echo "### Recommended Action"
    echo "1. Check if agent is still processing"
    echo "2. Post checkpoint request to thread"
    echo "3. Consider reassignment if no response"
  fi
}
```

### Settings for Parallel Operation

In `.claude/ghe.local.md`:

```yaml
# Parallel processing settings
autonomous_mode: false           # Enable auto-dispatch
max_concurrent_dev: 3           # Max parallel DEV threads
max_concurrent_test: 2          # Max parallel TEST threads
max_concurrent_review: 2        # Max parallel REVIEW threads
dispatch_interval: 300          # Seconds between dispatch cycles
stale_threshold_hours: 24       # Hours before thread considered stale
```
