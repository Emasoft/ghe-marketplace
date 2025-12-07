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
from datetime import datetime
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


def fetch_github_comments(issue_num: int) -> List[str]:
    """Fetch comments from a GitHub issue."""
    try:
        result = subprocess.run(
            ["gh", "issue", "view", str(issue_num), "--json", "comments",
             "--jq", ".comments[].body"],
            capture_output=True,
            text=True,
            check=False,
            timeout=30
        )
        if result.returncode == 0 and result.stdout.strip():
            # Each comment is separated by newlines, but comments can contain newlines
            # So we fetch them differently
            result2 = subprocess.run(
                ["gh", "issue", "view", str(issue_num), "--json", "comments"],
                capture_output=True,
                text=True,
                check=False,
                timeout=30
            )
            if result2.returncode == 0:
                data = json.loads(result2.stdout)
                return [c.get("body", "") for c in data.get("comments", [])]
    except (subprocess.TimeoutExpired, subprocess.SubprocessError, json.JSONDecodeError):
        pass

    return []


def store_pending_message() -> None:
    """Store a pending message from stdin (UserPromptSubmit hook)."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        # No valid input
        sys.exit(0)

    prompt = input_data.get("prompt", "")
    session_id = input_data.get("session_id", "")

    if not prompt:
        sys.exit(0)

    # Load existing pending messages
    data = load_pending()

    # Update session ID
    if data.get("session_id") != session_id:
        # New session, clear old pending
        data = {"pending": [], "session_id": session_id}

    # Create message record
    message = {
        "timestamp": datetime.now().isoformat(),
        "hash": compute_hash(prompt),
        "signature": extract_signature(prompt),
        "key_phrases": extract_key_phrases(prompt, 10),
        "preview": prompt[:100] + "..." if len(prompt) > 100 else prompt
    }

    # Add to pending
    data["pending"].append(message)

    # Save
    save_pending(data)

    # Output nothing - this is a background operation
    sys.exit(0)


def verify_transcription() -> None:
    """Verify that pending messages have been transcribed (Stop hook)."""
    data = load_pending()
    pending = data.get("pending", [])

    if not pending:
        # Nothing pending, allow stop
        sys.exit(0)

    # Get current issue
    issue_num = get_current_issue()
    if not issue_num:
        # No issue configured, can't verify - allow stop but warn
        print("Warning: No GHE issue configured for transcription verification",
              file=sys.stderr)
        sys.exit(0)

    # Fetch GitHub comments
    comments = fetch_github_comments(issue_num)

    if not comments:
        # Can't fetch comments - allow stop but warn
        print(f"Warning: Could not fetch comments from issue #{issue_num}",
              file=sys.stderr)
        sys.exit(0)

    # Check each pending message
    still_pending = []
    for msg in pending:
        found = False
        for comment in comments:
            if message_matches_comment(msg, comment):
                found = True
                break

        if not found:
            still_pending.append(msg)

    if still_pending:
        # There are untranscribed messages - BLOCK!
        previews = [m.get("preview", "???")[:50] for m in still_pending[:3]]
        msg = f"TRANSCRIPTION REQUIRED: {len(still_pending)} message(s) not yet transcribed to issue #{issue_num}:\n"
        for i, preview in enumerate(previews, 1):
            msg += f"  {i}. \"{preview}...\"\n"
        msg += "\nYou MUST transcribe these messages before stopping. Use Mnemosyne to post them to the issue."

        print(msg, file=sys.stderr)
        sys.exit(2)  # Exit code 2 blocks Claude from stopping

    # All transcribed, update pending file
    data["pending"] = []
    save_pending(data)

    sys.exit(0)


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
        print("Usage: transcription_enforcer.py <store|verify|clear|show> [hash]",
              file=sys.stderr)
        sys.exit(1)

    command = sys.argv[1].lower()

    if command == "store":
        store_pending_message()
    elif command == "verify":
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
