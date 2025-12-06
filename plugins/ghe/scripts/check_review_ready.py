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
from pathlib import Path

# Import from ghe_common
try:
    import ghe_common
except ImportError:
    # Fallback if import fails
    print("ERROR: Cannot import ghe_common. Ensure ghe_common.py is in the same directory.", file=sys.stderr)
    sys.exit(1)


# Additional color codes
CYAN = '\033[0;36m'


def run_gh_command(args, capture_output=True):
    """Execute gh CLI command and return output.

    Args:
        args: List of command arguments (e.g., ['issue', 'list', '--json', 'number,title'])
        capture_output: Whether to capture stdout/stderr

    Returns:
        subprocess.CompletedProcess object
    """
    try:
        result = subprocess.run(
            ['gh'] + args,
            capture_output=capture_output,
            text=True,
            check=False
        )
        return result
    except FileNotFoundError:
        print("ERROR: 'gh' command not found. Please install GitHub CLI.", file=sys.stderr)
        sys.exit(1)


def get_review_threads_from_file(threads_file):
    """Extract threads in REVIEW phase from threads file.

    Args:
        threads_file: Path to ghe-background-threads.json

    Returns:
        List of thread objects in REVIEW phase
    """
    try:
        with open(threads_file, 'r') as f:
            data = json.load(f)
            threads = data.get('threads', [])

            # Filter for active threads in REVIEW phase
            review_threads = [
                thread for thread in threads
                if thread.get('status') == 'active' and thread.get('phase') == 'REVIEW'
            ]
            return review_threads
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def get_review_issues_from_github():
    """Fetch issues with phase:review label from GitHub.

    Returns:
        List of issue objects with number and title
    """
    result = run_gh_command([
        'issue', 'list',
        '--label', 'phase:review',
        '--state', 'open',
        '--json', 'number,title'
    ])

    if result.returncode != 0:
        return []

    try:
        issues = json.loads(result.stdout)
        return issues
    except json.JSONDecodeError:
        return []


def output_json(threads):
    """Output threads in JSON format.

    Args:
        threads: List of thread/issue objects
    """
    output = {
        'review_ready': threads,
        'count': len(threads)
    }
    print(json.dumps(output, indent=2))


def output_notify(threads, from_github=False):
    """Output notification message for review-ready threads.

    Args:
        threads: List of thread/issue objects
        from_github: Whether threads came from GitHub (True) or threads file (False)
    """
    main_issue = ghe_common.ghe_get_setting('current_issue', '')

    print()
    print(f"{ghe_common.GHE_YELLOW}========================================{ghe_common.GHE_NC}")
    print(f"{ghe_common.GHE_YELLOW}   FEATURE(S) READY FOR REVIEW!{ghe_common.GHE_NC}")
    print(f"{ghe_common.GHE_YELLOW}========================================{ghe_common.GHE_NC}")
    print()

    for thread in threads:
        if from_github:
            # GitHub issue format
            number = thread.get('number')
            title = thread.get('title')
            print(f"  Issue #{number}: {title}")
        else:
            # Threads file format
            issue = thread.get('issue')
            title = thread.get('title')
            print(f"  Issue #{issue}: {title}")

    print()
    print("These features have completed DEV and TEST phases.")
    print("Hera is conducting the review and may need your input.")
    print()

    if main_issue and main_issue != 'null':
        print(f"Currently in main conversation: #{main_issue}")
        print()
        print("Would you like to:")
        print("  1. Temporarily pause our conversation")
        print("  2. Join a feature thread to participate in the review")
        print()

    print("To switch: \"join review for #<issue-number>\"")
    print()


def output_list(threads, from_github=False):
    """Output threads in list format.

    Args:
        threads: List of thread/issue objects
        from_github: Whether threads came from GitHub (True) or threads file (False)
    """
    print(f"{ghe_common.GHE_GREEN}Threads ready for review:{ghe_common.GHE_NC}")

    for thread in threads:
        if from_github:
            # GitHub issue format
            number = thread.get('number')
            title = thread.get('title')
            print(f"  #{number}: {title}")
        else:
            # Threads file format
            issue = thread.get('issue')
            title = thread.get('title')
            parent_issue = thread.get('parent_issue')
            parent_str = f"#{parent_issue}" if parent_issue else "none"
            print(f"  #{issue}: {title} (parent: {parent_str})")

    if not from_github:
        print()
        print(f"Total: {len(threads)} thread(s)")


def main():
    """Main entry point."""
    # Parse command line arguments
    mode = sys.argv[1] if len(sys.argv) > 1 else 'list'

    # Initialize GHE environment
    ghe_common.ghe_init()

    # Check threads file
    threads_file = Path(ghe_common.GHE_REPO_ROOT) / '.claude' / 'ghe-background-threads.json'

    if not threads_file.exists():
        if mode == '--json':
            print('{"review_ready": [], "count": 0}')
        else:
            print("No background threads tracked.")
        sys.exit(0)

    # Find threads in REVIEW phase from threads file
    review_threads = get_review_threads_from_file(threads_file)

    if not review_threads:
        # Also check GitHub directly for phase:review labels
        review_issues = get_review_issues_from_github()

        if not review_issues:
            if mode == '--json':
                print('{"review_ready": [], "count": 0}')
            else:
                print("No threads ready for review.")
            sys.exit(0)

        # Use GitHub data
        if mode == '--json':
            output_json(review_issues)
        elif mode == '--notify':
            output_notify(review_issues, from_github=True)
        else:
            output_list(review_issues, from_github=True)
        sys.exit(0)

    # Process from threads file
    if mode == '--json':
        output_json(review_threads)
    elif mode == '--notify':
        output_notify(review_threads, from_github=False)
    else:
        output_list(review_threads, from_github=False)


if __name__ == '__main__':
    main()
