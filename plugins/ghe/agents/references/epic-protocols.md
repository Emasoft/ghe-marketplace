# Epic Protocols Reference

This reference covers epic creation, wave creation, epic phase transitions, and epic completion protocols.

## Epic Creation Protocol

**CRITICAL**: Epics coordinate GROUPS of issues via WAVES. Athena owns ALL epic phases.

### When to Create an Epic

| Trigger | Action | Epic Type |
|---------|--------|-----------|
| Large feature requiring multiple issues | Create epic | `epic-feature` |
| Codebase-wide refactoring | Create epic | `epic-refactoring` |
| Database/API migration | Create epic | `epic-migration` |
| Plugin/addon development | Create epic | `epic-addons` |
| Web server changes | Create epic | `epic-webserver` |
| Single small bug/feature | **NO EPIC** - use regular thread | `dev` label directly |

### Epic Creation Commands (Athena Only)

```bash
# Create epic thread (meta-level planning)
EPIC_TYPE="epic-feature"
EPIC_TITLE="User Authentication System"

# Source avatar helper
source "${CLAUDE_PLUGIN_ROOT}/scripts/post-with-avatar.sh"
HEADER=$(avatar_header "Athena")

gh issue create \
  --title "[EPIC] [DEV] ${EPIC_TYPE}: ${EPIC_TITLE}" \
  --label "epic" \
  --label "phase:dev" \
  --label "${EPIC_TYPE}" \
  --label "ready" \
  --body "${HEADER}
## Epic: ${EPIC_TITLE}

### Phase
**DEV**: Planning what to develop (epic thread)

### Scope
This epic coordinates the complete ${EPIC_TITLE} feature.

### WAVE 1 (Foundation) - To Be Created
- [ ] #TBD - Database schema for users
- [ ] #TBD - User model and validation
- [ ] #TBD - Password hashing utilities

### WAVE 2 (Core Auth) - After Wave 1 Complete
- [ ] #TBD - Login endpoint
- [ ] #TBD - Logout endpoint
- [ ] #TBD - Session management

### WAVE 3 (Advanced) - After Wave 2 Complete
- [ ] #TBD - Password reset flow
- [ ] #TBD - Two-factor authentication

### Managed By
**Athena** (all epic phases)

### Child Issues Managed By
- DEV phase: Hephaestus
- TEST phase: Artemis
- REVIEW phase: Hera
- Phase transitions: Themis"
```

### Creating a WAVE (Athena Only)

```bash
EPIC_ISSUE=<epic issue number>
WAVE_NUM=1

# Create all issues for WAVE 1
for FEATURE in "Database schema" "User model" "Password hashing"; do
  gh issue create \
    --title "[DEV] ${FEATURE}" \
    --label "phase:dev" \
    --label "parent-epic:${EPIC_ISSUE}" \
    --label "wave:${WAVE_NUM}" \
    --label "ready" \
    --body "Part of Epic #${EPIC_ISSUE}, Wave ${WAVE_NUM}.

## Feature
${FEATURE}

## Parent Epic
#${EPIC_ISSUE}

## Wave
Wave ${WAVE_NUM} - Foundation

## Managed By
- DEV: Hephaestus
- TEST: Artemis
- REVIEW: Hera
- Phase transitions: Themis"
done

# Update epic with created issues
HEADER=$(avatar_header "Athena")
gh issue comment $EPIC_ISSUE --body "${HEADER}
## Wave ${WAVE_NUM} Created

### Issues
- #NEW1 - Database schema
- #NEW2 - User model
- #NEW3 - Password hashing

### Next Steps
These issues will now go through normal DEV → TEST → REVIEW cycles.
Themis will notify this epic when all Wave ${WAVE_NUM} issues reach release."
```

### Wave Tracking (Athena Only)

```bash
EPIC_ISSUE=123
WAVE_NUM=1

# Find all issues in a specific wave
gh issue list --label "parent-epic:${EPIC_ISSUE}" --label "wave:${WAVE_NUM}" --json number,title,state,labels

# Check wave progress (count closed issues with completed label)
TOTAL=$(gh issue list --label "parent-epic:${EPIC_ISSUE}" --label "wave:${WAVE_NUM}" --json number | jq 'length')
COMPLETED=$(gh issue list --label "parent-epic:${EPIC_ISSUE}" --label "wave:${WAVE_NUM}" --label "completed" --state closed --json number | jq 'length')
echo "Wave ${WAVE_NUM} progress: ${COMPLETED}/${TOTAL} issues completed"

# Check if wave is complete (all issues closed with completed label)
if [ "$COMPLETED" -eq "$TOTAL" ]; then
  echo "WAVE ${WAVE_NUM} COMPLETE - ready for next wave"
fi
```

### Epic Phase Transitions (Athena Requests, Themis Executes)

**CRITICAL**: Epic phase labels (`epic` + phase labels `dev`/`test`/`review`/`complete`) are **Themis-only**.
Athena coordinates and requests transitions, but Themis validates and executes them.

Epic phases transition based on PLANNING completion, not development completion:

```bash
EPIC_ISSUE=<epic issue number>

# Transition DEV → TEST phase for epic
# Condition: All waves are PLANNED (not necessarily developed)
# Athena has defined WHAT to develop in each wave

# Source avatar helper
source "${CLAUDE_PLUGIN_ROOT}/scripts/post-with-avatar.sh"
HEADER=$(avatar_header "Athena")

# Step 1: Athena requests transition
gh issue comment $EPIC_ISSUE --body "${HEADER}
## Requesting Epic Transition: DEV → TEST Phase

### Verification
- [ ] All waves are planned
- [ ] Requirements defined for each wave
- [ ] Ready to plan TEST strategy

### What This Means
Development planning is complete. Now planning TEST strategy."

# Step 2: Spawn Themis to execute transition (epic phase labels are Themis-only)
# DO NOT add/remove epic/dev/test/review labels directly
echo "SPAWN phase-gate: Validate and execute epic transition DEV → TEST phase for epic #${EPIC_ISSUE}"

# Themis will:
# 1. Validate transition criteria
# 2. Remove dev label, add test label (epic label stays)
# 3. Post transition notification
```

### Epic Completion (Athena Requests, Themis Executes)

**CRITICAL**: Epic phase labels and `complete` label are **Themis-only**.

When ALL waves are complete (all child issues closed with `completed` label):

```bash
EPIC_ISSUE=123

# Verify ALL child issues are completed (closed with completed label)
TOTAL=$(gh issue list --label "parent-epic:${EPIC_ISSUE}" --json number | jq 'length')
COMPLETED=$(gh issue list --label "parent-epic:${EPIC_ISSUE}" --label "completed" --state closed --json number | jq 'length')

if [ "$COMPLETED" -eq "$TOTAL" ]; then
  # Step 1: Athena requests epic completion
  HEADER=$(avatar_header "Athena")
  gh issue comment $EPIC_ISSUE --body "${HEADER}
## Requesting Epic Completion

### Verification
- Total child issues: ${TOTAL}
- Completed: ${COMPLETED}
- All issues complete: YES

### Requesting Themis to mark epic complete"

  # Step 2: Spawn Themis to execute completion (epic labels are Themis-only)
  # DO NOT remove/add epic/dev/test/review/complete labels directly
  echo "SPAWN phase-gate: Validate and execute epic completion for epic #${EPIC_ISSUE}"

  # Themis will:
  # 1. Validate all child issues are closed with completed label
  # 2. Remove phase labels (dev, test, review - whichever is current)
  # 3. Add complete label (epic label stays)
  # 4. Close epic issue
  # 5. Post completion notification
fi
```

### Agent Responsibilities Summary

| Agent | Handles | Never Handles |
|-------|---------|---------------|
| **Athena** | Epic coordination, wave planning, requests transitions | Phase labels (Themis-only), single issue execution |
| **Hephaestus** | Regular `dev` threads | Epic threads, phase labels |
| **Artemis** | Regular `test` threads | Epic threads, phase labels |
| **Hera** | Regular `review` threads | Epic threads, phase labels |
| **Themis** | ALL phase labels (dev/test/review, epic+phases, gate:*), ALL transitions | Execution work |
