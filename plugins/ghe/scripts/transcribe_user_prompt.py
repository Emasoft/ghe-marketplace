#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Hook: UserPromptSubmit - Full GHE instructions for processing user messages
Outputs the complete instructions that were previously in the invalid "type": "prompt"
"""

from datetime import datetime
from pathlib import Path


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to .claude/hook_debug.log in standard log format."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [transcribe_user_prompt] - {message}\n")
    except Exception:
        pass


USER_PROMPT_OUTPUT = """## GHE Issue Tracker (Mnemosyne)

### CRITICAL: SENSITIVE DATA REDACTION

**BEFORE posting ANY content to GitHub, you MUST redact sensitive data!**

Replace the following with `XX REDACTED XX`:

| Type | Pattern |
|------|---------|
| **API Keys** | `sk-...`, `api_key=...`, `apikey:...`, `ghp_...`, `gho_...` |
| **Tokens** | `token=...`, `bearer ...`, any JWT |
| **Passwords** | `password=...`, `passwd:...`, `pwd=...`, `secret=...` |
| **Emails** | ALL emails EXCEPT those ending in `@noreply.github.com` |
| **User Paths** | `/Users/<name>/` -> `/Users/XX REDACTED XX/` |
| **User Paths** | `/home/<name>/` -> `/home/XX REDACTED XX/` |
| **User Paths** | `C:\\Users\\<name>\\` -> `C:\\Users\\XX REDACTED XX\\` |
| **AWS Keys** | `AKIA...`, `aws_access_key_id` |
| **Private Keys** | `-----BEGIN ... PRIVATE KEY-----` -> `[PRIVATE KEY XX REDACTED XX]` |
| **Connection Strings** | Credentials in `mongodb://`, `postgres://`, `mysql://` |

**Keep code structure intact** - only replace sensitive VALUES.

---

### MANDATORY ACTIONS (Delegate to Hermes!)

**To save context tokens, delegate ALL these checks to Hermes agent:**

```
Hermes, perform GHE status check:
1. Check GHE_REPORTS/ for NEW reports from ALL agents:
   - Athena (planning), Hephaestus (DEV), Artemis (TEST), Hera (REVIEW)
   - Themis (transitions), Mnemosyne (transcription), Hermes (status)
   - Ares (enforcement), Chronos (CI/CD), Argos Panoptes (monitoring), Cerberus (PR checks)
   Report naming: <TIMESTAMP>_<title or description>_(<AGENT>).md
   Timestamp format: YYYYMMDDHHMMSSTimezone
   FLAT structure - no subfolders!
2. Check if Athena launched a WAVE from any epic issue
3. Check if any agent added labels or opened/closed issues
4. Check for CI error reports
5. Report back ONLY notifications for the user (issue #, title, agent name)
```

**After Hermes reports back, notify user of any updates (one line each):**
```
[GHE] Issue #N "Title" - AgentName posted TYPE report
```

---

### TRANSCRIPTION (Order Mnemosyne!)

**IF an issue is set for transcription:**

Order Mnemosyne to post the user's message:
```
Mnemosyne, transcribe to Issue #N:
- Content: <EXACT user message with XX REDACTED XX applied>
- Element type: Classify as KNOWLEDGE/ACTION/JUDGEMENT
- Post as: User avatar with GitHub username
```

---

### TRIGGER DETECTION

**NEW ISSUE triggers** (create new):
- "lets work on this new issue" / "create a new issue"
- "open an issue" / "file an issue"
- Discussion moved to a completely new topic

**EXISTING ISSUE triggers** (extract number):
- "issue #123", "#123", "work on 123", "claim 123"
- GitHub URLs: `/issues/123`
- Context marker: `[Currently discussing issue n.123]`

**If trigger detected:**
1. For NEW: `gh issue create --title "TITLE" --body "BODY" --label "phase:dev"`
2. For EXISTING: `python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auto_transcribe.py set-issue NUMBER`

---

### DELEGATION CHECK (ALWAYS DELEGATE!)

**Check if task needs delegation:**
- Complex multi-step task -> Spawn background agent
- Code implementation -> Delegate to Hephaestus (background)
- Testing needed -> Delegate to Artemis (background)
- Review needed -> Delegate to Hera (background)
- Research/analysis -> Delegate to local Task agent

**NEVER do development work in main thread - ALWAYS delegate!**

```bash
# Spawn background agent
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/spawn_background.py "<task>" "$(pwd)"
```

---

### REQUIREMENTS CHECK (Order Athena!)

**If user discusses a new feature or change:**

Order Athena to write requirements:
```
Athena, write requirements for: <feature/change description>
- Create EARS-format requirements document
- Post to current issue thread (full text, not link!)
- Save to REQUIREMENTS/ folder (permanent design docs - NEVER deleted)
- Also save summary report to GHE_REPORTS/<TIMESTAMP>_requirements_<feature>_(Athena).md
```

---

### PHASE TRANSITION DETECTION

| Pattern | Action |
|---------|--------|
| "ready for testing" / "DEV complete" | Transition to TEST |
| "tests passed" / "ready for review" | Transition to REVIEW |
| "needs rework" / "back to DEV" | Demote to DEV |

---

### USER REVIEW NOTIFICATION

**CRITICAL**: Never ask user to review until Hera has:
1. Posted REVIEW report to issue thread (full text, not link!)
2. Saved report to GHE_REPORTS/<TIMESTAMP>_issue_N_review_complete_(Hera).md

Only THEN notify:
```
[GHE] Issue #N "Title" ready for your review - Hera posted REVIEW report
```

---

### REPORT POSTING RULES (CRITICAL!)

**ALL agent reports MUST be posted to BOTH locations:**

1. **GitHub Issue Thread** - Full report text (NOT just a link!)
2. **GHE_REPORTS/** - Same full report text (FLAT structure, no subfolders!)

**Report naming:** `<TIMESTAMP>_<title or description>_(<AGENT>).md`
**Timestamp format:** `YYYYMMDDHHMMSSTimezone`

**ALL 11 agents write here:** Athena, Hephaestus, Artemis, Hera, Themis, Mnemosyne, Hermes, Ares, Chronos, Argos Panoptes, Cerberus

**REQUIREMENTS/** is SEPARATE - permanent design documents, never deleted.
"""


def main() -> None:
    """Output the user prompt instructions"""
    debug_log("Hook triggered: transcribe_user_prompt starting")
    debug_log(f"Output length: {len(USER_PROMPT_OUTPUT)} chars")
    print(USER_PROMPT_OUTPUT)
    debug_log("Hook completed: transcribe_user_prompt finished")


if __name__ == "__main__":
    debug_log("Script invoked directly via __main__")
    main()
