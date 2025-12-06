#!/usr/bin/env python3
"""
release.py - Generic marketplace release automation tool.

A fully portable release script for Claude Code plugin marketplaces.
Reads all configuration from marketplace.json and plugin.json files.
No hardcoded values - can be used on any marketplace project.

Usage:
    python scripts/release.py patch "Fix bug description"
    python scripts/release.py minor "Add new feature"
    python scripts/release.py major "Breaking changes"

Requirements:
    - GitHub CLI (gh) installed and authenticated
    - Must be run from the marketplace root directory
    - .claude-plugin/marketplace.json must exist
"""

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple


class Colors:
    """ANSI color codes for terminal output."""
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
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
    """Print error and exit."""
    print(f"{Colors.RED}[ERROR]{Colors.NC} {msg}", file=sys.stderr)
    sys.exit(1)


def run_cmd(cmd: str, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    """Run a shell command."""
    result = subprocess.run(cmd, shell=True, capture_output=capture, text=True)
    if check and result.returncode != 0:
        error(f"Command failed: {cmd}\n{result.stderr if capture else ''}")
    return result


class MarketplaceConfig:
    """Configuration loaded from marketplace and plugin JSON files."""

    def __init__(self, repo_root: Path):
        self.repo_root = repo_root
        self.marketplace_json_path = repo_root / '.claude-plugin' / 'marketplace.json'
        self.marketplace_data: Dict = {}
        self.plugins: list = []

        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from marketplace.json."""
        if not self.marketplace_json_path.exists():
            error(f"marketplace.json not found: {self.marketplace_json_path}")

        with open(self.marketplace_json_path) as f:
            self.marketplace_data = json.load(f)

        self.plugins = self.marketplace_data.get('plugins', [])
        if not self.plugins:
            error("No plugins defined in marketplace.json")

    @property
    def marketplace_name(self) -> str:
        """Get marketplace name."""
        return self.marketplace_data.get('name', 'unknown-marketplace')

    @property
    def current_version(self) -> str:
        """Get current version from marketplace metadata."""
        version = self.marketplace_data.get('metadata', {}).get('version', '0.0.0')
        # Extract base version without suffix
        return re.sub(r'-.*$', '', version)

    @property
    def version_suffix(self) -> str:
        """Get version suffix (e.g., '-alpha', '-beta', or empty)."""
        version = self.marketplace_data.get('metadata', {}).get('version', '')
        match = re.search(r'(-[a-zA-Z]+)$', version)
        return match.group(1) if match else ''

    @property
    def primary_plugin(self) -> Dict:
        """Get primary plugin (first one)."""
        return self.plugins[0] if self.plugins else {}

    @property
    def primary_plugin_name(self) -> str:
        """Get primary plugin name."""
        return self.primary_plugin.get('name', 'unknown')

    @property
    def primary_plugin_path(self) -> Path:
        """Get primary plugin source path."""
        source = self.primary_plugin.get('source', './plugins/unknown')
        return self.repo_root / source.lstrip('./')

    @property
    def primary_plugin_json_path(self) -> Path:
        """Get primary plugin's plugin.json path."""
        return self.primary_plugin_path / '.claude-plugin' / 'plugin.json'

    def get_readme_paths(self) -> list:
        """Get all README paths that need version updates."""
        paths = [self.repo_root / 'README.md']
        plugin_readme = self.primary_plugin_path / 'README.md'
        if plugin_readme.exists():
            paths.append(plugin_readme)
        return paths


def get_repo_url() -> str:
    """Get the GitHub repository URL dynamically."""
    result = run_cmd("gh repo view --json nameWithOwner --jq '.nameWithOwner'", capture=True)
    repo_name = result.stdout.strip()
    return f"https://github.com/{repo_name}"


def get_previous_tag() -> str:
    """Get the previous git tag for changelog link."""
    result = run_cmd("git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo 'v0.0.0'", capture=True)
    return result.stdout.strip()


def check_prerequisites() -> None:
    """Verify all prerequisites are met."""
    info("Checking prerequisites...")

    for cmd in ['gh', 'git']:
        result = run_cmd(f"command -v {cmd}", check=False, capture=True)
        if result.returncode != 0:
            error(f"{cmd} is not installed")

    result = run_cmd("gh auth status", check=False, capture=True)
    if result.returncode != 0:
        error("Not authenticated with GitHub CLI. Run 'gh auth login'")

    result = run_cmd("git rev-parse --git-dir", check=False, capture=True)
    if result.returncode != 0:
        error("Not in a git repository")

    result = run_cmd("git status --porcelain", capture=True)
    if result.stdout.strip():
        warn("You have uncommitted changes. They will be included in this release.")
        response = input("Continue? [y/N] ").strip().lower()
        if response != 'y':
            sys.exit(0)

    success("Prerequisites check passed")


def bump_version(current: str, bump_type: str) -> str:
    """Bump version based on type (patch/minor/major)."""
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


def update_marketplace_json(config: MarketplaceConfig, new_version: str) -> None:
    """Update version in marketplace.json."""
    version_with_suffix = f"{new_version}{config.version_suffix}"

    data = config.marketplace_data.copy()
    data['metadata']['version'] = version_with_suffix

    for plugin in data.get('plugins', []):
        plugin['version'] = version_with_suffix

    with open(config.marketplace_json_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    success(f"Updated {config.marketplace_json_path.name}")


def update_plugin_json(config: MarketplaceConfig, new_version: str) -> None:
    """Update version in plugin.json."""
    plugin_json_path = config.primary_plugin_json_path

    if not plugin_json_path.exists():
        warn(f"Plugin JSON not found: {plugin_json_path}")
        return

    with open(plugin_json_path) as f:
        data = json.load(f)

    # Plugin.json typically uses version without suffix
    data['version'] = new_version

    with open(plugin_json_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    success(f"Updated {plugin_json_path.name}")


def update_readme_files(config: MarketplaceConfig, old_version: str, new_version: str) -> None:
    """Update version references in README files."""
    suffix = config.version_suffix
    suffix_escaped = suffix.replace('-', '--')  # Shield.io escaping

    for readme_path in config.get_readme_paths():
        if not readme_path.exists():
            continue

        with open(readme_path) as f:
            content = f.read()

        replacements = [
            # Shields.io badges with suffix (escaped)
            (f'version-{old_version}{suffix_escaped}-blue', f'version-{new_version}{suffix_escaped}-blue'),
            # Shields.io badges without suffix
            (f'version-{old_version}-blue', f'version-{new_version}-blue'),
            # Release tag links with suffix
            (f'v{old_version}{suffix}', f'v{new_version}{suffix}'),
            # Release tag links without suffix
            (f'v{old_version}', f'v{new_version}'),
        ]

        for old, new in replacements:
            content = content.replace(old, new)

        with open(readme_path, 'w') as f:
            f.write(content)

        success(f"Updated {readme_path.name}")


def create_commit(new_version: str, suffix: str, notes: str) -> None:
    """Create git commit with all changes."""
    run_cmd("git add -A")
    tag = f"v{new_version}{suffix}"
    commit_msg = f"Release {tag}: {notes}"
    run_cmd(f'git commit -m "{commit_msg}"')
    success("Created commit")


def create_tag(new_version: str, suffix: str, notes: str) -> None:
    """Create and push git tag."""
    tag = f"v{new_version}{suffix}"
    run_cmd(f'git tag -a "{tag}" -m "{tag}: {notes}"')
    run_cmd("git push origin main")
    run_cmd(f'git push origin "{tag}"')
    success(f"Created and pushed tag {tag}")


def create_release(config: MarketplaceConfig, new_version: str, notes: str) -> None:
    """Create GitHub release."""
    prev_tag = get_previous_tag()
    tag = f"v{new_version}{config.version_suffix}"
    repo_url = get_repo_url()
    marketplace_name = config.marketplace_name
    plugin_name = config.primary_plugin_name

    release_body = f"""## What's Changed

{notes}

## Installation

```bash
/plugin marketplace update {marketplace_name}
/plugin install {plugin_name}@{marketplace_name}
```

## Full Changelog
{repo_url}/compare/{prev_tag}...{tag}"""

    import tempfile
    with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
        f.write(release_body)
        temp_file = f.name

    try:
        plugin_name_upper = plugin_name.upper()
        run_cmd(f'gh release create "{tag}" --title "{plugin_name_upper} {tag}" --notes-file "{temp_file}"')
        success("Created GitHub release")
    finally:
        Path(temp_file).unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(
        description='Generic marketplace release automation tool.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/release.py patch "Fix avatar loading issue"
  python scripts/release.py minor "Add new feature"
  python scripts/release.py major "Breaking API changes"

Configuration is read from:
  - .claude-plugin/marketplace.json (marketplace config)
  - plugins/<name>/.claude-plugin/plugin.json (plugin config)
        """
    )
    parser.add_argument('bump_type', choices=['patch', 'minor', 'major'],
                        help='Version bump type')
    parser.add_argument('notes', help='Release notes (brief description)')

    args = parser.parse_args()

    print()
    info("Starting release process...")
    print()

    # Use current working directory as repo root (where user runs the script from)
    # This makes the script portable - works whether run from marketplace/scripts/
    # or installed as a plugin at ~/.claude/plugins/cache/
    repo_root = Path.cwd()

    # Load configuration
    config = MarketplaceConfig(repo_root)

    # Check prerequisites
    check_prerequisites()

    # Calculate versions
    current_version = config.current_version
    new_version = bump_version(current_version, args.bump_type)
    suffix = config.version_suffix

    print()
    info(f"Marketplace: {config.marketplace_name}")
    info(f"Plugin: {config.primary_plugin_name}")
    info(f"Current version: {current_version}{suffix}")
    info(f"New version: {new_version}{suffix}")
    print()

    # Confirm
    response = input(f"Proceed with release v{new_version}{suffix}? [y/N] ").strip().lower()
    if response != 'y':
        print("Aborted.")
        sys.exit(0)

    print()

    # Step 1: Update JSON files
    info("Step 1/5: Updating JSON files...")
    update_marketplace_json(config, new_version)
    update_plugin_json(config, new_version)

    # Step 2: Update README files
    info("Step 2/5: Updating README files...")
    update_readme_files(config, current_version, new_version)

    # Step 3: Create commit
    info("Step 3/5: Creating commit...")
    create_commit(new_version, suffix, args.notes)

    # Step 4: Create and push tag
    info("Step 4/5: Creating and pushing tag...")
    create_tag(new_version, suffix, args.notes)

    # Step 5: Create GitHub release
    info("Step 5/5: Creating GitHub release...")
    create_release(config, new_version, args.notes)

    print()
    success(f"Release v{new_version}{suffix} complete!")
    print()
    repo_url = get_repo_url()
    info(f"URL: {repo_url}/releases/tag/v{new_version}{suffix}")
    print()


if __name__ == '__main__':
    main()
