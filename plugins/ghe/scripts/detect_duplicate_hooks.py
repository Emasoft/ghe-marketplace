#!/usr/bin/env python3
"""
detect-duplicate-hooks.py - Detect duplicate hook configurations
Part of the GHE Plugin - enforces ONE SOURCE OF TRUTH rule
"""

import os
import re
import sys
from pathlib import Path
from ghe_common import GHE_RED as RED, GHE_GREEN as GREEN, GHE_YELLOW as YELLOW, GHE_CYAN as CYAN, GHE_NC as NC, GHE_PLUGIN_ROOT

# Determine plugin root (allow env var override)
PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', GHE_PLUGIN_ROOT)

# Counter for duplicates
duplicates_found = 0


def check_location(path: str, desc: str, is_canonical: bool = False) -> None:
    """
    Function to check a location for hooks

    Args:
        path: Path to check
        desc: Description for output
        is_canonical: Whether this is the canonical location
    """
    global duplicates_found

    if Path(path).is_file():
        if is_canonical:
            print(f"{GREEN}[CANONICAL]{NC} {desc}")
            print(f"            {path}")
        else:
            print(f"{RED}[DUPLICATE]{NC} {desc}")
            print(f"            {path}")
            duplicates_found += 1


def check_settings_json(path: str, desc: str) -> None:
    """
    Function to check settings.json for hooks section

    Args:
        path: Path to settings.json
        desc: Description for output
    """
    global duplicates_found

    if Path(path).is_file():
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            if '"hooks"' in content:
                print(f"{RED}[DUPLICATE]{NC} {desc} has hooks section")
                print(f"            {path}")
                duplicates_found += 1
        except (IOError, OSError):
            pass


def main() -> int:
    """Main function"""
    global duplicates_found

    print(f"{CYAN}GHE Hook Duplicate Detector{NC}")
    print("Checking for duplicate hook configurations...")
    print("")

    print("=== Checking Hook Locations ===")
    print("")

    # 1. Canonical location - GHE plugin hooks
    canonical_hook = f"{PLUGIN_ROOT}/hooks/hooks.json"
    if Path(canonical_hook).is_file():
        print(f"{GREEN}[CANONICAL]{NC} GHE Plugin hooks (the ONE source of truth)")
        print(f"            {canonical_hook}")
    else:
        print(f"{YELLOW}[WARNING]{NC} Canonical hook file not found!")
        print(f"            Expected: {canonical_hook}")
    print("")

    # 2. Check for project-level hooks in current directory
    print("=== Checking Project-Level Duplicates ===")
    claude_hooks_dir = Path(".claude/hooks")
    if claude_hooks_dir.is_dir():
        for hook_file in list(claude_hooks_dir.glob("*.json")) + list(claude_hooks_dir.glob("*.sh")):
            if hook_file.is_file():
                print(f"{RED}[DUPLICATE]{NC} Project-level hook")
                print(f"            {Path.cwd()}/{hook_file}")
                duplicates_found += 1

    # Also check for hooks.json directly in .claude/
    if Path(".claude/hooks.json").is_file():
        print(f"{RED}[DUPLICATE]{NC} Project-level hooks.json")
        print(f"            {Path.cwd()}/.claude/hooks.json")
        duplicates_found += 1
    print("")

    # 3. Check global settings
    print("=== Checking Global Duplicates ===")
    home = Path.home()
    check_settings_json(str(home / ".claude" / "settings.json"), "Global settings.json")

    # Check for global hooks directory
    global_hooks_dir = home / ".claude" / "hooks"
    if global_hooks_dir.is_dir():
        for hook_file in list(global_hooks_dir.glob("*.json")) + list(global_hooks_dir.glob("*.sh")):
            if hook_file.is_file():
                print(f"{RED}[DUPLICATE]{NC} Global hook file")
                print(f"            {hook_file}")
                duplicates_found += 1
    print("")

    # 4. Check for other plugins with conflicting hooks
    print("=== Checking Other Plugin Conflicts ===")
    plugins_dir = home / ".claude" / "plugins"
    if plugins_dir.is_dir():
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and "ghe" not in str(plugin_dir):
                plugin_hooks = plugin_dir / "hooks" / "hooks.json"
                if plugin_hooks.is_file():
                    try:
                        with open(plugin_hooks, 'r', encoding='utf-8') as f:
                            content = f.read()
                        # Check if it has any hooks that conflict with GHE
                        if re.search(r"auto_approve|auto-transcribe|phase-transition", content):
                            print(f"{YELLOW}[CONFLICT]{NC} Plugin with similar hooks")
                            print(f"            {plugin_hooks}")
                            duplicates_found += 1
                    except (IOError, OSError):
                        pass

    # Also check plugin cache
    cache_dir = home / ".claude" / "plugins" / "cache"
    if cache_dir.is_dir():
        for plugin_dir in cache_dir.iterdir():
            if plugin_dir.is_dir() and "ghe" not in str(plugin_dir):
                plugin_hooks = plugin_dir / "hooks" / "hooks.json"
                if plugin_hooks.is_file():
                    try:
                        with open(plugin_hooks, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if re.search(r"auto_approve|auto-transcribe|phase-transition", content):
                            print(f"{YELLOW}[CONFLICT]{NC} Cached plugin with similar hooks")
                            print(f"            {plugin_hooks}")
                            duplicates_found += 1
                    except (IOError, OSError):
                        pass
    print("")

    # Summary
    print("=== Summary ===")
    if duplicates_found == 0:
        print(f"{GREEN}No duplicates found. ONE SOURCE OF TRUTH is enforced.{NC}")
        return 0
    else:
        print(f"{RED}Found {duplicates_found} duplicate(s)!{NC}")
        print("")
        print("To fix, remove all duplicates and keep ONLY the canonical location:")
        print(f"  {canonical_hook}")
        print("")
        print("Quick fix commands:")
        print("  rm -rf .claude/hooks/                    # Remove project-level duplicates")
        print("  rm -rf ~/.claude/hooks/                  # Remove global duplicates")
        print("  # Edit ~/.claude/settings.json to remove 'hooks' section")
        return 1


if __name__ == '__main__':
    sys.exit(main())
