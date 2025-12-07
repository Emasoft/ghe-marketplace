#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""
Background Transcription Worker for GHE

This worker runs in the background and posts WAL entries to GitHub.
It ensures:
- Chronological ordering (by sequence number)
- Correct speaker attribution (user=username, claude="Claude")
- Deduplication (via content hash)
- Retry with exponential backoff
- Single worker instance (via file locking)

This script is spawned by capture_claude.py and session_start.py.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add scripts directory to path for imports
_script_dir = Path(__file__).parent.resolve()
if str(_script_dir) not in sys.path:
    sys.path.insert(0, str(_script_dir))

from wal_manager import (
    wal_read_unposted,
    wal_mark_posted,
    wal_find_by_hash,
    acquire_worker_lock,
    release_worker_lock,
    get_wal_path,
)


# Element type badges
BADGE_KNOWLEDGE = "![](https://img.shields.io/badge/element-knowledge-blue)"
BADGE_ACTION = "![](https://img.shields.io/badge/element-action-green)"
BADGE_JUDGEMENT = "![](https://img.shields.io/badge/element-judgement-orange)"


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to hook_debug.log."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [transcription_worker] - {message}\n")
    except Exception:
        pass


def get_repo_path() -> str:
    """
    Get the repository path from config.

    Returns:
        Path to the repository root
    """
    # Find .claude directory
    cwd = Path.cwd()
    claude_dir = cwd / ".claude"
    if not claude_dir.exists():
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                claude_dir = parent / ".claude"
                break
        else:
            return str(cwd)

    # Try ghe.local.md for repo_path
    config_file = claude_dir / "ghe.local.md"
    if config_file.exists():
        try:
            with open(config_file) as f:
                content = f.read()
            match = re.search(r'^repo_path:\s*["\']?([^"\'\n]+)["\']?', content, re.MULTILINE)
            if match:
                path = match.group(1).strip()
                if path and Path(path).is_dir():
                    return path
        except IOError:
            pass

    return str(cwd)


def run_gh(*args: str, cwd: Optional[str] = None) -> subprocess.CompletedProcess:
    """
    Run gh command in the correct repo directory.

    Args:
        *args: Arguments to pass to gh
        cwd: Working directory (defaults to repo path)

    Returns:
        CompletedProcess result
    """
    repo_root = cwd or get_repo_path()
    return subprocess.run(
        ["gh"] + list(args),
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def get_github_username() -> str:
    """Get the current GitHub username."""
    # Check environment first
    env_user = os.environ.get("GITHUB_OWNER") or os.environ.get("GITHUB_USER")
    if env_user:
        return env_user

    try:
        result = run_gh("api", "user", "--jq", ".login")
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
        pass

    try:
        result = subprocess.run(
            ["git", "config", "user.name"],
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (subprocess.SubprocessError, subprocess.TimeoutExpired):
        pass

    return "unknown"


def get_avatar_url(speaker: str, is_user: bool) -> str:
    """
    Get avatar URL for a speaker.

    Args:
        speaker: Speaker name ("user" or "claude")
        is_user: True if this is a user message

    Returns:
        Avatar URL
    """
    if is_user:
        username = get_github_username()
        return f"https://avatars.githubusercontent.com/{username}?s=81"
    else:
        # Claude avatar from plugin assets
        # Get base URL dynamically
        try:
            result = run_gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
            if result.returncode == 0 and result.stdout.strip():
                repo = result.stdout.strip()
                return f"https://raw.githubusercontent.com/{repo}/main/plugins/ghe/assets/avatars/claude.png"
        except (subprocess.SubprocessError, subprocess.TimeoutExpired):
            pass
        # Fallback to Emasoft repo
        return "https://raw.githubusercontent.com/Emasoft/ghe-marketplace/main/plugins/ghe/assets/avatars/claude.png"


def redact_sensitive(text: str) -> str:
    """Redact sensitive data from text."""
    # API keys
    text = re.sub(r"sk-ant-[a-zA-Z0-9_-]+", "[REDACTED_API_KEY]", text)
    text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_KEY]", text)
    text = re.sub(r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GH_TOKEN]", text)
    text = re.sub(r"gho_[a-zA-Z0-9]{36}", "[REDACTED_GH_TOKEN]", text)

    # Passwords
    text = re.sub(
        r"(password|passwd|pwd|secret|token|key)([\"']?\s*[:=]\s*[\"']?)[^\"'\s]+",
        r"\1\2[REDACTED]",
        text,
        flags=re.IGNORECASE,
    )

    # User home paths
    text = re.sub(r"/Users/[^/]+/", "/Users/[USER]/", text)
    text = re.sub(r"/home/[^/]+/", "/home/[USER]/", text)

    # Email addresses (except noreply)
    text = re.sub(
        r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "[REDACTED_EMAIL]",
        text,
    )
    text = re.sub(
        r"\[REDACTED_EMAIL\](@users\.noreply\.github\.com)",
        r"\1",
        text,
    )

    return text


def classify_element(content: str) -> str:
    """Classify content into element types and return badges."""
    badges = []

    # Knowledge indicators
    knowledge_pattern = r"(spec|requirement|design|algorithm|api|schema|architecture|protocol|format|structure|definition|concept|theory|documentation|how.*(work|function)|explain|what is|overview)"
    if re.search(knowledge_pattern, content, re.IGNORECASE):
        badges.append(BADGE_KNOWLEDGE)

    # Action indicators
    action_patterns = [
        r"(```|diff|patch|function |class |def |const |let |var |import |export |<[a-z]+>)",
        r"\.(py|js|ts|jsx|tsx|md|yml|yaml|json|xml|html|css|scss|sass|less|sh|bash|zsh|rb|go|rs|java|kt|swift|c|cpp|h|hpp)",
        r"(create[d]?|implement|writ(e|ten)|add(ed)?|modif(y|ied)|edit(ed)?|fix(ed)?|update[d]?|refactor)",
    ]
    for pattern in action_patterns:
        if re.search(pattern, content, re.IGNORECASE):
            if BADGE_ACTION not in badges:
                badges.append(BADGE_ACTION)
            break

    # Judgement indicators
    judgement_pattern = r"(bug|error|issue|problem|fail|broken|wrong|missing|review|feedback|test|should|must|need|improve|concern)"
    if re.search(judgement_pattern, content, re.IGNORECASE):
        if BADGE_JUDGEMENT not in badges:
            badges.append(BADGE_JUDGEMENT)

    if not badges:
        badges.append(BADGE_KNOWLEDGE)

    return " ".join(badges)


def get_or_create_fallback_issue() -> Optional[int]:
    """Get or create a fallback issue for messages without an issue."""
    # Search for existing fallback issue
    try:
        result = run_gh(
            "issue", "list",
            "--search", "GENERAL DISCUSSION in:title",
            "--state", "open",
            "--json", "number,title",
            "--limit", "1",
        )
        if result.returncode == 0:
            issues = json.loads(result.stdout)
            if issues:
                return issues[0]["number"]

        # Create new fallback issue
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        result = run_gh(
            "issue", "create",
            "--title", f"[GENERAL] GENERAL DISCUSSION - {timestamp}",
            "--label", "general,auto-created",
            "--body", """## General Discussion Thread

This issue was auto-created as a fallback for transcription when no specific issue is configured.

---
**Auto-created by GHE Transcription Worker**
""",
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            if "/issues/" in url:
                return int(url.split("/issues/")[-1])
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, ValueError, json.JSONDecodeError) as e:
        debug_log(f"Error creating fallback issue: {e}", "ERROR")

    return None


def fetch_recent_comments(issue_num: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Fetch recent comments from an issue for deduplication."""
    try:
        result = run_gh("issue", "view", str(issue_num), "--json", "comments")
        if result.returncode == 0:
            data = json.loads(result.stdout)
            comments = data.get("comments", [])
            # Return last N comments
            return comments[-limit:]
    except (subprocess.SubprocessError, subprocess.TimeoutExpired, json.JSONDecodeError):
        pass
    return []


def compute_content_hash(content: str) -> str:
    """Compute hash of content for deduplication."""
    normalized = " ".join(content.lower().split())
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def is_already_posted(issue_num: int, content_hash: str) -> Optional[str]:
    """
    Check if content is already posted to the issue.

    Returns comment ID if found, None otherwise.
    """
    comments = fetch_recent_comments(issue_num)
    for comment in comments:
        body = comment.get("body", "")
        if compute_content_hash(body) == content_hash:
            return comment.get("id", "duplicate")
    return None


def post_entry_to_github(entry: Dict[str, Any]) -> Optional[str]:
    """
    Post a WAL entry to GitHub.

    Args:
        entry: WAL entry dict

    Returns:
        Comment ID on success, None on failure
    """
    issue_num = entry.get("issue", 0)
    speaker = entry.get("speaker", "unknown")
    content = entry.get("content", "")
    content_hash = entry.get("hash", "")

    if not content:
        debug_log("Empty content, skipping", "WARN")
        return "skipped-empty"

    # Handle issue=0 (no issue was configured when captured)
    if not issue_num or issue_num == 0:
        fallback = get_or_create_fallback_issue()
        if fallback:
            issue_num = fallback
            debug_log(f"Using fallback issue #{fallback}")
        else:
            debug_log("No issue and failed to create fallback", "ERROR")
            return None

    # Check if already posted (deduplication)
    existing_id = is_already_posted(issue_num, content_hash)
    if existing_id:
        debug_log(f"Already posted (hash={content_hash}), skipping")
        return existing_id

    # Determine speaker details
    is_user = speaker == "user"
    if is_user:
        display_name = get_github_username()
    else:
        display_name = "Claude"  # ALWAYS "Claude" for assistant messages!

    avatar_url = get_avatar_url(speaker, is_user)

    # Prepare content
    safe_content = redact_sensitive(content)
    badges = classify_element(safe_content)

    # Format comment
    comment_body = f"""<p><img src="{avatar_url}" width="81" height="81" alt="{display_name}" align="middle">&nbsp;&nbsp;&nbsp;&nbsp;<span style="vertical-align: middle;"><strong>{display_name} said:</strong></span></p>

{safe_content}

---

{badges}"""

    # Post to GitHub
    try:
        result = run_gh("issue", "comment", str(issue_num), "--body", comment_body)
        if result.returncode == 0:
            # Extract comment ID from URL if possible
            url = result.stdout.strip()
            if "#issuecomment-" in url:
                comment_id = url.split("#issuecomment-")[-1]
            else:
                comment_id = f"posted-{datetime.now(timezone.utc).isoformat()}"
            debug_log(f"Posted seq={entry.get('seq')} to issue #{issue_num}")
            return comment_id
        else:
            debug_log(f"gh command failed: {result.stderr}", "ERROR")
            return None
    except (subprocess.SubprocessError, subprocess.TimeoutExpired) as e:
        debug_log(f"Post failed: {e}", "ERROR")
        return None


def process_wal_entries() -> int:
    """
    Process all unposted WAL entries.

    Returns:
        Number of entries successfully posted
    """
    entries = wal_read_unposted()
    if not entries:
        debug_log("No unposted entries")
        return 0

    # Sort by sequence number (CRITICAL for chronological order)
    entries.sort(key=lambda e: e.get("seq", 0))

    debug_log(f"Processing {len(entries)} unposted entries")

    posted_count = 0
    retry_delays = [1, 2, 4, 8, 16]  # Exponential backoff

    for entry in entries:
        seq = entry.get("seq", 0)
        retries = 0
        success = False

        while retries <= len(retry_delays):
            comment_id = post_entry_to_github(entry)

            if comment_id:
                # Mark as posted in WAL
                if wal_mark_posted(seq, comment_id):
                    debug_log(f"Marked seq={seq} as posted")
                    posted_count += 1
                    success = True
                    break
                else:
                    debug_log(f"Failed to mark seq={seq} as posted", "WARN")
                    success = True  # Still consider it success, just WAL update failed
                    break
            else:
                # Retry with backoff
                if retries < len(retry_delays):
                    delay = retry_delays[retries]
                    debug_log(f"Retry {retries + 1} for seq={seq} in {delay}s")
                    time.sleep(delay)
                    retries += 1
                else:
                    debug_log(f"Max retries exceeded for seq={seq}", "ERROR")
                    break

        # Rate limiting between successful posts
        if success:
            time.sleep(0.5)

    return posted_count


def main() -> None:
    """Main entry point for the background worker."""
    debug_log("Transcription worker starting")

    # Acquire exclusive lock
    lock_file = acquire_worker_lock()
    if not lock_file:
        debug_log("Another worker is running, exiting")
        sys.exit(0)

    try:
        posted = process_wal_entries()
        debug_log(f"Worker completed, posted {posted} entries")
    except Exception as e:
        debug_log(f"Worker error: {e}", "ERROR")
    finally:
        release_worker_lock(lock_file)
        debug_log("Worker released lock and exiting")


if __name__ == "__main__":
    main()
