---
name: background-agents
description: This skill should be used when spawning Claude agents in background Terminal windows, running agents autonomously without blocking the conversation, delegating tasks to external Claude instances, or understanding how the auto-approval PreToolUse hook works. Triggers include "background agent", "spawn agent", "external claude", "autonomous agent", "parallel agent", "delegate to agent", or "run agent in background".
---

# Background Agents

## Overview

This skill enables spawning Claude Code agents in background Terminal windows that work autonomously while the main conversation continues. Background agents use a PreToolUse hook to auto-approve safe operations, eliminating the need for `--dangerously-skip-permissions`.

## Requirements

- **macOS only** (uses Terminal.app and AppleScript)
- **Claude Code CLI** installed
- **jq** for JSON parsing in hooks
- **GHE plugin** installed

## Quick Start

### Method 1: Slash Command

```
/ghe:spawn-agent "Write unit tests for src/utils.py"
```

### Method 2: Direct Script

```bash
bash "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_background.sh" \
  "Your task description here" \
  "$(pwd)"
```

### Method 3: Ask Claude

Request Claude to spawn an agent:

```
Spawn a background agent to refactor the database module
and save a report to agents_reports/refactor_report.md
```

## How It Works

### Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   Main Claude       │     │  Background Claude  │
│   (Interactive)     │     │  (Terminal Window)  │
├─────────────────────┤     ├─────────────────────┤
│ Chat continues here │────▶│ Agent works here    │
│ Spawns agents       │     │ Auto-approved ops   │
│ Receives reports    │◀────│ Writes results      │
└─────────────────────┘     └─────────────────────┘
                │
                ▼
       ┌─────────────────┐
       │  PreToolUse     │
       │  auto_approve   │
       │  Hook           │
       └─────────────────┘
```

### Components

| Component | Location | Purpose |
|-----------|----------|---------|
| spawn_background.sh | `scripts/` | Opens Terminal, starts Claude, sends prompt |
| auto_approve.sh | `scripts/` | PreToolUse hook for auto-approving safe operations |
| hooks.json | `hooks/` | Registers the hook with Claude Code |

### Spawn Process

1. Script opens new Terminal window (without stealing focus)
2. Runs `claude` command in project directory
3. Waits for Claude to initialize (~6 seconds)
4. Pastes the task prompt via clipboard
5. Returns focus to original application

## Auto-Approval Security Model

The PreToolUse hook makes permission decisions based on operation type and path safety. See `references/security-model.md` for the complete whitelist.

### Decision Summary

| Category | Decision | Examples |
|----------|----------|----------|
| Read-only tools | ALLOW | Read, Glob, Grep, LS, Task |
| Write within project | ALLOW | Write, Edit to project files |
| Write outside project | DENY | Write to /etc, /usr, ~ |
| Safe bash commands | ALLOW | git, python, npm, ruff |
| Dangerous commands | DENY | sudo, rm -rf / |
| Unknown | ASK | Prompts user |

## Spawning Multiple Agents

To run agents in parallel:

```bash
# Agent 1: Tests
bash "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_background.sh" \
  "Run pytest, report to agents_reports/tests.md" "$(pwd)" &

# Agent 2: Linting
bash "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_background.sh" \
  "Run linters, report to agents_reports/lint.md" "$(pwd)" &

# Agent 3: Documentation
bash "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_background.sh" \
  "Update docs, save to agents_reports/docs.md" "$(pwd)" &

wait
```

## Best Practices

### Clear Task Descriptions

```bash
# Good - specific and actionable
"Run pytest on tests/unit/, fix failures, report to agents_reports/test_fix.md"

# Bad - vague
"Fix tests"
```

### Always Specify Output

Tell agents where to save results:

```bash
"Analyze src/api.py and save analysis to agents_reports/api_analysis.md"
```

### Use agents_reports/ Directory

```
project/
├── agents_reports/
│   ├── test_results_20241205.md
│   ├── code_review_20241205.md
│   └── refactor_plan_20241205.md
└── src/
```

### Include Context

```bash
"Working on a Python FastAPI project. Main app is src/main.py.
Add input validation to all endpoints.
Report to agents_reports/validation.md"
```

## Troubleshooting

### Agent Not Starting

1. Verify Terminal.app is available
2. Check Claude CLI: `which claude`
3. Check AppleScript permissions in System Preferences

### Auto-Approval Not Working

1. Check hook registration:
   ```bash
   cat ~/.claude/plugins/cache/ghe/hooks/hooks.json | jq '.hooks.PreToolUse'
   ```

2. Check hook log:
   ```bash
   cat /tmp/background_agent_hook.log
   ```

3. Verify jq: `which jq`

### Terminal Steals Focus

The script briefly activates Terminal (~0.5s) to paste, then returns focus. This is expected behavior.

## Environment Variables

```bash
# Wait time for Claude init (default: 6)
export BACKGROUND_AGENT_WAIT=8

# Hook log location (default: /tmp/background_agent_hook.log)
export BACKGROUND_AGENT_LOG=/custom/path.log

# Disable logging
unset BACKGROUND_AGENT_LOG
```

## Implementation Details

For developers implementing similar functionality or debugging issues, see `references/implementation-tricks.md` which documents:

- **Terminal background trick**: Using `do script` without `activate`
- **Clipboard paste method**: Using `pbcopy` + Cmd+V instead of `keystroke`
- **Focus restoration**: Capturing current app and switching back
- **Hook JSON format**: The correct `hookSpecificOutput` wrapper structure
- **Hook type discovery**: Why `PreToolUse` not `PermissionRequest`
- **Testing hooks standalone**: Pipe JSON to test without full Claude session
- **Closing Terminal**: Options for auto-closing after agent completes

## Resources

### references/security-model.md

Complete documentation of the auto-approval whitelist, including all allowed tools, bash commands, and path safety rules.

### references/implementation-tricks.md

Technical implementation discoveries and solutions for macOS Terminal automation, AppleScript escaping, and hook development.
