#!/usr/bin/env python3
"""
release.py - Automate version bump, tag, and GitHub release for GHE plugin.

Usage:
    python release.py patch "Fix bug description"
    python release.py minor "Add new feature"
    python release.py major "Breaking changes"

Requirements:
    - GitHub CLI (gh) installed and authenticated
    - jq installed (for JSON validation)
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Tuple

# Colors for terminal output
class Colors:
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    NC = '\033[0m'  # No Color

def info(msg: str) -> None:
    print(f"{Colors.BLUE}[INFO]{Colors.NC} {msg}")

def success(msg: str) -> None:
    print(f"{Colors.GREEN}[OK]{Colors.NC} {msg}")

def warn(msg: str) -> None:
    print(f"{Colors.YELLOW}[WARN]{Colors.NC} {msg}")

def error(msg: str) -> None:
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}", file=sys.stderr)
    sys.exit(1)

def run_cmd(cmd: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command."""
    result = subprocess.run(
        cmd,
        shell=True,
        capture_output=capture,
        text=True
    )
    if check and result.returncode != 0:
        error(f"Command failed: {cmd}\n{result.stderr if capture else ''}")
    return result

def get_paths() -> dict:
    """Get all relevant file paths."""
    script_dir = Path(__file__).parent.resolve()
    plugin_dir = script_dir.parent
    repo_root = plugin_dir.parent.parent

    return {
        'script_dir': script_dir,
        'plugin_dir': plugin_dir,
        'repo_root': repo_root,
        'plugin_json': plugin_dir / '.claude-plugin' / 'plugin.json',
        'plugin_readme': plugin_dir / 'README.md',
        'root_readme': repo_root / 'README.md',
        'marketplace_json': repo_root / '.claude-plugin' / 'marketplace.json',
    }

def check_prerequisites(paths: dict) -> None:
    """Verify all prerequisites are met."""
    info("Checking prerequisites...")

    # Check required commands
    for cmd in ['gh', 'jq', 'git']:
        result = run_cmd(f"command -v {cmd}", check=False, capture=True)
        if result.returncode != 0:
            error(f"{cmd} is not installed")

    # Check gh auth
    result = run_cmd("gh auth status", check=False, capture=True)
    if result.returncode != 0:
        error("Not authenticated with GitHub CLI. Run 'gh auth login'")

    # Check we're in a git repo
    result = run_cmd("git rev-parse --git-dir", check=False, capture=True)
    if result.returncode != 0:
        error("Not in a git repository")

    # Verify all files exist
    for name, path in paths.items():
        if name.endswith(('_json', '_readme')):
            if not path.exists():
                error(f"File not found: {path}")

    # Check for uncommitted changes
    result = run_cmd("git status --porcelain", capture=True)
    if result.stdout.strip():
        warn("You have uncommitted changes. They will be included in this release.")
        response = input("Continue? [y/N] ").strip().lower()
        if response != 'y':
            sys.exit(0)

    success("Prerequisites check passed")

def get_current_version(plugin_json: Path) -> str:
    """Get current version from plugin.json (without -alpha suffix)."""
    with open(plugin_json) as f:
        data = json.load(f)
    version = data.get('version', '0.0.0')
    # Remove -alpha suffix if present
    return re.sub(r'-alpha$', '', version)

def bump_version(current: str, bump_type: str) -> str:
    """Bump version based on type (patch/minor/major)."""
    # Remove any suffix
    current = re.sub(r'-.*$', '', current)

    parts = current.split('.')
    if len(parts) != 3:
        error(f"Invalid version format: {current}")

    major, minor, patch = map(int, parts)

    if bump_type == 'major':
        major += 1
        minor = 0
        patch = 0
    elif bump_type == 'minor':
        minor += 1
        patch = 0
    elif bump_type == 'patch':
        patch += 1
    else:
        error(f"Invalid bump type: {bump_type}. Use patch, minor, or major.")

    return f"{major}.{minor}.{patch}"

def update_json_file(file_path: Path, new_version: str, is_marketplace: bool = False) -> None:
    """Update version in a JSON file."""
    with open(file_path) as f:
        data = json.load(f)

    if is_marketplace:
        # marketplace.json has nested version fields with -alpha suffix
        version_with_alpha = f"{new_version}-alpha"
        data['metadata']['version'] = version_with_alpha
        data['plugins'][0]['version'] = version_with_alpha
    else:
        # plugin.json has simple version field without suffix
        data['version'] = new_version

    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    success(f"Updated {file_path.name}")

def update_readme_file(file_path: Path, old_version: str, new_version: str) -> None:
    """Update version references in a README file."""
    with open(file_path) as f:
        content = f.read()

    # Patterns to replace (order matters - more specific first)
    replacements = [
        # Shields.io badges with --alpha (double dash for escaping)
        (f'version-{old_version}--alpha-blue', f'version-{new_version}--alpha-blue'),
        # Shields.io badges without suffix
        (f'version-{old_version}-blue', f'version-{new_version}-blue'),
        # Release tag links with -alpha
        (f'v{old_version}-alpha', f'v{new_version}-alpha'),
        # Release tag links without suffix
        (f'v{old_version}', f'v{new_version}'),
        # Version headers like "### GHE v0.2.1-alpha"
        (f'GHE v{old_version}-alpha', f'GHE v{new_version}-alpha'),
        (f'GHE v{old_version}', f'GHE v{new_version}'),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    with open(file_path, 'w') as f:
        f.write(content)

    success(f"Updated {file_path.name}")

def create_commit(version: str, notes: str) -> None:
    """Create git commit with all changes."""
    run_cmd("git add -A")
    commit_msg = f"Release v{version}-alpha: {notes}"
    run_cmd(f'git commit -m "{commit_msg}"')
    success("Created commit")

def create_tag(version: str, notes: str) -> None:
    """Create and push git tag."""
    tag = f"v{version}-alpha"
    run_cmd(f'git tag -a "{tag}" -m "{tag}: {notes}"')
    run_cmd("git push origin main")
    run_cmd(f'git push origin "{tag}"')
    success(f"Created and pushed tag {tag}")

def get_previous_tag() -> str:
    """Get the previous git tag for changelog link."""
    result = run_cmd("git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo 'v0.0.0'", capture=True)
    return result.stdout.strip()

def create_release(version: str, notes: str) -> None:
    """Create GitHub release."""
    prev_tag = get_previous_tag()
    tag = f"v{version}-alpha"

    release_body = f"""## What's Changed

{notes}

## Installation

```bash
/plugin marketplace update ghe-marketplace
/plugin install ghe@ghe-marketplace
```

## Full Changelog
https://github.com/Emasoft/ghe-marketplace/compare/{prev_tag}...{tag}"""

    # Write release body to temp file to avoid shell escaping issues
    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(release_body)
        temp_file = f.name

    try:
        run_cmd(f'gh release create "{tag}" --title "GHE {tag}" --notes-file "{temp_file}"')
        success("Created GitHub release")
    finally:
        Path(temp_file).unlink(missing_ok=True)

def main():
    parser = argparse.ArgumentParser(
        description='Automate version bump, tag, and GitHub release for GHE plugin.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python release.py patch "Fix avatar loading issue"
  python release.py minor "Add new agent personas"
  python release.py major "Breaking API changes"
        """
    )
    parser.add_argument('bump_type', choices=['patch', 'minor', 'major'],
                        help='Version bump type')
    parser.add_argument('notes', help='Release notes (brief description)')

    args = parser.parse_args()

    print()
    info("Starting release process...")
    print()

    # Get paths
    paths = get_paths()

    # Check prerequisites
    check_prerequisites(paths)

    # Get versions
    current_version = get_current_version(paths['plugin_json'])
    new_version = bump_version(current_version, args.bump_type)

    print()
    info(f"Current version: {current_version}")
    info(f"New version: {new_version}")
    print()

    # Confirm
    response = input(f"Proceed with release v{new_version}-alpha? [y/N] ").strip().lower()
    if response != 'y':
        print("Aborted.")
        sys.exit(0)

    print()

    # Step 1: Update JSON files
    info("Step 1/5: Updating JSON files...")
    update_json_file(paths['plugin_json'], new_version, is_marketplace=False)
    update_json_file(paths['marketplace_json'], new_version, is_marketplace=True)

    # Step 2: Update README files
    info("Step 2/5: Updating README files...")
    update_readme_file(paths['root_readme'], current_version, new_version)
    update_readme_file(paths['plugin_readme'], current_version, new_version)

    # Step 3: Create commit
    info("Step 3/5: Creating commit...")
    create_commit(new_version, args.notes)

    # Step 4: Create and push tag
    info("Step 4/5: Creating and pushing tag...")
    create_tag(new_version, args.notes)

    # Step 5: Create GitHub release
    info("Step 5/5: Creating GitHub release...")
    create_release(new_version, args.notes)

    print()
    success(f"Release v{new_version}-alpha complete!")
    print()
    info(f"URL: https://github.com/Emasoft/ghe-marketplace/releases/tag/v{new_version}-alpha")
    print()

if __name__ == '__main__':
    main()
