#!/usr/bin/env python3
"""
GHE Session Recovery - Check for active issue and recover context
Called by SessionStart hook

This script:
1. Checks if there's a current issue set in config
2. If not, checks for last_active_issue.json and auto-activates it
3. Recovers context for the active issue
"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Add script directory to path for imports
script_dir = Path(__file__).parent
sys.path.insert(0, str(script_dir))


def debug_log(message: str) -> None:
    """Append debug message to .claude/hook_debug.log with timestamp."""
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"[{timestamp}] session_recover: {message}\n")
    except Exception:
        pass  # Never fail on logging

# Safe import with fallback - MUST output valid JSON on any failure
debug_log("Starting session_recover.py")
try:
    from ghe_common import ghe_init, GHE_CURRENT_ISSUE, GHE_PLUGIN_ROOT
    debug_log("Imported ghe_common successfully")
except ImportError as e:
    debug_log(f"ImportError: {e} - exiting with valid JSON")
    # If import fails, output valid JSON and exit gracefully
    print(json.dumps({"event": "SessionStart", "suppressOutput": True}))
    sys.exit(0)


def get_repo_from_settings() -> str:
    """
    Read repo from plugin settings file .claude/ghe.local.md

    Returns:
        repo string (owner/repo format) or empty string
    """
    settings_file = Path(".claude/ghe.local.md")

    if not settings_file.exists():
        return ""

    try:
        content = settings_file.read_text()
        # Extract frontmatter between --- markers
        import re
        match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not match:
            return ""

        frontmatter = match.group(1)
        # Extract repo field
        repo_match = re.search(r'^repo:\s*["\']?([^"\'\n]+)["\']?\s*$', frontmatter, re.MULTILINE)
        if repo_match:
            return repo_match.group(1).strip()
        return ""

    except Exception:
        return ""


def auto_resume_last_issue() -> str:
    """
    Check for last_active_issue.json and auto-resume if found.
    Reads repo from plugin settings file (.claude/ghe.local.md).

    IMPORTANT: This function must be fast to avoid hook timeout.
    It only updates the config file directly - no subprocess calls.

    Returns:
        Issue number if resumed, empty string otherwise
    """
    last_active_file = Path(".claude/last_active_issue.json")

    if not last_active_file.exists():
        debug_log("last_active_issue.json not found")
        return ""

    debug_log(f"Found last_active_issue.json")
    try:
        data = json.loads(last_active_file.read_text())
        issue_num = str(data.get("issue", ""))
        title = data.get("title", "")
        debug_log(f"Parsed issue={issue_num}, title={title[:50] if title else 'N/A'}")

        if not issue_num:
            debug_log("No issue number in file")
            return ""

        # Get repo from plugin settings file (not from last_active_issue.json)
        repo = get_repo_from_settings()
        debug_log(f"Repo from settings: {repo or 'N/A'}")

        # Build gh command with repo if available
        gh_cmd = ["gh", "issue", "view", issue_num, "--json", "number", "--jq", ".number"]
        if repo:
            gh_cmd.extend(["--repo", repo])

        # Verify issue still exists on GitHub (quick check, 5s timeout)
        debug_log(f"Verifying issue with gh (5s timeout)...")
        result = subprocess.run(
            gh_cmd,
            capture_output=True,
            text=True,
            check=True,
            timeout=5
        )
        debug_log(f"gh returned: {result.stdout.strip()}")

        if result.stdout.strip() != issue_num:
            debug_log(f"Issue mismatch: expected {issue_num}, got {result.stdout.strip()}")
            return ""

        # Direct config update - FAST, no subprocess call
        # This avoids the expensive set-issue subprocess that caused timeouts
        config_file = Path(".claude/ghe.local.md")
        if config_file.exists():
            debug_log("Updating config file directly")
            content = config_file.read_text()
            import re
            # Update current_issue
            if re.search(r'^current_issue:.*$', content, re.MULTILINE):
                content = re.sub(r'^current_issue:.*$', f'current_issue: {issue_num}', content, flags=re.MULTILINE)
            # Update current_phase
            if re.search(r'^current_phase:.*$', content, re.MULTILINE):
                content = re.sub(r'^current_phase:.*$', 'current_phase: CONVERSATION', content, flags=re.MULTILINE)
            config_file.write_text(content)
            debug_log("Config updated successfully")

        debug_log(f"Auto-resumed issue #{issue_num}")
        return issue_num

    except json.JSONDecodeError as e:
        debug_log(f"JSONDecodeError: {e}")
        return ""
    except subprocess.CalledProcessError as e:
        debug_log(f"CalledProcessError: {e.returncode} - {e.stderr}")
        return ""
    except subprocess.TimeoutExpired:
        debug_log("TimeoutExpired: gh command took >5s")
        return ""
    except FileNotFoundError as e:
        debug_log(f"FileNotFoundError: {e}")
        return ""
    except Exception as e:
        debug_log(f"Unexpected error: {type(e).__name__}: {e}")
        return ""


def main() -> None:
    """Main function"""
    debug_log("main() started")

    # Initialize GHE environment
    debug_log("Calling ghe_init()...")
    ghe_init()
    debug_log("ghe_init() completed")

    # Import again after init to get updated values
    from ghe_common import GHE_CURRENT_ISSUE, GHE_PLUGIN_ROOT
    debug_log(f"GHE_CURRENT_ISSUE={GHE_CURRENT_ISSUE}, GHE_PLUGIN_ROOT={GHE_PLUGIN_ROOT}")

    active_issue = GHE_CURRENT_ISSUE

    # If no current issue, try to auto-resume from last_active_issue.json
    if not active_issue or active_issue == "null":
        debug_log("No current issue, trying auto-resume...")
        active_issue = auto_resume_last_issue()
        debug_log(f"auto_resume_last_issue returned: {active_issue or 'empty'}")

    if active_issue and active_issue != "null":
        # Try to run recall-elements script silently with timeout
        # Using 10s timeout to stay well under the 30s hook timeout
        recall_script = Path(GHE_PLUGIN_ROOT) / 'scripts' / 'recall_elements.py'
        debug_log(f"Running recall_elements.py for issue #{active_issue} (10s timeout)...")

        try:
            result = subprocess.run(
                [sys.executable, str(recall_script),
                 '--issue', active_issue, '--recover'],
                capture_output=True,
                text=True,
                check=False,
                timeout=10
            )
            debug_log(f"recall_elements.py completed: exit={result.returncode}")
        except subprocess.TimeoutExpired:
            debug_log("recall_elements.py TIMEOUT (>10s)")
        except subprocess.SubprocessError as e:
            debug_log(f"recall_elements.py SubprocessError: {e}")
        except FileNotFoundError as e:
            debug_log(f"recall_elements.py FileNotFoundError: {e}")
    else:
        debug_log("No active issue to recover")

    # Suppress output from user view
    debug_log("Outputting JSON and exiting successfully")
    print(json.dumps({"event": "SessionStart", "suppressOutput": True}))


if __name__ == '__main__':
    main()
