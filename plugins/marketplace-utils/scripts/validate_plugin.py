#!/usr/bin/env python3
"""
validate_plugin.py - Plugin validation tool for Claude Code plugin marketplaces.

Validates plugin structure, manifest, and configuration before release.
Uses the Claude Code CLI plugin validator internally.

Usage:
    python validate_plugin.py <plugin-name>      # Validate specific plugin
    python validate_plugin.py --all              # Validate all plugins
    python validate_plugin.py --version          # Show script version

Examples:
    python validate_plugin.py ghe
    python validate_plugin.py marketplace-utils
    python validate_plugin.py --all

Requirements:
    - Claude Code CLI installed
    - Must be run from the marketplace root directory
    - .claude-plugin/marketplace.json must exist
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Script version - automatically updated by release.py when releasing marketplace-utils
__version__ = "1.1.1"
SCRIPT_NAME = "validate_plugin.py"


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
    print(f"Plugin validation tool for Claude Code marketplaces")
    print()


class MarketplaceConfig:
    """Configuration loaded from marketplace JSON file."""

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
            sys.exit(1)

        with open(self.marketplace_json_path) as f:
            self.marketplace_data = json.load(f)

        self.plugins = self.marketplace_data.get('plugins', [])
        if not self.plugins:
            error("No plugins defined in marketplace.json")
            sys.exit(1)

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

    def get_plugin_path(self, name: str) -> Optional[Path]:
        """Get plugin directory path."""
        plugin = self.get_plugin_by_name(name)
        if not plugin:
            return None
        source = plugin.get('source', '')
        if source:
            return self.repo_root / source.lstrip('./')
        return None


def validate_plugin(config: MarketplaceConfig, plugin_name: str) -> bool:
    """Validate a single plugin using Claude Code CLI.

    Returns True if validation passed, False otherwise.
    """
    plugin_path = config.get_plugin_path(plugin_name)
    if not plugin_path:
        error(f"Cannot find plugin path for '{plugin_name}'")
        return False

    if not plugin_path.exists():
        error(f"Plugin directory does not exist: {plugin_path}")
        return False

    plugin_json = plugin_path / '.claude-plugin' / 'plugin.json'
    if not plugin_json.exists():
        error(f"plugin.json not found: {plugin_json}")
        return False

    info(f"Validating '{plugin_name}'...")

    result = subprocess.run(
        f'claude plugin validate "{plugin_path}"',
        shell=True,
        capture_output=True,
        text=True
    )

    if result.returncode == 0:
        success(f"Plugin '{plugin_name}' validation passed")
        return True
    else:
        error(f"Plugin '{plugin_name}' validation failed:")
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        return False


def validate_all_plugins(config: MarketplaceConfig) -> bool:
    """Validate all plugins in the marketplace.

    Returns True if all validations passed, False otherwise.
    """
    all_passed = True
    results = []

    for plugin_name in config.get_plugin_names():
        passed = validate_plugin(config, plugin_name)
        results.append((plugin_name, passed))
        if not passed:
            all_passed = False
        print()

    # Print summary
    print("=" * 60)
    print(f"{Colors.CYAN}Validation Summary{Colors.NC}")
    print("=" * 60)

    for name, passed in results:
        status = f"{Colors.GREEN}PASS{Colors.NC}" if passed else f"{Colors.RED}FAIL{Colors.NC}"
        print(f"  {name:<30} [{status}]")

    print()

    if all_passed:
        success(f"All {len(results)} plugins passed validation")
    else:
        failed = sum(1 for _, p in results if not p)
        error(f"{failed} of {len(results)} plugins failed validation")

    return all_passed


def list_plugins(config: MarketplaceConfig) -> None:
    """List all available plugins."""
    print()
    print(f"{Colors.CYAN}Available plugins:{Colors.NC}")
    for name in config.get_plugin_names():
        plugin = config.get_plugin_by_name(name)
        version = plugin.get('version', '?') if plugin else '?'
        print(f"  - {name} (v{version})")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Plugin validation tool for Claude Code plugin marketplaces.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python validate_plugin.py ghe                 # Validate specific plugin
  python validate_plugin.py marketplace-utils   # Validate marketplace-utils
  python validate_plugin.py --all               # Validate all plugins
  python validate_plugin.py --version           # Show script version

The script uses 'claude plugin validate' internally and requires
Claude Code CLI to be installed.
        """
    )

    parser.add_argument(
        'plugin_name',
        nargs='?',
        help='Name of the plugin to validate'
    )

    parser.add_argument(
        '--all', '-a',
        action='store_true',
        help='Validate all plugins in the marketplace'
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

    # Use current working directory as repo root
    repo_root = Path.cwd()

    # Load configuration
    config = MarketplaceConfig(repo_root)

    # Handle --all
    if args.all:
        passed = validate_all_plugins(config)
        sys.exit(0 if passed else 1)

    # Validate single plugin
    if not args.plugin_name:
        list_plugins(config)
        error("Missing required argument: plugin_name (or use --all)")
        sys.exit(1)

    # Validate plugin name exists
    if args.plugin_name not in config.get_plugin_names():
        list_plugins(config)
        error(f"Unknown plugin: {args.plugin_name}")
        sys.exit(1)

    passed = validate_plugin(config, args.plugin_name)
    sys.exit(0 if passed else 1)


if __name__ == '__main__':
    main()
