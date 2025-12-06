# Wave Management Reference

This reference covers WAVE-based development, wave lifecycle, wave completion notifications, and wave tracking.

## WAVE-Based Development

**CRITICAL**: Epics organize work into WAVES. Athena writes ALL requirements BEFORE starting a wave.

### What is a WAVE?

A WAVE is a batch of child issues that:
1. Have complete requirements design files written by Athena
2. Can be developed in parallel (no blocking dependencies within wave)
3. Must ALL complete before the next wave starts

```
EPIC: User Authentication System
│
├── WAVE 1 (Foundation) - Requirements written, wave started
│   ├── Issue #101: Database schema for users
│   ├── Issue #102: User model and validation
│   └── Issue #103: Password hashing utilities
│
├── WAVE 2 (Core Auth) - Requirements drafted, waiting for WAVE 1
│   ├── (pending) Login endpoint
│   ├── (pending) Logout endpoint
│   └── (pending) Session management
│
└── WAVE 3 (Advanced) - Requirements not yet written
    ├── (future) Password reset flow
    ├── (future) Two-factor authentication
    └── (future) OAuth integration
```

### WAVE Labels

| Label | Purpose |
|-------|---------|
| `wave:1` | First wave of issues |
| `wave:2` | Second wave (depends on wave 1 completion) |
| `wave:N` | Nth wave |
| `parent-epic:123` | Links child issue to parent epic |

### Athena's Two Actions

**Athena only performs TWO types of actions:**

1. **PLAN A WAVE** - Write requirements design files
2. **START A WAVE** - Create issues from requirements

**After starting a wave, Athena does NOTHING until Themis notifies wave completion.**

### WAVE Lifecycle

```
PHASE 1: PLANNING (Athena active)
         │
         ▼
Athena writes requirements design file for each issue in wave
         │
         ▼
All requirements reviewed and finalized
         │
         ▼
PHASE 2: STARTING THE WAVE (Athena's only action)
         │
         ▼
Athena creates one issue per requirement file:
  - Title: [DEV] [Feature Name]
  - Label: dev, parent-epic:NNN, wave:N
  - Body: The complete requirements design file
         │
         ▼
PHASE 3: PASSIVE WAITING (Athena does NOTHING)
         │
         ▼
Hephaestus develops each issue (DEV phase)
Artemis tests each issue (TEST phase)
Hera reviews each issue (REVIEW phase)
Themis promotes each issue through phases
         │
    [Athena does NOT intervene]
    [Problems are handled by the three managers]
         │
         ▼
PHASE 4: WAVE COMPLETION (Themis triggers Athena)
         │
         ▼
When LAST issue reaches RELEASE, Themis posts to epic
         │
         ▼
Athena receives notification → Returns to PHASE 1 for next wave
```

### CRITICAL: Athena's Passive Waiting

**After starting a wave, Athena:**
- Does NOT monitor individual threads
- Does NOT intervene in problems
- Does NOT help Hephaestus/Artemis/Hera
- Does NOT respond to thread comments
- ONLY waits for Themis's wave completion notification

**Why?** Clear separation of concerns:
- Athena = Strategic planning
- Hephaestus/Artemis/Hera = Tactical execution
- Themis = Phase transitions and notifications

### Starting a Wave

**PREREQUISITE**: ALL requirements design files must be complete AND saved to REQUIREMENTS folder.

```bash
EPIC_ISSUE=123
WAVE_NUM=1
PROJECT_ROOT=$(git rev-parse --show-toplevel)

# Source avatar helper
source "${CLAUDE_PLUGIN_ROOT}/scripts/post-with-avatar.sh"

# Step 1: Verify requirements folder exists
REQUIREMENTS_DIR="${PROJECT_ROOT}/REQUIREMENTS/epic-${EPIC_ISSUE}/wave-${WAVE_NUM}"
if [ ! -d "$REQUIREMENTS_DIR" ]; then
  echo "ERROR: Requirements folder does not exist: $REQUIREMENTS_DIR"
  echo "Cannot start wave without requirements files!"
  exit 1
fi

# Step 2: Count requirements files (must have _EPIC suffix for epic issues)
EPIC_PADDED=$(printf "%05d" $EPIC_ISSUE)
REQ_COUNT=$(ls -1 "$REQUIREMENTS_DIR"/REQ-*_EPIC${EPIC_PADDED}.md 2>/dev/null | wc -l)
if [ "$REQ_COUNT" -eq 0 ]; then
  echo "ERROR: No requirements files found in $REQUIREMENTS_DIR"
  echo "Expected format: REQ-NNN-name_EPIC${EPIC_PADDED}.md"
  exit 1
fi

echo "Found $REQ_COUNT requirements files for epic #${EPIC_ISSUE}. Starting wave..."

# Step 3: For EACH requirements file, create an issue
for REQ_FILE in "$REQUIREMENTS_DIR"/REQ-*_EPIC${EPIC_PADDED}.md; do
  # Extract feature name from filename
  # REQ-101-user-schema_EPIC00123.md -> user schema
  FEATURE_NAME=$(basename "$REQ_FILE" .md | sed "s/REQ-[0-9]*-//" | sed "s/_EPIC[0-9]*//" | tr '-' ' ')

  # Read requirements content
  REQ_CONTENT=$(cat "$REQ_FILE")
  REQ_SIZE=${#REQ_CONTENT}

  # Build issue body with link
  REQ_RELATIVE_PATH="REQUIREMENTS/epic-${EPIC_ISSUE}/wave-${WAVE_NUM}/$(basename $REQ_FILE)"

  # Extract checklist items from requirements file
  # Acceptance Criteria (lines starting with - [ ] **AC-)
  AC_CHECKLIST=$(grep -E '^\s*-\s*\[\s*\]\s*\*\*AC-' "$REQ_FILE" | head -10 || echo "")
  # Atomic Changes (lines starting with number. **CHANGE-)
  CHANGES_CHECKLIST=$(grep -E '^\s*[0-9]+\.\s*\*\*CHANGE-' "$REQ_FILE" | sed 's/^/- [ ] /' | head -10 || echo "")
  # Tests (lines starting with | UT- or | EC- or | IT-)
  TESTS_CHECKLIST=$(grep -E '^\|\s*(UT|EC|IT)-' "$REQ_FILE" | awk -F'|' '{print "- [ ] " $2 ": " $3}' | head -10 || echo "")

  # Build checklist section
  CHECKLIST="## Implementation Checklist

### Acceptance Criteria
${AC_CHECKLIST:-No acceptance criteria found - check requirements file}

### Atomic Changes
${CHANGES_CHECKLIST:-No atomic changes found - check requirements file}

### Tests (TDD - write BEFORE implementation)
${TESTS_CHECKLIST:-No tests found - check requirements file}

### Final Verification
- [ ] All tests pass
- [ ] Code reviewed
- [ ] Documentation updated"

  if [ "$REQ_SIZE" -lt 4000 ]; then
    # Less than ~10 pages: embed full content + checklist
    ISSUE_BODY="## Requirements

**File**: [$(basename $REQ_FILE)](${REQ_RELATIVE_PATH})

---

${CHECKLIST}

---

<details>
<summary>Full Requirements Document</summary>

${REQ_CONTENT}

</details>"
  else
    # Large file: link only + checklist
    ISSUE_BODY="## Requirements

**File**: [$(basename $REQ_FILE)](${REQ_RELATIVE_PATH})

> Requirements file is large (${REQ_SIZE} chars). See linked file for full content.

---

${CHECKLIST}

---

### Requirements Summary
$(head -50 "$REQ_FILE" | tail -40)"
  fi

  # Create the issue
  gh issue create \
    --title "[DEV] ${FEATURE_NAME}" \
    --label "phase:dev" \
    --label "parent-epic:${EPIC_ISSUE}" \
    --label "wave:${WAVE_NUM}" \
    --label "ready" \
    --body "$ISSUE_BODY"
done

# After creating ALL issues, post to epic
HEADER=$(avatar_header "Athena")
gh issue comment $EPIC_ISSUE --body "${HEADER}
## Wave ${WAVE_NUM} Started

### Issues Created
- #NEW1 - Database schema for users
- #NEW2 - User model and validation
- #NEW3 - Password hashing utilities

### Status
Wave ${WAVE_NUM} is now active. Issues have been assigned \`dev\` labels.

### Next Steps
Hephaestus will claim and develop these issues.
I will wait for Themis to notify when all issues reach release.

### My Role Until Then
**PASSIVE WAITING** - I will not intervene in individual threads."
```

### WAVE Completion Notification (from Themis)

When Themis promotes the LAST issue of a wave to release, it MUST post to the epic:

```markdown
## WAVE COMPLETION NOTIFICATION

### Wave
Wave 1 of Epic #123

### Status
ALL ISSUES COMPLETE

### Issues Released
| Issue | Title | Released At |
|-------|-------|-------------|
| #101 | Database schema | 2025-01-15 |
| #102 | User model | 2025-01-16 |
| #103 | Password hashing | 2025-01-16 |

### Next Action
Athena: Begin planning WAVE 2 (write requirements design files)
```

### Athena's Response to WAVE Completion

When Athena receives a wave completion notification:

```bash
EPIC_ISSUE=123
COMPLETED_WAVE=1
NEXT_WAVE=2

# Post wave completion acknowledgment
HEADER=$(avatar_header "Athena")
gh issue comment $EPIC_ISSUE --body "${HEADER}
## Wave ${COMPLETED_WAVE} Complete

All issues in Wave ${COMPLETED_WAVE} have reached release status.

### Now Planning Wave ${NEXT_WAVE}
Writing requirements design files for the next batch of issues...

### Wave ${NEXT_WAVE} Requirements (In Progress)
- [ ] Login endpoint - writing requirements...
- [ ] Logout endpoint - writing requirements...
- [ ] Session management - writing requirements...

### Status
**PLANNING PHASE** - Will start Wave ${NEXT_WAVE} when all requirements are finalized."
```
