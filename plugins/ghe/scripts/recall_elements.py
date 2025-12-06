#!/usr/bin/env python3
"""
recall_elements.py - Element-based memory recall from GitHub Issues
Part of GitHub Elements (GHE) plugin

Element Types:
  knowledge - Requirements, specs, design, algorithms, explanations ("The Talk")
  action    - Code, assets, images, sounds, video, 3D models, configs ("The Reality")
  judgement - Bugs, reviews, feedback, test results, critiques ("The Verdict")

KEY INSIGHT: Only ACTION elements change the project. KNOWLEDGE and JUDGEMENT are discussion.
"""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple
from pathlib import Path

# Import GHE common utilities
from ghe_common import ghe_init, ghe_gh, GHE_RED, GHE_GREEN, GHE_YELLOW, GHE_BLUE, GHE_CYAN, GHE_NC

# Create color aliases for backward compatibility
class Colors:
    """ANSI color codes for terminal output (aliased from ghe_common)."""
    RED = GHE_RED
    GREEN = GHE_GREEN
    BLUE = GHE_BLUE
    YELLOW = GHE_YELLOW
    ORANGE = '\033[0;33m'  # Keep ORANGE as it's not in ghe_common
    CYAN = GHE_CYAN
    NC = GHE_NC
    BOLD = '\033[1m'  # Keep BOLD as it's not in ghe_common


# Badge patterns for searching
PATTERN_KNOWLEDGE = "element-knowledge"
PATTERN_ACTION = "element-action"
PATTERN_JUDGEMENT = "element-judgement"


def get_pattern(element_type: str) -> str:
    """Get badge pattern for element type.

    Args:
        element_type: Element type (knowledge, action, or judgement)

    Returns:
        Badge pattern string
    """
    patterns = {
        'knowledge': PATTERN_KNOWLEDGE,
        'action': PATTERN_ACTION,
        'judgement': PATTERN_JUDGEMENT
    }
    return patterns.get(element_type, '')


def get_color(element_type: str) -> str:
    """Get ANSI color code for element type.

    Args:
        element_type: Element type (knowledge, action, judgement, or other)

    Returns:
        ANSI color code string
    """
    colors = {
        'knowledge': Colors.BLUE,
        'action': Colors.GREEN,
        'judgement': Colors.ORANGE
    }
    return colors.get(element_type, Colors.NC)


def run_gh_command(args: List[str]) -> Optional[str]:
    """Run a gh CLI command and return the output.

    Args:
        args: Command arguments to pass to gh

    Returns:
        Command output as string, or None on failure
    """
    # Use ghe_gh wrapper from ghe_common - unpack args list
    result = ghe_gh(*args, capture=True)
    if result is None or result.returncode != 0:
        return None
    return result.stdout


def get_repo_name() -> str:
    """Get current repository name in format: owner/repo.

    Returns:
        Repository name or empty string if not in a repo
    """
    output = run_gh_command(['repo', 'view', '--json', 'nameWithOwner', '--jq', '.nameWithOwner'])
    return output.strip() if output else ''


def transform_links(content: str) -> str:
    """Transform GitHub links for better context preservation.

    Transforms:
    - Issue references (#123 -> full URL)
    - File references (path/to/file.py -> clickable link)
    - Directory references (REQUIREMENTS/, docs/)

    Args:
        content: Text content to transform

    Returns:
        Transformed content with clickable links
    """
    repo = get_repo_name()

    if not repo:
        # Not in a GitHub repo or gh not authenticated
        return content

    # Transform issue references (#123 -> full URL)
    content = re.sub(
        r'#(\d+)',
        rf'[#\1](https://github.com/{repo}/issues/\1)',
        content
    )

    # Transform file references (path/to/file.py -> clickable link)
    file_extensions = r'\.(py|js|ts|md|yaml|yml|json|sh|tsx|jsx|css|html|txt|conf|cfg)'
    file_pattern = rf'([a-zA-Z0-9_/.@-]+{file_extensions})'

    def replace_file_path(match):
        """Replace file path with link if file exists."""
        file_path = match.group(1)
        if Path(file_path).is_file():
            # Check for line number
            line_match = re.search(r':(\d+)', content[match.end():match.end()+10])
            if line_match:
                line_num = line_match.group(1)
                return f'[`{file_path}:{line_num}`](https://github.com/{repo}/blob/main/{file_path}#L{line_num})'
            else:
                return f'[`{file_path}`](https://github.com/{repo}/blob/main/{file_path})'
        return match.group(0)

    content = re.sub(file_pattern, replace_file_path, content)

    # Transform REQUIREMENTS/ directory references
    content = re.sub(
        r'REQUIREMENTS/([^\s\)]+\.md)',
        rf'[REQUIREMENTS/\1](https://github.com/{repo}/blob/main/REQUIREMENTS/\1)',
        content
    )

    # Transform docs/ directory references
    content = re.sub(
        r'docs/([^\s\)]+\.(md|txt))',
        rf'[docs/\1](https://github.com/{repo}/blob/main/docs/\1)',
        content
    )

    return content


def apply_link_transformation(output: str) -> str:
    """Apply link transformation to output if enabled.

    Args:
        output: Text to potentially transform

    Returns:
        Transformed or original text
    """
    transform_links_enabled = os.environ.get('TRANSFORM_LINKS', 'true').lower() == 'true'

    if transform_links_enabled:
        return transform_links(output)
    return output


def show_stats(issue: str) -> None:
    """Show element distribution statistics for an issue.

    Args:
        issue: GitHub issue number
    """
    print(f"{Colors.BOLD}{Colors.CYAN}GitHub Elements Statistics: Issue #{issue}{Colors.NC}")
    print(f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print()

    # Get statistics using jq
    jq_query = '''
        {
            total: .comments | length,
            knowledge: [.comments[] | select(.body | contains("element-knowledge"))] | length,
            action: [.comments[] | select(.body | contains("element-action"))] | length,
            judgement: [.comments[] | select(.body | contains("element-judgement"))] | length,
            compound: [.comments[] | select(
                ((.body | contains("element-knowledge")) and (.body | contains("element-action"))) or
                ((.body | contains("element-knowledge")) and (.body | contains("element-judgement"))) or
                ((.body | contains("element-action")) and (.body | contains("element-judgement")))
            )] | length
        }
    '''

    output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', jq_query
    ])

    if not output:
        return

    stats = json.loads(output)
    total = stats['total']
    knowledge = stats['knowledge']
    action = stats['action']
    judgement = stats['judgement']
    compound = stats['compound']

    # Calculate percentages
    k_pct = (knowledge * 100 // total) if total > 0 else 0
    a_pct = (action * 100 // total) if total > 0 else 0
    j_pct = (judgement * 100 // total) if total > 0 else 0

    # Display counts with visual bars
    print(f"{Colors.BOLD}Element Distribution:{Colors.NC}")
    print()

    # Knowledge bar
    print(f"  {Colors.BLUE}KNOWLEDGE{Colors.NC}  {knowledge:<3} ", end='')
    print(f"{Colors.BLUE}{'█' * (k_pct // 5)}{Colors.NC}", end='')
    print(f"{'░' * (20 - k_pct // 5)} {k_pct}%")

    # Action bar
    print(f"  {Colors.GREEN}ACTION{Colors.NC}     {action:<3} ", end='')
    print(f"{Colors.GREEN}{'█' * (a_pct // 5)}{Colors.NC}", end='')
    print(f"{'░' * (20 - a_pct // 5)} {a_pct}%")

    # Judgement bar
    print(f"  {Colors.ORANGE}JUDGEMENT{Colors.NC}  {judgement:<3} ", end='')
    print(f"{Colors.ORANGE}{'█' * (j_pct // 5)}{Colors.NC}", end='')
    print(f"{'░' * (20 - j_pct // 5)} {j_pct}%")

    print()
    print(f"{Colors.BOLD}Summary:{Colors.NC}")
    print(f"  Total comments:    {total}")
    print(f"  Compound elements: {compound} (multi-badge)")
    print()


def query_by_type(issue: str, element_type: str, last_n: int = 0, search_pattern: str = '') -> None:
    """Query and display elements by type.

    Args:
        issue: GitHub issue number
        element_type: Element type (knowledge, action, or judgement)
        last_n: Return only the last N elements (0 = all)
        search_pattern: Filter elements containing this pattern (case-insensitive)
    """
    pattern = get_pattern(element_type)
    color = get_color(element_type)

    print(f"{Colors.BOLD}{color}Recalling {element_type.upper()} elements from Issue #{issue}{Colors.NC}")
    print(f"{color}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print()

    # Build jq filter
    if search_pattern:
        # Case-insensitive search within element type
        jq_filter = f'''
            [.comments[] | select(.body | contains("{pattern}")) |
             select(.body | ascii_downcase | contains("{search_pattern.lower()}"))]
        '''
    else:
        jq_filter = f'[.comments[] | select(.body | contains("{pattern}"))]'

    # Add sorting
    jq_filter += ' | sort_by(.createdAt)'

    # Add limiting
    if last_n > 0:
        jq_filter += f' | .[-{last_n}:]'

    # Format output
    jq_filter += ' | .[] | {date: .createdAt, author: .author.login, body: .body}'

    # Execute query
    output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', jq_filter
    ])

    if not output or output.strip() == '':
        print(f"{Colors.YELLOW}No {element_type} elements found{Colors.NC}")
        if search_pattern:
            print(f'{Colors.YELLOW}(searched for: "{search_pattern}"){Colors.NC}')
        return

    # Parse and display results
    for line in output.strip().split('\n'):
        if not line.strip():
            continue

        try:
            element = json.loads(line)
            date = element['date'].split('T')[0]
            author = element['author']
            body = element['body']

            # Format output with box drawing
            formatted = f"┌──────────────────────────────────────────────────────────────┐\n"
            formatted += f"│ {date} │ @{author}\n"
            formatted += f"├──────────────────────────────────────────────────────────────┤\n"

            # Show first 15 lines of body
            body_lines = body.split('\n')[:15]
            for body_line in body_lines:
                formatted += f"│ {body_line}\n"

            formatted += f"└──────────────────────────────────────────────────────────────┘\n"

            # Apply link transformation and print
            print(apply_link_transformation(formatted))

        except json.JSONDecodeError:
            continue


def query_compound(issue: str, types: str, last_n: int = 0) -> None:
    """Query elements with multiple badges (compound elements).

    Args:
        issue: GitHub issue number
        types: Compound type string (e.g., "knowledge+action")
        last_n: Return only the last N elements (0 = all)
    """
    print(f"{Colors.BOLD}{Colors.CYAN}Recalling COMPOUND elements ({types}) from Issue #{issue}{Colors.NC}")
    print(f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print()

    # Parse compound type and build conditions
    conditions = []

    if 'knowledge' in types:
        conditions.append(f'(.body | contains("{PATTERN_KNOWLEDGE}"))')

    if 'action' in types:
        conditions.append(f'(.body | contains("{PATTERN_ACTION}"))')

    if 'judgement' in types:
        conditions.append(f'(.body | contains("{PATTERN_JUDGEMENT}"))')

    if not conditions:
        print(f"{Colors.RED}Error: Invalid compound type{Colors.NC}", file=sys.stderr)
        return

    # Join conditions with 'and'
    condition_str = ' and '.join(conditions)

    # Build jq filter
    jq_filter = f'[.comments[] | select({condition_str})] | sort_by(.createdAt)'

    if last_n > 0:
        jq_filter += f' | .[-{last_n}:]'

    jq_filter += ' | .[] | {date: .createdAt, author: .author.login, body: .body}'

    # Execute query
    output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', jq_filter
    ])

    if not output or output.strip() == '':
        print(f"{Colors.YELLOW}No compound elements found matching: {types}{Colors.NC}")
        return

    # Parse and display results
    for line in output.strip().split('\n'):
        if not line.strip():
            continue

        try:
            element = json.loads(line)
            date = element['date'].split('T')[0]
            author = element['author']
            body = element['body']

            # Format output with box drawing
            formatted = f"┌──────────────────────────────────────────────────────────────┐\n"
            formatted += f"│ {date} │ @{author}\n"
            formatted += f"├──────────────────────────────────────────────────────────────┤\n"

            # Show first 15 lines of body
            body_lines = body.split('\n')[:15]
            for body_line in body_lines:
                formatted += f"│ {body_line}\n"

            formatted += f"└──────────────────────────────────────────────────────────────┘\n"

            # Apply link transformation and print
            print(apply_link_transformation(formatted))

        except json.JSONDecodeError:
            continue


def smart_recover(issue: str) -> None:
    """Smart recovery mode - show context for resuming work.

    Displays:
    1. Element statistics
    2. First KNOWLEDGE element (original context)
    3. Last ACTION element (current state)
    4. Recent JUDGEMENT elements (open issues)
    5. Recommended next action

    Args:
        issue: GitHub issue number
    """
    print(f"{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.BOLD}{Colors.CYAN}║         GHE SMART RECOVERY: Issue #{issue:<27}║{Colors.NC}")
    print(f"{Colors.BOLD}{Colors.CYAN}╚════════════════════════════════════════════════════════════════╝{Colors.NC}")
    print()

    # 1. Show statistics first
    show_stats(issue)

    # 2. Get first KNOWLEDGE (original context)
    print(f"{Colors.BOLD}{Colors.BLUE}═══ ORIGINAL CONTEXT (First Knowledge Element) ═══{Colors.NC}")
    print()

    jq_query = '''
        [.comments[] | select(.body | contains("element-knowledge"))] |
        first |
        if . then
            "Date: \\(.createdAt | split("T")[0])\\nAuthor: @\\(.author.login)\\n\\n\\(.body | split("\\n")[0:20] | join("\\n"))"
        else
            "No knowledge elements found"
        end
    '''

    output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', jq_query
    ])

    if output and output.strip() and output.strip() != 'null':
        first_knowledge = output.strip().strip('"').replace('\\n', '\n')
        first_knowledge = apply_link_transformation(first_knowledge)
        print(f"{Colors.BLUE}{first_knowledge}{Colors.NC}")
    else:
        print(f"{Colors.YELLOW}No knowledge elements found{Colors.NC}")

    print()

    # 3. Get last ACTION (current state)
    print(f"{Colors.BOLD}{Colors.GREEN}═══ CURRENT STATE (Last Action Element) ═══{Colors.NC}")
    print()

    jq_query = '''
        [.comments[] | select(.body | contains("element-action"))] |
        last |
        if . then
            "Date: \\(.createdAt | split("T")[0])\\nAuthor: @\\(.author.login)\\n\\n\\(.body | split("\\n")[0:25] | join("\\n"))"
        else
            "No action elements found"
        end
    '''

    output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', jq_query
    ])

    if output and output.strip() and output.strip() != 'null':
        last_action = output.strip().strip('"').replace('\\n', '\n')
        last_action = apply_link_transformation(last_action)
        print(f"{Colors.GREEN}{last_action}{Colors.NC}")
    else:
        print(f"{Colors.YELLOW}No action elements found{Colors.NC}")

    print()

    # 4. Get recent JUDGEMENT (open issues)
    print(f"{Colors.BOLD}{Colors.ORANGE}═══ OPEN ISSUES (Recent Judgement Elements) ═══{Colors.NC}")
    print()

    jq_query = '''
        [.comments[] | select(.body | contains("element-judgement"))] |
        .[-3:] |
        .[] |
        "┌─ \\(.createdAt | split("T")[0]) │ @\\(.author.login)\\n\\(.body | split("\\n")[0:10] | .[] | "│ \\(.)")\\n└─────────────────────────────────"
    '''

    output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', jq_query
    ])

    if output and output.strip():
        recent_judgements = output.strip().strip('"').replace('\\n', '\n')
        recent_judgements = apply_link_transformation(recent_judgements)
        print(f"{Colors.ORANGE}{recent_judgements}{Colors.NC}")
    else:
        print(f"{Colors.YELLOW}No judgement elements found{Colors.NC}")

    print()

    # 5. Recommended next action
    print(f"{Colors.BOLD}{Colors.CYAN}═══ RECOMMENDED NEXT ACTION ═══{Colors.NC}")
    print()

    # Get counts for analysis
    action_count_output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', '[.comments[] | select(.body | contains("element-action"))] | length'
    ])
    action_count = int(action_count_output.strip()) if action_count_output else 0

    knowledge_count_output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', '[.comments[] | select(.body | contains("element-knowledge"))] | length'
    ])
    knowledge_count = int(knowledge_count_output.strip()) if knowledge_count_output else 0

    judgement_count_output = run_gh_command([
        'issue', 'view', issue,
        '--comments',
        '--json', 'comments',
        '--jq', '[.comments[] | select(.body | contains("element-judgement"))] | length'
    ])
    judgement_count = int(judgement_count_output.strip()) if judgement_count_output else 0

    # Provide recommendations
    if judgement_count > 0:
        print(f"1. {Colors.ORANGE}Address recent judgements{Colors.NC} - There are {judgement_count} issues/feedback to review")

    if action_count > 0:
        print(f"2. {Colors.GREEN}Continue from last action{Colors.NC} - Resume development from last checkpoint")

    if knowledge_count > 0 and action_count == 0:
        print(f"1. {Colors.BLUE}Start implementation{Colors.NC} - Knowledge exists but no actions yet")

    if knowledge_count == 0 and action_count == 0 and judgement_count == 0:
        print(f"{Colors.YELLOW}No elements found. This issue may not be using GHE element tracking.{Colors.NC}")

    print()
    print(f"{Colors.CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{Colors.NC}")
    print(f"{Colors.CYAN}Recovery complete. Use --type to drill into specific elements.{Colors.NC}")


def create_parser() -> argparse.ArgumentParser:
    """Create argument parser with all options.

    Returns:
        Configured ArgumentParser instance
    """
    parser = argparse.ArgumentParser(
        description='Element-based memory recall from GitHub Issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
ELEMENT TYPES:
  knowledge   "The Talk" - Requirements, specs, design, algorithms (blue)
  action      "The Reality" - Code, assets, images, sounds, video, configs (green)
  judgement   "The Verdict" - Bugs, reviews, feedback, critiques (orange)

  KEY: Only ACTION changes the project. KNOWLEDGE/JUDGEMENT are discussion.

EXAMPLES:
  # Get all KNOWLEDGE elements from issue #201
  recall_elements.py --issue 201 --type knowledge

  # Get last 5 ACTION elements
  recall_elements.py --issue 201 --type action --last 5

  # Search for JWT-related JUDGEMENT elements
  recall_elements.py --issue 201 --type judgement --search "jwt"

  # Show element statistics
  recall_elements.py --issue 201 --stats

  # Smart recovery for resuming work
  recall_elements.py --issue 201 --recover

  # Get compound elements (both knowledge and action)
  recall_elements.py --issue 201 --compound "knowledge+action"

RECALL DECISION GUIDE:
  "What code did we write?"        → --type action
  "What assets were created?"      → --type action
  "Show the new images/sprites"    → --type action
  "What files changed?"            → --type action
  "What were the requirements?"    → --type knowledge
  "What was the design?"           → --type knowledge
  "What bugs did we find?"         → --type judgement
  "What issues remain?"            → --type judgement
  "What feedback was given?"       → --type judgement
  "Full context"                   → --recover
        '''
    )

    parser.add_argument(
        '--issue',
        type=str,
        required=True,
        help='Issue number to query (required)'
    )

    parser.add_argument(
        '--type',
        type=str,
        choices=['knowledge', 'action', 'judgement'],
        help='Element type to recall (knowledge|action|judgement)'
    )

    parser.add_argument(
        '--last',
        type=int,
        default=0,
        metavar='N',
        help='Return only the last N elements of the type'
    )

    parser.add_argument(
        '--search',
        type=str,
        default='',
        metavar='PATTERN',
        help='Filter elements containing PATTERN (case-insensitive)'
    )

    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show element distribution statistics'
    )

    parser.add_argument(
        '--recover',
        action='store_true',
        help='Smart recovery mode - show context for resuming work'
    )

    parser.add_argument(
        '--compound',
        type=str,
        metavar='TYPE',
        help='Get elements with multiple badges (e.g., "knowledge+action")'
    )

    return parser


def validate_args(args: argparse.Namespace) -> None:
    """Validate parsed arguments.

    Args:
        args: Parsed command-line arguments

    Raises:
        SystemExit: If validation fails
    """
    # Validate issue number
    if not args.issue.isdigit():
        print(f"{Colors.RED}Error: Issue must be a number{Colors.NC}", file=sys.stderr)
        sys.exit(1)

    # Check that at least one mode is specified
    if not any([args.type, args.stats, args.recover, args.compound]):
        print(f"{Colors.RED}Error: Specify --type, --stats, --recover, or --compound{Colors.NC}", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    """Main entry point for the script."""
    # Initialize GHE environment
    ghe_init()

    parser = create_parser()
    args = parser.parse_args()

    validate_args(args)

    # Execute requested operation
    if args.stats:
        show_stats(args.issue)
    elif args.recover:
        smart_recover(args.issue)
    elif args.compound:
        query_compound(args.issue, args.compound, args.last)
    elif args.type:
        query_by_type(args.issue, args.type, args.last, args.search)


if __name__ == '__main__':
    main()
