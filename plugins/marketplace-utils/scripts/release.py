#!/usr/bin/env python3
"""
release.py - Generic marketplace release automation tool.

A fully portable release script for Claude Code plugin marketplaces.
Supports independent versioning of each plugin within the marketplace.

Usage:
    python release.py patch <plugin-name> "Fix bug description"
    python release.py minor <plugin-name> "Add new feature"
    python release.py major <plugin-name> "Breaking changes"
    python release.py --list                    # List all plugins and versions

Examples:
    python release.py patch ghe "Fix avatar loading"
    python release.py minor marketplace-utils "Add TOC generator"
    python release.py major ghe "Breaking: New API"

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
from typing import Dict, List, Optional


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
        self.plugins: List[Dict] = []

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

    def get_plugin_names(self) -> List[str]:
        """Get list of all plugin names."""
        return [p.get('name', 'unknown') for p in self.plugins]

    def get_plugin_by_name(self, name: str) -> Optional[Dict]:
        """Get plugin entry by name."""
        for plugin in self.plugins:
            if plugin.get('name') == name:
                return plugin
        return None

    def get_plugin_index(self, name: str) -> int:
        """Get plugin index in the plugins array."""
        for i, plugin in enumerate(self.plugins):
            if plugin.get('name') == name:
                return i
        return -1

    def get_plugin_path(self, name: str) -> Optional[Path]:
        """Get plugin directory path."""
        plugin = self.get_plugin_by_name(name)
        if not plugin:
            return None
        source = plugin.get('source', '')
        if source:
            return self.repo_root / source.lstrip('./')
        return None

    def get_plugin_json_path(self, name: str) -> Optional[Path]:
        """Get plugin.json path for a specific plugin."""
        plugin_path = self.get_plugin_path(name)
        if plugin_path:
            json_path = plugin_path / '.claude-plugin' / 'plugin.json'
            if json_path.exists():
                return json_path
        return None

    def get_plugin_version(self, name: str) -> str:
        """Get current version of a specific plugin."""
        plugin = self.get_plugin_by_name(name)
        if plugin:
            return plugin.get('version', '0.0.0')
        return '0.0.0'

    def get_plugin_readme_path(self, name: str) -> Optional[Path]:
        """Get README path for a specific plugin."""
        plugin_path = self.get_plugin_path(name)
        if plugin_path:
            readme = plugin_path / 'README.md'
            if readme.exists():
                return readme
        return None


def get_repo_url() -> str:
    """Get the GitHub repository URL dynamically."""
    result = run_cmd("gh repo view --json nameWithOwner --jq '.nameWithOwner'", capture=True)
    repo_name = result.stdout.strip()
    return f"https://github.com/{repo_name}"


def get_previous_tag(plugin_name: str) -> str:
    """Get the previous git tag for this plugin."""
    # Look for tags matching this plugin pattern
    result = run_cmd(f"git tag -l '{plugin_name}-v*' --sort=-v:refname | head -1", capture=True, check=False)
    if result.stdout.strip():
        return result.stdout.strip()
    # Fall back to any previous tag
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


def parse_version(version: str) -> tuple:
    """Parse version string into (base_version, suffix)."""
    match = re.match(r'^(\d+\.\d+\.\d+)(-.*)?$', version)
    if match:
        return match.group(1), match.group(2) or ''
    return '0.0.0', ''


def bump_version(current: str, bump_type: str) -> str:
    """Bump version based on type (patch/minor/major)."""
    base, _ = parse_version(current)
    parts = base.split('.')

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


def update_marketplace_json_for_plugin(config: MarketplaceConfig, plugin_name: str, new_version: str) -> None:
    """Update version for a specific plugin in marketplace.json."""
    data = config.marketplace_data.copy()

    # Find and update the specific plugin
    plugin_index = config.get_plugin_index(plugin_name)
    if plugin_index < 0:
        error(f"Plugin '{plugin_name}' not found in marketplace.json")

    data['plugins'][plugin_index]['version'] = new_version

    with open(config.marketplace_json_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    success(f"Updated marketplace.json ({plugin_name} -> {new_version})")


def update_plugin_json(config: MarketplaceConfig, plugin_name: str, new_version: str) -> None:
    """Update version in the specific plugin's plugin.json."""
    plugin_json_path = config.get_plugin_json_path(plugin_name)

    if not plugin_json_path:
        warn(f"plugin.json not found for {plugin_name}")
        return

    with open(plugin_json_path) as f:
        data = json.load(f)

    data['version'] = new_version

    with open(plugin_json_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    rel_path = plugin_json_path.relative_to(config.repo_root)
    success(f"Updated {rel_path}")


def update_readme_for_plugin(config: MarketplaceConfig, plugin_name: str, old_version: str, new_version: str) -> None:
    """Update version references in the plugin's README."""
    readme_path = config.get_plugin_readme_path(plugin_name)
    if not readme_path:
        return

    with open(readme_path) as f:
        content = f.read()

    # Parse old and new versions
    old_base, old_suffix = parse_version(old_version)
    new_base, new_suffix = parse_version(new_version)
    old_suffix_escaped = old_suffix.replace('-', '--')
    new_suffix_escaped = new_suffix.replace('-', '--')

    replacements = [
        # Shields.io badges with suffix
        (f'version-{old_base}{old_suffix_escaped}-blue', f'version-{new_base}{new_suffix_escaped}-blue'),
        # Shields.io badges without suffix
        (f'version-{old_base}-blue', f'version-{new_base}-blue'),
        # Version strings
        (f'v{old_version}', f'v{new_version}'),
        (old_version, new_version),
    ]

    for old, new in replacements:
        content = content.replace(old, new)

    with open(readme_path, 'w') as f:
        f.write(content)

    success(f"Updated {readme_path.name}")


def create_commit(plugin_name: str, new_version: str, notes: str) -> None:
    """Create git commit with all changes."""
    run_cmd("git add -A")
    tag = f"{plugin_name}-v{new_version}"
    commit_msg = f"Release {tag}: {notes}"
    run_cmd(f'git commit -m "{commit_msg}"')
    success("Created commit")


def create_tag(plugin_name: str, new_version: str, notes: str) -> None:
    """Create and push git tag."""
    tag = f"{plugin_name}-v{new_version}"
    run_cmd(f'git tag -a "{tag}" -m "{tag}: {notes}"')
    run_cmd("git push origin main")
    run_cmd(f'git push origin "{tag}"')
    success(f"Created and pushed tag {tag}")


def create_release(config: MarketplaceConfig, plugin_name: str, new_version: str, notes: str) -> None:
    """Create GitHub release for the plugin."""
    prev_tag = get_previous_tag(plugin_name)
    tag = f"{plugin_name}-v{new_version}"
    repo_url = get_repo_url()
    marketplace_name = config.marketplace_name

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
        plugin_upper = plugin_name.upper()
        run_cmd(f'gh release create "{tag}" --title "{plugin_upper} v{new_version}" --notes-file "{temp_file}"')
        success("Created GitHub release")
    finally:
        Path(temp_file).unlink(missing_ok=True)


def list_plugins(config: MarketplaceConfig) -> None:
    """List all plugins and their current versions."""
    print()
    print(f"{Colors.CYAN}Marketplace: {config.marketplace_name}{Colors.NC}")
    print()
    print(f"{'Plugin':<25} {'Version':<15} {'Source'}")
    print("-" * 70)
    for plugin in config.plugins:
        name = plugin.get('name', 'unknown')
        version = plugin.get('version', '0.0.0')
        source = plugin.get('source', 'N/A')
        print(f"{name:<25} {version:<15} {source}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Generic marketplace release automation tool with independent plugin versioning.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python release.py patch ghe "Fix avatar loading issue"
  python release.py minor marketplace-utils "Add TOC generator"
  python release.py major ghe "Breaking API changes"
  python release.py --list

Each plugin maintains its own version independently.
        """
    )
    parser.add_argument('--list', '-l', action='store_true',
                        help='List all plugins and their versions')
    parser.add_argument('bump_type', nargs='?', choices=['patch', 'minor', 'major'],
                        help='Version bump type')
    parser.add_argument('plugin_name', nargs='?',
                        help='Name of the plugin to release')
    parser.add_argument('notes', nargs='?',
                        help='Release notes (brief description)')

    args = parser.parse_args()

    # Use current working directory as repo root
    repo_root = Path.cwd()

    # Load configuration
    config = MarketplaceConfig(repo_root)

    # Handle --list
    if args.list:
        list_plugins(config)
        return

    # Validate required arguments
    if not args.bump_type:
        parser.print_help()
        print()
        error("Missing required argument: bump_type")
    if not args.plugin_name:
        print()
        info("Available plugins:")
        for name in config.get_plugin_names():
            print(f"  - {name}")
        print()
        error("Missing required argument: plugin_name")
    if not args.notes:
        error("Missing required argument: notes")

    # Validate plugin name
    if args.plugin_name not in config.get_plugin_names():
        print()
        info("Available plugins:")
        for name in config.get_plugin_names():
            print(f"  - {name}")
        print()
        error(f"Unknown plugin: {args.plugin_name}")

    print()
    info("Starting release process...")
    print()

    # Check prerequisites
    check_prerequisites()

    # Get current and new versions for this plugin
    current_version = config.get_plugin_version(args.plugin_name)
    current_base, current_suffix = parse_version(current_version)
    new_base = bump_version(current_version, args.bump_type)
    new_version = f"{new_base}{current_suffix}"

    print()
    info(f"Marketplace: {config.marketplace_name}")
    info(f"Plugin: {args.plugin_name}")
    info(f"Current version: {current_version}")
    info(f"New version: {new_version}")
    print()

    # Confirm
    response = input(f"Proceed with release {args.plugin_name}-v{new_version}? [y/N] ").strip().lower()
    if response != 'y':
        print("Aborted.")
        sys.exit(0)

    print()

    # Step 1: Update JSON files
    info("Step 1/5: Updating JSON files...")
    update_marketplace_json_for_plugin(config, args.plugin_name, new_version)
    update_plugin_json(config, args.plugin_name, new_version)

    # Step 2: Update README
    info("Step 2/5: Updating README...")
    update_readme_for_plugin(config, args.plugin_name, current_version, new_version)

    # Step 3: Create commit
    info("Step 3/5: Creating commit...")
    create_commit(args.plugin_name, new_version, args.notes)

    # Step 4: Create and push tag
    info("Step 4/5: Creating and pushing tag...")
    create_tag(args.plugin_name, new_version, args.notes)

    # Step 5: Create GitHub release
    info("Step 5/5: Creating GitHub release...")
    create_release(config, args.plugin_name, new_version, args.notes)

    print()
    success(f"Release {args.plugin_name}-v{new_version} complete!")
    print()
    repo_url = get_repo_url()
    info(f"URL: {repo_url}/releases/tag/{args.plugin_name}-v{new_version}")
    print()


if __name__ == '__main__':
    main()
