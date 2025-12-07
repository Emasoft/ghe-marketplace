#!/usr/bin/env python3
"""
detect-duplicate-hooks.py - Detect duplicate hook configurations
Part of the GHE Plugin - enforces ONE SOURCE OF TRUTH rule
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from ghe_common import (
    GHE_RED as RED,
    GHE_GREEN as GREEN,
    GHE_YELLOW as YELLOW,
    GHE_CYAN as CYAN,
    GHE_NC as NC,
    GHE_PLUGIN_ROOT,
)


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to .claude/hook_debug.log in standard log format."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [detect_duplicate_hooks] - {message}\n")
    except Exception:
        pass


# Determine plugin root (allow env var override)
PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT", GHE_PLUGIN_ROOT)

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

    debug_log(f"Checking location: {path} (is_canonical={is_canonical})")
    if Path(path).is_file():
        if is_canonical:
            debug_log(f"Found canonical hook file: {path}")
            print(f"{GREEN}[CANONICAL]{NC} {desc}")
            print(f"            {path}")
        else:
            debug_log(f"Found duplicate hook file: {path}", "WARN")
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

    debug_log(f"Checking settings.json: {path}")
    if Path(path).is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            if '"hooks"' in content:
                debug_log(f"Found hooks section in settings.json: {path}", "WARN")
                print(f"{RED}[DUPLICATE]{NC} {desc} has hooks section")
                print(f"            {path}")
                duplicates_found += 1
            else:
                debug_log(f"No hooks section in settings.json: {path}")
        except (IOError, OSError) as e:
            debug_log(f"Error reading settings.json {path}: {e}", "ERROR")
    else:
        debug_log(f"Settings.json not found: {path}")


def main() -> int:
    """Main function"""
    global duplicates_found

    debug_log("Starting GHE Hook Duplicate Detector")
    debug_log(f"PLUGIN_ROOT={PLUGIN_ROOT}")
    print(f"{CYAN}GHE Hook Duplicate Detector{NC}")
    print("Checking for duplicate hook configurations...")
    print("")

    print("=== Checking Hook Locations ===")
    print("")

    # 1. Canonical location - GHE plugin hooks
    canonical_hook = f"{PLUGIN_ROOT}/hooks/hooks.json"
    debug_log(f"Checking canonical hook location: {canonical_hook}")
    if Path(canonical_hook).is_file():
        debug_log(f"Canonical hook file found: {canonical_hook}")
        print(f"{GREEN}[CANONICAL]{NC} GHE Plugin hooks (the ONE source of truth)")
        print(f"            {canonical_hook}")
    else:
        debug_log(f"Canonical hook file NOT found: {canonical_hook}", "WARN")
        print(f"{YELLOW}[WARNING]{NC} Canonical hook file not found!")
        print(f"            Expected: {canonical_hook}")
    print("")

    # 2. Check for project-level hooks in current directory
    debug_log("Checking project-level duplicates")
    print("=== Checking Project-Level Duplicates ===")
    claude_hooks_dir = Path(".claude/hooks")
    if claude_hooks_dir.is_dir():
        debug_log(f"Found .claude/hooks directory at {claude_hooks_dir}")
        for hook_file in list(claude_hooks_dir.glob("*.json")) + list(
            claude_hooks_dir.glob("*.sh")
        ):
            if hook_file.is_file():
                debug_log(f"Found project-level duplicate: {hook_file}", "WARN")
                print(f"{RED}[DUPLICATE]{NC} Project-level hook")
                print(f"            {Path.cwd()}/{hook_file}")
                duplicates_found += 1
    else:
        debug_log("No .claude/hooks directory found (good)")

    # Also check for hooks.json directly in .claude/
    if Path(".claude/hooks.json").is_file():
        debug_log("Found .claude/hooks.json duplicate", "WARN")
        print(f"{RED}[DUPLICATE]{NC} Project-level hooks.json")
        print(f"            {Path.cwd()}/.claude/hooks.json")
        duplicates_found += 1
    print("")

    # 3. Check global settings
    debug_log("Checking global duplicates")
    print("=== Checking Global Duplicates ===")
    home = Path.home()
    debug_log(f"Home directory: {home}")
    check_settings_json(str(home / ".claude" / "settings.json"), "Global settings.json")

    # Check for global hooks directory
    global_hooks_dir = home / ".claude" / "hooks"
    debug_log(f"Checking global hooks directory: {global_hooks_dir}")
    if global_hooks_dir.is_dir():
        debug_log(f"Found global hooks directory: {global_hooks_dir}")
        for hook_file in list(global_hooks_dir.glob("*.json")) + list(
            global_hooks_dir.glob("*.sh")
        ):
            if hook_file.is_file():
                debug_log(f"Found global duplicate hook: {hook_file}", "WARN")
                print(f"{RED}[DUPLICATE]{NC} Global hook file")
                print(f"            {hook_file}")
                duplicates_found += 1
    else:
        debug_log("No global hooks directory found (good)")
    print("")

    # 4. Check for other plugins with conflicting hooks
    debug_log("Checking other plugin conflicts")
    print("=== Checking Other Plugin Conflicts ===")
    plugins_dir = home / ".claude" / "plugins"
    debug_log(f"Checking plugins directory: {plugins_dir}")
    if plugins_dir.is_dir():
        for plugin_dir in plugins_dir.iterdir():
            if plugin_dir.is_dir() and "ghe" not in str(plugin_dir):
                debug_log(f"Checking plugin: {plugin_dir}")
                plugin_hooks = plugin_dir / "hooks" / "hooks.json"
                if plugin_hooks.is_file():
                    try:
                        with open(plugin_hooks, "r", encoding="utf-8") as f:
                            content = f.read()
                        # Check if it has any hooks that conflict with GHE
                        if re.search(
                            r"auto_approve|auto-transcribe|phase-transition", content
                        ):
                            debug_log(
                                f"Found conflicting plugin hooks: {plugin_hooks}",
                                "WARN",
                            )
                            print(f"{YELLOW}[CONFLICT]{NC} Plugin with similar hooks")
                            print(f"            {plugin_hooks}")
                            duplicates_found += 1
                        else:
                            debug_log(f"Plugin hooks OK (no conflicts): {plugin_hooks}")
                    except (IOError, OSError) as e:
                        debug_log(
                            f"Error reading plugin hooks {plugin_hooks}: {e}", "ERROR"
                        )
    else:
        debug_log("No plugins directory found")

    # Also check plugin cache
    cache_dir = home / ".claude" / "plugins" / "cache"
    debug_log(f"Checking plugin cache: {cache_dir}")
    if cache_dir.is_dir():
        for plugin_dir in cache_dir.iterdir():
            if plugin_dir.is_dir() and "ghe" not in str(plugin_dir):
                debug_log(f"Checking cached plugin: {plugin_dir}")
                plugin_hooks = plugin_dir / "hooks" / "hooks.json"
                if plugin_hooks.is_file():
                    try:
                        with open(plugin_hooks, "r", encoding="utf-8") as f:
                            content = f.read()
                        if re.search(
                            r"auto_approve|auto-transcribe|phase-transition", content
                        ):
                            debug_log(
                                f"Found conflicting cached plugin hooks: {plugin_hooks}",
                                "WARN",
                            )
                            print(
                                f"{YELLOW}[CONFLICT]{NC} Cached plugin with similar hooks"
                            )
                            print(f"            {plugin_hooks}")
                            duplicates_found += 1
                        else:
                            debug_log(
                                f"Cached plugin hooks OK (no conflicts): {plugin_hooks}"
                            )
                    except (IOError, OSError) as e:
                        debug_log(
                            f"Error reading cached plugin hooks {plugin_hooks}: {e}",
                            "ERROR",
                        )
    else:
        debug_log("No plugin cache directory found")
    print("")

    # Summary
    debug_log(f"Detection complete. Duplicates found: {duplicates_found}")
    print("=== Summary ===")
    if duplicates_found == 0:
        debug_log("No duplicates found. ONE SOURCE OF TRUTH is enforced.")
        print(f"{GREEN}No duplicates found. ONE SOURCE OF TRUTH is enforced.{NC}")
        return 0
    else:
        debug_log(f"Found {duplicates_found} duplicate(s)!", "WARN")
        print(f"{RED}Found {duplicates_found} duplicate(s)!{NC}")
        print("")
        print("To fix, remove all duplicates and keep ONLY the canonical location:")
        print(f"  {canonical_hook}")
        print("")
        print("Quick fix commands:")
        print(
            "  rm -rf .claude/hooks/                    # Remove project-level duplicates"
        )
        print("  rm -rf ~/.claude/hooks/                  # Remove global duplicates")
        print("  # Edit ~/.claude/settings.json to remove 'hooks' section")
        return 1


if __name__ == "__main__":
    sys.exit(main())
