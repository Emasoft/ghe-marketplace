# Implementation Tricks for Background Agents

This document captures the technical discoveries made while implementing `spawn_background.sh` and `auto_approve.sh` on macOS.

> **Naming convention**: Script files use underscores (`auto_approve.sh`), plugin/skill directories use hyphens (`background-agents`). Spaces are never allowed.

## Terminal Background Execution

### Problem
Opening a Terminal window with `osascript` normally steals focus from the current application.

### Solution
Use `do script` WITHOUT `activate`:

```applescript
tell application "Terminal"
    -- This opens Terminal but does NOT bring it to front
    do script "cd /path/to/project && claude"
    
    -- Optional: Apply dark theme
    try
        set current settings of front window to settings set "Pro"
    end try
end tell
```

### Key Insight
The `activate` command is what steals focus. Omitting it keeps Terminal in the background.

## Sending Text to Background Terminal

### Problem
Using `keystroke` to type text into Terminal requires Terminal to be the active application. But we don't want to activate Terminal.

### Failed Approach
```applescript
-- This does NOT work if Terminal isn't active
tell application "System Events"
    tell process "Terminal"
        keystroke "hello world"  -- Goes to wrong app!
    end tell
end tell
```

### Working Solution: Clipboard + Brief Activation

```bash
# 1. Copy prompt to clipboard
echo "$PROMPT" | pbcopy

# 2. Get current frontmost app
CURRENT_APP=$(osascript -e 'tell application "System Events" to get name of first process whose frontmost is true')

# 3. Briefly activate Terminal, paste, return focus
osascript << EOF
tell application "Terminal"
    activate
    delay 0.3
end tell
tell application "System Events"
    keystroke "v" using command down  -- Cmd+V paste
    delay 0.2
    keystroke return
end tell
delay 0.3
tell application "$CURRENT_APP"
    activate
end tell
EOF
```

### Key Insight
- Use `pbcopy` to put prompt on clipboard (avoids escaping issues)
- Briefly activate Terminal (~0.5s) just to paste
- Immediately return focus to original app
- Total disruption is minimal

## PreToolUse Hook Format

### Problem
The hook wasn't auto-approving operations. We tried various JSON formats that didn't work.

### Failed Formats

```json
// WRONG - This format does nothing
{"decision": "approve"}

// WRONG - This format does nothing  
{"approve": true}

// WRONG - Missing hookSpecificOutput wrapper
{"permissionDecision": "allow"}
```

### Correct Format

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow",
    "permissionDecisionReason": "Human-readable reason"
  }
}
```

### Key Fields
- `hookSpecificOutput` - Required wrapper object
- `hookEventName` - Must be `"PreToolUse"`
- `permissionDecision` - One of: `"allow"`, `"deny"`, `"ask"`
- `permissionDecisionReason` - Explanation shown to user

### Example Implementation

```bash
approve() {
    local REASON="${1:-Auto-approved}"
    cat << EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow","permissionDecisionReason":"$REASON"}}
EOF
    exit 0
}

deny_it() {
    local REASON="${1:-Denied}"
    cat << EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"$REASON"}}
EOF
    exit 0
}

ask_user() {
    cat << EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"ask","permissionDecisionReason":"Requires user approval"}}
EOF
    exit 0
}
```

## Hook Type: PreToolUse vs PermissionRequest

### Discovery
We initially tried registering as a `PermissionRequest` hook - this is WRONG.

### Correct Registration
The hook must be registered as `PreToolUse` in hooks.json:

```json
{
  "hooks": {
    "PreToolUse": [
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
    ]
  }
}
```

### Key Insight
- `PreToolUse` runs BEFORE each tool execution
- It receives tool details as JSON on stdin
- It can return permission decisions to allow/deny/ask
- `PermissionRequest` is a different hook type with different purpose

## Parsing Tool Input

### Input Format
The hook receives JSON on stdin:

```json
{
  "tool_name": "Write",
  "tool_input": {
    "file_path": "/path/to/file.md",
    "content": "..."
  },
  "cwd": "/current/working/directory",
  "hook_event_name": "PreToolUse"
}
```

### Extraction with jq

```bash
INPUT=$(cat)
TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // .tool_input.path // empty')
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
```

### Key Insight
- Use `// empty` to handle missing fields gracefully
- Some tools use `file_path`, others use `path`
- `cwd` gives the project directory for path safety checks

## Closing Terminal After Agent Completes

### Option 1: Agent Self-Closes
Add to the agent's task:

```
"When done, run: osascript -e 'tell application \"Terminal\" to close front window'"
```

### Option 2: Auto-Close on Exit
Modify Terminal preferences:
- Terminal > Preferences > Profiles > Shell
- "When the shell exits": Close the window

### Option 3: Script-Based Monitoring
```bash
# In spawn script, after sending prompt:
(
    # Wait for agent to complete (check for output file)
    while [ ! -f "GHE_REPORTS/result.md" ]; do
        sleep 10
    done
    sleep 5  # Grace period
    
    # Close the Terminal window
    osascript -e 'tell application "Terminal" to close front window'
) &
```

### Key Insight
The cleanest approach is Option 2 (Terminal preference) or having the agent include a close command in its final output.

## Quote Escaping in AppleScript

### Problem
Complex prompts with quotes, newlines, or special characters break AppleScript.

### Failed Approach
```bash
# This breaks on special characters
ESCAPED=$(echo "$PROMPT" | sed 's/"/\\"/g')
osascript -e "keystroke \"$ESCAPED\""
```

### Working Solution
Use clipboard (pbcopy) instead of escaping:

```bash
echo "$PROMPT" > /tmp/prompt.txt
cat /tmp/prompt.txt | pbcopy
# Then paste with Cmd+V
```

### Key Insight
Clipboard bypass eliminates ALL escaping issues regardless of prompt content.

## Testing Hooks Standalone

To test hook logic without running a full Claude session:

```bash
# Simulate a Write tool call
echo '{"tool_name":"Write","tool_input":{"file_path":"/project/test.md"},"cwd":"/project"}' | \
    bash /path/to/auto_approve.sh

# Expected output:
# {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"allow",...}}
```

### Key Insight
Hooks can be tested in isolation by piping test JSON to them. This is much faster than testing with real Claude sessions.

## Summary of Key Discoveries

1. **No `activate`** = Terminal stays in background
2. **pbcopy + Cmd+V** = Reliable text input without escaping issues
3. **Brief focus switch** = Necessary for paste, but returns immediately
4. **`hookSpecificOutput` wrapper** = Required for hook decisions
5. **PreToolUse not PermissionRequest** = Correct hook type for auto-approval
6. **jq with `// empty`** = Graceful handling of missing JSON fields
