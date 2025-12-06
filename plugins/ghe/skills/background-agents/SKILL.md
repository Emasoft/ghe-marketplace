---
name: background-agents
description: This skill should be used when spawning Claude agents in background Terminal windows, running agents autonomously without blocking the conversation, delegating tasks to external Claude instances, or understanding how the auto-approval PreToolUse hook works. Triggers include "background agent", "spawn agent", "external claude", "autonomous agent", "parallel agent", "delegate to agent", or "run agent in background".
---

## IRON LAW: User Specifications Are Sacred

**THIS LAW IS ABSOLUTE AND ADMITS NO EXCEPTIONS.**

1. **Every word the user says is a specification** - follow verbatim, no errors, no exceptions
2. **Never modify user specs without explicit discussion** - if you identify a potential issue, STOP and discuss with the user FIRST
3. **Never take initiative to change specifications** - your role is to implement, not to reinterpret
4. **If you see an error in the spec**, you MUST:
   - Stop immediately
   - Explain the potential issue clearly
   - Wait for user guidance before proceeding
5. **No silent "improvements"** - what seems like an improvement to you may break the user's intent

**Violation of this law invalidates all work produced.**

## Background Agent Boundaries

When running as a background agent, you may ONLY write to:
- The project directory and its subdirectories
- The parent directory (for sub-git projects)
- ~/.claude (for plugin/settings fixes)
- /tmp

Do NOT write outside these locations.

---

## GHE_REPORTS Folder Structure (CRITICAL!)

**GHE_REPORTS is a FLAT folder - NO SUBFOLDERS!**

```
project/
├── GHE_REPORTS/                    # FLAT structure, git-tracked
│   ├── 20251206143000GMT+01_epic_15_wave_launched_(Athena).md
│   ├── 20251206143022GMT+01_issue_42_dev_complete_(Hephaestus).md
│   ├── 20251206150000GMT+01_issue_42_tests_passed_(Artemis).md
│   ├── 20251206160000GMT+01_issue_42_review_complete_(Hera).md
│   └── ...
├── REQUIREMENTS/                   # SEPARATE folder - permanent design docs
│   └── issue-N-requirements.md     # NEVER deleted
└── ...
```

**Report Naming Convention:** `<TIMESTAMP>_<title or description>_(<AGENT>).md`
**Timestamp Format:** `YYYYMMDDHHMMSSTimezone`

**ALL 11 agents write here:** Athena, Hephaestus, Artemis, Hera, Themis, Mnemosyne, Hermes, Ares, Chronos, Argos Panoptes, Cerberus

**CRITICAL**: Reports must be posted to BOTH:
1. **GitHub Issue Thread** - Full report text (NOT just a link!)
2. **GHE_REPORTS/ folder** - Same full report text (FLAT, no subfolders!)

**REQUIREMENTS/ is SEPARATE** - permanent design documents with legal validity, NEVER deleted.

**Deletion Policy:**
- GHE_REPORTS should be git-tracked - it constitutes the pulse of the GHE plugin
- DELETE ONLY when user EXPLICITLY orders deletion due to space constraints
- DO NOT delete during normal project cleanup or just because reports were archived to GitHub

---

# Background Agents

## Overview

This skill enables spawning Claude Code agents in background Terminal windows that work autonomously while the main conversation continues.

**Key Features:**
- **TRUE background execution** - Terminal windows NEVER steal focus
- **No keystrokes** - Prompt piped directly to Claude via command line
- **Unique window tracking** - Each agent has unique ID (title) and TTY path
- **Autonomous operation** - Uses `--dangerously-skip-permissions` for unattended execution
- **Clean separation** - Each agent runs in isolated Terminal window

**How It Works:**
1. Prompt is written to temp file
2. Terminal window created in background (never activated)
3. Claude runs with prompt piped: `cat prompt.txt | claude --dangerously-skip-permissions`
4. Window gets unique title like `GHE-AGENT-20251206_143502-96268`
5. Output saved to `GHE_REPORTS/` directory (FLAT, no subfolders)

## Requirements

- **macOS only** (uses Terminal.app and AppleScript)
- **Claude Code CLI** installed
- **jq** for JSON parsing in hooks

## Installation

This feature is included in the GHE plugin. Install or update GHE:

```bash
# Add marketplace (if not already added)
claude marketplace add https://github.com/Emasoft/ghe-marketplace

# Install/update the plugin
claude plugin install ghe@ghe-marketplace
```

After installation, restart Claude Code to load the hooks.

## Verify Installation

### Step 1: Check Plugin is Installed

```bash
claude plugin list | grep ghe
```

Expected output should show `ghe@ghe-marketplace` as installed.

### Step 2: Check Hook is Registered

```bash
cat ~/.claude/plugins/cache/ghe/hooks/hooks.json | jq '.hooks.PreToolUse[0]'
```

Expected output:
```json
{
  "matcher": ".*",
  "hooks": [
    {
      "type": "command",
      "command": "bash ${CLAUDE_PLUGIN_ROOT}/scripts/auto_approve.sh",
      "timeout": 10000
    }
  ]
}
```

### Step 3: Check Scripts are Present

```bash
ls -la ~/.claude/plugins/cache/ghe/scripts/ | grep -E "(auto_approve|spawn_background)"
```

Expected output should show both `auto_approve.sh` and `spawn_background.sh`.

### Step 4: Check jq is Installed

```bash
which jq
```

If not installed:
```bash
brew install jq
```

### Step 5: Test the Hook Standalone

```bash
echo '{"tool_name":"Read","tool_input":{"file_path":"test.md"},"cwd":"/tmp"}' | \
    bash ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Expected output:
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"Safe read-only tool"}}
```

### Step 6: Test Security (Write Outside Project)

```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"/etc/test"},"cwd":"/tmp"}' | \
    bash ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Expected output (should DENY):
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"Write outside project: /etc/test"}}
```

## First Run Test

To verify everything works end-to-end:

### 1. Create Test Directory

```bash
mkdir -p ~/test-background-agents/GHE_REPORTS
cd ~/test-background-agents
```

### 2. Start Claude in Test Directory

```bash
claude
```

### 3. Ask Claude to Spawn a Test Agent

Type this in the Claude session:

```
Please spawn a background agent to write "SUCCESS" to GHE_REPORTS/test_result.md
```

### 4. Wait and Check

Wait ~15 seconds, then check:

```bash
cat ~/test-background-agents/GHE_REPORTS/test_result.md
```

Expected: File contains "SUCCESS" or similar confirmation.

### 5. Check Hook Log

```bash
cat /tmp/background_agent_hook.log | tail -5
```

Should show ALLOW decisions for the Write operation.

### 6. Cleanup

```bash
rm -rf ~/test-background-agents
```

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
and save a report to GHE_REPORTS/<TIMESTAMP>_refactor_report_(Agent).md
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

## The auto_approve.sh Hook

The core of background agents is the `auto_approve.sh` PreToolUse hook script. This hook intercepts every tool call and returns a permission decision.

> **Note on naming**: The hook script uses underscores (`auto_approve.sh`) following shell scripting conventions. Plugin/skill directories use hyphens (`background-agents`). Spaces are never allowed in Claude Code plugin names, directories, or files.

### Hook Location

After installing GHE, the hook is at:
```
~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

### How the Hook Works

1. Claude is about to use a tool (Read, Write, Bash, etc.)
2. Claude sends tool details as JSON to the hook via stdin
3. Hook analyzes the tool and returns a permission decision
4. Claude either proceeds, blocks, or asks user based on decision

### Hook Input Format

The hook receives JSON on stdin:
```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.md",
    "content": "file contents..."
  },
  "cwd": "/current/working/directory",
  "hook_event_name": "PreToolUse"
}
```

### Hook Output Format

The hook must return JSON with this exact structure:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Human-readable reason"
  }
}
```

Valid `permissionDecision` values:
- `"allow"` - Operation proceeds without user prompt
- `"deny"` - Operation is blocked
- `"ask"` - User is prompted for approval

### Testing the Hook Directly

#### Test 1: Read Tool (should ALLOW)
```bash
echo '{"tool_name":"Read","tool_input":{"file_path":"test.md"},"cwd":"/tmp"}' | \
    bash ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Expected:
```json
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"Safe read-only tool"}}
```

#### Test 2: Write Inside Project (should ALLOW)
```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"/myproject/src/test.md"},"cwd":"/myproject"}' | \
    bash ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Expected: `"permissionDecision":"allow"`

#### Test 3: Write Outside Project (should DENY)
```bash
echo '{"tool_name":"Write","tool_input":{"file_path":"/etc/passwd"},"cwd":"/myproject"}' | \
    bash ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Expected: `"permissionDecision":"deny"`

#### Test 4: Safe Bash Command (should ALLOW)
```bash
echo '{"tool_name":"Bash","tool_input":{"command":"git status"},"cwd":"/myproject"}' | \
    bash ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Expected: `"permissionDecision":"allow"`

#### Test 5: Dangerous Bash Command (should DENY)
```bash
echo '{"tool_name":"Bash","tool_input":{"command":"sudo rm -rf /"},"cwd":"/myproject"}' | \
    bash ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Expected: `"permissionDecision":"deny"`

#### Test 6: Unknown Tool (should ASK)
```bash
echo '{"tool_name":"SomeNewTool","tool_input":{},"cwd":"/myproject"}' | \
    bash ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Expected: `"permissionDecision":"ask"`

### Checking Hook Logs

The hook logs all decisions to `/tmp/background_agent_hook.log`:

```bash
# View recent decisions
tail -20 /tmp/background_agent_hook.log

# Watch live decisions
tail -f /tmp/background_agent_hook.log

# Filter for denials only
grep "DENY" /tmp/background_agent_hook.log

# Clear log
> /tmp/background_agent_hook.log
```

Log format:
```
[Fri Dec  5 10:46:28 CET 2025] Tool: Write, Path: /project/file.md, Cmd:
[Fri Dec  5 10:46:28 CET 2025] ALLOW: Write within project directory
```

### Customizing the Hook

To add custom tool approvals, edit the hook script:

```bash
# Open for editing
nano ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

#### Adding a New Tool
Find the `case "$TOOL_NAME"` section and add:
```bash
case "$TOOL_NAME" in
    # ... existing cases ...

    "MyCustomTool")
        approve "My custom tool is safe"
        ;;
esac
```

#### Adding a New Bash Command
Find the `case "$COMMAND"` section and add:
```bash
case "$COMMAND" in
    # ... existing cases ...

    mycustomcmd\ *)
        approve "Custom command approved" ;;
esac
```

#### Adding a Path Exception
Modify the `is_safe_path()` function:
```bash
is_safe_path() {
    local P="$1"
    [[ -z "$P" ]] && return 0
    [[ "$P" != "/"* ]] && return 0
    [[ "$P" == "$PROJECT_ROOT"* ]] && return 0
    [[ "$P" == "/tmp"* ]] && return 0
    # Add your custom safe path:
    [[ "$P" == "/my/custom/safe/path"* ]] && return 0
    return 1
}
```

### Disabling the Hook Temporarily

To disable auto-approval temporarily:

```bash
# Rename the hook
mv ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh \
   ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh.disabled

# Re-enable
mv ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh.disabled \
   ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh
```

Or modify hooks.json to remove the PreToolUse entry.

### Hook Without GHE Plugin

To use the hook in other projects without installing GHE:

1. Copy the hook script:
```bash
mkdir -p /your/project/.claude/hooks/scripts
cp ~/.claude/plugins/cache/ghe/scripts/auto_approve.sh \
   /your/project/.claude/hooks/scripts/
```

2. Create hooks.json:
```bash
cat > /your/project/.claude/hooks/hooks.json << 'EOF'
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "bash .claude/hooks/scripts/auto_approve.sh",
            "timeout": 10000
          }
        ]
      }
    ]
  }
}
EOF
```

3. Reference in project settings:
```bash
cat > /your/project/.claude/settings.json << 'EOF'
{
  "hooks": "./.claude/hooks/hooks.json"
}
EOF
```

## Security Model

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
  "Run pytest, report to GHE_REPORTS/\$(date +%Y%m%d%H%M%S%Z)_pytest_results_(Artemis).md" "$(pwd)" &

# Agent 2: Linting
bash "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_background.sh" \
  "Run linters, report to GHE_REPORTS/\$(date +%Y%m%d%H%M%S%Z)_lint_results_(Ares).md" "$(pwd)" &

# Agent 3: Documentation
bash "${CLAUDE_PLUGIN_ROOT}/scripts/spawn_background.sh" \
  "Update docs, save to GHE_REPORTS/\$(date +%Y%m%d%H%M%S%Z)_docs_update_(Hermes).md" "$(pwd)" &

wait
```

## Best Practices

### Clear Task Descriptions

```bash
# Good - specific and actionable
"Run pytest on tests/unit/, fix failures, report to GHE_REPORTS/<TIMESTAMP>_test_fix_(Artemis).md"

# Bad - vague
"Fix tests"
```

### Always Specify Output

Tell agents where to save results:

```bash
"Analyze src/api.py and save analysis to GHE_REPORTS/<TIMESTAMP>_api_analysis_(Athena).md"
```

### Use GHE_REPORTS/ Directory (FLAT - No Subfolders!)

```
project/
├── GHE_REPORTS/                                          # FLAT structure
│   ├── 20251205150000AEST_test_results_(Artemis).md
│   ├── 20251205160000AEST_code_review_(Hera).md
│   └── 20251205170000AEST_refactor_plan_(Athena).md
└── src/
```

### Include Context

```bash
"Working on a Python FastAPI project. Main app is src/main.py.
Add input validation to all endpoints.
Report to GHE_REPORTS/<TIMESTAMP>_validation_(Themis).md"
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
