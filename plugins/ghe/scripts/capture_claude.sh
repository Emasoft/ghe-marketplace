#!/bin/bash
# Fast Stop hook - spawns Python in background and exits immediately
# Bash starts in ~1ms vs Python's ~100ms

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Spawn Python in background and exit immediately
nohup python3 "$SCRIPT_DIR/capture_claude_worker.py" </dev/stdin >/dev/null 2>&1 &

# Exit immediately - don't wait for Python
exit 0
