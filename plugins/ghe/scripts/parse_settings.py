#!/usr/bin/env python3
"""
GitHub Elements Settings Parser
Extracts settings from .claude/ghe.local.md
Usage: ./parse_settings.py [field-name]
Without field-name: outputs all frontmatter
With field-name: outputs that field's value
"""

import re
import sys
from datetime import datetime
from pathlib import Path

# Add script directory to sys.path for ghe_common import
SCRIPT_DIR = Path(__file__).parent.resolve()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import ghe_common  # noqa: E402 - Must import after sys.path modification


def debug_log(message: str, level: str = "INFO") -> None:
    """Append debug message to .claude/hook_debug.log in standard log format."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [parse_settings] - {message}\n")
    except Exception:
        pass


# Default values for all settings
DEFAULTS = {
    "enabled": "true",
    "enforcement_level": "standard",
    "serena_sync": "true",
    "auto_worktree": "false",
    "checkpoint_interval_minutes": "30",
    "notification_level": "normal",
    "default_reviewer": "",
    "stale_threshold_hours": "24",
    "epic_label_prefix": "parent-epic:",
    "auto_transcribe": "true",
    "auto_create_issue": "true",
    "current_issue": "",
}


def extract_frontmatter(content: str) -> str:
    """
    Extract YAML frontmatter from content (everything between --- markers)

    Args:
        content: File content

    Returns:
        Frontmatter content without delimiters
    """
    # Match everything between first --- and second ---
    # Use sed -n '/^---$/,/^---$/{ /^---$/d; p; }' logic
    lines = content.split("\n")
    in_frontmatter = False
    frontmatter_lines = []

    for line in lines:
        if line.strip() == "---":
            if in_frontmatter:
                # Second ---, end of frontmatter
                break
            else:
                # First ---, start of frontmatter
                in_frontmatter = True
                continue
        if in_frontmatter:
            frontmatter_lines.append(line)

    return "\n".join(frontmatter_lines)


def extract_field_value(frontmatter: str, field: str) -> str:
    """
    Extract specific field value from frontmatter

    Args:
        frontmatter: YAML frontmatter content
        field: Field name to extract

    Returns:
        Field value or empty string if not found
    """
    # Match field: value (with optional quotes)
    pattern = rf"^{re.escape(field)}:\s*(.*)$"
    match = re.search(pattern, frontmatter, re.MULTILINE)

    if not match:
        return ""

    value = match.group(1).strip()

    # Remove surrounding quotes (double or single)
    if value:
        # Remove double quotes
        if value.startswith('"') and value.endswith('"'):
            value = value[1:-1]
        # Remove single quotes
        elif value.startswith("'") and value.endswith("'"):
            value = value[1:-1]

    return value


def main() -> int:
    """
    Main entry point

    Returns:
        Exit code (0 for success)
    """
    debug_log("parse_settings.py starting")
    # Initialize GHE environment
    ghe_common.ghe_init()

    # Get field name from command line (if provided)
    field_name = sys.argv[1] if len(sys.argv) > 1 else None
    debug_log(f"Requested field: {field_name if field_name else 'ALL (frontmatter)'}")

    # Check if settings file exists
    if not ghe_common.GHE_CONFIG_FILE or not Path(ghe_common.GHE_CONFIG_FILE).is_file():
        debug_log(
            f"Settings file not found: {ghe_common.GHE_CONFIG_FILE}, using defaults"
        )
        # Return defaults if no settings file
        if field_name:
            print(DEFAULTS.get(field_name, ""))
        # If no field specified and no config file, output nothing (like bash version)
        return 0

    # Read config file
    try:
        with open(ghe_common.GHE_CONFIG_FILE, "r", encoding="utf-8") as f:
            content = f.read()
        debug_log(
            f"Read settings file: {ghe_common.GHE_CONFIG_FILE} ({len(content)} bytes)"
        )
    except (IOError, OSError) as e:
        debug_log(f"Error reading settings file: {e}", "ERROR")
        # On error, return defaults
        if field_name:
            print(DEFAULTS.get(field_name, ""))
        return 0

    # Extract frontmatter
    frontmatter = extract_frontmatter(content)
    debug_log(f"Extracted frontmatter ({len(frontmatter)} chars)")

    # If no field specified, output all frontmatter
    if not field_name:
        print(frontmatter)
        return 0

    # Extract specific field value
    value = extract_field_value(frontmatter, field_name)

    # Return value or default
    if not value:
        default_val = DEFAULTS.get(field_name, "")
        debug_log(f"Field '{field_name}' not found, using default: '{default_val}'")
        print(default_val)
    else:
        debug_log(f"Field '{field_name}' = '{value}'")
        print(value)

    debug_log("parse_settings.py completed successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
