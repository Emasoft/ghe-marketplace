# Element-Based Memory Recall System

**Version**: 0.3.0 (planned)
**Status**: Design Document

---

## Core Insight

The three element badges are not decorative - they form a **semantic triple-store indexing system** for memory recall:

```
┌───────────────────────────────────────────────────────────────────────────────────┐
│                          ELEMENT CLASSIFICATION SYSTEM                            │
├───────────────────────────────────────────────────────────────────────────────────┤
│                                                                                   │
│  ┌───────────────────┐   ┌───────────────────┐   ┌───────────────────┐           │
│  │    KNOWLEDGE      │   │      ACTION       │   │     JUDGEMENT     │           │
│  │    (blue)         │   │     (green)       │   │     (orange)      │           │
│  │    "The Talk"     │   │   "The Reality"   │   │   "The Verdict"   │           │
│  ├───────────────────┤   ├───────────────────┤   ├───────────────────┤           │
│  │ - Requirements    │   │ CODE:             │   │ - Bug reports     │           │
│  │ - Specs           │   │  - Functions      │   │ - Reviews         │           │
│  │ - Design docs     │   │  - Classes        │   │ - Test results    │           │
│  │ - Architecture    │   │  - Scripts        │   │ - Feedback        │           │
│  │ - Algorithms      │   │  - Configs        │   │ - Verdicts        │           │
│  │ - Explanations    │   │                   │   │ - Critiques       │           │
│  │ - Protocols       │   │ ASSETS:           │   │ - Issues found    │           │
│  │ - Definitions     │   │  - Images/Sprites │   │ - Concerns        │           │
│  │ - Theory          │   │  - Icons/Graphics │   │ - Questions       │           │
│  │                   │   │  - Audio/Sound FX │   │                   │           │
│  │ (Plans/Ideas)     │   │  - Video/Animation│   │ (Evaluation)      │           │
│  │                   │   │  - 3D Models      │   │                   │           │
│  │                   │   │  - Stylesheets    │   │                   │           │
│  │                   │   │  - Fonts          │   │                   │           │
│  │                   │   │                   │   │                   │           │
│  │                   │   │ (Tangible Change) │   │                   │           │
│  └───────────────────┘   └───────────────────┘   └───────────────────┘           │
│                                                                                   │
│  KEY INSIGHT: Only ACTION elements change the project. KNOWLEDGE and JUDGEMENT   │
│  are discussion/evaluation - they inform but don't alter artifacts.              │
│                                                                                   │
│  Badge Format (searchable, no alt text):                                          │
│  ![](https://img.shields.io/badge/element-knowledge-blue)                         │
│  ![](https://img.shields.io/badge/element-action-green)                           │
│  ![](https://img.shields.io/badge/element-judgement-orange)                       │
│                                                                                   │
└───────────────────────────────────────────────────────────────────────────────────┘
```

---

## Recall Query Mapping

### Primary Recall Scenarios

| What User Wants to Recall | Element Type | Search Pattern |
|---------------------------|--------------|----------------|
| "What code did we write?" | **ACTION** | `element-action` |
| "What assets were created?" | **ACTION** | `element-action` |
| "What images/sprites were added?" | **ACTION** | `element-action` |
| "Show the new icons/graphics" | **ACTION** | `element-action` |
| "What files changed?" | **ACTION** | `element-action` |
| "Show me the implementation" | **ACTION** | `element-action` |
| "What were the requirements?" | **KNOWLEDGE** | `element-knowledge` |
| "What was the design?" | **KNOWLEDGE** | `element-knowledge` |
| "What bugs did we find?" | **JUDGEMENT** | `element-judgement` |
| "What issues/problems exist?" | **JUDGEMENT** | `element-judgement` |
| "What tests failed?" | **JUDGEMENT** | `element-judgement` |
| "What feedback was given?" | **JUDGEMENT** | `element-judgement` |
| "What decisions were made?" | **KNOWLEDGE** + **JUDGEMENT** | Both |

### Element Semantics

| Element | Nature | Examples |
|---------|--------|----------|
| **KNOWLEDGE** | "The Talk" - Plans, ideas, theory | Requirements, specs, architecture docs, algorithms |
| **ACTION** | "The Reality" - Tangible changes | Code, assets, images, sounds, video, configs, stylesheets |
| **JUDGEMENT** | "The Verdict" - Evaluation | Bug reports, reviews, test failures, critiques, feedback |

**Key Insight**: Only ACTION elements actually change the project. In a video game project, 90% of ACTION elements might be asset uploads (sprites, 3D models, sounds) rather than code.

### Compound Queries

| Complex Query | Element Combination | Logic |
|--------------|---------------------|-------|
| "What code fixed the bug?" | ACTION + JUDGEMENT | Action that mentions fix |
| "Requirements with issues" | KNOWLEDGE + JUDGEMENT | Both badges present |
| "Explained implementations" | KNOWLEDGE + ACTION | Both badges present |
| "Full context for feature X" | ALL THREE | Sequential from all types |

---

## Query Implementation

### Badge Detection Patterns

```bash
# Search patterns for each element type
PATTERN_KNOWLEDGE="element-knowledge"
PATTERN_ACTION="element-action"
PATTERN_JUDGEMENT="element-judgement"

# Regex for badge detection in comment body
BADGE_REGEX="element-(knowledge|action|judgement)"
```

### JQ Filters for Element-Based Recall

```bash
# Get all KNOWLEDGE elements from issue
gh issue view $ISSUE --comments --json comments --jq '
  .comments[] |
  select(.body | contains("element-knowledge")) |
  {
    author: .author.login,
    date: .createdAt,
    body: .body
  }
'

# Get all ACTION elements from issue
gh issue view $ISSUE --comments --json comments --jq '
  .comments[] |
  select(.body | contains("element-action")) |
  {
    author: .author.login,
    date: .createdAt,
    body: .body
  }
'

# Get all JUDGEMENT elements from issue
gh issue view $ISSUE --comments --json comments --jq '
  .comments[] |
  select(.body | contains("element-judgement")) |
  {
    author: .author.login,
    date: .createdAt,
    body: .body
  }
'

# Get LAST element of each type (most recent)
gh issue view $ISSUE --comments --json comments --jq '
  {
    last_knowledge: [.comments[] | select(.body | contains("element-knowledge"))] | last,
    last_action: [.comments[] | select(.body | contains("element-action"))] | last,
    last_judgement: [.comments[] | select(.body | contains("element-judgement"))] | last
  }
'

# Get elements with MULTIPLE badges (compound elements)
gh issue view $ISSUE --comments --json comments --jq '
  .comments[] |
  select(
    (.body | contains("element-knowledge")) and
    (.body | contains("element-action"))
  )
'

# Count elements by type
gh issue view $ISSUE --comments --json comments --jq '
  {
    knowledge: [.comments[] | select(.body | contains("element-knowledge"))] | length,
    action: [.comments[] | select(.body | contains("element-action"))] | length,
    judgement: [.comments[] | select(.body | contains("element-judgement"))] | length
  }
'
```

---

## Recall Protocol

### Phase 1: Discover Available Elements

Before recall, understand what's stored:

```bash
ISSUE=201

# Get element distribution
STATS=$(gh issue view $ISSUE --comments --json comments --jq '
  {
    total: .comments | length,
    knowledge: [.comments[] | select(.body | contains("element-knowledge"))] | length,
    action: [.comments[] | select(.body | contains("element-action"))] | length,
    judgement: [.comments[] | select(.body | contains("element-judgement"))] | length
  }
')

echo "Issue #$ISSUE Memory Statistics:"
echo "$STATS" | jq '.'

# Output:
# {
#   "total": 45,
#   "knowledge": 12,
#   "action": 28,
#   "judgement": 15
# }
```

### Phase 2: Targeted Recall by Intent

#### Recall Pattern A: "What were we building?"

```bash
# Get KNOWLEDGE elements (requirements, design, specs)
gh issue view $ISSUE --comments --json comments --jq '
  [.comments[] | select(.body | contains("element-knowledge"))] |
  sort_by(.createdAt) |
  .[] |
  "[\(.createdAt | split("T")[0])] \(.body | split("\n")[0:5] | join(" "))"
'
```

#### Recall Pattern B: "What code did we write?"

```bash
# Get ACTION elements (code, implementations)
gh issue view $ISSUE --comments --json comments --jq '
  [.comments[] | select(.body | contains("element-action"))] |
  sort_by(.createdAt) |
  .[-5:] |  # Last 5 action elements
  .[] |
  {
    date: .createdAt,
    preview: (.body | split("\n")[0:10] | join("\n"))
  }
'
```

#### Recall Pattern C: "What problems did we encounter?"

```bash
# Get JUDGEMENT elements (bugs, issues, feedback)
gh issue view $ISSUE --comments --json comments --jq '
  [.comments[] | select(.body | contains("element-judgement"))] |
  sort_by(.createdAt) |
  .[] |
  {
    date: .createdAt,
    preview: (.body | split("\n")[0:5] | join("\n"))
  }
'
```

### Phase 3: Contextual Recovery

For full session recovery, retrieve elements in logical order:

```bash
ISSUE=201

# 1. First, get KNOWLEDGE (what were we trying to do?)
echo "=== KNOWLEDGE: Requirements & Design ==="
gh issue view $ISSUE --comments --json comments --jq '
  [.comments[] | select(.body | contains("element-knowledge"))] |
  first |
  .body
' | head -50

# 2. Then, get last ACTION (what did we do?)
echo ""
echo "=== LAST ACTION: Most Recent Work ==="
gh issue view $ISSUE --comments --json comments --jq '
  [.comments[] | select(.body | contains("element-action"))] |
  last |
  .body
'

# 3. Finally, get JUDGEMENT (what issues remain?)
echo ""
echo "=== RECENT JUDGEMENTS: Open Issues ==="
gh issue view $ISSUE --comments --json comments --jq '
  [.comments[] | select(.body | contains("element-judgement"))] |
  .[-3:] |
  .[] |
  .body
'
```

---

## Recall Decision Tree

```
USER ASKS TO RECALL SOMETHING
           │
           ▼
┌─────────────────────────────────────────────────────┐
│ CLASSIFY THE RECALL REQUEST                         │
├─────────────────────────────────────────────────────┤
│                                                     │
│  "code" "implementation" "changes" "wrote"          │
│       │                                             │
│       └──► Search ACTION elements                   │
│                                                     │
│  "requirements" "design" "specs" "architecture"     │
│       │                                             │
│       └──► Search KNOWLEDGE elements                │
│                                                     │
│  "bugs" "issues" "problems" "failed" "feedback"     │
│       │                                             │
│       └──► Search JUDGEMENT elements                │
│                                                     │
│  "everything" "full context" "where we left off"    │
│       │                                             │
│       └──► Search ALL elements, chronological       │
│                                                     │
│  "last checkpoint" "current state"                  │
│       │                                             │
│       └──► Search for "State Snapshot" pattern      │
│                                                     │
└─────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│ OPTIMIZE RETRIEVAL                                  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Short thread (< 20 comments)?                      │
│       └──► Fetch all matching elements              │
│                                                     │
│  Long thread (20-100 comments)?                     │
│       └──► Fetch last N matching elements           │
│                                                     │
│  Very long thread (> 100 comments)?                 │
│       └──► Fetch only most recent of each type      │
│           + count totals for context                │
│                                                     │
└─────────────────────────────────────────────────────┘
           │
           ▼
┌─────────────────────────────────────────────────────┐
│ FORMAT RECALL OUTPUT                                │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ## Memory Recall: Issue #N                         │
│                                                     │
│  ### Element Distribution                           │
│  - Knowledge: X elements                            │
│  - Action: Y elements                               │
│  - Judgement: Z elements                            │
│                                                     │
│  ### Requested: [ELEMENT TYPE]                      │
│  [Content of matching elements]                     │
│                                                     │
│  ### Recommended Next Action                        │
│  [Based on last elements of each type]              │
│                                                     │
└─────────────────────────────────────────────────────┘
```

---

## Smart Recall Heuristics

### Heuristic 1: First KNOWLEDGE Sets Context

The FIRST knowledge element in a thread typically contains:
- Original requirements
- Problem statement
- Acceptance criteria

**Always show this when doing full recovery.**

### Heuristic 2: Last ACTION Shows Current State

The LAST action element shows:
- Most recent code changes
- Latest implementation state
- Files currently modified

**This is the "resume point" for development work.**

### Heuristic 3: Recent JUDGEMENT Shows Open Issues

JUDGEMENT elements from the last 24-48 hours likely contain:
- Unresolved bugs
- Pending feedback
- Test failures needing attention

**These are blockers that need addressing.**

### Heuristic 4: Multi-Badge Elements Are Key

Comments with MULTIPLE badges are often:
- Implementation of requirements (KNOWLEDGE + ACTION)
- Bug fixes (ACTION + JUDGEMENT)
- Design decisions (KNOWLEDGE + JUDGEMENT)

**These are high-signal elements worth retrieving.**

---

## Recall Script Interface

### Proposed CLI

```bash
# recall-elements.sh - Element-based memory recall

# Get all elements of a type
recall-elements.sh --issue 201 --type knowledge
recall-elements.sh --issue 201 --type action
recall-elements.sh --issue 201 --type judgement

# Get last N elements of a type
recall-elements.sh --issue 201 --type action --last 5

# Get element statistics
recall-elements.sh --issue 201 --stats

# Get smart recovery summary
recall-elements.sh --issue 201 --recover

# Search within elements
recall-elements.sh --issue 201 --type action --search "jwt"

# Get compound elements (multiple badges)
recall-elements.sh --issue 201 --compound "knowledge+action"
```

### Recovery Output Format

```markdown
## GHE Memory Recovery: Issue #201

### Thread Statistics
| Element Type | Count | Last Updated |
|--------------|-------|--------------|
| Knowledge    | 12    | 2h ago       |
| Action       | 28    | 30m ago      |
| Judgement    | 15    | 1h ago       |

### Original Context (First Knowledge)
[First knowledge element - requirements/specs]

### Current State (Last Action)
[Last action element - most recent work]

### Open Issues (Recent Judgements)
[Last 3 judgement elements - bugs/feedback]

### Recommended Next Action
Based on the last checkpoint, you should:
1. [Derived from last action element]
2. [Derived from unresolved judgements]
```

---

## Integration with SessionStart

### Updated Recovery Flow

```
SessionStart Hook
       │
       ▼
┌──────────────────────────────────────────────┐
│ 1. Check if current_issue is set             │
│    └── If not: Show "No active issue"        │
│                                              │
│ 2. Get element statistics                    │
│    └── Count KNOWLEDGE, ACTION, JUDGEMENT    │
│                                              │
│ 3. Smart Summary Generation                  │
│    a. First KNOWLEDGE → Original context     │
│    b. Last ACTION → Current state            │
│    c. Recent JUDGEMENT → Open issues         │
│                                              │
│ 4. Display Recovery Summary                  │
│    └── Structured format for immediate use   │
│                                              │
│ 5. Set TodoWrite from last checkpoint        │
│    └── Completed/InProgress/Pending items    │
└──────────────────────────────────────────────┘
```

---

## Element Lifecycle

```
NEW CONVERSATION EXCHANGE
          │
          ▼
    classify_element()
          │
          ├── Detect KNOWLEDGE patterns
          │   (spec, requirement, design, algorithm, api, schema...)
          │
          ├── Detect ACTION patterns
          │   (```, diff, function, class, def, .py, .js, create...)
          │
          └── Detect JUDGEMENT patterns
              (bug, error, issue, problem, fail, review, feedback...)
          │
          ▼
    BADGES ASSIGNED (one or more)
          │
          ▼
    POST TO GITHUB ISSUE
          │
          ▼
    ELEMENT IS NOW SEARCHABLE
          │
          ├── By element type (badge)
          ├── By date (createdAt)
          ├── By author (agent name)
          └── By content (full text)
```

---

## Advantages of Element-Based Recall

| Without Element Types | With Element Types |
|----------------------|-------------------|
| Scan all comments | Query specific types |
| Read everything | Read only relevant |
| Manual filtering | Automatic filtering |
| Context overflow | Targeted retrieval |
| Linear search | Indexed search |
| "Find the code" manually | `--type action` |
| "Find the bugs" manually | `--type judgement` |

---

## Implementation Priority

### Phase 1: recall-elements.sh (HIGH)
Create the CLI tool for element-based queries.

### Phase 2: SessionStart Integration (HIGH)
Update hooks to auto-run element-aware recovery.

### Phase 3: Smart Summarization (MEDIUM)
Add heuristics for automatic context building.

### Phase 4: SERENA Integration (LOW)
Sync element types to SERENA memory bank.

---

## Example Recall Session

```
USER: "What bugs did we find in the JWT implementation?"

CLAUDE (internally):
1. Parse intent → JUDGEMENT elements
2. Parse topic → "JWT"
3. Query:
   gh issue view 201 --comments --json comments --jq '
     [.comments[] |
      select(.body | contains("element-judgement")) |
      select(.body | ascii_downcase | contains("jwt"))]
   '

OUTPUT:
## Recalled Judgement Elements (JWT-related)

### Found 3 matching elements:

**[2025-01-15 10:00]** Hera
> Bug: JWT expiry check has off-by-one error
> Location: src/auth/jwt.service.ts:87
> Status: Fixed in commit xyz789

**[2025-01-15 11:30]** Artemis
> Test failure: test_token_blacklist
> Error: Missing await on async call
> Status: UNRESOLVED

**[2025-01-15 14:00]** Hera
> Review finding: No test for malformed JWT
> Recommendation: Add boundary test cases
> Status: Needs DEV attention

### Summary
- 1 bug fixed
- 1 test failure unresolved
- 1 coverage gap identified
```

---

*This document defines the element-based recall system for GHE v0.3.0*
