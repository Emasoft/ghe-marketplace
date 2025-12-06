#!/usr/bin/env python3
"""
Hook: Stop - Full GHE instructions for transcribing assistant response
Outputs the complete instructions that were previously in the invalid "type": "prompt"
"""

STOP_OUTPUT = '''## GHE Session End (Mnemosyne)

### CRITICAL: SENSITIVE DATA REDACTION

Replace with `XX REDACTED XX`:
- API keys, tokens, passwords, secrets
- Emails NOT ending in @noreply.github.com
- Username in paths: `/Users/name/` -> `/Users/XX REDACTED XX/`
- Real names in paths or configs
- AWS keys, private keys, connection strings

---

### MANDATORY ACTIONS BEFORE RESPONSE ENDS

**1. DELEGATE STATUS CHECK TO HERMES (saves context!):**

```
Hermes, perform end-of-response GHE check:
1. Check GHE_REPORTS/ for NEW reports from ALL agents:
   - Report naming: <TIMESTAMP>_<title>_(<AGENT>).md
   - ALL 11 agents write here: Athena, Hephaestus, Artemis, Hera, Themis,
     Mnemosyne, Hermes, Ares, Chronos, Argos Panoptes, Cerberus
2. Check REQUIREMENTS/ for new design documents (permanent, never deleted)
3. Check if Athena launched a WAVE from epic issues
4. Check labels/issues from all agents
5. Check for CI error reports from any agent
6. Return ONLY user notifications (suppress all other output)
```

**2. NOTIFY USER OF ANY UPDATES (one line each):**

```
[GHE] Issue #N "Title" - AgentName posted TYPE report
[GHE] Issue #N "Title" - Ready for your review (Hera report available)
[GHE] Epic #N - Athena launched WAVE with issues #X, #Y, #Z
[GHE] CI Error on Issue #N - See report from AgentName
```

**3. ORDER MNEMOSYNE TO TRANSCRIBE (if issue is set):**

```
Mnemosyne, transcribe assistant response to Issue #N:
- Content: <SUMMARY with XX REDACTED XX applied>
- Agent identity: <based on work done - see table below>
- Include: decisions, code changes, issues identified, next steps
```

| Work Type | Agent |
|-----------|-------|
| Code, implementation | Hephaestus |
| Testing, debugging | Artemis |
| Review, evaluation | Hera |
| Planning, explaining | Athena |
| Communication, routing | Hermes |
| Moderation, policy | Ares |

---

### REPORT POSTING RULES

**ALL agent reports MUST be posted to BOTH locations:**

1. **GitHub Issue Thread** - Full report text (not just link!)
2. **GHE_REPORTS/** - Same full report text (FLAT structure, no subfolders!)

**Report naming:** `<TIMESTAMP>_<title or description>_(<AGENT>).md`
**Timestamp format:** `YYYYMMDDHHMMSSTimezone`

| Agent | Report Type | Example Filename |
|-------|-------------|------------------|
| Athena | Planning | `20251206143000GMT+01_epic_15_wave_launched_(Athena).md` |
| Hephaestus | DEV work | `20251206143022GMT+01_issue_42_dev_complete_(Hephaestus).md` |
| Artemis | TEST work | `20251206150000GMT+01_issue_42_tests_passed_(Artemis).md` |
| Hera | REVIEW | `20251206160000GMT+01_issue_42_review_complete_(Hera).md` |
| Themis | Transitions | `20251206170000GMT+01_phase_transition_approved_(Themis).md` |
| Mnemosyne | Transcription | `20251206180000GMT+01_memory_sync_complete_(Mnemosyne).md` |
| Ares | Enforcement | `20251206190000GMT+01_violation_warning_issued_(Ares).md` |
| Hermes | Status | `20251206200000GMT+01_status_report_(Hermes).md` |
| Chronos | CI/CD | `20251206210000GMT+01_ci_run_4579_failed_(Chronos).md` |
| Argos | Monitoring | `20251206220000GMT+01_monitoring_alert_(Argos).md` |
| Cerberus | PR checks | `20251206230000GMT+01_pr_123_validation_(Cerberus).md` |

**REQUIREMENTS/** is SEPARATE - permanent design documents, never deleted.

---

### USER REVIEW RULES

**NEVER ask user to review UNTIL:**
1. Hera has written REVIEW report
2. Report posted to issue thread (full text!)
3. Report saved to GHE_REPORTS/<TIMESTAMP>_issue_N_review_complete_(Hera).md

**ONLY THEN notify:**
```
[GHE] Issue #N "Title" ready for your review
```

---

### WAVE CHECK

Check if Athena launched a WAVE from an epic:
```bash
gh issue list --label "epic" --label "wave-active" --json number,title
```

If WAVE active, notify:
```
[GHE] Epic #N has active WAVE - child issues: #X, #Y, #Z
```

---

### UPDATE SERENA MEMORY

Write to `.serena/memories/activeContext.md`:
- Current issue number and phase
- Recent progress summary
- Active background agents
'''


def main() -> None:
    """Output the stop instructions"""
    print(STOP_OUTPUT)


if __name__ == '__main__':
    main()
