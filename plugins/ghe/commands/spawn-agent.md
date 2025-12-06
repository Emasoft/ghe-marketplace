---
description: "Spawn a background Claude agent in a new Terminal window (macOS only)"
arguments:
  - name: task
    description: "The task for the background agent to perform"
    required: true
  - name: output_file
    description: "Where to save the result (default: GHE_REPORTS/<TIMESTAMP>_task_result_(Agent).md)"
    required: false
---

# GHE Background Agent Spawner

Spawn a Claude agent in a background Terminal window. The agent works autonomously while you continue chatting.

## Task

**Task:** $ARGUMENTS.task
**Output:** ${ARGUMENTS.output_file:-GHE_REPORTS/$(TZ='Australia/Brisbane' date +%Y%m%d%H%M%S%Z)_task_result_(Agent).md}

## Instructions

Run the spawn script:

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_background.sh" \
  "Please complete this task and save the result to ${ARGUMENTS.output_file:-GHE_REPORTS/\$(TZ='Australia/Brisbane' date +%Y%m%d%H%M%S%Z)_task_result_(Agent).md}: $ARGUMENTS.task" \
  "$(pwd)"
```

## Features

- **Background execution**: Terminal opens but returns focus to your current app
- **Auto-approval**: PreToolUse hook auto-approves safe operations (no --dangerously-skip-permissions needed)
- **Security**: Writes blocked outside project, dangerous commands denied
- **macOS only**: Uses Terminal.app and AppleScript

## Security Model

| Operation | Decision |
|-----------|----------|
| Read, Glob, Grep, LS | ALLOW |
| Write/Edit within project | ALLOW |
| Write/Edit outside project | DENY |
| Bash (git, npm, python) | ALLOW |
| Bash (sudo, rm -rf /) | DENY |
| MCP tools | ALLOW |
| Unknown | ASK user |
