#!/usr/bin/env python3
"""
Transcription Enforcement System for GHE Plugin

This module ensures that user messages are transcribed to GitHub issues
by tracking pending messages and blocking Claude from stopping until
transcription is verified.

Usage:
    # Store pending message (called by UserPromptSubmit hook)
    python3 transcription_enforcer.py store

    # Verify transcription (called by Stop hook)
    python3 transcription_enforcer.py verify

    # Clear pending (called after successful transcription)
    python3 transcription_enforcer.py clear <hash>
"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Import from ghe_common
try:
    from ghe_common import (
        ghe_get_setting,
        ghe_find_config_file,
        GHE_PLUGIN_ROOT,
    )
except ImportError:
    # Fallback for standalone execution
    GHE_PLUGIN_ROOT = Path(__file__).parent.parent
    def ghe_get_setting(key: str, default: Any = None) -> Any:
        return default
    def ghe_find_config_file() -> Optional[str]:
        return None


# Constants
PENDING_FILE = ".claude/ghe_pending_transcriptions.json"
REDACTION_PLACEHOLDER = "XX REDACTED XX"
MIN_MATCH_THRESHOLD = 0.7  # 70% similarity required


def get_pending_file_path() -> Path:
    """Get the path to the pending transcriptions file."""
    # Try to find project root
    cwd = Path.cwd()

    # Look for .claude directory
    claude_dir = cwd / ".claude"
    if not claude_dir.exists():
        # Try parent directories
        for parent in cwd.parents:
            if (parent / ".claude").exists():
                claude_dir = parent / ".claude"
                break
        else:
            # Create in cwd
            claude_dir = cwd / ".claude"
            claude_dir.mkdir(exist_ok=True)

    return claude_dir / "ghe_pending_transcriptions.json"


def load_pending() -> Dict[str, Any]:
    """Load pending transcriptions from file."""
    path = get_pending_file_path()
    if path.exists():
        try:
            with open(path) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"pending": [], "session_id": None}


def save_pending(data: Dict[str, Any]) -> None:
    """Save pending transcriptions to file."""
    path = get_pending_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    # Lowercase
    text = text.lower()
    # Remove extra whitespace
    text = " ".join(text.split())
    # Remove common punctuation
    text = re.sub(r'[^\w\s]', ' ', text)
    # Remove extra whitespace again
    text = " ".join(text.split())
    return text


def extract_signature(text: str) -> str:
    """Extract a signature from text for matching."""
    normalized = normalize_text(text)
    # Take first 200 chars as signature (enough to identify uniquely)
    return normalized[:200]


def compute_hash(text: str) -> str:
    """Compute a hash of the normalized text."""
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def extract_key_phrases(text: str, max_phrases: int = 10) -> List[str]:
    """Extract key phrases from text for fuzzy matching."""
    normalized = normalize_text(text)
    words = normalized.split()

    # Get unique words, filter out very short ones
    unique_words = []
    seen = set()
    for word in words:
        if len(word) >= 4 and word not in seen:
            seen.add(word)
            unique_words.append(word)
            if len(unique_words) >= max_phrases:
                break

    return unique_words


def calculate_similarity(text1: str, text2: str) -> float:
    """Calculate similarity between two texts."""
    # Extract key phrases from both
    phrases1 = set(extract_key_phrases(text1, 20))
    phrases2 = set(extract_key_phrases(text2, 20))

    if not phrases1 or not phrases2:
        return 0.0

    # Calculate Jaccard similarity
    intersection = len(phrases1 & phrases2)
    union = len(phrases1 | phrases2)

    return intersection / union if union > 0 else 0.0


def message_matches_comment(message: Dict[str, Any], comment_body: str) -> bool:
    """Check if a pending message matches a GitHub comment."""
    # Remove redaction placeholders from comment for matching
    clean_comment = re.sub(r'XX REDACTED XX', '', comment_body)

    # Try hash match first (exact match after normalization)
    comment_hash = compute_hash(clean_comment)
    if message.get("hash") == comment_hash:
        return True

    # Try signature match
    comment_sig = extract_signature(clean_comment)
    if message.get("signature") and message["signature"] in comment_sig:
        return True

    # Try key phrase matching
    if message.get("key_phrases"):
        msg_phrases = set(message["key_phrases"])
        comment_phrases = set(extract_key_phrases(clean_comment, 20))

        if msg_phrases:
            # Check if enough phrases match
            matches = len(msg_phrases & comment_phrases)
            if matches >= len(msg_phrases) * MIN_MATCH_THRESHOLD:
                return True

    # Try similarity score
    if message.get("signature"):
        similarity = calculate_similarity(message["signature"], clean_comment)
        if similarity >= MIN_MATCH_THRESHOLD:
            return True

    return False


def get_current_issue() -> Optional[int]:
    """Get the current issue number from config."""
    # Try to read from last_active_issue.json
    pending_path = get_pending_file_path()
    config_path = pending_path.parent / "last_active_issue.json"

    if config_path.exists():
        try:
            with open(config_path) as f:
                data = json.load(f)
                return data.get("issue")
        except (json.JSONDecodeError, IOError):
            pass

    return None


def fetch_github_comments(issue_num: int, since: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Fetch comments from a GitHub issue.

    Args:
        issue_num: The issue number
        since: Optional ISO timestamp - only return comments after this time

    Returns:
        List of comment dicts with 'body' and 'createdAt' fields
    """
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--json", "comments"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            comments = data.get("comments", [])

            # Filter by timestamp if provided
            if since:
                filtered = []
                for c in comments:
                    created = c.get("createdAt", "")
                    # Compare ISO timestamps (lexicographic comparison works for ISO format)
                    if created >= since:
                        filtered.append({
                            "body": c.get("body", ""),
                            "createdAt": created
                        })
                return filtered
            else:
                return [{"body": c.get("body", ""), "createdAt": c.get("createdAt", "")}
                        for c in comments]
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError):
        pass

    return []


def silent_exit() -> None:
    """Exit silently with suppressOutput JSON."""
    print(json.dumps({"suppressOutput": True}))
    sys.exit(0)


def store_pending_message() -> None:
    """Store a pending user message from stdin (UserPromptSubmit hook)."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No valid input
        silent_exit()

    prompt = input_data.get("prompt", "")
    session_id = input_data.get("session_id", "")

    if not prompt:
        silent_exit()

    # Skip hook feedback messages (these are system-injected, not real user messages)
    skip_patterns = [
        "Stop hook feedback:",
        "TRANSCRIPTION BLOCKING",
        "PreToolUse hook feedback:",
        "PostToolUse hook feedback:",
        "SessionStart hook feedback:",
    ]
    for pattern in skip_patterns:
        if pattern in prompt:
            silent_exit()

    # Load existing pending messages
    data = load_pending()

    # Update session ID
    if data.get("session_id") != session_id:
        # New session, clear old pending
        data = {"pending": [], "session_id": session_id}

    # Create message record - marked as USER message
    message = {
        "speaker": "user",
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "hash": compute_hash(prompt),
        "signature": extract_signature(prompt),
        "key_phrases": extract_key_phrases(prompt, 10),
        "preview": prompt[:100] + "..." if len(prompt) > 100 else prompt
    }

    # Add to pending
    data["pending"].append(message)

    # Save
    save_pending(data)

    # Exit silently
    silent_exit()


def extract_claude_response(transcript_path: str) -> Optional[str]:
    """
    Extract Claude's last response from the transcript file.

    The transcript is a JSONL file with conversation messages.
    We look for the last assistant message.
    """
    if not transcript_path:
        print("DEBUG extract_claude_response: path is empty", file=sys.stderr)
        return None

    # CRITICAL: Expand tilde in path (Stop hook provides ~/ paths)
    expanded_path = os.path.expanduser(transcript_path)

    if not Path(expanded_path).exists():
        print(f"DEBUG extract_claude_response: path doesn't exist: {transcript_path} -> {expanded_path}", file=sys.stderr)
        return None

    try:
        last_assistant_msg = None
        entry_count = 0
        assistant_count = 0
        with open(expanded_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                    entry_count += 1

                    # The transcript structure has message object with role inside
                    # Structure: {"message": {"role": "assistant", "content": [...]}}
                    message = entry.get("message", {})
                    if not isinstance(message, dict):
                        continue

                    message_role = message.get("role", "")

                    # Look for assistant messages
                    if message_role == "assistant":
                        assistant_count += 1
                        # Get the content from inside message
                        content = message.get("content", "")
                        if isinstance(content, list):
                            # Content is a list of blocks (text, tool_use, thinking, etc.)
                            text_parts = []
                            for block in content:
                                if isinstance(block, dict) and block.get("type") == "text":
                                    text_parts.append(block.get("text", ""))
                                elif isinstance(block, str):
                                    text_parts.append(block)
                            content = "\n".join(text_parts)
                        if content:
                            last_assistant_msg = content
                except json.JSONDecodeError:
                    continue

        print(f"DEBUG extract_claude_response: parsed {entry_count} entries, found {assistant_count} assistant messages", file=sys.stderr)
        if last_assistant_msg:
            print(f"DEBUG extract_claude_response: last msg length={len(last_assistant_msg)}", file=sys.stderr)
        else:
            print("DEBUG extract_claude_response: NO assistant message content found", file=sys.stderr)

        return last_assistant_msg
    except IOError as e:
        print(f"DEBUG extract_claude_response: IOError: {e}", file=sys.stderr)
        return None


def store_claude_response() -> None:
    """Store Claude's response from transcript (called at Stop hook)."""
    # Load pending first to store debug info
    data = load_pending()

    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        data["last_store_debug"] = "Failed to parse JSON input from Stop hook"
        save_pending(data)
        silent_exit()

    transcript_path = input_data.get("transcript_path", "")
    session_id = input_data.get("session_id", "")

    # Expand tilde for checking
    expanded_path = os.path.expanduser(transcript_path) if transcript_path else ""
    path_exists = Path(expanded_path).exists() if expanded_path else False

    # Store debug info in pending file (visible via verify)
    debug_info = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "transcript_path": transcript_path,
        "expanded_path": expanded_path,
        "path_exists": path_exists,
    }

    # Extract Claude's last response from transcript
    response = extract_claude_response(transcript_path)

    debug_info["response_found"] = bool(response)
    debug_info["response_length"] = len(response) if response else 0

    if not response:
        # No response to store - save debug info for visibility
        debug_info["error"] = "No assistant message found in transcript"
        data["last_store_debug"] = debug_info
        save_pending(data)
        silent_exit()

    # Store successful debug info
    data["last_store_debug"] = debug_info

    # Create message record - marked as CLAUDE message
    message = {
        "speaker": "claude",
        "timestamp": datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
        "hash": compute_hash(response),
        "signature": extract_signature(response),
        "key_phrases": extract_key_phrases(response, 10),
        "preview": response[:100] + "..." if len(response) > 100 else response
    }

    # Add to pending
    data["pending"].append(message)

    # Save
    save_pending(data)

    silent_exit()


def has_user_avatar(comment_body: str) -> bool:
    """Check if comment has a user avatar (GitHub avatars.githubusercontent.com)."""
    return "avatars.githubusercontent.com" in comment_body


def has_claude_avatar(comment_body: str) -> bool:
    """Check if comment has a Claude/agent avatar (from plugin assets)."""
    # Check for plugin avatar URLs
    return "/assets/avatars/" in comment_body or "claude.png" in comment_body.lower()


def has_speaker_name(comment_body: str, expected_speaker: str) -> Tuple[bool, str]:
    """
    Check if comment has the correct speaker name in header.

    Returns:
        Tuple of (is_correct, actual_name_found)
    """
    # Look for the speaker name pattern in first few lines
    lines = comment_body.split('\n')[:10]
    header_text = '\n'.join(lines).lower()

    if expected_speaker == "user":
        # User messages should have a GitHub username (not "claude")
        if "claude" in header_text and "avatars.githubusercontent.com" not in comment_body:
            return False, "Claude (wrong)"
        # Check for any username-like pattern
        if "avatars.githubusercontent.com" in comment_body:
            return True, "User"
        return False, "Unknown"
    elif expected_speaker == "claude":
        # Claude messages should have "Claude" in header
        if "claude" in header_text:
            return True, "Claude"
        return False, "Missing Claude name"

    return False, "Unknown"


def has_badges_section(comment_body: str) -> Tuple[bool, str]:
    """
    Check if comment has badges section after ---\\n (horizontal rule with newline).

    The format should be:
    ---
    [badges here]

    Returns:
        Tuple of (has_valid_badges, issue_description)
    """
    # Look for horizontal rule pattern: ---\n followed by content
    hr_pattern = re.compile(r'\n---\n', re.MULTILINE)

    if not hr_pattern.search(comment_body):
        return False, "Missing horizontal rule (---\\n) before badges"

    # Check there's content after the ---
    parts = comment_body.split('\n---\n')
    if len(parts) < 2:
        return False, "Missing badges section after horizontal rule"

    badges_section = parts[-1].strip()
    if not badges_section:
        return False, "Empty badges section after horizontal rule"

    # Check for badge-like content (typically contains shields.io or img elements)
    if 'badge' in badges_section.lower() or 'shield' in badges_section.lower() or '![' in badges_section:
        return True, "OK"

    # Also accept any content after --- as valid (might be custom format)
    if len(badges_section) > 10:
        return True, "OK"

    return False, "Badges section too short or missing badge content"


def check_message_completeness(message: Dict[str, Any], comment_body: str) -> Tuple[bool, float]:
    """
    Check if the message content appears complete in the comment.

    Returns:
        Tuple of (is_complete, match_percentage)
    """
    # Get key phrases from original message
    msg_phrases = set(message.get("key_phrases", []))
    if not msg_phrases:
        return True, 1.0  # Can't check without phrases

    # Clean comment for matching
    clean_comment = re.sub(r'XX REDACTED XX', '', comment_body)
    comment_phrases = set(extract_key_phrases(clean_comment, 30))

    # Calculate match percentage
    if not msg_phrases:
        return True, 1.0

    matches = len(msg_phrases & comment_phrases)
    match_pct = matches / len(msg_phrases)

    # Require at least 60% of key phrases to be present
    return match_pct >= 0.6, match_pct


def check_no_mixed_speakers(comments: List[Dict[str, Any]], pending: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Check that user and Claude messages aren't mixed in the same comment.

    Returns list of issues found.
    """
    issues = []

    for comment in comments:
        body = comment.get("body", "")

        # Check if this comment contains both a user message and a Claude message
        user_match = None
        claude_match = None

        for msg in pending:
            if message_matches_comment(msg, body):
                if msg.get("speaker") == "user":
                    user_match = msg
                elif msg.get("speaker") == "claude":
                    claude_match = msg

        if user_match and claude_match:
            issues.append({
                "comment_preview": body[:100],
                "issue": "Both user and Claude messages in same comment - must be separate!"
            })

    return issues


def verify_transcription() -> None:
    """
    Verify that pending messages have been transcribed as separate comments
    with correct format (Stop hook).

    Requirements for proper conversation format:
    - User messages: separate comment with user avatar AND username
    - Claude messages: separate comment with Claude avatar AND "Claude" name
    - Each comment must have badges section after ---\\n
    - User and Claude messages must NOT be in the same comment
    - Message content must be complete (not truncated)
    """
    data = load_pending()
    pending = data.get("pending", [])

    if not pending:
        # Nothing pending, allow stop
        silent_exit()

    # Get current issue
    issue_num = get_current_issue()
    if not issue_num:
        # No issue configured, can't verify - allow stop
        silent_exit()

    # Find the oldest pending message timestamp for efficient filtering
    oldest_timestamp = min(m.get("timestamp", "") for m in pending)

    # Fetch only comments after the oldest pending message
    comments = fetch_github_comments(issue_num, since=oldest_timestamp)

    if not comments:
        # No comments found after our timestamp
        all_comments = fetch_github_comments(issue_num)
        if all_comments is None:
            # Can't verify - allow stop
            silent_exit()
        comments = []

    # Check for mixed speakers (user + Claude in same comment)
    mixed_issues = check_no_mixed_speakers(comments, pending)

    # Check each pending message against fetched comments
    still_pending = []
    format_issues = []

    for msg in pending:
        speaker = msg.get("speaker", "unknown")
        found_in_comment = None

        for comment in comments:
            body = comment.get("body", "")
            if message_matches_comment(msg, body):
                found_in_comment = body
                break

        if not found_in_comment:
            still_pending.append(msg)
            continue

        # Found the message - now verify ALL format requirements
        msg_issues = []

        # 1. Check correct avatar
        if speaker == "user":
            if not has_user_avatar(found_in_comment):
                msg_issues.append("Missing user avatar")
        elif speaker == "claude":
            if not has_claude_avatar(found_in_comment):
                msg_issues.append("Missing Claude avatar")

        # 2. Check correct speaker name
        name_ok, name_found = has_speaker_name(found_in_comment, speaker)
        if not name_ok:
            msg_issues.append(f"Wrong/missing speaker name (found: {name_found})")

        # 3. Check badges section after ---\n
        badges_ok, badges_issue = has_badges_section(found_in_comment)
        if not badges_ok:
            msg_issues.append(badges_issue)

        # 4. Check message completeness
        complete_ok, match_pct = check_message_completeness(msg, found_in_comment)
        if not complete_ok:
            msg_issues.append(f"Incomplete message (only {match_pct*100:.0f}% content found)")

        if msg_issues:
            format_issues.append({
                "msg": msg,
                "issues": msg_issues
            })

    # Compile all issues for reporting
    all_issues = []

    if still_pending:
        all_issues.append(f"NOT TRANSCRIBED ({len(still_pending)} message(s)):")
        for m in still_pending[:3]:
            speaker = m.get("speaker", "?")
            preview = m.get("preview", "???")[:50]
            all_issues.append(f"  [{speaker.upper()}] \"{preview}...\"")

    if mixed_issues:
        all_issues.append(f"MIXED SPEAKERS ({len(mixed_issues)} comment(s)):")
        for item in mixed_issues[:2]:
            all_issues.append(f"  {item['issue']}")

    if format_issues:
        all_issues.append(f"FORMAT PROBLEMS ({len(format_issues)} message(s)):")
        for item in format_issues[:3]:
            speaker = item["msg"].get("speaker", "?")
            preview = item["msg"].get("preview", "???")[:30]
            issues_str = ", ".join(item["issues"][:2])
            all_issues.append(f"  [{speaker.upper()}] \"{preview}...\" -> {issues_str}")

    if all_issues:
        error_msg = f"TRANSCRIPTION BLOCKING on issue #{issue_num}:\n"
        error_msg += "\n".join(all_issues)
        error_msg += "\n\n" + "="*60
        error_msg += "\nYou MUST fix these issues before you can stop!"
        error_msg += "\n\nREQUIREMENTS for each transcribed message:"
        error_msg += "\n  1. SEPARATE comments for user and Claude (never mixed)"
        error_msg += "\n  2. User messages: user avatar + GitHub username"
        error_msg += "\n  3. Claude messages: Claude avatar + 'Claude' name"
        error_msg += "\n  4. Horizontal rule (---) on its own line before badges"
        error_msg += "\n  5. Badges section after the horizontal rule"
        error_msg += "\n  6. Complete message content (not truncated)"
        error_msg += "\n\nEDIT the problematic comments to fix issues, or POST missing messages!"
        error_msg += "\n" + "="*60

        # DEBUG: Show pending messages breakdown
        error_msg += "\n\n[DEBUG] Pending messages breakdown:"
        user_count = sum(1 for m in pending if m.get("speaker") == "user")
        claude_count = sum(1 for m in pending if m.get("speaker") == "claude")
        other_count = len(pending) - user_count - claude_count
        error_msg += f"\n  Total: {len(pending)} | User: {user_count} | Claude: {claude_count} | Other: {other_count}"
        for i, m in enumerate(pending[:5]):  # Show first 5
            speaker = m.get("speaker", "?")
            preview = m.get("preview", "???")[:40]
            ts = m.get("timestamp", "?")[:19]
            error_msg += f"\n  [{i+1}] {speaker}: \"{preview}...\" @ {ts}"

        # DEBUG: Show last store-response debug info
        last_debug = data.get("last_store_debug")
        if last_debug:
            error_msg += "\n\n[DEBUG] Last store-response:"
            if isinstance(last_debug, dict):
                error_msg += f"\n  transcript_path: {last_debug.get('transcript_path', 'N/A')}"
                error_msg += f"\n  expanded_path: {last_debug.get('expanded_path', 'N/A')}"
                error_msg += f"\n  path_exists: {last_debug.get('path_exists', 'N/A')}"
                error_msg += f"\n  response_found: {last_debug.get('response_found', 'N/A')}"
                error_msg += f"\n  response_length: {last_debug.get('response_length', 'N/A')}"
                if last_debug.get('error'):
                    error_msg += f"\n  ERROR: {last_debug.get('error')}"
            else:
                error_msg += f"\n  {last_debug}"

        print(error_msg, file=sys.stderr)
        sys.exit(2)  # Exit code 2 blocks Claude from stopping

    # All properly transcribed, update pending file
    data["pending"] = []
    save_pending(data)

    silent_exit()


def clear_pending(hash_to_clear: Optional[str] = None) -> None:
    """Clear pending messages (after manual transcription)."""
    data = load_pending()

    if hash_to_clear:
        # Clear specific message
        data["pending"] = [m for m in data.get("pending", [])
                          if m.get("hash") != hash_to_clear]
    else:
        # Clear all
        data["pending"] = []

    save_pending(data)
    print(f"Cleared pending transcriptions", file=sys.stderr)
    sys.exit(0)


def show_pending() -> None:
    """Show current pending messages."""
    data = load_pending()
    pending = data.get("pending", [])

    if not pending:
        print("No pending transcriptions")
    else:
        print(f"Pending transcriptions ({len(pending)}):")
        for i, msg in enumerate(pending, 1):
            print(f"  {i}. [{msg.get('timestamp', '???')}] {msg.get('preview', '???')[:60]}...")

    sys.exit(0)


def main() -> None:
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: transcription_enforcer.py <store|store-response|verify|clear|show> [hash]",
              file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "store":
        # Store user message (UserPromptSubmit hook)
        store_pending_message()
    elif command == "store-response":
        # Store Claude response (Stop hook, before verify)
        store_claude_response()
    elif command == "verify":
        # Verify all pending messages are transcribed (Stop hook)
        verify_transcription()
    elif command == "clear":
        hash_to_clear = sys.argv[2] if len(sys.argv) > 2 else None
        clear_pending(hash_to_clear)
    elif command == "show":
        show_pending()
    else:
        print(f"Unknown command: {command}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
