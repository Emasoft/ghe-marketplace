# Avatar Banner Integration

## Overview

All GitHub issue/PR comments MUST include an avatar banner for visual identity. The `post_with_avatar.py` module provides functions to format and post comments with proper avatars.

## Agent Identities

| Agent | Display Name | Avatar |
|-------|--------------|--------|
| ghe:dev-thread-manager | Hephaestus | hephaestus.png |
| ghe:test-thread-manager | Artemis | artemis.png |
| ghe:review-thread-manager | Hera | hera.png |
| ghe:github-elements-orchestrator | Athena | athena.png |
| ghe:phase-gate | Themis | themis.png |
| ghe:memory-sync | Mnemosyne | mnemosyne.png |
| ghe:enforcement | Ares | ares.png |
| ghe:reporter | Hermes | hermes.png |
| ghe:ci-issue-opener | Chronos | chronos.png |
| ghe:pr-checker | Cerberus | cerberus.png |

## Usage in Python Scripts

```python
#!/usr/bin/env python3
"""Example script using avatar helpers."""
import sys
import os
sys.path.insert(0, os.environ.get('CLAUDE_PLUGIN_ROOT', '.') + '/scripts')

from post_with_avatar import post_issue_comment, format_comment

# Method 1: Simple post
post_issue_comment(42, "Hera", "Your message content here")

# Method 2: Format then post (for complex messages)
body = format_comment("Hera", """## Review Started

I am beginning the REVIEW evaluation.

### Scope
- Code quality
- Test coverage
- Security review
""")

# Post using gh CLI
import subprocess
subprocess.run(['gh', 'issue', 'comment', '42', '--body', body])
```

## CLI Usage

```bash
# Post a simple comment
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/post_with_avatar.py" \
    --issue 42 --agent "Hera" --body "Your message here"

# Test avatar URLs
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/post_with_avatar.py" --test
```

## Comment Format

All posts follow this structure:

```markdown
<img src="AVATAR_URL" width="77" align="left"/>

**AGENT_NAME said:**
<br><br>

[Your content here]
```

## Separator Usage

Only add `---` separator if the message includes:
- File links
- Citations
- References that need visual separation

```markdown
<img src="AVATAR_URL" width="77" align="left"/>

**Hera said:**
<br><br>

Here is my analysis of the issue.

---

**Files modified:**
- `src/main.py`
- `tests/test_main.py`
```

## Important Notes

1. **Empty line after avatar**: Always leave an empty line after the `<img>` tag
2. **`<br><br>` after name**: Always add double `<br><br>` after "**Name said:**"
3. **Avatar size**: Always use `width="77"` for consistency
4. **Alignment**: Always use `align="left"` for the avatar
