---
name: hook-development
description: |
  This skill should be used when writing Claude Code plugin hooks or debugging
  the "operation was aborted" error. Teaches the critical "immediate response"
  pattern that prevents Claude Code's internal timeout from aborting hooks.
  Essential knowledge for plugin developers creating PreToolUse, PostToolUse,
  UserPromptSubmit, Stop, or SessionStart hooks.
triggers:
  - write a hook
  - create a hook
  - hook development
  - hook best practices
  - operation was aborted
  - hook timeout
  - hook aborted
  - PreToolUse hook
  - PostToolUse hook
  - UserPromptSubmit hook
  - Stop hook
  - SessionStart hook
---

# Writing Reliable Claude Code Hooks

This skill teaches you how to write hooks that **never get aborted** by Claude Code's internal timeout mechanism.

## The Problem: "Operation Was Aborted"

You've probably seen this error:
```
Plugin hook ... failed to start: The operation was aborted.
Check that the command exists and is executable.
```

This happens because **Claude Code has an internal timeout** (via JavaScript's `AbortController`) that expects hooks to respond quickly. If your hook doesn't output JSON fast enough, Claude Code aborts the process.

## The Solution: Immediate Response Pattern

The fix is simple but critical: **Output JSON immediately after reading stdin**, then fork the actual work to a subprocess.

### The Wrong Way (Gets Aborted)

```python
#!/usr/bin/env python3
import json
import sys

def main():
    # Read stdin
    input_data = json.load(sys.stdin)

    # DO WORK HERE (takes 100-500ms)
    process_data(input_data)  # TOO SLOW!
    do_more_work()            # STILL WORKING...

    # Output JSON - TOO LATE! Already aborted!
    print(json.dumps({"event": "UserPromptSubmit"}))

if __name__ == "__main__":
    main()
```

Timeline:
```
0ms    - Hook starts
10ms   - Reads stdin
100ms  - Still doing work...
200ms  - ABORTED by Claude Code's internal timeout
500ms  - Would have output JSON (never reached)
```

### The Right Way (Never Aborted)

```python
#!/usr/bin/env python3
import json
import os
import subprocess
import sys
from pathlib import Path

def main():
    # Step 1: Read stdin IMMEDIATELY
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
        sys.exit(0)

    # Step 2: Output JSON IMMEDIATELY (satisfies Claude Code's timeout)
    print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
    sys.stdout.flush()

    # Step 3: Fork subprocess to do actual work
    env = os.environ.copy()
    env["MY_DATA"] = json.dumps(input_data)  # Pass data via env var

    worker_script = Path(__file__).parent / "worker.py"
    subprocess.Popen(
        [sys.executable, str(worker_script)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,  # Detach from parent
        env=env,
    )

    sys.exit(0)

if __name__ == "__main__":
    main()
```

Timeline:
```
0ms    - Hook starts
10ms   - Reads stdin
20ms   - Outputs JSON (Claude Code satisfied!)
30ms   - Forks subprocess
40ms   - Hook exits cleanly
...    - Worker does actual work in background
```

## Hook Configuration (hooks.json)

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "matcher": ".*",
        "hooks": [
          {
            "type": "command",
            "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/my_hook.py",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

**Important notes:**
- Use `python3` prefix (not just the script path)
- `${CLAUDE_PLUGIN_ROOT}` is expanded by Claude Code
- `timeout` is YOUR timeout (in seconds), separate from Claude Code's internal timeout
- Don't use `suppressOutput: true` during debugging - you need to see errors

## Script Setup Checklist

### 1. Make Scripts Executable

**CRITICAL**: All hook scripts must be executable!

```bash
chmod +x scripts/*.py
```

Without this, you'll get cryptic errors like "command not found" or "permission denied".

### 2. Choose Your Invocation Method

There are three ways to invoke Python hooks. Each has tradeoffs:

#### Method A: `python3` prefix (RECOMMENDED)

```json
"command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/my_hook.py"
```

**Pros**: Works reliably, python3 is always in PATH
**Cons**: None significant
**Shebang**: `#!/usr/bin/env python3`

#### Method B: Direct script execution

```json
"command": "${CLAUDE_PLUGIN_ROOT}/scripts/my_hook.py"
```

**Pros**: Cleaner command
**Cons**: Requires executable permission, relies on shebang
**Shebang**: `#!/usr/bin/env python3` (REQUIRED)

#### Method C: `uv run` with inline dependencies (ADVANCED)

```json
"command": "uv run ${CLAUDE_PLUGIN_ROOT}/scripts/my_hook.py"
```

**Pros**: Can specify dependencies inline via PEP 723
**Cons**: `uv` may not be in Claude Code's PATH on all systems
**Shebang**: Use PEP 723 format:

```python
#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "requests>=2.31.0",
# ]
# ///
```

**WARNING**: On macOS, `/opt/homebrew/bin` may not be in Claude Code's PATH. If `uv` fails, fall back to Method A.

### 3. Shebang Reference

| Shebang | Use Case |
|---------|----------|
| `#!/usr/bin/env python3` | Standard Python script |
| `#!/usr/bin/env -S uv run --script` | Script with inline dependencies |
| `#!/bin/bash` | Shell script hooks |

**Common mistake**: Escaped shebangs like `#\!/usr/bin/env python3` - the backslash breaks it!

### 4. The suppressOutput Setting

```json
{
  "type": "command",
  "command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/my_hook.py",
  "timeout": 30,
  "suppressOutput": true  // REMOVE THIS WHEN DEBUGGING!
}
```

- `suppressOutput: true` - Hides all output (clean but hides errors)
- `suppressOutput: false` or omitted - Shows errors (use during development)

**Debugging workflow**:
1. Remove `suppressOutput` to see errors
2. Fix the errors
3. Add `suppressOutput: true` back for production

## Output Visibility Reference

### Who Sees What

| Output Channel | Visible To | When | How to Use |
|----------------|------------|------|------------|
| **stdout (JSON)** | Claude Code | Always | `print(json.dumps({...}), flush=True)` |
| **stdout (text)** | User (in chat) | When `suppressOutput: false` | `print("message")` |
| **stderr** | User (in chat) | When `suppressOutput: false` | `print("error", file=sys.stderr)` |
| **File log** | Developer (via file) | Always | Write to `.claude/hook_debug.log` |
| **Exit code** | Claude Code | Always | `sys.exit(0)` or `sys.exit(2)` |

### Output Behavior Matrix

| `suppressOutput` | stdout JSON | stdout text | stderr | File log |
|------------------|-------------|-------------|--------|----------|
| `true` | Parsed by Claude Code | Hidden | Hidden | Always works |
| `false`/omitted | Parsed by Claude Code | Shown to user | Shown to user | Always works |

### JSON Output Fields (stdout)

Claude Code parses JSON from stdout to control behavior:

| Field | Type | Effect |
|-------|------|--------|
| `decision` | `"block"` | Blocks the operation (PreToolUse/UserPromptSubmit) |
| `reason` | string | Shown to user when blocking |
| `additionalContext` | string | Added to Claude's context |
| `suppressOutput` | boolean | In JSON response, not hooks.json |

Example blocking response:
```python
print(json.dumps({
    "decision": "block",
    "reason": "Operation not allowed: dangerous command detected"
}), flush=True)
sys.exit(2)  # Exit code 2 = block
```

Example adding context:
```python
print(json.dumps({
    "additionalContext": "Note: User is in production environment"
}), flush=True)
sys.exit(0)
```

### Exit Codes

| Exit Code | Meaning | Effect |
|-----------|---------|--------|
| `0` | Success | Operation proceeds normally |
| `2` | Block | Operation is blocked, stderr shown to user |
| Other | Error | Non-blocking error, stderr shown in verbose mode |

### Redirecting Output

#### To hide all user-visible output:
```json
"suppressOutput": true
```

#### To log to file (always works):
```python
def debug_log(message: str) -> None:
    log_file = Path(".claude/hook_debug.log")
    log_file.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().isoformat()
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")
```

#### To show message to user (when not suppressed):
```python
# Via stderr (recommended for errors)
print("Warning: something happened", file=sys.stderr)

# Via stdout text (before JSON)
print("Info: processing...")
print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
```

#### To send context to Claude (not shown to user):
```python
print(json.dumps({
    "additionalContext": "This info goes to Claude's context only"
}), flush=True)
```

### Summary: Where to Put Output

| What You Want | Where to Put It |
|---------------|-----------------|
| Debug during development | `stderr` + `suppressOutput: false` |
| Permanent debug log | File (`.claude/hook_debug.log`) |
| Block operation with message | JSON `decision: "block"` + `reason` + exit 2 |
| Add context for Claude | JSON `additionalContext` |
| Silent production operation | `suppressOutput: true` + file logging |

## Hook Events Reference

| Event | When It Fires | Input Schema |
|-------|---------------|--------------|
| `SessionStart` | When Claude Code starts | `{session_id, cwd}` |
| `UserPromptSubmit` | User sends a message | `{prompt, transcript_path, session_id, cwd}` |
| `Stop` | Claude finishes responding | `{transcript_path, stop_reason}` |
| `PreToolUse` | Before a tool runs | `{tool_name, tool_input}` |
| `PostToolUse` | After a tool runs | `{tool_name, tool_input, tool_output}` |

### Event-Specific Output Handling

**IMPORTANT**: Each event type handles JSON output differently!

#### UserPromptSubmit (SPECIAL HANDLING)

This event has unique output behavior:

| Exit Code | JSON Field | Effect |
|-----------|------------|--------|
| `0` | (none) | Prompt proceeds normally |
| `0` | `additionalContext` | Text added to Claude's context (user doesn't see) |
| `0` | `systemMessage` | Shown as system message in chat |
| `2` | `decision: "block"` | Prompt is **erased from context**, stderr shown to user |
| `2` | `reason` | Shown to user explaining why blocked |

```python
# Allow prompt but add context for Claude
print(json.dumps({
    "additionalContext": "User is working on production database"
}), flush=True)
sys.exit(0)

# Block prompt completely (erased from history!)
print(json.dumps({
    "decision": "block",
    "reason": "Cannot execute destructive commands in production"
}), flush=True)
sys.exit(2)
```

**Key difference**: When UserPromptSubmit blocks with exit code 2, the **prompt is erased from context** - Claude never sees it!

#### PreToolUse

| Exit Code | JSON Field | Effect |
|-----------|------------|--------|
| `0` | (none) | Tool executes normally |
| `0` | `permissionDecision: "allow"` | Explicitly allow |
| `0` | `permissionDecision: "deny"` | Block tool, show reason |
| `2` | `decision: "block"` | Block tool execution |
| `2` | `reason` | Shown to user |

```python
# Block dangerous command
if "rm -rf" in tool_input.get("command", ""):
    print(json.dumps({
        "decision": "block",
        "reason": "Dangerous command blocked: rm -rf"
    }), flush=True)
    sys.exit(2)
```

#### PostToolUse

| Exit Code | JSON Field | Effect |
|-----------|------------|--------|
| `0` | (none) | Continue normally |
| `0` | `additionalContext` | Add info about tool result |

```python
# Add context about what happened
print(json.dumps({
    "additionalContext": f"Tool {tool_name} modified 5 files"
}), flush=True)
sys.exit(0)
```

#### Stop

| Exit Code | JSON Field | Effect |
|-----------|------------|--------|
| `0` | (none) | Session ends normally |
| `0` | `additionalContext` | Added for next turn |

```python
# Add reminder for next turn
print(json.dumps({
    "additionalContext": "Remember to run tests before committing"
}), flush=True)
sys.exit(0)
```

#### SessionStart

| Exit Code | JSON Field | Effect |
|-----------|------------|--------|
| `0` | (none) | Session starts normally |
| `0` | `additionalContext` | Added to initial context |
| `0` | `systemMessage` | Shown to user at start |

```python
# Welcome message and context
print(json.dumps({
    "systemMessage": "GHE plugin loaded. Transcription active.",
    "additionalContext": "Project: my-app, Branch: feature/new-ui"
}), flush=True)
sys.exit(0)
```

### Event Comparison Matrix

| Event | Can Block? | Erases Context? | `additionalContext` | `systemMessage` |
|-------|------------|-----------------|---------------------|-----------------|
| `SessionStart` | No | No | Yes | Yes |
| `UserPromptSubmit` | Yes (exit 2) | **Yes** (when blocked) | Yes | Yes |
| `PreToolUse` | Yes (exit 2) | No | Yes | No |
| `PostToolUse` | No | No | Yes | No |
| `Stop` | No | No | Yes | No |

## Complete Example: Message Logger

### Hook Script (log_messages.py)

```python
#!/usr/bin/env python3
"""UserPromptSubmit hook that logs messages without getting aborted."""

import json
import os
import subprocess
import sys
from pathlib import Path

def main():
    # CRITICAL: Read stdin immediately
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
        sys.exit(0)

    # CRITICAL: Output JSON immediately to prevent abort
    print(json.dumps({"event": "UserPromptSubmit"}), flush=True)
    sys.stdout.flush()

    # Fork the actual logging work
    prompt = input_data.get("prompt", "")
    if prompt:
        env = os.environ.copy()
        env["LOG_MESSAGE"] = prompt

        worker = Path(__file__).parent / "log_worker.py"
        if worker.exists():
            subprocess.Popen(
                [sys.executable, str(worker)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
            )

    sys.exit(0)

if __name__ == "__main__":
    main()
```

### Worker Script (log_worker.py)

```python
#!/usr/bin/env python3
"""Background worker that does the actual logging."""

import os
from datetime import datetime
from pathlib import Path

def main():
    message = os.environ.get("LOG_MESSAGE", "")
    if not message:
        return

    log_file = Path(".claude/message_log.txt")
    log_file.parent.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().isoformat()
    with open(log_file, "a") as f:
        f.write(f"[{timestamp}] {message}\n")

if __name__ == "__main__":
    main()
```

## Debugging Tips

1. **Remove `suppressOutput: true`** during development to see errors
2. **Add debug logging** to a file (stdout goes to Claude Code)
3. **Test hooks manually** before deploying:
   ```bash
   echo '{"prompt": "test"}' | python3 my_hook.py
   ```
4. **Check the debug log**:
   ```bash
   tail -f .claude/hook_debug.log
   ```

## Common Mistakes

| Mistake | Fix |
|---------|-----|
| Doing work before outputting JSON | Output JSON first, fork work |
| Using `time.sleep()` in hook | Never sleep in the main hook |
| Reading large files before responding | Fork to worker, read there |
| Making API calls in hook | Fork to worker, call API there |
| Forgetting `flush=True` | Always flush stdout immediately |
| Not using `start_new_session=True` | Worker might get killed with parent |
| Script not executable | Run `chmod +x script.py` |
| Escaped shebang `#\!` | Use `#!` (no backslash) |
| Using `uv` without checking PATH | Fall back to `python3` prefix |
| `suppressOutput: true` hiding errors | Remove it during debugging |
| Relying on shell environment | Claude Code has minimal PATH |
| Multiple plugins with same hook event | Can cause race conditions |

## Troubleshooting Guide

### Error: "failed to start: The operation was aborted"

**Cause**: Hook didn't output JSON fast enough before Claude Code's internal timeout.

**Fix**: Use the immediate response pattern - output JSON first, fork work to subprocess.

### Error: "command not found" or "permission denied"

**Cause**: Script not executable or bad shebang.

**Fix**:
```bash
chmod +x scripts/*.py
# Check shebang is correct (no backslash!)
head -1 scripts/my_hook.py  # Should show: #!/usr/bin/env python3
```

### Error: "uv: command not found"

**Cause**: `uv` not in Claude Code's PATH (common on macOS with Homebrew).

**Fix**: Use `python3` prefix instead:
```json
"command": "python3 ${CLAUDE_PLUGIN_ROOT}/scripts/my_hook.py"
```

### Hook runs but nothing happens

**Causes**:
1. `suppressOutput: true` hiding errors
2. Worker subprocess failing silently
3. Wrong working directory

**Fix**:
1. Remove `suppressOutput` temporarily
2. Add debug logging to worker script
3. Use absolute paths or `${CLAUDE_PLUGIN_ROOT}`

### Hook works manually but fails in Claude Code

**Cause**: Different environment (PATH, working directory, etc.)

**Fix**:
1. Don't rely on shell aliases or custom PATH entries
2. Use `python3` or full paths to executables
3. Pass data via environment variables, not stdin to subprocess

## Key Takeaways

1. **Output JSON within 50ms** - Claude Code's internal timeout is aggressive
2. **Fork heavy work** - Use subprocess with `start_new_session=True`
3. **Pass data via environment variables** - Safer than command args
4. **Always exit 0** - Non-zero exit codes have special meanings
5. **Test manually first** - Easier to debug outside Claude Code

## Bundled Template Scripts

This skill includes ready-to-use template scripts in the `scripts/` directory:

- **`scripts/example_hook.py`** - Template hook with the immediate response pattern
- **`scripts/example_worker.py`** - Template worker for background processing

To use these templates:
1. Copy them to your plugin's `scripts/` directory
2. Rename and customize for your use case
3. Update `hooks.json` to point to your hook script

## Related Resources

- [Claude Code Hooks Documentation](https://docs.anthropic.com/en/docs/claude-code/hooks)
- [GitHub Issue #5468](https://github.com/anthropics/claude-code/issues/5468) - AbortError investigation
- GHE Plugin source code: `plugins/ghe/scripts/capture_user.py`
