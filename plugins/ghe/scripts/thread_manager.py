#!/usr/bin/env python3
"""
thread_manager.py - Phase-based thread management for GHE

Manages thread lifecycle with proper manager assignment and changelog tracking.

Usage:
    python3 thread_manager.py init <issue> [requirements]
    python3 thread_manager.py transition <issue> <phase>
    python3 thread_manager.py add-changelog <issue> <entry> [comment_id]
    python3 thread_manager.py add-testlog <issue> <entry> [comment_id]
    python3 thread_manager.py add-reviewlog <issue> <entry> [comment_id]
    python3 thread_manager.py get-manager <phase>
    python3 thread_manager.py get-posting-agent <issue>
    python3 thread_manager.py is-epic <issue>
    python3 thread_manager.py update-manager <issue> <phase>
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime, timezone
from typing import Optional

# Import from GHE common utilities
from ghe_common import (
    ghe_init,
    ghe_gh,
    GHE_RED as RED,
    GHE_GREEN as GREEN,
    GHE_NC as NC,
)

# Import from post_with_avatar module
from post_with_avatar import get_avatar_url
from pathlib import Path


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.

    Format: YYYY-MM-DD HH:MM:SS,mmm LEVEL [logger] - message
    Compatible with: lnav, glogg, Splunk, ELK, Log4j viewers
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [thread_manager] - {message}\n")
    except Exception:
        pass  # Never fail on logging


# Phase to Manager mapping
PHASE_MANAGERS = {
    "dev": "Hephaestus",
    "test": "Artemis",
    "review": "Hera",
    "epic": "Athena",
}

# Manager descriptions
MANAGER_ROLES = {
    "Hephaestus": "DEV Phase Manager - Builds and shapes the implementation",
    "Artemis": "TEST Phase Manager - Hunts bugs and verifies quality",
    "Hera": "REVIEW Phase Manager - Evaluates and renders final verdict",
    "Athena": "EPIC Manager - Coordinates design and plans waves",
}


def get_phase_manager(phase: str) -> str:
    """
    Get manager for a phase.

    Args:
        phase: Phase name (dev/test/review/epic)

    Returns:
        Manager name for the phase (defaults to Hephaestus if unknown)
    """
    phase = phase.lower()
    return PHASE_MANAGERS.get(phase, "Hephaestus")


def is_epic_issue(issue_num: int) -> bool:
    """
    Check if issue is an EPIC.

    Args:
        issue_num: Issue number

    Returns:
        True if issue has 'epic' label, False otherwise
    """
    try:
        result = ghe_gh(
            "issue",
            "view",
            str(issue_num),
            "--json",
            "labels",
            "--jq",
            ".labels[].name",
            capture=True,
        )
        labels = result.stdout.lower()
        return "epic" in labels
    except subprocess.CalledProcessError:
        return False


def get_issue_phase(issue_num: int) -> str:
    """
    Get current phase from issue labels.

    Args:
        issue_num: Issue number

    Returns:
        Current phase (dev/test/review), defaults to 'dev'
    """
    try:
        result = ghe_gh(
            "issue",
            "view",
            str(issue_num),
            "--json",
            "labels",
            "--jq",
            ".labels[].name",
            capture=True,
        )
        labels = result.stdout

        if "phase:review" in labels:
            return "review"
        elif "phase:test" in labels:
            return "test"
        elif "phase:dev" in labels:
            return "dev"
        else:
            return "dev"  # Default to dev
    except subprocess.CalledProcessError:
        return "dev"


def create_first_post(issue_num: int, phase: str, requirements: str) -> str:
    """
    Create first post template.

    Args:
        issue_num: Issue number
        phase: Current phase
        requirements: Requirements text

    Returns:
        Formatted first post template
    """
    manager = get_phase_manager(phase)
    avatar_url = get_avatar_url(manager)
    role = MANAGER_ROLES[manager]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    template = f'''<p><img src="{avatar_url}" width="81" height="81" alt="{manager}" align="middle">&nbsp;&nbsp;&nbsp;&nbsp;<span style="vertical-align: middle;"><strong>{manager} said:</strong></span></p>

**Role:** {role}

## Requirements

{requirements}

---

## Changelog (DEV)

_No entries yet_

---

## Test Log (TEST)

_Phase not started_

---

## Review Log (REVIEW)

_Phase not started_

---

_Last updated: {timestamp}_'''

    return template


def update_first_post_manager(issue_num: int, new_phase: str) -> None:
    """
    Update first post with new manager (phase transition).

    Args:
        issue_num: Issue number
        new_phase: New phase name
    """
    new_manager = get_phase_manager(new_phase)
    avatar_url = get_avatar_url(new_manager)
    role = MANAGER_ROLES[new_manager]

    # Get current first post (issue body)
    result = ghe_gh(
        "issue", "view", str(issue_num), "--json", "body", "--jq", ".body", capture=True
    )
    current_body = result.stdout

    # Create new header
    new_header = f'''<p><img src="{avatar_url}" width="81" height="81" alt="{new_manager}" align="middle">&nbsp;&nbsp;&nbsp;&nbsp;<span style="vertical-align: middle;"><strong>{new_manager} said:</strong></span></p>

**Role:** {role}'''

    # Extract everything after the header (from ## Requirements onwards)
    match = re.search(r"^## Requirements", current_body, re.MULTILINE)
    if match:
        content_after_header = current_body[match.start() :]
    else:
        # Fallback if structure is unexpected
        content_after_header = current_body

    # Combine new header with existing content
    new_body = f"{new_header}\n\n{content_after_header}"

    # Update the issue body
    ghe_gh("issue", "edit", str(issue_num), "--body", new_body)

    print(f"{GREEN}Updated thread manager to {new_manager} for issue #{issue_num}{NC}")


def add_changelog_entry(
    issue_num: int, entry: str, comment_id: Optional[str] = None
) -> None:
    """
    Add changelog entry.

    Args:
        issue_num: Issue number
        entry: Changelog entry text
        comment_id: Optional comment ID to link to
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    link_text = ""

    if comment_id:
        result = ghe_gh(
            "repo",
            "view",
            "--json",
            "nameWithOwner",
            "--jq",
            ".nameWithOwner",
            capture=True,
        )
        repo = result.stdout.strip()
        link_text = f" -> [details](https://github.com/{repo}/issues/{issue_num}#issuecomment-{comment_id})"

    new_entry = f"- [{timestamp}] {entry}{link_text}"

    # Get current body
    result = ghe_gh(
        "issue", "view", str(issue_num), "--json", "body", "--jq", ".body", capture=True
    )
    current_body = result.stdout

    # Process the body to add the changelog entry
    updated_body = _add_log_entry(
        current_body, new_entry, "Changelog (DEV)", "_No entries yet_"
    )

    # Update timestamp
    updated_body = _update_timestamp(updated_body)

    # Update issue
    ghe_gh("issue", "edit", str(issue_num), "--body", updated_body)

    print(f"Added changelog entry to issue #{issue_num}")


def add_testlog_entry(
    issue_num: int, entry: str, comment_id: Optional[str] = None
) -> None:
    """
    Add test log entry.

    Args:
        issue_num: Issue number
        entry: Test log entry text
        comment_id: Optional comment ID to link to
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    link_text = ""

    if comment_id:
        result = ghe_gh(
            "repo",
            "view",
            "--json",
            "nameWithOwner",
            "--jq",
            ".nameWithOwner",
            capture=True,
        )
        repo = result.stdout.strip()
        link_text = f" -> [details](https://github.com/{repo}/issues/{issue_num}#issuecomment-{comment_id})"

    new_entry = f"- [{timestamp}] {entry}{link_text}"

    # Get current body
    result = ghe_gh(
        "issue", "view", str(issue_num), "--json", "body", "--jq", ".body", capture=True
    )
    current_body = result.stdout

    # Process the body to add the test log entry
    updated_body = _add_log_entry(
        current_body, new_entry, "Test Log (TEST)", "_Phase not started_"
    )

    # Update timestamp
    updated_body = _update_timestamp(updated_body)

    # Update issue
    ghe_gh("issue", "edit", str(issue_num), "--body", updated_body)

    print(f"Added test log entry to issue #{issue_num}")


def add_reviewlog_entry(
    issue_num: int, entry: str, comment_id: Optional[str] = None
) -> None:
    """
    Add review log entry.

    Args:
        issue_num: Issue number
        entry: Review log entry text
        comment_id: Optional comment ID to link to
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    link_text = ""

    if comment_id:
        result = ghe_gh(
            "repo",
            "view",
            "--json",
            "nameWithOwner",
            "--jq",
            ".nameWithOwner",
            capture=True,
        )
        repo = result.stdout.strip()
        link_text = f" -> [details](https://github.com/{repo}/issues/{issue_num}#issuecomment-{comment_id})"

    new_entry = f"- [{timestamp}] {entry}{link_text}"

    # Get current body
    result = ghe_gh(
        "issue", "view", str(issue_num), "--json", "body", "--jq", ".body", capture=True
    )
    current_body = result.stdout

    # Process the body to add the review log entry
    updated_body = _add_log_entry(
        current_body, new_entry, "Review Log (REVIEW)", "_Phase not started_"
    )

    # Update timestamp
    updated_body = _update_timestamp(updated_body)

    # Update issue
    ghe_gh("issue", "edit", str(issue_num), "--body", updated_body)

    print(f"Added review log entry to issue #{issue_num}")


def _add_log_entry(body: str, entry: str, section_header: str, placeholder: str) -> str:
    """
    Helper function to add a log entry to a specific section.

    Args:
        body: Current issue body
        entry: New entry to add
        section_header: Section header to find (e.g., "Changelog (DEV)")
        placeholder: Placeholder text to replace (e.g., "_No entries yet_")

    Returns:
        Updated body with new entry
    """
    lines = body.split("\n")
    result = []
    in_section = False
    entry_added = False

    for line in lines:
        if f"## {section_header}" in line:
            in_section = True
            result.append(line)
        elif in_section and placeholder in line:
            # Replace placeholder with entry
            result.append(entry)
            entry_added = True
            in_section = False
        elif in_section and line.strip() == "---":
            # End of section - add entry before the separator
            if not entry_added:
                result.append(entry)
                entry_added = True
            result.append(line)
            in_section = False
        else:
            result.append(line)

    return "\n".join(result)


def _update_timestamp(body: str) -> str:
    """
    Update the timestamp in the issue body.

    Args:
        body: Current issue body

    Returns:
        Body with updated timestamp
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    updated = re.sub(r"_Last updated:.*_", f"_Last updated: {timestamp}_", body)
    return updated


def init_thread(
    issue_num: int, requirements: str = "No requirements specified"
) -> None:
    """
    Initialize thread with first post.

    Args:
        issue_num: Issue number
        requirements: Requirements text
    """
    debug_log(f"Creating thread for issue #{issue_num}")
    # Check if epic
    if is_epic_issue(issue_num):
        phase = "epic"
    else:
        phase = get_issue_phase(issue_num)

    first_post = create_first_post(issue_num, phase, requirements)

    # Update the issue body with the first post template
    ghe_gh("issue", "edit", str(issue_num), "--body", first_post)

    manager = get_phase_manager(phase)
    print(f"{GREEN}Initialized thread #{issue_num} with {manager} as manager{NC}")


def transition_phase(issue_num: int, new_phase: str) -> None:
    """
    Transition phase and update manager.

    Args:
        issue_num: Issue number
        new_phase: New phase to transition to
    """
    # Update labels
    old_phase = get_issue_phase(issue_num)

    # Remove old phase label (ignore errors if it doesn't exist)
    try:
        ghe_gh(
            "issue",
            "edit",
            str(issue_num),
            "--remove-label",
            f"phase:{old_phase}",
            capture=True,
        )
    except subprocess.CalledProcessError:
        pass  # Ignore if label doesn't exist

    # Add new phase label
    ghe_gh("issue", "edit", str(issue_num), "--add-label", f"phase:{new_phase}")

    # Update first post manager
    update_first_post_manager(issue_num, new_phase)

    new_manager = get_phase_manager(new_phase)
    print(f"{GREEN}Transitioned issue #{issue_num} from {old_phase} to {new_phase}{NC}")
    print(f"{GREEN}New thread manager: {new_manager}{NC}")


def get_posting_agent(issue_num: int) -> str:
    """
    Get appropriate agent for posting based on phase.
    Athena ONLY for epic threads.

    Args:
        issue_num: Issue number

    Returns:
        Agent name for posting
    """
    if is_epic_issue(issue_num):
        return "Athena"
    else:
        phase = get_issue_phase(issue_num)
        return get_phase_manager(phase)


def main() -> None:
    """Main CLI entry point."""
    debug_log("thread_manager started")
    # Initialize GHE environment
    ghe_init()

    parser = argparse.ArgumentParser(
        description="Phase-based thread management for GHE",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  init <issue> [requirements]              Initialize thread with first post template
  transition <issue> <phase>               Transition to new phase (dev/test/review)
  add-changelog <issue> <entry> [comment_id]    Add changelog entry
  add-testlog <issue> <entry> [comment_id]      Add test log entry
  add-reviewlog <issue> <entry> [comment_id]    Add review log entry
  get-manager <phase>                      Get manager name for phase
  get-posting-agent <issue>                Get appropriate agent for posting
  is-epic <issue>                          Check if issue is an epic
  update-manager <issue> <phase>           Update first post manager avatar

Phase managers:
  dev    -> Hephaestus (builds and shapes)
  test   -> Artemis (hunts bugs)
  review -> Hera (evaluates quality)
  epic   -> Athena (coordinates design)
        """,
    )

    parser.add_argument("command", help="Command to execute")
    parser.add_argument("args", nargs="*", help="Command arguments")

    args = parser.parse_args()

    command = args.command
    cmd_args = args.args
    debug_log(f"Command: {command}")

    try:
        if command == "init":
            if len(cmd_args) < 1:
                print(f"{RED}Error: init requires issue number{NC}", file=sys.stderr)
                sys.exit(1)
            issue_num = int(cmd_args[0])
            requirements = (
                cmd_args[1] if len(cmd_args) > 1 else "No requirements specified"
            )
            init_thread(issue_num, requirements)

        elif command == "transition":
            if len(cmd_args) < 2:
                print(
                    f"{RED}Error: transition requires issue number and phase{NC}",
                    file=sys.stderr,
                )
                sys.exit(1)
            issue_num = int(cmd_args[0])
            new_phase = cmd_args[1]
            transition_phase(issue_num, new_phase)

        elif command == "add-changelog":
            if len(cmd_args) < 2:
                print(
                    f"{RED}Error: add-changelog requires issue number and entry{NC}",
                    file=sys.stderr,
                )
                sys.exit(1)
            issue_num = int(cmd_args[0])
            entry = cmd_args[1]
            comment_id = cmd_args[2] if len(cmd_args) > 2 else None
            add_changelog_entry(issue_num, entry, comment_id)

        elif command == "add-testlog":
            if len(cmd_args) < 2:
                print(
                    f"{RED}Error: add-testlog requires issue number and entry{NC}",
                    file=sys.stderr,
                )
                sys.exit(1)
            issue_num = int(cmd_args[0])
            entry = cmd_args[1]
            comment_id = cmd_args[2] if len(cmd_args) > 2 else None
            add_testlog_entry(issue_num, entry, comment_id)

        elif command == "add-reviewlog":
            if len(cmd_args) < 2:
                print(
                    f"{RED}Error: add-reviewlog requires issue number and entry{NC}",
                    file=sys.stderr,
                )
                sys.exit(1)
            issue_num = int(cmd_args[0])
            entry = cmd_args[1]
            comment_id = cmd_args[2] if len(cmd_args) > 2 else None
            add_reviewlog_entry(issue_num, entry, comment_id)

        elif command == "get-manager":
            if len(cmd_args) < 1:
                print(f"{RED}Error: get-manager requires phase{NC}", file=sys.stderr)
                sys.exit(1)
            phase = cmd_args[0]
            print(get_phase_manager(phase))

        elif command == "get-posting-agent":
            if len(cmd_args) < 1:
                print(
                    f"{RED}Error: get-posting-agent requires issue number{NC}",
                    file=sys.stderr,
                )
                sys.exit(1)
            issue_num = int(cmd_args[0])
            print(get_posting_agent(issue_num))

        elif command == "is-epic":
            if len(cmd_args) < 1:
                print(f"{RED}Error: is-epic requires issue number{NC}", file=sys.stderr)
                sys.exit(1)
            issue_num = int(cmd_args[0])
            print("true" if is_epic_issue(issue_num) else "false")

        elif command == "update-manager":
            if len(cmd_args) < 2:
                print(
                    f"{RED}Error: update-manager requires issue number and phase{NC}",
                    file=sys.stderr,
                )
                sys.exit(1)
            issue_num = int(cmd_args[0])
            new_phase = cmd_args[1]
            update_first_post_manager(issue_num, new_phase)

        else:
            debug_log(f"Unknown command: {command}", level="ERROR")
            print(f"{RED}Error: Unknown command '{command}'{NC}", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

        debug_log("thread_manager completed")

    except subprocess.CalledProcessError as e:
        debug_log(f"Error executing gh command: {e}", level="ERROR")
        print(f"{RED}Error executing gh command: {e}{NC}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        debug_log(f"Error: {e}", level="ERROR")
        print(f"{RED}Error: {e}{NC}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
