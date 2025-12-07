#!/usr/bin/env python3
"""
GHE Auto-Transcribe System
Posts every conversation exchange to GitHub issues with element classification
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional

# Import from ghe_common module
try:
    import ghe_common
except ImportError:
    print("Error: Cannot import from ghe_common module", file=sys.stderr)
    sys.exit(1)

# Initialize GHE environment - MUST be called before accessing global variables
ghe_common.ghe_init()

# Now import the initialized variables
from ghe_common import (
    GHE_PLUGIN_ROOT,
    GHE_CONFIG_FILE,
    GHE_REPO_ROOT,
    GHE_RED,
    GHE_GREEN,
    GHE_YELLOW,
    GHE_NC,
    GHE_AGENT_AVATARS,
    ghe_get_setting,
    ghe_get_github_user,
    ghe_get_avatar_url,
)

# Legacy aliases for compatibility with existing code
PLUGIN_ROOT = GHE_PLUGIN_ROOT
CONFIG_FILE = GHE_CONFIG_FILE
REPO_ROOT = GHE_REPO_ROOT

# Colors (using library colors)
RED = GHE_RED
GREEN = GHE_GREEN
YELLOW = GHE_YELLOW
NC = GHE_NC

# Use GHE_AGENT_AVATARS from ghe_common as the single source of truth
AVATARS = GHE_AGENT_AVATARS

# Element type badges (GitHub-friendly markdown) - no alt text, just badges
BADGE_KNOWLEDGE = "![](https://img.shields.io/badge/element-knowledge-blue)"
BADGE_ACTION = "![](https://img.shields.io/badge/element-action-green)"
BADGE_JUDGEMENT = "![](https://img.shields.io/badge/element-judgement-orange)"


def get_avatar_url(name: str) -> str:
    """
    Get avatar URL - checks agents first, then falls back to GitHub user avatar.
    Uses centralized ghe_get_avatar_url from ghe_common.

    Args:
        name: Agent name or GitHub username

    Returns:
        Avatar URL
    """
    # Use centralized function from ghe_common
    return ghe_get_avatar_url(name)


def check_github_repo() -> bool:
    """
    Check if we have a GitHub repo

    Returns:
        True if GitHub repo is configured, False otherwise
    """
    # Use REPO_ROOT for all git operations (handles nested repos)
    try:
        subprocess.run(
            ["git", "-C", REPO_ROOT, "rev-parse", "--git-dir"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        print("Not a git repository", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            ["git", "-C", REPO_ROOT, "remote", "get-url", "origin"],
            capture_output=True,
            text=True,
        )
        remote = result.stdout.strip()
        if not remote or "github.com" not in remote:
            print("No GitHub remote found", file=sys.stderr)
            return False
    except subprocess.CalledProcessError:
        print("No GitHub remote found", file=sys.stderr)
        return False

    # Verify gh is authenticated
    try:
        subprocess.run(
            ["gh", "auth", "status"],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError:
        print("GitHub CLI not authenticated", file=sys.stderr)
        return False

    return True


def run_gh(*args: str) -> subprocess.CompletedProcess:
    """
    Run gh commands from REPO_ROOT
    This ensures gh finds the correct GitHub remote

    Args:
        *args: Arguments to pass to gh command

    Returns:
        CompletedProcess result
    """
    return subprocess.run(
        ["gh"] + list(args),
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )


def ensure_config() -> None:
    """
    Get or create config file
    """
    if not Path(CONFIG_FILE).exists():
        Path(CONFIG_FILE).parent.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            f.write("""---
enabled: true
auto_transcribe: true
current_issue: null
current_phase: null
session_id: null
---

# GHE Auto-Transcribe Configuration

Auto-transcription is enabled. All conversations will be recorded to GitHub issues.
""")


def get_config(key: str, default: str = "") -> str:
    """
    Read config value

    Args:
        key: Configuration key
        default: Default value if key not found

    Returns:
        Configuration value or default
    """
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r") as f:
            content = f.read()
            # Extract value from YAML frontmatter
            pattern = rf"^{re.escape(key)}:\s*(.*)$"
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                value = match.group(1).strip().strip('"').strip("'")
                if value and value != "null":
                    return value
    return default


def set_config(key: str, value: str) -> None:
    """
    Update config value

    Args:
        key: Configuration key
        value: New value
    """
    if Path(CONFIG_FILE).exists():
        with open(CONFIG_FILE, "r") as f:
            content = f.read()

        # Check if key exists
        pattern = rf"^{re.escape(key)}:.*$"
        if re.search(pattern, content, re.MULTILINE):
            # Update existing
            content = re.sub(pattern, f"{key}: {value}", content, flags=re.MULTILINE)
        else:
            # Add after frontmatter opening
            content = re.sub(r"^---$", f"---\n{key}: {value}", content, count=1, flags=re.MULTILINE)

        with open(CONFIG_FILE, "w") as f:
            f.write(content)


def redact_sensitive(text: str) -> str:
    """
    Redact sensitive data

    Args:
        text: Text to redact

    Returns:
        Redacted text
    """
    # Redact API keys
    text = re.sub(r"sk-ant-[a-zA-Z0-9_-]+", "[REDACTED_API_KEY]", text)
    text = re.sub(r"sk-[a-zA-Z0-9]{20,}", "[REDACTED_KEY]", text)
    text = re.sub(r"ghp_[a-zA-Z0-9]{36}", "[REDACTED_GH_TOKEN]", text)
    text = re.sub(r"gho_[a-zA-Z0-9]{36}", "[REDACTED_GH_TOKEN]", text)

    # Redact passwords in common patterns
    text = re.sub(
        r"(password|passwd|pwd|secret|token|key)([\"']?\s*[:=]\s*[\"']?)[^\"'\s]+",
        r"\1\2[REDACTED]",
        text,
        flags=re.IGNORECASE,
    )

    # Redact user home paths (keep structure visible)
    text = re.sub(r"/Users/[^/]+/", "/Users/[USER]/", text)
    text = re.sub(r"/home/[^/]+/", "/home/[USER]/", text)

    # Redact email addresses (except noreply)
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
    """
    Classify content into element types

    Args:
        content: Content to classify

    Returns:
        Badge string with element classifications
    """
    badges = []

    # Check for KNOWLEDGE indicators
    knowledge_pattern = r"(spec|requirement|design|algorithm|api|schema|architecture|protocol|format|structure|definition|concept|theory|documentation|how.*(work|function)|explain|what is|overview)"
    if re.search(knowledge_pattern, content, re.IGNORECASE):
        badges.append(BADGE_KNOWLEDGE)

    # Check for ACTION indicators (code, assets, any concrete project artifacts)
    # ACTION = tangible changes to the project: code, images, sounds, video, 3D, stylesheets, configs
    action_indicators = [
        r"(```|diff|patch|function |class |def |const |let |var |import |export |<[a-z]+>)",
        r"\.(py|js|ts|jsx|tsx|md|yml|yaml|json|xml|html|css|scss|sass|less|sh|bash|zsh|rb|go|rs|java|kt|swift|c|cpp|h|hpp)",
        r"\.(png|jpg|jpeg|gif|svg|ico|webp|avif|bmp|tiff|mp3|wav|ogg|flac|aac|m4a|mp4|webm|avi|mov|mkv|glb|gltf|obj|fbx|blend|dae|3ds|ttf|otf|woff|woff2|eot)",
        r"(raw\.githubusercontent\.com|github\.com/.*/blob/|cdn\.|assets/|images/|sprites/|textures/|sounds/|audio/|video/|models/|fonts/)",
        r"(create[d]?|implement|writ(e|ten)|add(ed)?|modif(y|ied)|edit(ed)?|fix(ed)?|update[d]?|refactor|upload(ed)?|commit(ted)?|push(ed)?|deploy(ed)?|built|generat(e|ed)|render(ed)?|compil(e|ed)|export(ed)?|import(ed)?|install(ed)?|reinstall(ed)?|uninstall(ed)?|run|ran|execut(e|ed)|launch(ed)?|start(ed)?|stop(ped)?|restart(ed)?)",
        r"(asset[s]?|sprite[s]?|icon[s]?|graphic[s]?|image[s]?|texture[s]?|sound[s]?|audio|video|model[s]?|animation[s]?|stylesheet|font[s]?|avatar[s]?|logo|banner|thumbnail|screenshot)",
    ]

    for pattern in action_indicators:
        if re.search(pattern, content, re.IGNORECASE):
            if BADGE_ACTION not in badges:
                badges.append(BADGE_ACTION)
            break

    # Check for JUDGEMENT indicators
    judgement_pattern = r"(bug|error|issue|problem|fail|broken|wrong|missing|review|feedback|test|should|must|need|improve|concern|question|why|critique|evaluate|assess|verdict|pass|reject)"
    if re.search(judgement_pattern, content, re.IGNORECASE):
        if BADGE_JUDGEMENT not in badges:
            badges.append(BADGE_JUDGEMENT)

    # Default to knowledge if no classification
    if not badges:
        badges.append(BADGE_KNOWLEDGE)

    return " ".join(badges)


def extract_explicit_issue(text: str) -> Optional[str]:
    """
    Extract explicit issue number from text

    Patterns expanded to recognize:
      - Context marker: [Currently discussing issue n.123]
      - Bracketed: [issue #123], [Issue #123]
      - GitHub URLs: https://github.com/OWNER/REPO/issues/123
      - Action words with #: work on #123, claim #123, fix #123
      - Action words without #: work on issue 123, claim 123
      - Simple: issue 123, Issue 123
      - Standalone hash: #123 (word boundary)

    Args:
        text: Text to search for issue reference

    Returns:
        Issue number as string, or None if not found
    """
    # Pattern 1: [Currently discussing issue n.123] - context marker
    match = re.search(r"\[Currently discussing issue n\.(\d+)\]", text)
    if match:
        return match.group(1)

    # Pattern 2: [issue #123] or [Issue #123] - bracketed format
    match = re.search(r"\[[Ii]ssue #(\d+)\]", text)
    if match:
        return match.group(1)

    # Pattern 3: GitHub URL - https://github.com/OWNER/REPO/issues/123
    match = re.search(r"github\.com/[^/]+/[^/]+/issues/(\d+)", text)
    if match:
        return match.group(1)

    # Pattern 4: Action words with # - work on #123, working on issue #123
    match = re.search(r"[Ww]ork(?:ing)? on (?:issue )?#(\d+)", text)
    if match:
        return match.group(1)

    # Pattern 5: Action words with # - lets work on #123
    match = re.search(r"[Ll]ets? work on (?:issue )?#(\d+)", text)
    if match:
        return match.group(1)

    # Pattern 6: claim/fix/resume/close/check with # - claim #123, fix #123
    match = re.search(r"(?:[Cc]laim|[Ff]ix|[Rr]esume|[Cc]lose|[Cc]heck) (?:issue )?#(\d+)", text)
    if match:
        return match.group(1)

    # Pattern 7: Action words WITHOUT # - work on issue 123, work on 123
    match = re.search(r"[Ww]ork(?:ing)? on (?:issue )?(\d+)", text)
    if match:
        return match.group(1)

    # Pattern 8: lets work on issue 123 or lets work on 123
    match = re.search(r"[Ll]ets? work on (?:issue )?(\d+)", text)
    if match:
        return match.group(1)

    # Pattern 9: claim/fix/resume/close/check WITHOUT # - claim 123, fix issue 123
    match = re.search(r"(?:[Cc]laim|[Ff]ix|[Rr]esume|[Cc]lose|[Cc]heck) (?:issue )?(\d+)", text)
    if match:
        return match.group(1)

    # Pattern 10: Simple "issue 123" or "Issue 123" (case insensitive)
    match = re.search(r"[Ii]ssue (\d+)", text)
    if match:
        return match.group(1)

    # Pattern 11: Standalone #123 at word boundary (not part of other text)
    # Must be at start, after space, or end of string
    match = re.search(r"(?:^|\s)#(\d+)(?:$|\s)", text)
    if match:
        return match.group(1)

    return None


def find_or_create_issue(topic: str) -> Optional[str]:
    """
    Find or create issue for conversation

    Args:
        topic: Conversation topic

    Returns:
        Issue number as string, or None on failure
    """
    # FIRST: Check for explicit issue mention in the message
    explicit_issue = extract_explicit_issue(topic)
    if explicit_issue:
        # Verify it exists (open or closed - we can still post to closed issues)
        try:
            result = run_gh("issue", "view", explicit_issue, "--json", "number", "--jq", ".number")
            if result.stdout.strip() == explicit_issue:
                set_config("current_issue", explicit_issue)
                return explicit_issue
        except subprocess.CalledProcessError:
            pass

    current_issue = get_config("current_issue", "")

    # If we have an active issue, use it
    if current_issue and current_issue != "null":
        # Verify it still exists and is open
        try:
            result = run_gh("issue", "view", current_issue, "--json", "state", "--jq", ".state")
            if "OPEN" in result.stdout:
                return current_issue
        except subprocess.CalledProcessError:
            pass

    # Try to find an existing open issue matching the topic
    keywords = " ".join(
        word for word in re.findall(r"[a-z]{4,}", topic.lower())[:5]
    )

    if keywords:
        try:
            result = run_gh("issue", "list", "--state", "open", "--limit", "10", "--json", "number,title,body")
            issues = json.loads(result.stdout)

            # Filter for matching issues
            first_keyword = keywords.split()[0]
            for issue in issues:
                searchable = (issue.get("title", "") + " " + issue.get("body", "")).lower()
                if first_keyword in searchable:
                    found_issue = str(issue["number"])
                    set_config("current_issue", found_issue)
                    return found_issue
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass

    # Create a new session issue
    session_id = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    title = f"[SESSION] Development Session {session_id}"

    body = f"""## Development Session

**Started**: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")}
**Session ID**: {session_id}

This issue tracks the conversation and work done during this development session.

---

### Element Types

--- {BADGE_KNOWLEDGE} {BADGE_ACTION} {BADGE_JUDGEMENT}

---
"""

    try:
        result = run_gh("issue", "create", "--title", title, "--label", "session", "--body", body)
        # Extract issue number from URL (format: https://github.com/owner/repo/issues/N)
        issue_url = result.stdout.strip()
        match = re.search(r"/(\d+)$", issue_url)
        if match:
            new_issue = match.group(1)
            set_config("current_issue", new_issue)
            set_config("session_id", session_id)
            return new_issue
    except subprocess.CalledProcessError:
        pass

    return None


def linkify_content(content: str) -> str:
    """
    Transform local references to GitHub links for better traceability
    NOTE: Uses temp file to avoid issues with special characters in content

    Args:
        content: Content to linkify

    Returns:
        Linkified content
    """
    try:
        result = run_gh("repo", "view", "--json", "nameWithOwner", "--jq", ".nameWithOwner")
        repo = result.stdout.strip()
    except subprocess.CalledProcessError:
        return content

    if not repo or not content:
        return content

    # Use a temp file to avoid sed issues with special characters
    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".txt") as tmpfile:
        tmpfile.write(content)
        tmpfile_path = tmpfile.name

    try:
        # Transform file:line references (e.g., `file.py:42`)
        subprocess.run(
            [
                "sed",
                "-i.bak",
                "-E",
                rf"s@`([a-zA-Z0-9_/.-]+\.(py|js|ts|md|yaml|yml|json|sh)):([0-9]+)`@[`\1:\3`](https://github.com/{repo}/blob/main/\1#L\3)@g",
                tmpfile_path,
            ],
            check=False,
        )

        # Transform REQUIREMENTS references
        subprocess.run(
            [
                "sed",
                "-i.bak",
                "-E",
                rf"s@\bREQUIREMENTS/([^[:space:])\"]+\.md)@[REQUIREMENTS/\1](https://github.com/{repo}/blob/main/REQUIREMENTS/\1)@g",
                tmpfile_path,
            ],
            check=False,
        )

        # Transform REQ-XXX references to search links
        subprocess.run(
            [
                "sed",
                "-i.bak",
                "-E",
                rf"s@\b(REQ-[0-9]{{3}})\b@[\1](https://github.com/{repo}/search?q=\1)@g",
                tmpfile_path,
            ],
            check=False,
        )

        # Transform issue references if not already linked (avoid double-linking)
        subprocess.run(
            [
                "sed",
                "-i.bak",
                "-E",
                rf"s@([^[])#([0-9]+)([^]])@\1[#\2](https://github.com/{repo}/issues/\2)\3@g",
                tmpfile_path,
            ],
            check=False,
        )

        # Read result
        with open(tmpfile_path, "r") as f:
            result_content = f.read()

        return result_content
    finally:
        # Cleanup
        Path(tmpfile_path).unlink(missing_ok=True)
        Path(f"{tmpfile_path}.bak").unlink(missing_ok=True)


def post_to_issue(issue_num: str, speaker: str, message: str, is_user: bool = False) -> None:
    """
    Post message to issue

    Args:
        issue_num: Issue number
        speaker: Speaker name (agent or username)
        message: Message content
        is_user: Whether this is a user message
    """
    # Get avatar - use get_avatar_url which handles both agents and GitHub users
    avatar_url = get_avatar_url(speaker)

    # Redact sensitive data
    safe_message = redact_sensitive(message)

    # Linkify content (convert local paths to GitHub links)
    linkified_message = linkify_content(safe_message)

    # Classify element
    badges = classify_element(linkified_message)

    # Format the comment - new style with 81x81 avatar
    comment = f"""<p><img src="{avatar_url}" width="81" height="81" alt="{speaker}" align="middle">&nbsp;&nbsp;&nbsp;&nbsp;<span style="vertical-align: middle;"><strong>{speaker} said:</strong></span></p>

{linkified_message}

---

{badges}"""

    # Post to GitHub
    run_gh("issue", "comment", issue_num, "--body", comment)

    # Update TOC after posting
    try:
        scripts_dir = Path(__file__).parent
        subprocess.run(
            ['python3', str(scripts_dir / 'toc_manager.py'), 'update', str(issue_num)],
            capture_output=True, check=False, timeout=30
        )
    except (subprocess.TimeoutExpired, subprocess.SubprocessError):
        pass  # TOC update is non-critical, don't block on failure


def post_user_message(message: str) -> bool:
    """
    Main: Post user message

    Args:
        message: User message

    Returns:
        True on success, False on failure
    """
    if not check_github_repo():
        return False

    ensure_config()

    # Check if enabled
    if get_config("enabled", "true") != "true":
        return True

    if get_config("auto_transcribe", "true") != "true":
        return True

    # Get or create issue
    issue = find_or_create_issue(message)

    if issue:
        post_to_issue(issue, ghe_get_github_user(), message, True)
        print(f"Posted to issue #{issue}")
        return True

    return False


def get_posting_agent(issue_num: str, requested_agent: Optional[str] = None) -> str:
    """
    Get appropriate posting agent based on issue phase
    - Epic issues: Always Athena
    - Normal issues: Phase manager (Hephaestus/Artemis/Hera)

    Args:
        issue_num: Issue number
        requested_agent: Explicitly requested agent name

    Returns:
        Agent name
    """
    # If agent explicitly requested, always use it
    if requested_agent:
        return requested_agent

    # Check if epic issue (has epic label)
    try:
        result = run_gh("issue", "view", issue_num, "--json", "labels", "--jq", ".labels[].name")
        labels = result.stdout.lower()

        if "epic" in labels:
            return "Athena"

        # For normal issues, determine manager from phase
        if "phase:review" in labels:
            return "Hera"
        elif "phase:test" in labels:
            return "Artemis"
        else:
            return "Hephaestus"  # Default to DEV manager
    except subprocess.CalledProcessError:
        return "Hephaestus"  # Default fallback


def post_assistant_message(message: str, requested_agent: Optional[str] = None) -> bool:
    """
    Main: Post assistant message

    Args:
        message: Assistant message
        requested_agent: Explicitly requested agent name

    Returns:
        True on success, False on failure
    """
    if not check_github_repo():
        return False

    ensure_config()

    # Check if enabled
    if get_config("enabled", "true") != "true":
        return True

    if get_config("auto_transcribe", "true") != "true":
        return True

    issue = get_config("current_issue", "")

    if issue and issue != "null":
        # Get appropriate agent based on issue phase (Athena only for epics)
        agent = get_posting_agent(issue, requested_agent)
        post_to_issue(issue, agent, message, False)
        print(f"Posted to issue #{issue} as {agent}")
        return True

    return False


def inject_claude_md_reminder(issue_num: str, title: str = "") -> None:
    """
    Inject issue reminder into project CLAUDE.md

    Args:
        issue_num: Issue number
        title: Issue title (optional, fetched from GitHub if not provided)
    """
    # Fetch title from GitHub if not provided
    if not title:
        try:
            result = run_gh("issue", "view", issue_num, "--json", "title", "--jq", ".title")
            title = result.stdout.strip()
        except subprocess.CalledProcessError:
            title = ""

    claude_md = Path("CLAUDE.md")
    marker = "<!-- GHE-CURRENT-ISSUE -->"

    # Format title line if available
    title_line = f": {title}" if title else ""

    instruction = f"""
{marker}
## GHE Active Transcription

**CRITICAL**: All conversation is being transcribed to GitHub.

```
Currently discussing issue n.{issue_num}{title_line}
```

**You MUST include this line in your responses when referencing the current work.**
{marker}
"""

    if claude_md.exists():
        content = claude_md.read_text()

        # Remove any existing GHE section
        if marker in content:
            # Remove existing block (between markers)
            content = re.sub(
                rf"{re.escape(marker)}.*?{re.escape(marker)}\n?",
                "",
                content,
                flags=re.DOTALL,
            )

        # Append new instruction at the end
        content += instruction
        claude_md.write_text(content)
        print("Injected issue reminder into CLAUDE.md")
    else:
        # Create minimal CLAUDE.md with instruction
        claude_md.write_text(f"# Project Instructions\n{instruction}")
        print("Created CLAUDE.md with issue reminder")


def remove_claude_md_reminder() -> None:
    """
    Remove issue reminder from CLAUDE.md
    """
    claude_md = Path("CLAUDE.md")
    marker = "<!-- GHE-CURRENT-ISSUE -->"

    if claude_md.exists():
        content = claude_md.read_text()
        if marker in content:
            content = re.sub(
                rf"{re.escape(marker)}.*?{re.escape(marker)}\n?",
                "",
                content,
                flags=re.DOTALL,
            )
            claude_md.write_text(content)
            print("Removed issue reminder from CLAUDE.md")


def set_current_issue(issue_num: str) -> bool:
    """
    Set current issue for MAIN THREAD transcription

    This is for the FOREGROUND conversation between USER and CLAUDE.
    It only enables transcription - NO agents are spawned here.
    The main thread is just Claude posting verbatim exchanges.

    For feature/bug DEVELOPMENT threads (with agents), use:
      create_feature_thread.py

    Args:
        issue_num: Issue number

    Returns:
        True on success, False on failure
    """
    if not check_github_repo():
        return False

    ensure_config()

    # Verify issue exists and get title
    try:
        result = run_gh("issue", "view", issue_num, "--json", "number,title", "--jq", "[.number, .title] | @tsv")
        parts = result.stdout.strip().split("\t")
        if parts[0] != issue_num:
            print(f"Issue #{issue_num} not found", file=sys.stderr)
            return False
        issue_title = parts[1] if len(parts) > 1 else ""
    except subprocess.CalledProcessError:
        print(f"Issue #{issue_num} not found", file=sys.stderr)
        return False

    # SAVE the previous issue BEFORE switching (for resume functionality)
    previous = get_config("current_issue", "")
    if previous and previous != "null" and previous != issue_num:
        save_last_active_issue(previous)
        print(f"{YELLOW}Saved previous issue #{previous}{NC}")

    print(f"{GREEN}Setting main conversation thread to issue #{issue_num}{NC}")

    # Update config - this is the MAIN thread (user + Claude conversation)
    set_config("current_issue", issue_num)
    set_config("current_phase", "CONVERSATION")  # Special phase for main thread

    # Inject reminder into CLAUDE.md (with title)
    inject_claude_md_reminder(issue_num, issue_title)

    # Mark issue as active conversation (NOT phase:dev - that's for feature threads)
    try:
        run_gh("issue", "edit", issue_num, "--add-label", "conversation")
        run_gh("issue", "edit", issue_num, "--add-label", "in-progress")
    except subprocess.CalledProcessError:
        pass

    print()
    print(f"{GREEN}Issue #{issue_num} is now the MAIN CONVERSATION THREAD{NC}")
    print()
    print("TRANSCRIPTION IS NOW ACTIVE")
    print(f"All exchanges between you and Claude will be posted VERBATIM to issue #{issue_num}")
    print()
    print("This is the foreground thread - NO agents will be spawned here.")
    print("To develop a feature/fix a bug, ask Claude and a BACKGROUND thread will be created.")
    print()
    print("Include in your responses:")
    title_suffix = f": {issue_title}" if issue_title else ""
    print(f"  Currently discussing issue n.{issue_num}{title_suffix}")
    return True


def get_current_issue() -> None:
    """
    Get current issue with title
    """
    ensure_config()
    issue = get_config("current_issue", "")
    if issue and issue != "null":
        # Get title from GitHub
        try:
            result = run_gh("issue", "view", issue, "--json", "title", "--jq", ".title")
            title = result.stdout.strip()
        except subprocess.CalledProcessError:
            title = ""

        print(f"{GREEN}TRANSCRIPTION ACTIVE{NC}")
        title_display = f": {title}" if title else ""
        print(f"Current issue: #{issue}{title_display}")
        print()
        print(f"Include in responses: Currently discussing issue n.{issue}{title_display}")
    else:
        print(f"{YELLOW}TRANSCRIPTION INACTIVE{NC}")
        print("No current issue set")
        print()
        print("To activate: set-issue <NUMBER>")


def save_last_active_issue(issue_num: str) -> None:
    """
    Save current issue to last_active_issue.json
    This enables "resume last issue" functionality

    Note: repo is NOT stored here - it's in plugin settings (.claude/ghe.local.md)

    Args:
        issue_num: Issue number to save
    """
    # Only save if we have a valid issue number
    if not issue_num or issue_num == "null":
        return

    last_active_file = Path(".claude/last_active_issue.json")

    # Get issue title from GitHub
    try:
        result = run_gh("issue", "view", issue_num, "--json", "title", "--jq", ".title")
        title = result.stdout.strip()
    except subprocess.CalledProcessError:
        title = "Unknown"

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    # Ensure .claude directory exists
    last_active_file.parent.mkdir(parents=True, exist_ok=True)

    # Save to JSON file (repo is in plugin settings, not here)
    data = {
        "issue": int(issue_num),
        "title": title,
        "last_active": timestamp,
    }

    with open(last_active_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved last active issue: #{issue_num}")


def get_last_active_issue() -> bool:
    """
    Get last active issue from JSON file

    Returns:
        True if found, False otherwise
    """
    last_active_file = Path(".claude/last_active_issue.json")

    if not last_active_file.exists():
        print(f"{YELLOW}No last active issue found{NC}")
        print()
        print("No previous session recorded in .claude/last_active_issue.json")
        return False

    try:
        with open(last_active_file, "r") as f:
            data = json.load(f)

        issue = data.get("issue")
        title = data.get("title")
        last_active = data.get("last_active")

        if not issue or issue == "null":
            print(f"{YELLOW}Invalid last active issue file{NC}")
            return False

        print(f"{GREEN}Last Active Issue Found{NC}")
        print()
        print(f"  Issue:       #{issue}")
        print(f"  Title:       {title}")
        print(f"  Last Active: {last_active}")
        print()
        print(f"To resume: set-issue {issue}")
        return True
    except (json.JSONDecodeError, KeyError):
        print(f"{YELLOW}Invalid last active issue file{NC}")
        return False


def get_last_issue_number() -> Optional[str]:
    """
    Get last issue number only (for scripting)

    Returns:
        Issue number as string, or None if not found
    """
    last_active_file = Path(".claude/last_active_issue.json")

    if last_active_file.exists():
        try:
            with open(last_active_file, "r") as f:
                data = json.load(f)
            issue = data.get("issue")
            if issue:
                return str(issue)
        except (json.JSONDecodeError, KeyError):
            pass

    return None


def clear_current_issue() -> None:
    """
    Clear current issue (stop transcription)
    """
    ensure_config()

    # SAVE the current issue BEFORE clearing (for resume functionality)
    current = get_config("current_issue", "")
    if current and current != "null":
        save_last_active_issue(current)

    # Remove from config
    set_config("current_issue", "null")

    # Remove CLAUDE.md reminder
    remove_claude_md_reminder()

    print(f"{YELLOW}TRANSCRIPTION STOPPED{NC}")
    print("No issue is now active for transcription")

    if current and current != "null":
        print()
        print(f"Previous issue #{current} has been saved.")
        print("To resume later: get-last-issue")


def main() -> None:
    """
    CLI interface
    """
    parser = argparse.ArgumentParser(
        description="GHE Auto-Transcribe System - Posts conversation exchanges to GitHub issues",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  user <message>              Post user message to current issue
  assistant <message> [agent] Post assistant message (default: Athena)
  find-issue <topic>          Find or create issue for topic
  set-issue <number>          Set current issue and activate transcription
  get-issue                   Show current issue status
  clear-issue                 Stop transcription and clear current issue
  get-last-issue              Show the last active issue (from previous session)
  last-issue-number           Get only the issue number (for scripting)
  resume                      Resume transcription to the last active issue
  check                       Verify GitHub repo is configured

IMPORTANT: Transcription only happens AFTER set-issue is called!

Issue patterns recognized in messages:
  [Currently discussing issue n.123]
  [issue #123]
  working on issue #123
  lets work on #123
  claim #123

Resume workflow:
  1. User says: 'what were we working on?' or 'resume last issue'
  2. Claude checks: auto-transcribe.py get-last-issue
  3. Claude resumes: auto-transcribe.py resume (or set-issue N)
        """,
    )

    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    if args.command == "user":
        if len(args.args) < 1:
            print("Error: user command requires a message", file=sys.stderr)
            sys.exit(1)
        post_user_message(args.args[0])

    elif args.command == "assistant":
        if len(args.args) < 1:
            print("Error: assistant command requires a message", file=sys.stderr)
            sys.exit(1)
        agent = args.args[1] if len(args.args) > 1 else "Athena"
        post_assistant_message(args.args[0], agent)

    elif args.command == "find-issue":
        if len(args.args) < 1:
            print("Error: find-issue command requires a topic", file=sys.stderr)
            sys.exit(1)
        issue = find_or_create_issue(args.args[0])
        if issue:
            print(issue)

    elif args.command == "set-issue":
        if len(args.args) < 1:
            print("Error: set-issue command requires an issue number", file=sys.stderr)
            sys.exit(1)
        if not set_current_issue(args.args[0]):
            sys.exit(1)

    elif args.command == "get-issue":
        get_current_issue()

    elif args.command == "clear-issue":
        clear_current_issue()

    elif args.command == "get-last-issue":
        if not get_last_active_issue():
            sys.exit(1)

    elif args.command == "last-issue-number":
        # Returns ONLY the issue number (for scripting/piping)
        issue = get_last_issue_number()
        if issue:
            print(issue)
        else:
            sys.exit(1)

    elif args.command == "resume":
        # Convenience: Resume the last active issue
        last_issue = get_last_issue_number()
        if last_issue:
            if not set_current_issue(last_issue):
                sys.exit(1)
        else:
            print("No previous issue to resume")
            sys.exit(1)

    elif args.command == "check":
        if check_github_repo():
            print(json.dumps({"event": "SessionStart", "suppressOutput": True}))
        else:
            print(json.dumps({"event": "SessionStart", "suppressOutput": True, "error": "No GitHub repo"}))
            sys.exit(1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
