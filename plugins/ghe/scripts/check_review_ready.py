#!/usr/bin/env python3
"""check_review_ready.py - Check for background threads ready for user review

This script is called by Claude to check if any background feature/bug
threads have reached the REVIEW phase and are waiting for user participation.

When a thread is ready, Claude should ask the user if they want to:
1. Temporarily pause the main conversation
2. Join the feature thread to participate in review with Hera

Usage:
    check_review_ready.py           # List all review-ready threads
    check_review_ready.py --json    # Output as JSON
    check_review_ready.py --notify  # Generate notification message
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Import from ghe_common
try:
    import ghe_common
except ImportError:
    # Fallback if import fails
    print(
        "ERROR: Cannot import ghe_common. Ensure ghe_common.py is in the same directory.",
        file=sys.stderr,
    )
    sys.exit(1)


# Additional color codes
CYAN = "\033[0;36m"


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to .claude/hook_debug.log in standard log format."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [check_review_ready] - {message}\n")
    except Exception:
        pass


def run_gh_command(
    args: list[str], capture_output: bool = True
) -> subprocess.CompletedProcess[str]:
    """Execute gh CLI command and return output.

    Args:
        args: List of command arguments (e.g., ['issue', 'list', '--json', 'number,title'])
        capture_output: Whether to capture stdout/stderr

    Returns:
        subprocess.CompletedProcess object
    """
    debug_log(f"Running gh command: gh {' '.join(args)}")
    try:
        result = subprocess.run(
            ["gh"] + args, capture_output=capture_output, text=True, check=False
        )
        debug_log(f"gh command returncode: {result.returncode}")
        return result
    except FileNotFoundError:
        debug_log("gh command not found", "ERROR")
        print(
            "ERROR: 'gh' command not found. Please install GitHub CLI.", file=sys.stderr
        )
        sys.exit(1)


def get_review_threads_from_file(threads_file: Path) -> list[dict[str, object]]:
    """Extract threads in REVIEW phase from threads file.

    Args:
        threads_file: Path to ghe-background-threads.json

    Returns:
        List of thread objects in REVIEW phase
    """
    debug_log(f"Reading threads file: {threads_file}")
    try:
        with open(threads_file, "r") as f:
            data: dict[str, object] = json.load(f)
            threads_raw = data.get("threads", [])
            threads: list[dict[str, object]] = (
                threads_raw if isinstance(threads_raw, list) else []
            )
            debug_log(f"Found {len(threads)} total threads in file")

            # Filter for active threads in REVIEW phase
            review_threads: list[dict[str, object]] = [
                thread
                for thread in threads
                if isinstance(thread, dict)
                and thread.get("status") == "active"
                and thread.get("phase") == "REVIEW"
            ]
            debug_log(f"Found {len(review_threads)} threads in REVIEW phase")
            return review_threads
    except (json.JSONDecodeError, FileNotFoundError) as e:
        debug_log(f"Failed to read threads file: {e}", "ERROR")
        return []


def get_review_issues_from_github() -> list[dict[str, object]]:
    """Fetch issues with phase:review label from GitHub.

    Returns:
        List of issue objects with number and title
    """
    debug_log("Fetching issues with phase:review label from GitHub")
    result = run_gh_command(
        [
            "issue",
            "list",
            "--label",
            "phase:review",
            "--state",
            "open",
            "--json",
            "number,title",
        ]
    )

    if result.returncode != 0:
        debug_log(f"gh issue list failed with returncode {result.returncode}", "ERROR")
        return []

    try:
        issues_raw: object = json.loads(result.stdout)
        issues: list[dict[str, object]] = (
            issues_raw if isinstance(issues_raw, list) else []
        )
        debug_log(f"Found {len(issues)} issues with phase:review label")
        return issues
    except json.JSONDecodeError as e:
        debug_log(f"Failed to parse gh output: {e}", "ERROR")
        return []


def output_json(threads: list[dict[str, object]]) -> None:
    """Output threads in JSON format.

    Args:
        threads: List of thread/issue objects
    """
    output: dict[str, object] = {"review_ready": threads, "count": len(threads)}
    print(json.dumps(output, indent=2))


def output_notify(threads: list[dict[str, object]], from_github: bool = False) -> None:
    """Output notification message for review-ready threads.

    Args:
        threads: List of thread/issue objects
        from_github: Whether threads came from GitHub (True) or threads file (False)
    """
    main_issue = ghe_common.ghe_get_setting("current_issue", "")

    print()
    print(
        f"{ghe_common.GHE_YELLOW}========================================{ghe_common.GHE_NC}"
    )
    print(f"{ghe_common.GHE_YELLOW}   FEATURE(S) READY FOR REVIEW!{ghe_common.GHE_NC}")
    print(
        f"{ghe_common.GHE_YELLOW}========================================{ghe_common.GHE_NC}"
    )
    print()

    for thread in threads:
        if from_github:
            # GitHub issue format
            number = thread.get("number")
            title = thread.get("title")
            print(f"  Issue #{number}: {title}")
        else:
            # Threads file format
            issue = thread.get("issue")
            title = thread.get("title")
            print(f"  Issue #{issue}: {title}")

    print()
    print("These features have completed DEV and TEST phases.")
    print("Hera is conducting the review and may need your input.")
    print()

    if main_issue and main_issue != "null":
        print(f"Currently in main conversation: #{main_issue}")
        print()
        print("Would you like to:")
        print("  1. Temporarily pause our conversation")
        print("  2. Join a feature thread to participate in the review")
        print()

    print('To switch: "join review for #<issue-number>"')
    print()


def output_list(threads: list[dict[str, object]], from_github: bool = False) -> None:
    """Output threads in list format.

    Args:
        threads: List of thread/issue objects
        from_github: Whether threads came from GitHub (True) or threads file (False)
    """
    print(f"{ghe_common.GHE_GREEN}Threads ready for review:{ghe_common.GHE_NC}")

    for thread in threads:
        if from_github:
            # GitHub issue format
            number = thread.get("number")
            title = thread.get("title")
            print(f"  #{number}: {title}")
        else:
            # Threads file format
            issue = thread.get("issue")
            title = thread.get("title")
            parent_issue = thread.get("parent_issue")
            parent_str = f"#{parent_issue}" if parent_issue else "none"
            print(f"  #{issue}: {title} (parent: {parent_str})")

    if not from_github:
        print()
        print(f"Total: {len(threads)} thread(s)")


def main() -> None:
    """Main entry point."""
    debug_log("check_review_ready.py started")
    # Parse command line arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else "list"
    debug_log(f"Mode: {mode}")

    # Initialize GHE environment
    ghe_common.ghe_init()
    debug_log("GHE environment initialized")

    # Check threads file - GHE_REPO_ROOT is guaranteed to be set after ghe_init()
    repo_root: str = ghe_common.GHE_REPO_ROOT or "."
    threads_file = Path(repo_root) / ".claude" / "ghe-background-threads.json"
    debug_log(f"Threads file path: {threads_file}")

    if not threads_file.exists():
        debug_log("Threads file does not exist")
        if mode == "--json":
            print('{"review_ready": [], "count": 0}')
        else:
            print("No background threads tracked.")
        debug_log("check_review_ready.py completed (no threads file)")
        sys.exit(0)

    # Find threads in REVIEW phase from threads file
    review_threads = get_review_threads_from_file(threads_file)

    if not review_threads:
        debug_log("No review threads in file, checking GitHub")
        # Also check GitHub directly for phase:review labels
        review_issues = get_review_issues_from_github()

        if not review_issues:
            debug_log("No review issues found on GitHub either")
            if mode == "--json":
                print('{"review_ready": [], "count": 0}')
            else:
                print("No threads ready for review.")
            debug_log("check_review_ready.py completed (no review threads)")
            sys.exit(0)

        # Use GitHub data
        debug_log(f"Using {len(review_issues)} issues from GitHub")
        if mode == "--json":
            output_json(review_issues)
        elif mode == "--notify":
            output_notify(review_issues, from_github=True)
        else:
            output_list(review_issues, from_github=True)
        debug_log("check_review_ready.py completed (GitHub data)")
        sys.exit(0)

    # Process from threads file
    debug_log(f"Using {len(review_threads)} threads from file")
    if mode == "--json":
        output_json(review_threads)
    elif mode == "--notify":
        output_notify(review_threads, from_github=False)
    else:
        output_list(review_threads, from_github=False)
    debug_log("check_review_ready.py completed (file data)")


if __name__ == "__main__":
    main()
