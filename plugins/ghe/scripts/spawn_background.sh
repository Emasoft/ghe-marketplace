#!/bin/bash
# Spawn a Claude session in a BACKGROUND Terminal window (macOS only)
# The Terminal opens but does NOT steal focus from your current work!
#
# Usage: spawn_background.sh "Your prompt here" [working_dir]
#
# Environment variables:
#   BACKGROUND_AGENT_WAIT - Seconds to wait for Claude init (default: 6)

set -e

PROMPT="${1:-Hello! Please run git status and create a summary.}"
WORKING_DIR="${2:-$(pwd)}"
WAIT_TIME="${BACKGROUND_AGENT_WAIT:-6}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Ensure we have an absolute path
if [[ "$WORKING_DIR" != "/"* ]]; then
    WORKING_DIR="$(cd "$WORKING_DIR" && pwd)"
fi

# Create reports directory for agent output
mkdir -p "$WORKING_DIR/agents_reports"

# Build the claude command
CLAUDE_CMD="cd '$WORKING_DIR' && claude"

# Detect OS
if [[ "$(uname)" != "Darwin" ]]; then
    echo "ERROR: This script only works on macOS (requires Terminal.app)"
    echo "For Linux, consider using tmux or screen instead."
    exit 1
fi

# Open Terminal in BACKGROUND without stealing focus
osascript << EOF
tell application "Terminal"
    -- Create new window WITHOUT activating Terminal
    do script "$CLAUDE_CMD"
    
    -- Apply dark theme if available
    try
        set current settings of front window to settings set "Pro"
    end try
end tell
EOF

echo "Terminal opened in background, waiting ${WAIT_TIME}s for Claude..."
sleep "$WAIT_TIME"

# Write prompt to temp file to avoid escaping issues
PROMPT_FILE=$(mktemp /tmp/claude_prompt_XXXXXX.txt)
echo "$PROMPT" > "$PROMPT_FILE"

# Copy prompt to clipboard
cat "$PROMPT_FILE" | pbcopy

# Get the frontmost app so we can switch back
CURRENT_APP=$(osascript -e 'tell application "System Events" to get name of first process whose frontmost is true')

# Briefly activate Terminal to paste, then switch back
osascript << EOF
tell application "Terminal"
    activate
    delay 0.3
end tell
tell application "System Events"
    keystroke "v" using command down
    delay 0.2
    keystroke return
end tell
-- Switch back to the original app
delay 0.3
tell application "$CURRENT_APP"
    activate
end tell
EOF

# Cleanup temp file
rm -f "$PROMPT_FILE"

echo "=============================================="
echo "Background Claude Agent Started!"
echo "=============================================="
echo "Timestamp: $TIMESTAMP"
echo "Directory: $WORKING_DIR"
echo "Prompt:    ${PROMPT:0:60}..."
echo ""
echo "The agent is working in a background Terminal."
echo "Continue chatting - you won't be interrupted!"
echo "Check agents_reports/ for output when done."
echo "=============================================="
