#!/usr/bin/env python3
"""
Generate Table of Contents for README.md

Parses H2 and H3 headers and generates a markdown TOC with anchor links.
Inserts TOC after the intro section (after first ---).

Usage:
    python generate_toc.py [--dry-run]

Options:
    --dry-run    Print TOC without modifying README
"""

import re
import sys
from pathlib import Path


def header_to_anchor(header: str) -> str:
    """Convert header text to GitHub-compatible anchor link."""
    # Remove markdown formatting like **bold** or *italic*
    anchor = re.sub(r'\*+([^*]+)\*+', r'\1', header)
    # Remove other markdown like `code`
    anchor = re.sub(r'`([^`]+)`', r'\1', anchor)
    # Convert to lowercase
    anchor = anchor.lower()
    # Replace spaces with hyphens
    anchor = anchor.replace(' ', '-')
    # Remove special characters except hyphens
    anchor = re.sub(r'[^a-z0-9\-]', '', anchor)
    # Remove multiple consecutive hyphens
    anchor = re.sub(r'-+', '-', anchor)
    # Remove leading/trailing hyphens
    anchor = anchor.strip('-')
    return anchor


def extract_headers(content: str) -> list[tuple[int, str, str]]:
    """Extract H2 and H3 headers from markdown content.

    Returns list of (level, text, anchor) tuples.
    Skips headers that are part of the title block (before first ---).
    """
    headers = []
    in_code_block = False
    past_first_separator = False

    for line in content.split('\n'):
        # Track code blocks
        if line.startswith('```'):
            in_code_block = not in_code_block
            continue

        if in_code_block:
            continue

        # Track if we're past the title block
        if line.strip() == '---':
            past_first_separator = True
            continue

        # Only extract headers after title block
        if not past_first_separator:
            continue

        # Match ## or ### at start of line
        match = re.match(r'^(#{2,3})\s+(.+)$', line)
        if match:
            hashes, text = match.groups()
            level = len(hashes)
            anchor = header_to_anchor(text)
            headers.append((level, text.strip(), anchor))

    return headers


def generate_toc(headers: list[tuple[int, str, str]]) -> str:
    """Generate markdown TOC from headers."""
    lines = ['## Table of Contents', '']

    for level, text, anchor in headers:
        # Skip the TOC header itself if it exists
        if text.lower() == 'table of contents':
            continue
        # Indent H3 with 2 spaces
        indent = '  ' if level == 3 else ''
        # Clean display text (remove ** formatting for cleaner look)
        display = re.sub(r'\*+([^*]+)\*+', r'\1', text)
        lines.append(f'{indent}- [{display}](#{anchor})')

    lines.append('')  # Trailing newline
    return '\n'.join(lines)


def find_toc_insertion_point(content: str) -> int:
    """Find where to insert TOC (after first --- separator after header)."""
    # Find the second --- (first is after badges, we want after that)
    matches = list(re.finditer(r'\n---\n', content))
    if len(matches) >= 1:
        # Insert after the first --- separator (after badges/intro)
        return matches[0].end()
    return 0


def remove_existing_toc(content: str) -> str:
    """Remove existing TOC if present."""
    # Match ## Table of Contents section until next ## header
    pattern = r'## Table of Contents\n.*?(?=\n## |\Z)'
    return re.sub(pattern, '', content, flags=re.DOTALL)


def main():
    dry_run = '--dry-run' in sys.argv

    # Find README relative to script location
    script_dir = Path(__file__).parent
    readme_path = script_dir.parent / 'README.md'

    if not readme_path.exists():
        print(f"ERROR: README.md not found at {readme_path}")
        sys.exit(1)

    content = readme_path.read_text()

    # Remove existing TOC first
    content = remove_existing_toc(content)

    # Extract headers and generate TOC
    headers = extract_headers(content)
    toc = generate_toc(headers)

    if dry_run:
        print("Generated TOC:")
        print("-" * 40)
        print(toc)
        print("-" * 40)
        print(f"\nFound {len(headers)} headers")
        return

    # Find insertion point and insert TOC
    insertion_point = find_toc_insertion_point(content)
    if insertion_point == 0:
        print("WARNING: Could not find insertion point, inserting at beginning")

    new_content = content[:insertion_point] + '\n' + toc + '\n' + content[insertion_point:]

    # Write back
    readme_path.write_text(new_content)
    print(f"TOC generated with {len(headers)} entries")
    print(f"Updated: {readme_path}")


if __name__ == '__main__':
    main()
