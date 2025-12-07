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

## Hook Events Reference

| Event | When It Fires | Input Schema |
|-------|---------------|--------------|
| `SessionStart` | When Claude Code starts | `{session_id, cwd}` |
| `UserPromptSubmit` | User sends a message | `{prompt, transcript_path, session_id, cwd}` |
| `Stop` | Claude finishes responding | `{transcript_path, stop_reason}` |
| `PreToolUse` | Before a tool runs | `{tool_name, tool_input}` |
| `PostToolUse` | After a tool runs | `{tool_name, tool_input, tool_output}` |

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
