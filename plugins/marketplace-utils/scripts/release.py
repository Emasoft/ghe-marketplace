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
    python release.py --version                 # Show script version

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
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

# Script version - automatically updated by release.py when releasing marketplace-utils
__version__ = "1.1.4"
SCRIPT_NAME = "release.py"


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


def print_version() -> None:
    """Print version information."""
    print(f"{Colors.CYAN}{SCRIPT_NAME}{Colors.NC} v{__version__}")
    print(f"Marketplace release automation tool")
    print()


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


def validate_plugin(config: MarketplaceConfig, plugin_name: str) -> None:
    """Validate plugin using Claude Code plugin validator."""
    info(f"Validating plugin '{plugin_name}'...")

    plugin_path = config.get_plugin_path(plugin_name)
    if not plugin_path:
        error(f"Cannot find plugin path for '{plugin_name}'")

    result = run_cmd(f"claude plugin validate \"{plugin_path}\"", check=False, capture=True)
    if result.returncode != 0:
        error(f"Plugin validation failed:\n{result.stdout}\n{result.stderr}")

    success(f"Plugin '{plugin_name}' validation passed")


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

    old_version = data['plugins'][plugin_index].get('version', 'unknown')
    data['plugins'][plugin_index]['version'] = new_version

    with open(config.marketplace_json_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    success(f"{config.marketplace_json_path}")
    print(f"       plugins[{plugin_name}].version: {old_version} -> {new_version}")


def update_plugin_json(config: MarketplaceConfig, plugin_name: str, new_version: str) -> None:
    """Update version in the specific plugin's plugin.json."""
    plugin_json_path = config.get_plugin_json_path(plugin_name)

    if not plugin_json_path:
        warn(f"plugin.json not found for {plugin_name}")
        return

    with open(plugin_json_path) as f:
        data = json.load(f)

    old_version = data.get('version', 'unknown')
    data['version'] = new_version

    with open(plugin_json_path, 'w') as f:
        json.dump(data, f, indent=2)
        f.write('\n')

    success(f"{plugin_json_path}")
    print(f"       version: {old_version} -> {new_version}")


def update_script_versions(config: MarketplaceConfig, plugin_name: str, new_version: str) -> None:
    """Update __version__ in all Python scripts for marketplace-utils plugin."""
    if plugin_name != 'marketplace-utils':
        return  # Only update script versions for marketplace-utils

    plugin_path = config.get_plugin_path(plugin_name)
    if not plugin_path:
        return

    scripts_dir = plugin_path / 'scripts'
    if not scripts_dir.exists():
        return

    version_pattern = re.compile(r'^__version__\s*=\s*["\'][\d.]+["\']', re.MULTILINE)

    for script_path in scripts_dir.glob('*.py'):
        with open(script_path) as f:
            content = f.read()

        if '__version__' in content:
            new_content = version_pattern.sub(f'__version__ = "{new_version}"', content)
            if new_content != content:
                with open(script_path, 'w') as f:
                    f.write(new_content)
                success(f"Updated version in {script_path.name}")


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


def update_marketplace_readme(config: MarketplaceConfig) -> None:
    """Update the main marketplace README with current plugin versions."""
    readme_path = config.repo_root / 'README.md'
    if not readme_path.exists():
        warn("Marketplace README.md not found")
        return

    with open(readme_path) as f:
        content = f.read()

    # Generate version table
    today = datetime.now().strftime('%Y-%m-%d')
    version_section = f"""<!-- PLUGIN-VERSIONS-START -->
## Plugin Versions

| Plugin | Version | Description |
|--------|---------|-------------|
"""
    for plugin in config.plugins:
        name = plugin.get('name', 'unknown')
        version = plugin.get('version', '0.0.0')
        desc = plugin.get('description', '')
        # Truncate description to keep table readable
        if len(desc) > 60:
            desc = desc[:57] + '...'
        version_section += f"| {name} | {version} | {desc} |\n"

    version_section += f"""
*Last updated: {today}*

<!-- PLUGIN-VERSIONS-END -->

"""

    # Check if version section already exists
    version_start = '<!-- PLUGIN-VERSIONS-START -->'
    version_end = '<!-- PLUGIN-VERSIONS-END -->'

    if version_start in content and version_end in content:
        # Replace existing section
        pattern = re.compile(
            re.escape(version_start) + r'.*?' + re.escape(version_end),
            re.DOTALL
        )
        content = pattern.sub(version_section.strip(), content)
    else:
        # Insert before TOC or after first ---
        toc_marker = '## Table of Contents'
        first_hr = '\n---\n'

        if toc_marker in content:
            # Insert before TOC
            content = content.replace(toc_marker, version_section + toc_marker)
        elif first_hr in content:
            # Insert after first horizontal rule (after header section)
            idx = content.find(first_hr)
            if idx != -1:
                insert_pos = idx + len(first_hr)
                content = content[:insert_pos] + '\n' + version_section + content[insert_pos:]
        else:
            warn("Could not find insertion point for version table in README")
            return

    # Also update the main version badge if present
    # Find shields.io version badge and update with the first plugin's version (usually main plugin)
    if config.plugins:
        main_plugin = config.plugins[0]
        main_name = main_plugin.get('name', 'ghe')
        main_version = main_plugin.get('version', '0.0.0')
        base, suffix = parse_version(main_version)
        suffix_escaped = suffix.replace('-', '--') if suffix else ''

        # Update version badge - handles both with and without suffix
        badge_pattern = r'(version-)\d+\.\d+\.\d+(?:--[a-zA-Z0-9]+)?(-blue)'
        new_badge = f'\\g<1>{base}{suffix_escaped}\\g<2>'
        content = re.sub(badge_pattern, new_badge, content)

        # Update release tag links
        old_tag_pattern = r'(releases/tag/)[\w-]+-v\d+\.\d+\.\d+(?:-[a-zA-Z0-9]+)?'
        new_tag = f'\\g<1>{main_name}-v{main_version}'
        content = re.sub(old_tag_pattern, new_tag, content)

        # Update section headers with version (e.g., "### GHE v0.5.8" -> "### GHE v0.5.9")
        # Match plugin name (case-insensitive) followed by version
        name_upper = main_name.upper()
        header_pattern = rf'(###\s+{name_upper}\s+v)\d+\.\d+\.\d+'
        content = re.sub(header_pattern, f'\\g<1>{main_version}', content, flags=re.IGNORECASE)

        # Update TOC links with version anchors (e.g., "#ghe-v058" -> "#ghe-v059")
        # The anchor format is: #pluginname-vXYZ (no dots, lowercase)
        version_nodots = main_version.replace('.', '')
        toc_pattern = rf'(\[{name_upper}\s+v)\d+\.\d+\.\d+(\]\(#{main_name.lower()}-v)\d+(\))'
        toc_replacement = f'\\g<1>{main_version}\\g<2>{version_nodots}\\g<3>'
        content = re.sub(toc_pattern, toc_replacement, content, flags=re.IGNORECASE)

    with open(readme_path, 'w') as f:
        f.write(content)

    success("Updated marketplace README.md with version table")


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


def clear_local_plugin_cache(config: MarketplaceConfig, plugin_name: str) -> None:
    """
    Clear local Claude Code plugin caches to force fresh install on next update.

    This function clears cached plugin data so users get the latest version
    when they run 'claude plugins install'. It does NOT modify installed_plugins.json
    as that is managed by Claude Code when users install plugins.
    """
    import shutil

    home = Path.home()
    marketplace_name = config.marketplace_name

    # Cache locations to clear
    cache_locations = [
        # Installed plugin cache (the main culprit)
        home / ".claude" / "plugins" / "cache" / f"{marketplace_name}-{plugin_name}",
        # Alternative naming patterns
        home / ".claude" / "plugins" / "cache" / plugin_name,
    ]

    cleared_any = False
    for cache_path in cache_locations:
        if cache_path.exists():
            try:
                shutil.rmtree(cache_path)
                success(f"Cleared cache: {cache_path}")
                cleared_any = True
            except Exception as e:
                warn(f"Failed to clear {cache_path}: {e}")

    if not cleared_any:
        info("No local plugin caches found to clear")

    # Update the marketplace cache by pulling latest
    marketplace_path = home / ".claude" / "plugins" / "marketplaces" / marketplace_name
    new_commit_sha = None
    if marketplace_path.exists() and (marketplace_path / ".git").exists():
        info("Updating marketplace cache from GitHub...")
        try:
            result = run_cmd(f'cd "{marketplace_path}" && git fetch origin && git reset --hard origin/main',
                           check=False, capture=True)
            if result.returncode == 0:
                success("Marketplace cache updated")
                # Get the new commit SHA
                sha_result = run_cmd(f'cd "{marketplace_path}" && git rev-parse HEAD',
                                   check=False, capture=True)
                if sha_result.returncode == 0:
                    new_commit_sha = sha_result.stdout.strip()
            else:
                warn("Could not update marketplace cache - run 'claude plugins marketplace update' manually")
        except Exception:
            warn("Could not update marketplace cache")

    print()
    info("Release complete! Users can update with: claude plugins install")
    print()


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
  python release.py --version

Each plugin maintains its own version independently.
        """
    )
    parser.add_argument('--version', '-v', action='store_true',
                        help='Show script version and exit')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List all plugins and their versions')
    parser.add_argument('bump_type', nargs='?', choices=['patch', 'minor', 'major'],
                        help='Version bump type')
    parser.add_argument('plugin_name', nargs='?',
                        help='Name of the plugin to release')
    parser.add_argument('notes', nargs='?',
                        help='Release notes (brief description)')

    args = parser.parse_args()

    # Handle --version
    if args.version:
        print_version()
        return

    # Print version banner
    print_version()

    # Use current working directory as repo root
    repo_root = Path.cwd()

    # Load configuration
    config = MarketplaceConfig(repo_root)

    # Handle --list
    if args.list:
        list_plugins(config)
        return

    # Validate required arguments - prompt interactively if missing
    if not args.bump_type:
        print()
        info("Select version bump type:")
        print("  1. patch (bug fixes, minor changes)")
        print("  2. minor (new features, backward compatible)")
        print("  3. major (breaking changes)")
        print()
        try:
            choice = input("Enter number (1-3) or 'q' to quit: ").strip()
            if choice.lower() == 'q':
                print("Aborted.")
                sys.exit(0)
            bump_map = {'1': 'patch', '2': 'minor', '3': 'major'}
            if choice in bump_map:
                args.bump_type = bump_map[choice]
            else:
                error(f"Invalid selection: {choice}")
        except EOFError:
            error("Bump type required")
    if not args.plugin_name:
        plugin_names = config.get_plugin_names()
        print()
        info("Select a plugin to release:")
        for i, name in enumerate(plugin_names, 1):
            version = config.get_plugin_version(name)
            print(f"  {i}. {name} (v{version})")
        print()
        try:
            choice = input("Enter number (or 'q' to quit): ").strip()
            if choice.lower() == 'q':
                print("Aborted.")
                sys.exit(0)
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(plugin_names):
                args.plugin_name = plugin_names[choice_idx]
            else:
                error(f"Invalid selection: {choice}")
        except (ValueError, EOFError):
            error("Invalid input")
    if not args.notes:
        print()
        try:
            args.notes = input("Enter release notes (brief description): ").strip()
            if not args.notes:
                error("Release notes cannot be empty")
        except EOFError:
            error("Release notes required")

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

    # Step 1: Validate plugin
    info("Step 1/8: Validating plugin...")
    validate_plugin(config, args.plugin_name)

    # Step 2: Update JSON files
    info("Step 2/8: Updating JSON files...")
    update_marketplace_json_for_plugin(config, args.plugin_name, new_version)
    update_plugin_json(config, args.plugin_name, new_version)

    # Step 3: Update script versions (only for marketplace-utils)
    info("Step 3/8: Updating script versions...")
    update_script_versions(config, args.plugin_name, new_version)

    # Reload config to get updated version for README generation
    config = MarketplaceConfig(repo_root)

    # Step 4: Update READMEs
    info("Step 4/8: Updating READMEs...")
    update_readme_for_plugin(config, args.plugin_name, current_version, new_version)
    update_marketplace_readme(config)

    # Step 5: Create commit
    info("Step 5/8: Creating commit...")
    create_commit(args.plugin_name, new_version, args.notes)

    # Step 6: Create and push tag
    info("Step 6/8: Creating and pushing tag...")
    create_tag(args.plugin_name, new_version, args.notes)

    # Step 7: Create GitHub release
    info("Step 7/8: Creating GitHub release...")
    create_release(config, args.plugin_name, new_version, args.notes)

    # Step 8: Clear local caches
    info("Step 8/8: Clearing local caches...")
    clear_local_plugin_cache(config, args.plugin_name)

    print()
    success(f"Release {args.plugin_name}-v{new_version} complete!")
    print()
    repo_url = get_repo_url()
    info(f"URL: {repo_url}/releases/tag/{args.plugin_name}-v{new_version}")
    print()


if __name__ == '__main__':
    main()
