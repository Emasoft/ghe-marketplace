#!/usr/bin/env python3
"""
TOC (Table of Contents) Manager for GHE Transcription System.

Manages a dynamic Table of Contents as the first comment on transcribed issues.
The TOC is updated automatically as new messages are posted.

Usage:
    # Initialize/update TOC for an issue
    python3 toc_manager.py update <issue_number>

    # Get TOC comment ID for an issue
    python3 toc_manager.py get-id <issue_number>
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Get plugin root
GHE_PLUGIN_ROOT = os.environ.get(
    "CLAUDE_PLUGIN_ROOT", str(Path(__file__).parent.parent)
)


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [toc_manager] - {message}\n")
    except Exception:
        pass


# TOC marker - identifies the TOC comment
TOC_MARKER = "<!-- GHE-TOC-v1 -->"
TOC_END_MARKER = "<!-- /GHE-TOC -->"

# Debug mode
DEBUG_MODE = os.environ.get("GHE_DEBUG", "0") == "1"


def debug_print(msg: str) -> None:
    """Print debug message only if DEBUG_MODE is enabled."""
    if DEBUG_MODE:
        print(f"DEBUG TOC: {msg}", file=sys.stderr)


def get_plugin_repo_root() -> str:
    """Get the plugin's repository root for gh commands."""
    return str(Path(GHE_PLUGIN_ROOT).parent.parent)


def get_issue_comments(issue_num: int) -> List[Dict[str, Any]]:
    """Fetch all comments from an issue."""
    debug_log(f"Fetching comments for issue #{issue_num}")
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--json", "comments"],
            capture_output=True,
            text=True,
            check=False,
            cwd=get_plugin_repo_root(),
            timeout=30,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            comments: List[Dict[str, Any]] = data.get("comments", [])
            debug_log(f"Fetched {len(comments)} comments for issue #{issue_num}")
            return comments
        debug_log(
            f"gh command failed with returncode {result.returncode}: {result.stderr}",
            "ERROR",
        )
    except (
        subprocess.TimeoutExpired,
        subprocess.SubprocessError,
        json.JSONDecodeError,
    ) as e:
        debug_log(f"Failed to fetch comments: {e}", "ERROR")
        debug_print(f"Failed to fetch comments: {e}")
    return []


def find_toc_comment(comments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Find the TOC comment in the list of comments."""
    for comment in comments:
        body = comment.get("body", "")
        if TOC_MARKER in body:
            return comment
    return None


def extract_message_info(comment: Dict[str, Any]) -> Optional[Dict[str, str]]:
    """
    Extract message info from a transcribed comment.

    Returns dict with:
        - speaker: 'user' or 'claude'
        - timestamp: ISO timestamp
        - preview: first 50 chars of content
        - url: comment URL
    """
    body = comment.get("body", "")

    # Skip TOC comments
    if TOC_MARKER in body:
        return None

    # Detect speaker from avatar/header
    is_user = "avatars.githubusercontent.com" in body
    is_claude = "/assets/avatars/" in body.lower() or "claude" in body[:200].lower()

    if not is_user and not is_claude:
        return None  # Not a transcribed message

    speaker = "user" if is_user else "claude"

    # Extract timestamp from createdAt
    created_at = comment.get("createdAt", "")

    # Extract preview from content (skip header/avatar section)
    # Find content after the first horizontal rule
    parts = body.split("\n---\n")
    content = parts[0] if parts else body

    # Remove markdown images and links
    content = re.sub(r"!\[.*?\]\(.*?\)", "", content)
    content = re.sub(r"\[.*?\]\(.*?\)", "", content)
    content = re.sub(r"<.*?>", "", content)
    content = content.strip()

    # Get first meaningful line
    lines = [
        line.strip()
        for line in content.split("\n")
        if line.strip() and not line.startswith("#")
    ]
    preview = lines[0][:50] if lines else "..."

    # Get comment URL
    url = comment.get("url", "")

    return {"speaker": speaker, "timestamp": created_at, "preview": preview, "url": url}


def generate_toc_content(messages: List[Dict[str, str]], issue_num: int) -> str:
    """Generate the TOC markdown content."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    toc = f"""{TOC_MARKER}
# Conversation Index

**Issue #{issue_num}** | Last updated: {now}

| # | Speaker | Time | Preview |
|---|---------|------|---------|
"""

    for i, msg in enumerate(messages, 1):
        speaker_icon = "**User**" if msg["speaker"] == "user" else "*Claude*"

        # Format timestamp
        ts = msg["timestamp"]
        if ts:
            try:
                dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                ts_formatted = dt.strftime("%H:%M")
            except ValueError:
                ts_formatted = ts[:5] if len(ts) >= 5 else ts
        else:
            ts_formatted = "?"

        preview = (
            msg["preview"][:40] + "..." if len(msg["preview"]) > 40 else msg["preview"]
        )
        preview = preview.replace("|", "\\|")  # Escape pipe for table

        # Make clickable if URL available
        if msg["url"]:
            toc += f"| [{i}]({msg['url']}) | {speaker_icon} | {ts_formatted} | {preview} |\n"
        else:
            toc += f"| {i} | {speaker_icon} | {ts_formatted} | {preview} |\n"

    if not messages:
        toc += "| - | - | - | *No messages yet* |\n"

    toc += f"\n{TOC_END_MARKER}"

    return toc


def create_toc_comment(issue_num: int, content: str) -> Optional[str]:
    """Create a new TOC comment on the issue."""
    debug_log(f"create_toc_comment() called for issue #{issue_num}")
    try:
        result = subprocess.run(
            ["gh", "issue", "comment", str(issue_num), "--body", content],
            capture_output=True,
            text=True,
            check=False,
            cwd=get_plugin_repo_root(),
            timeout=30,
        )
        if result.returncode == 0:
            debug_log(f"Created TOC comment on issue #{issue_num}")
            debug_print(f"Created TOC comment on issue #{issue_num}")
            return result.stdout.strip()
        else:
            debug_log(f"Failed to create TOC: {result.stderr}", "ERROR")
            debug_print(f"Failed to create TOC: {result.stderr}")
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        debug_log(f"Error creating TOC: {e}", "ERROR")
        debug_print(f"Error creating TOC: {e}")
    return None


def update_toc_comment(issue_num: int, comment_url: str, content: str) -> bool:
    """Update an existing TOC comment."""
    debug_log(f"update_toc_comment() called for issue #{issue_num}, url={comment_url}")
    # Extract comment ID from URL (format: .../issues/N#issuecomment-XXXXXX)
    match = re.search(r"issuecomment-(\d+)", comment_url)
    if not match:
        debug_log(f"Could not extract comment ID from URL: {comment_url}", "ERROR")
        debug_print(f"Could not extract comment ID from URL: {comment_url}")
        return False

    comment_id = match.group(1)
    debug_log(f"Extracted comment_id={comment_id}")

    try:
        # Use :owner/:repo syntax which gh CLI expands automatically
        result = subprocess.run(
            [
                "gh",
                "api",
                "-X",
                "PATCH",
                f"repos/:owner/:repo/issues/comments/{comment_id}",
                "-f",
                f"body={content}",
            ],
            capture_output=True,
            text=True,
            check=False,
            cwd=get_plugin_repo_root(),
            timeout=30,
        )
        if result.returncode == 0:
            debug_log(f"Updated TOC comment {comment_id}")
            debug_print(f"Updated TOC comment {comment_id}")
            return True
        else:
            debug_log(f"Failed to update TOC: {result.stderr}", "ERROR")
            debug_print(f"Failed to update TOC: {result.stderr}")
    except (subprocess.TimeoutExpired, subprocess.SubprocessError) as e:
        debug_log(f"Error updating TOC: {e}", "ERROR")
        debug_print(f"Error updating TOC: {e}")
    return False


def update_toc(issue_num: int) -> bool:
    """
    Update or create the TOC for an issue.

    Returns True if successful.
    """
    debug_log(f"update_toc() called for issue #{issue_num}")
    debug_print(f"Updating TOC for issue #{issue_num}")

    # Fetch all comments
    comments = get_issue_comments(issue_num)
    if not comments:
        debug_log("No comments found or failed to fetch", "WARN")
        debug_print("No comments found or failed to fetch")
        # Still try to create TOC even with no messages
        pass

    # Extract message info from each comment
    messages = []
    toc_comment = None

    for comment in comments:
        if TOC_MARKER in comment.get("body", ""):
            toc_comment = comment
            continue

        msg_info = extract_message_info(comment)
        if msg_info:
            messages.append(msg_info)

    debug_log(
        f"Found {len(messages)} transcribed messages, TOC exists: {toc_comment is not None}"
    )

    # Generate TOC content
    toc_content = generate_toc_content(messages, issue_num)

    # Update or create TOC
    if toc_comment:
        # Update existing TOC
        toc_url = toc_comment.get("url", "")
        debug_log(f"Updating existing TOC comment at {toc_url}")
        return update_toc_comment(issue_num, toc_url, toc_content)
    else:
        # Create new TOC as first comment
        debug_log("Creating new TOC comment")
        result = create_toc_comment(issue_num, toc_content)
        return result is not None


def get_toc_id(issue_num: int) -> Optional[str]:
    """Get the TOC comment ID for an issue."""
    debug_log(f"get_toc_id() called for issue #{issue_num}")
    comments = get_issue_comments(issue_num)
    toc_comment = find_toc_comment(comments)

    if toc_comment:
        url = toc_comment.get("url", "")
        match = re.search(r"issuecomment-(\d+)", url)
        if match:
            toc_id = match.group(1)
            debug_log(f"Found TOC comment ID: {toc_id}")
            return toc_id

    debug_log("No TOC comment found", "WARN")
    return None


def main() -> None:
    """Main entry point."""
    debug_log(f"main() called with args: {sys.argv}")
    if len(sys.argv) < 3:
        debug_log("Insufficient arguments provided", "ERROR")
        print("Usage: toc_manager.py <update|get-id> <issue_number>", file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1].lower()
    try:
        issue_num = int(sys.argv[2])
    except ValueError:
        debug_log(f"Invalid issue number: {sys.argv[2]}", "ERROR")
        print(f"Invalid issue number: {sys.argv[2]}", file=sys.stderr)
        sys.exit(1)

    debug_log(f"Executing command '{command}' for issue #{issue_num}")
    if command == "update":
        success = update_toc(issue_num)
        debug_log(f"update_toc returned: {success}")
        sys.exit(0 if success else 1)
    elif command == "get-id":
        toc_id = get_toc_id(issue_num)
        if toc_id:
            debug_log(f"Found TOC ID: {toc_id}")
            print(toc_id)
            sys.exit(0)
        else:
            debug_log("No TOC found for issue", "WARN")
            print("No TOC found", file=sys.stderr)
            sys.exit(1)
    else:
        debug_log(f"Unknown command: {command}", "ERROR")
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
