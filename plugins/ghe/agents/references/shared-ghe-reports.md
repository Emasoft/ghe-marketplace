# GHE Reports Rule

## Mandatory Dual-Location Posting

**ALL reports MUST be posted to BOTH locations:**

1. **GitHub Issue Thread** - Full report text (NOT just a link!)
2. **GHE_REPORTS/** - Same full report text (FLAT structure, no subfolders!)

## Report Naming Convention

**Format:** `<TIMESTAMP>_<title or description>_(<AGENT>).md`

**Timestamp format:** `YYYYMMDDHHMMSSTimezone`

**Examples:**
- `20251206160000GMT+01_issue_42_review_complete_(Hera).md`
- `20251206143000GMT+01_issue_15_test_results_(Artemis).md`
- `20251206120000GMT+01_epic_10_checkpoint_(Athena).md`

## Agent Report Authors

All 11 GHE agents write to GHE_REPORTS/:

| Agent | Display Name | Report Types |
|-------|--------------|--------------|
| ghe:github-elements-orchestrator | Athena | Epic checkpoints, coordination reports |
| ghe:dev-thread-manager | Hephaestus | DEV progress, implementation reports |
| ghe:test-thread-manager | Artemis | TEST results, coverage reports |
| ghe:review-thread-manager | Hera | REVIEW verdicts, quality assessments |
| ghe:phase-gate | Themis | Phase transition validations |
| ghe:memory-sync | Mnemosyne | Memory synchronization logs |
| ghe:reporter | Hermes | Status reports, metrics |
| ghe:enforcement | Ares | Violation reports, enforcement actions |
| ghe:ci-issue-opener | Chronos | CI failure reports |
| ghe:pr-checker | Cerberus | PR validation reports |

## REQUIREMENTS/ is SEPARATE

`REQUIREMENTS/` contains permanent design documents and is **never deleted**.

Only `GHE_REPORTS/` contains transient reports that may be cleaned up.

## Deletion Policy

**DELETE ONLY when user EXPLICITLY orders deletion due to space constraints.**

DO NOT delete reports during normal cleanup operations.

## Python Example

```python
#!/usr/bin/env python3
"""Example: Saving a report to GHE_REPORTS."""
import os
from datetime import datetime, timezone
from pathlib import Path

def save_report(issue_num: int, agent_name: str, report_content: str, description: str) -> str:
    """Save report to GHE_REPORTS folder."""
    # Create timestamp
    now = datetime.now(timezone.utc)
    timestamp = now.strftime('%Y%m%d%H%M%S') + 'UTC'

    # Create filename
    filename = f"{timestamp}_issue_{issue_num}_{description}_({agent_name}).md"

    # Ensure directory exists
    reports_dir = Path('GHE_REPORTS')
    reports_dir.mkdir(exist_ok=True)

    # Write report
    report_path = reports_dir / filename
    report_path.write_text(report_content)

    return str(report_path)

# Usage
report_path = save_report(
    issue_num=42,
    agent_name="Hera",
    report_content="# Review Complete\n\n## Verdict: PASS\n...",
    description="review_complete"
)
print(f"Report saved to: {report_path}")
```

## Bash Example

```bash
# Save report to GHE_REPORTS
ISSUE_NUM=42
AGENT="Hera"
TIMESTAMP=$(date -u +%Y%m%d%H%M%S)UTC
DESCRIPTION="review_complete"

REPORT_FILE="GHE_REPORTS/${TIMESTAMP}_issue_${ISSUE_NUM}_${DESCRIPTION}_(${AGENT}).md"

mkdir -p GHE_REPORTS
cat > "$REPORT_FILE" << 'EOF'
# Review Complete

## Verdict: PASS

...report content...
EOF

echo "Report saved to: $REPORT_FILE"
```
