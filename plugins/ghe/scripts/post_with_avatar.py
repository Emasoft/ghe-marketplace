#!/usr/bin/env python3
"""
post_with_avatar.py - Helper for posting GitHub comments with avatar banners

This module provides functions to post GitHub comments with avatar banners.
Can be used as a library (import functions) or CLI tool.

Usage as library:
    from post_with_avatar import post_issue_comment, format_comment
    post_issue_comment(42, "Claude", "Hello from Claude!")

Usage as CLI:
    python3 post_with_avatar.py --help
    python3 post_with_avatar.py --test
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))

from ghe_common import (
    ghe_init,
    ghe_gh,
    ghe_get_avatar_url,
    ghe_get_avatar_base_url,
    GHE_AGENT_AVATARS,
    GHE_AGENT_NAMES,
)


def get_github_user_avatar(username: str, size: int = 77) -> str:
    """
    Get GitHub user avatar URL dynamically.

    Args:
        username: GitHub username
        size: Avatar size in pixels (default: 77)

    Returns:
        URL to the user's GitHub avatar
    """
    return f"https://avatars.githubusercontent.com/{username}?s={size}"


def get_avatar_url(name: str) -> str:
    """
    Get avatar URL for an agent name.

    Args:
        name: Agent name or agent ID (e.g., "Claude" or "ghe:dev-thread-manager")

    Returns:
        URL to the agent's avatar image
    """
    # If name starts with "ghe:", map to display name
    if name.startswith("ghe:"):
        name = GHE_AGENT_NAMES.get(name, name)

    # Use centralized function
    return ghe_get_avatar_url(name)


def get_display_name(agent_id: str) -> str:
    """
    Get display name for an agent.

    Args:
        agent_id: Agent identifier (e.g., "ghe:dev-thread-manager")

    Returns:
        Human-readable display name
    """
    return GHE_AGENT_NAMES.get(agent_id, agent_id)


def get_avatar_header(name: str) -> str:
    """
    Generate the avatar header only (without content).
    Alias for avatar_header() for API compatibility.

    Args:
        name: Agent name or agent ID

    Returns:
        Formatted avatar header markdown
    """
    return avatar_header(name)


def format_comment(name: str, content: str) -> str:
    """
    Format a comment with avatar banner.

    Args:
        name: Agent name or agent ID
        content: Comment body content

    Returns:
        Formatted markdown with avatar and content
    """
    # If name starts with "ghe:", map to display name
    if name.startswith("ghe:"):
        name = GHE_AGENT_NAMES.get(name, name)

    avatar_url = get_avatar_url(name)

    return f'''<p><img src="{avatar_url}" width="81" height="81" alt="{name}" align="middle">&nbsp;&nbsp;&nbsp;&nbsp;<span style="vertical-align: middle;"><strong>{name} said:</strong></span></p>

{content}'''


def post_issue_comment(issue_num: int, agent_name: str, content: str) -> None:
    """
    Post a comment to a GitHub issue with avatar banner.

    Args:
        issue_num: Issue number
        agent_name: Agent name or agent ID
        content: Comment body content

    Raises:
        subprocess.CalledProcessError: If gh command fails
    """
    formatted = format_comment(agent_name, content)
    ghe_gh("issue", "comment", str(issue_num), "--body", formatted, capture=True)


def post_pr_comment(pr_num: int, agent_name: str, content: str) -> None:
    """
    Post a comment to a GitHub PR with avatar banner.

    Args:
        pr_num: Pull request number
        agent_name: Agent name or agent ID
        content: Comment body content

    Raises:
        subprocess.CalledProcessError: If gh command fails
    """
    formatted = format_comment(agent_name, content)
    ghe_gh("pr", "comment", str(pr_num), "--body", formatted, capture=True)


def avatar_header(name: str) -> str:
    """
    Generate the avatar header only (without content).

    Args:
        name: Agent name or agent ID

    Returns:
        Formatted avatar header markdown
    """
    # If name starts with "ghe:", map to display name
    if name.startswith("ghe:"):
        name = GHE_AGENT_NAMES.get(name, name)

    avatar_url = get_avatar_url(name)

    return f'''<p><img src="{avatar_url}" width="81" height="81" alt="{name}" align="middle">&nbsp;&nbsp;&nbsp;&nbsp;<span style="vertical-align: middle;"><strong>{name} said:</strong></span></p>

'''


def run_tests() -> None:
    """Run basic tests to verify functionality."""
    print("Running tests...")
    print(f"\n0. Avatar base URL (dynamic): {ghe_get_avatar_base_url()}")

    print("\n1. Testing get_avatar_url():")
    print(f"   Claude: {get_avatar_url('Claude')}")
    print(f"   ghe:dev-thread-manager: {get_avatar_url('ghe:dev-thread-manager')}")
    print(f"   Unknown agent: {get_avatar_url('NewAgent')}")

    print("\n2. Testing get_github_user_avatar():")
    print(f"   User 'octocat': {get_github_user_avatar('octocat')}")
    print(f"   User 'octocat' (size 128): {get_github_user_avatar('octocat', 128)}")

    print("\n3. Testing get_display_name():")
    print(f"   ghe:dev-thread-manager: {get_display_name('ghe:dev-thread-manager')}")
    print(f"   Claude: {get_display_name('Claude')}")

    print("\n4. Testing format_comment():")
    comment = format_comment("Claude", "This is a test comment.")
    print(f"   Result:\n{comment}")

    print("\n5. Testing avatar_header():")
    header = avatar_header("ghe:review-thread-manager")
    print(f"   Result:\n{header}")

    print("\n6. Available agents:")
    for agent_id, display_name in GHE_AGENT_NAMES.items():
        print(f"   {agent_id} -> {display_name}")

    print("\nAll tests completed successfully!")


def main() -> None:
    """Main CLI entry point."""
    ghe_init()  # Initialize GHE environment

    parser = argparse.ArgumentParser(
        description="Helper for posting GitHub comments with avatar banners",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run tests
  %(prog)s --test

  # Get avatar header only
  %(prog)s --header-only Claude

  # Use as Python module
  from post_with_avatar import post_issue_comment
  post_issue_comment(42, "Claude", "Hello!")

Available agents:
  Claude, Hephaestus, Artemis, Hera, Athena, Themis,
  Mnemosyne, Ares, Hermes, Chronos, Cerberus, Argos

Agent IDs:
  ghe:dev-thread-manager       -> Hephaestus
  ghe:test-thread-manager      -> Artemis
  ghe:review-thread-manager    -> Hera
  ghe:github-elements-orchestrator -> Athena
  ghe:phase-gate               -> Themis
  ghe:memory-sync              -> Mnemosyne
  ghe:enforcement              -> Ares
  ghe:reporter                 -> Hermes
  ghe:ci-issue-opener          -> Chronos
  ghe:pr-checker               -> Cerberus
        """
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Run tests to verify functionality"
    )

    parser.add_argument(
        "--header-only",
        metavar="AGENT_NAME",
        help="Print avatar header for the given agent and exit"
    )

    args = parser.parse_args()

    if args.header_only:
        print(avatar_header(args.header_only))
    elif args.test:
        run_tests()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
