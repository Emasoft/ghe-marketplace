#!/usr/bin/env python3
"""
generate_toc.py - Universal Table of Contents generator for Markdown files.

A flexible TOC generator that works with any markdown file.
Supports multiple files, glob patterns, configurable header levels,
and various insertion modes.

Usage:
    python generate_toc.py README.md
    python generate_toc.py docs/*.md
    python generate_toc.py --recursive .
    python generate_toc.py --dry-run --min-level 2 --max-level 4 file.md
    python generate_toc.py --version

Options:
    --dry-run       Print TOC without modifying files
    --min-level N   Minimum header level to include (default: 2)
    --max-level N   Maximum header level to include (default: 3)
    --title TEXT    Custom TOC title (default: "Table of Contents")
    --no-title      Don't add a title to the TOC
    --recursive     Process .md files recursively
    --insert MODE   Insertion mode: 'auto', 'top', 'marker' (default: auto)
    --marker TEXT   Custom marker for insertion (default: <!-- TOC -->)
    --version       Show script version and exit
"""

import argparse
import glob
import re
import sys
from pathlib import Path
from typing import List, Optional, Tuple

# Script version - automatically updated by release.py when releasing marketplace-utils
__version__ = "1.1.4"
SCRIPT_NAME = "generate_toc.py"


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    CYAN = '\033[0;36m'
    NC = '\033[0m'


def info(msg: str) -> None:
    """Print info message."""
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")


def success(msg: str) -> None:
    """Print success message."""
    print(f"{Colors.GREEN}[OK]{Colors.NC} {msg}")


def warn(msg: str) -> None:
    """Print warning message."""
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")


def error(msg: str) -> None:
    """Print error message."""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}", file=sys.stderr)


def print_version() -> None:
    """Print version information."""
    print(f"{Colors.CYAN}{SCRIPT_NAME}{Colors.NC} v{__version__}")
    print(f"Universal Markdown TOC generator")
    print()


def header_to_anchor(header: str) -> str:
    """Convert header text to GitHub-compatible anchor link.

    Handles:
    - Markdown formatting (**bold**, *italic*, `code`)
    - Special characters
    - Unicode characters
    - Emoji (removed)
    """
    anchor = header

    # Remove markdown formatting like **bold** or *italic*
    anchor = re.sub(r'\*+([^*]+)\*+', r'\1', anchor)

    # Remove markdown `code` formatting
    anchor = re.sub(r'`([^`]+)`', r'\1', anchor)

    # Remove HTML tags
    anchor = re.sub(r'<[^>]+>', '', anchor)

    # Remove emoji (common unicode ranges)
    anchor = re.sub(r'[\U0001F300-\U0001F9FF]', '', anchor)

    # Convert to lowercase
    anchor = anchor.lower()

    # Replace spaces with hyphens
    anchor = anchor.replace(' ', '-')

    # Remove special characters except hyphens and alphanumerics
    anchor = re.sub(r'[^a-z0-9\-_]', '', anchor)

    # Remove multiple consecutive hyphens
    anchor = re.sub(r'-+', '-', anchor)

    # Remove leading/trailing hyphens
    anchor = anchor.strip('-')

    return anchor


def extract_headers(
    content: str,
    min_level: int = 2,
    max_level: int = 3,
    skip_toc: bool = True
) -> List[Tuple[int, str, str]]:
    """Extract headers from markdown content.

    Args:
        content: Markdown content
        min_level: Minimum header level (1-6)
        max_level: Maximum header level (1-6)
        skip_toc: Skip "Table of Contents" header

    Returns:
        List of (level, text, anchor) tuples
    """
    headers = []
    in_code_block = False
    in_frontmatter = False
    frontmatter_count = 0

    lines = content.split('\n')

    for i, line in enumerate(lines):
        # Track YAML frontmatter (--- at start of file)
        if i == 0 and line.strip() == '---':
            in_frontmatter = True
            frontmatter_count = 1
            continue

        if in_frontmatter:
            if line.strip() == '---':
                frontmatter_count += 1
                if frontmatter_count >= 2:
                    in_frontmatter = False
            continue

        # Track code blocks
        if line.startswith('```') or line.startswith('~~~'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Match headers (# to ######)
        match = re.match(r'^(#{1,6})\s+(.+)$', line)
        if match:
            hashes, text = match.groups()
            level = len(hashes)

            # Filter by level
            if level < min_level or level > max_level:
                continue

            # Skip TOC header itself
            if skip_toc and text.lower().strip() in ['table of contents', 'toc', 'contents']:
                continue

            anchor = header_to_anchor(text)
            headers.append((level, text.strip(), anchor))

    return headers


def generate_toc(
    headers: List[Tuple[int, str, str]],
    title: Optional[str] = "Table of Contents",
    base_indent: int = 0
) -> str:
    """Generate markdown TOC from headers.

    Args:
        headers: List of (level, text, anchor) tuples
        title: TOC title (None for no title)
        base_indent: Base indentation level

    Returns:
        Formatted TOC as markdown string
    """
    lines = []

    if title:
        lines.append(f"## {title}")
        lines.append('')

    if not headers:
        lines.append('*No headers found*')
        lines.append('')
        return '\n'.join(lines)

    # Find minimum level to normalize indentation
    min_level = min(h[0] for h in headers)

    for level, text, anchor in headers:
        # Calculate indentation based on level difference
        indent_level = level - min_level + base_indent
        indent = '  ' * indent_level

        # Clean display text (remove ** formatting for cleaner look)
        display = re.sub(r'\*+([^*]+)\*+', r'\1', text)
        display = re.sub(r'`([^`]+)`', r'\1', display)

        lines.append(f'{indent}- [{display}](#{anchor})')

    lines.append('')  # Trailing newline
    return '\n'.join(lines)


def find_insertion_point(content: str, mode: str, marker: str) -> Tuple[int, int]:
    """Find where to insert/replace TOC.

    Args:
        content: File content
        mode: 'auto', 'top', or 'marker'
        marker: Marker string for 'marker' mode

    Returns:
        Tuple of (start_position, end_position) for replacement
    """
    if mode == 'marker':
        # Find marker pair for replacement
        start_marker = marker
        end_marker = marker.replace('<!--', '<!-- /') if '<!--' in marker else f'<!-- /{marker} -->'

        start_match = re.search(re.escape(start_marker), content)
        end_match = re.search(re.escape(end_marker), content)

        if start_match and end_match:
            return (start_match.start(), end_match.end())
        elif start_match:
            # Only start marker found, insert after it
            return (start_match.end(), start_match.end())

    elif mode == 'top':
        # Skip YAML frontmatter if present
        if content.startswith('---'):
            match = re.search(r'^---\n.*?\n---\n', content, re.DOTALL)
            if match:
                return (match.end(), match.end())
        return (0, 0)

    # Auto mode: try to find best insertion point
    # 1. After existing TOC (replace it)
    toc_pattern = r'## Table of Contents\n.*?(?=\n## |\n# |\Z)'
    toc_match = re.search(toc_pattern, content, re.DOTALL)
    if toc_match:
        return (toc_match.start(), toc_match.end())

    # 2. After first horizontal rule (common README pattern)
    hr_matches = list(re.finditer(r'\n---\n', content))
    if hr_matches:
        return (hr_matches[0].end(), hr_matches[0].end())

    # 3. After YAML frontmatter
    if content.startswith('---'):
        match = re.search(r'^---\n.*?\n---\n', content, re.DOTALL)
        if match:
            return (match.end(), match.end())

    # 4. After first header
    first_header = re.search(r'^#+ .+\n', content, re.MULTILINE)
    if first_header:
        return (first_header.end(), first_header.end())

    # 5. At the beginning
    return (0, 0)


def process_file(
    file_path: Path,
    dry_run: bool = False,
    min_level: int = 2,
    max_level: int = 3,
    title: Optional[str] = "Table of Contents",
    insert_mode: str = 'auto',
    marker: str = '<!-- TOC -->'
) -> bool:
    """Process a single markdown file.

    Args:
        file_path: Path to markdown file
        dry_run: If True, print TOC without modifying file
        min_level: Minimum header level
        max_level: Maximum header level
        title: TOC title (None for no title)
        insert_mode: 'auto', 'top', or 'marker'
        marker: Marker for 'marker' mode

    Returns:
        True if successful, False otherwise
    """
    if not file_path.exists():
        error(f"File not found: {file_path}")
        return False

    if not file_path.suffix.lower() in ['.md', '.markdown', '.mdown']:
        warn(f"Skipping non-markdown file: {file_path}")
        return False

    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        error(f"Failed to read {file_path}: {e}")
        return False

    # Extract headers
    headers = extract_headers(content, min_level, max_level)

    if not headers:
        warn(f"No headers found in {file_path}")
        return True

    # Generate TOC
    toc = generate_toc(headers, title)

    if dry_run:
        print(f"\n{Colors.CYAN}{'='*60}{Colors.NC}")
        print(f"{Colors.CYAN}File: {file_path}{Colors.NC}")
        print(f"{Colors.CYAN}{'='*60}{Colors.NC}")
        print(toc)
        print(f"Found {len(headers)} headers (levels {min_level}-{max_level})")
        return True

    # Find insertion point
    start_pos, end_pos = find_insertion_point(content, insert_mode, marker)

    # Build new content
    if insert_mode == 'marker':
        # Wrap TOC with markers
        toc_with_markers = f"{marker}\n{toc}{marker.replace('<!--', '<!-- /')}\n"
        new_content = content[:start_pos] + toc_with_markers + content[end_pos:]
    else:
        new_content = content[:start_pos] + '\n' + toc + '\n' + content[end_pos:]

    # Write back
    try:
        file_path.write_text(new_content, encoding='utf-8')
        success(f"Updated {file_path} ({len(headers)} headers)")
        return True
    except Exception as e:
        error(f"Failed to write {file_path}: {e}")
        return False


def collect_files(paths: List[str], recursive: bool = False) -> List[Path]:
    """Collect markdown files from paths and glob patterns.

    Args:
        paths: List of file paths or glob patterns
        recursive: If True, search recursively for .md files

    Returns:
        List of Path objects
    """
    files = []

    for path_str in paths:
        path = Path(path_str)

        if path.is_file():
            files.append(path)
        elif path.is_dir():
            if recursive:
                files.extend(path.rglob('*.md'))
            else:
                files.extend(path.glob('*.md'))
        elif '*' in path_str or '?' in path_str:
            # Glob pattern
            if recursive and '**' not in path_str:
                path_str = f"**/{path_str}"
            files.extend(Path('.').glob(path_str))
        else:
            warn(f"Path not found: {path_str}")

    # Remove duplicates while preserving order
    seen = set()
    unique_files = []
    for f in files:
        resolved = f.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique_files.append(f)

    return unique_files


def main():
    parser = argparse.ArgumentParser(
        description='Universal Table of Contents generator for Markdown files.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s README.md                    # Update single file
  %(prog)s docs/*.md                    # Update all .md in docs/
  %(prog)s --recursive .                # Update all .md recursively
  %(prog)s --dry-run file.md            # Preview without changes
  %(prog)s --min-level 1 --max-level 4 file.md   # Include H1-H4
  %(prog)s --no-title file.md           # TOC without title
  %(prog)s --insert marker --marker "<!-- TOC -->" file.md

Insertion Modes:
  auto    - Smart detection: replace existing TOC, or insert after
            first --- separator, or after frontmatter, or at top
  top     - Insert at top of file (after frontmatter if present)
  marker  - Insert/replace between marker pairs (e.g., <!-- TOC -->)
        """
    )

    parser.add_argument(
        'files',
        nargs='*',
        default=['.'],
        help='Markdown files or directories to process (default: current dir)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Print TOC without modifying files'
    )

    parser.add_argument(
        '--min-level',
        type=int,
        default=2,
        choices=range(1, 7),
        metavar='N',
        help='Minimum header level to include (default: 2)'
    )

    parser.add_argument(
        '--max-level',
        type=int,
        default=3,
        choices=range(1, 7),
        metavar='N',
        help='Maximum header level to include (default: 3)'
    )

    parser.add_argument(
        '--title',
        type=str,
        default='Table of Contents',
        help='Custom TOC title (default: "Table of Contents")'
    )

    parser.add_argument(
        '--no-title',
        action='store_true',
        help="Don't add a title to the TOC"
    )

    parser.add_argument(
        '--recursive', '-r',
        action='store_true',
        help='Process .md files recursively'
    )

    parser.add_argument(
        '--insert',
        choices=['auto', 'top', 'marker'],
        default='auto',
        help='Insertion mode (default: auto)'
    )

    parser.add_argument(
        '--marker',
        type=str,
        default='<!-- TOC -->',
        help='Custom marker for marker insertion mode'
    )

    parser.add_argument(
        '--version', '-v',
        action='store_true',
        help='Show script version and exit'
    )

    args = parser.parse_args()

    # Handle --version
    if args.version:
        print_version()
        return

    # Print version banner
    print_version()

    # Validate level range
    if args.min_level > args.max_level:
        error(f"min-level ({args.min_level}) cannot be greater than max-level ({args.max_level})")
        sys.exit(1)

    # Collect files
    files = collect_files(args.files, args.recursive)

    if not files:
        error("No markdown files found")
        sys.exit(1)

    info(f"Found {len(files)} markdown file(s)")

    # Determine title
    title = None if args.no_title else args.title

    # Process files
    success_count = 0
    for file_path in files:
        if process_file(
            file_path,
            dry_run=args.dry_run,
            min_level=args.min_level,
            max_level=args.max_level,
            title=title,
            insert_mode=args.insert,
            marker=args.marker
        ):
            success_count += 1

    # Summary
    if not args.dry_run:
        print()
        if success_count == len(files):
            success(f"Processed {success_count}/{len(files)} files")
        else:
            warn(f"Processed {success_count}/{len(files)} files")


if __name__ == '__main__':
    main()
