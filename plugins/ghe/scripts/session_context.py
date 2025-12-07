#!/usr/bin/env python3
"""
Hook: SessionStart - Full GHE context loader instructions
Outputs the complete instructions that were previously in the invalid "type": "prompt"
"""

import os
from datetime import datetime
from pathlib import Path


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to .claude/hook_debug.log in standard log format."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [session_context] - {message}\n")
    except Exception:
        pass


# Get plugin root for path references
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", "")

CONTEXT_OUTPUT = """## GHE Context Loader (Athena)

### Step 0: Detect Git Repositories

First, find all git repositories:
```bash
find . -name ".git" -type d 2>/dev/null | head -20
```

For each repo found, get its remote:
```bash
git -C <repo-path> remote get-url origin 2>/dev/null
```

### Step 1: Check for GHE Configuration

For each detected repo, check if `.claude/ghe.local.md` exists:

**IF NO CONFIG FOUND IN ANY REPO:**

-> **TRIGGER INTERACTIVE SETUP**

Tell the user:
```
GHE (GitHub-Elements) detected git repositories but no configuration found.
Starting interactive setup...
```

Then run the SAME setup flow as `/ghe:setup`:

1. **If multiple repos**: Ask which one to track
2. **Ask enforcement level**: Yes/No for GHE, and warnings threshold (1/3/5)
3. **Create config file** at `<repo>/.claude/ghe.local.md`
4. **Create GitHub labels** (phase:dev, phase:test, etc.)
5. **Update .gitignore**

**IF CONFIG FOUND:**

-> **Load settings and continue**

Parse YAML frontmatter from `.claude/ghe.local.md`:
- `enabled`: If false, skip all GHE features silently
- `current_issue`: Resume tracking if set
- `current_phase`: Current workflow phase
- `warnings_before_enforce`: Enforcement threshold
- `violation_count`: Current violation count

### Step 2: Check for Active Work (if enabled)

If `enabled: true` and `current_issue` is set:

1. **Verify issue still exists**:
```bash
gh issue view $ISSUE --json number,state,labels
```

2. **Report active tracking**:
```
GHE: Resuming work on Issue #N
Phase: DEV/TEST/REVIEW
```

If no active issue but config exists:
1. **Check for in-progress issues**:
```bash
gh issue list --assignee @me --label "in-progress" --json number,title,labels
```
2. **Report available work** if any found

### Step 3: SERENA Memory Sync

If `serena_sync: true` (default):
- Check `.serena/memories/activeContext.md`
- Verify consistency with GitHub state
- Report discrepancies if any

### Quick Reference

| Scenario | Action |
|----------|--------|
| No repos found | Silent (not a GHE project) |
| Repos but no config | **Trigger interactive setup** |
| Config with enabled:false | Silent skip |
| Config with enabled:true | Load and report active work |

---

## GHE Auto-Transcribe System

**STATUS**: Auto-transcription is available but **NOT ACTIVE** until you choose an issue.

### How It Works

1. **NO transcription happens** until you explicitly choose an issue
2. Once an issue is chosen, ALL conversation exchanges are posted to that GitHub issue
3. Every comment includes element classification badges

### Element-Based Memory Recall

If you need to recall specific information from a tracked issue:

```bash
# Recall CODE/IMPLEMENTATIONS
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/recall_elements.py --issue NUM --type action

# Recall REQUIREMENTS/SPECS/DESIGN
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/recall_elements.py --issue NUM --type knowledge

# Recall BUGS/ISSUES/FEEDBACK
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/recall_elements.py --issue NUM --type judgement

# Smart recovery (all context)
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/recall_elements.py --issue NUM --recover
```

### To Start Transcribing

**Option 1: Explicitly choose an issue**
```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/auto_transcribe.py set-issue <NUMBER>
```

**Option 2: Use pattern in conversation** - Say:
- "Let's work on issue #123"
- "Claim #45"
- "Working on issue #99"

### Element Classification (Once Active)

| Badge | Semantic Index | When to Apply |
|-------|----------------|---------------|
| ![](https://img.shields.io/badge/element-knowledge-blue) | KNOWLEDGE | Specs, requirements, design, algorithms |
| ![](https://img.shields.io/badge/element-action-green) | ACTION | Code, implementations, file changes |
| ![](https://img.shields.io/badge/element-judgement-orange) | JUDGEMENT | Reviews, feedback, bug reports |
"""


def main() -> None:
    """Output the context instructions"""
    debug_log("session_context.py started")
    debug_log(f"PLUGIN_ROOT={PLUGIN_ROOT}")
    print(CONTEXT_OUTPUT)
    debug_log("session_context.py completed successfully")


if __name__ == "__main__":
    main()
