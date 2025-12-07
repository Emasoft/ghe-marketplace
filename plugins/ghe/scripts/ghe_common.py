#!/usr/bin/env python3
"""
GHE Common Library
Shared functions for all GHE scripts
Import this module: from ghe_common import *
"""

import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Optional, List, Any, Dict

# Determine plugin root if not already set
# Library is at plugins/ghe/scripts/, so go up 1 level to get to plugins/ghe/
_script_dir = Path(__file__).parent.resolve()
GHE_PLUGIN_ROOT = os.environ.get('CLAUDE_PLUGIN_ROOT', str(_script_dir.parent))

# Colors for terminal output (ANSI escape codes)
GHE_RED = '\033[0;31m'
GHE_GREEN = '\033[0;32m'
GHE_YELLOW = '\033[1;33m'
GHE_BLUE = '\033[0;34m'
GHE_CYAN = '\033[0;36m'
GHE_NC = '\033[0m'  # No Color

# Global state (set by ghe_init())
GHE_CONFIG_FILE: Optional[str] = None
GHE_REPO_ROOT: Optional[str] = None
GHE_ENABLED: str = "false"
GHE_CURRENT_ISSUE: str = ""
GHE_CURRENT_PHASE: str = ""
GHE_AUTO_TRANSCRIBE: str = "false"

# Cached GitHub repo info (populated by ghe_get_github_repo)
_github_owner: Optional[str] = None
_github_repo: Optional[str] = None


def ghe_get_github_repo() -> tuple[Optional[str], Optional[str]]:
    """
    Get GitHub owner and repo name dynamically from git remote.
    Results are cached after first call.

    Returns:
        Tuple of (owner, repo) or (None, None) if not a GitHub repo
    """
    global _github_owner, _github_repo

    if _github_owner is not None and _github_repo is not None:
        return _github_owner, _github_repo

    # Run from plugin's repo directory (plugin is at REPO/plugins/ghe/)
    plugin_repo_root = str(Path(GHE_PLUGIN_ROOT).parent.parent)

    try:
        # Try gh CLI first (most reliable) - run from plugin repo
        result = subprocess.run(
            ['gh', 'repo', 'view', '--json', 'owner,name'],
            capture_output=True,
            text=True,
            check=False,
            cwd=plugin_repo_root  # Run from plugin's repo directory
        )
        if result.returncode == 0:
            import json
            data = json.loads(result.stdout)
            _github_owner = data.get('owner', {}).get('login')
            _github_repo = data.get('name')
            if _github_owner and _github_repo:
                return _github_owner, _github_repo
    except (subprocess.SubprocessError, json.JSONDecodeError):
        pass

    try:
        # Fallback to parsing git remote URL - run from plugin repo
        result = subprocess.run(
            ['git', '-C', plugin_repo_root, 'remote', 'get-url', 'origin'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            url = result.stdout.strip()
            # Parse github.com/owner/repo from various URL formats
            match = re.search(r'github\.com[/:]([^/]+)/([^/.]+)', url)
            if match:
                _github_owner = match.group(1)
                _github_repo = match.group(2)
                return _github_owner, _github_repo
    except subprocess.SubprocessError:
        pass

    return None, None


def ghe_get_avatar_base_url() -> str:
    """
    Get the base URL for agent avatars, dynamically using the repo owner/name.

    Returns:
        Base URL for avatar images
    """
    owner, repo = ghe_get_github_repo()
    if owner and repo:
        return f"https://raw.githubusercontent.com/{owner}/{repo}/main/plugins/ghe/assets/avatars"
    # Fallback to local relative path
    return f"file://{GHE_PLUGIN_ROOT}/assets/avatars"


def ghe_get_github_user() -> str:
    """
    Get the current GitHub username dynamically.

    Returns:
        GitHub username or 'unknown' if not authenticated
    """
    # Check environment first
    env_user = os.environ.get('GITHUB_OWNER') or os.environ.get('GITHUB_USER')
    if env_user:
        return env_user

    try:
        result = subprocess.run(
            ['gh', 'api', 'user', '--jq', '.login'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except subprocess.SubprocessError:
        pass

    try:
        # Fallback to git config
        result = subprocess.run(
            ['git', 'config', 'user.name'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except subprocess.SubprocessError:
        pass

    return 'unknown'


# Agent avatar configuration - SINGLE SOURCE OF TRUTH
# All scripts should import this instead of defining their own
GHE_AGENT_AVATARS: Dict[str, str] = {
    "Claude": "claude.png",
    "Athena": "athena.png",
    "Hephaestus": "hephaestus.png",
    "Artemis": "artemis.png",
    "Hera": "hera.png",
    "Themis": "themis.png",
    "Mnemosyne": "mnemosyne.png",
    "Ares": "ares.png",
    "Hermes": "hermes.png",
    "Chronos": "chronos.png",
    "Cerberus": "cerberus.png",
    "Argos": "argos.png",
    "Argos-Panoptes": "argos.png",
}

# Agent ID to display name mapping
GHE_AGENT_NAMES: Dict[str, str] = {
    "ghe:dev-thread-manager": "Hephaestus",
    "ghe:test-thread-manager": "Artemis",
    "ghe:review-thread-manager": "Hera",
    "ghe:github-elements-orchestrator": "Athena",
    "ghe:phase-gate": "Themis",
    "ghe:memory-sync": "Mnemosyne",
    "ghe:enforcement": "Ares",
    "ghe:reporter": "Hermes",
    "ghe:ci-issue-opener": "Chronos",
    "ghe:pr-checker": "Cerberus",
}


def ghe_get_avatar_url(agent_name: str, size: int = 77) -> str:
    """
    Get the full avatar URL for an agent or GitHub user.

    Args:
        agent_name: Agent display name or GitHub username
        size: Avatar size (default 77)

    Returns:
        Full URL to avatar image
    """
    # Check if it's a known agent
    if agent_name in GHE_AGENT_AVATARS:
        base = ghe_get_avatar_base_url()
        return f"{base}/{GHE_AGENT_AVATARS[agent_name]}"
    else:
        # Assume it's a GitHub username
        return f"https://avatars.githubusercontent.com/{agent_name}?s={size}"


def ghe_find_config_file() -> Optional[str]:
    """
    Find config file - try multiple locations
    Priority: 1) Plugin-relative path, 2) Git root, 3) Current directory

    Returns:
        Path to config file if found, None otherwise
    """
    # Try plugin-relative first (plugin is at REPO/plugins/ghe/)
    plugin_repo = Path(GHE_PLUGIN_ROOT).parent.parent
    config_path = plugin_repo / '.claude' / 'ghe.local.md'
    if config_path.is_file():
        return str(config_path)

    # Try git root
    try:
        result = subprocess.run(
            ['git', 'rev-parse', '--show-toplevel'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode == 0:
            git_root = result.stdout.strip()
            config_path = Path(git_root) / '.claude' / 'ghe.local.md'
            if config_path.is_file():
                return str(config_path)
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Try current directory
    config_path = Path.cwd() / '.claude' / 'ghe.local.md'
    if config_path.is_file():
        return str(config_path)

    return None


def ghe_get_repo_path(config_file: Optional[str] = None) -> str:
    """
    Read repo_path from config - SOURCE OF TRUTH from /ghe:setup
    This ensures we always use the exact repo the user selected

    Args:
        config_file: Optional path to config file

    Returns:
        Path to the repository root
    """
    if config_file is None:
        config_file = ghe_find_config_file()

    if config_file and Path(config_file).is_file():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Extract repo_path from YAML frontmatter
            match = re.search(r'^repo_path:\s*["\']?([^"\'\n]+)["\']?', content, re.MULTILINE)
            if match:
                path = match.group(1).strip()
                if path and Path(path).is_dir():
                    return path
        except (IOError, OSError):
            pass

    # Fallback to plugin-relative path
    fallback = Path(GHE_PLUGIN_ROOT).parent.parent
    return str(fallback.resolve())


def ghe_get_setting(key: str, default: str = "") -> str:
    """
    Read a setting from config frontmatter

    Args:
        key: The setting key to read
        default: Default value if not found

    Returns:
        The setting value or default
    """
    global GHE_CONFIG_FILE
    config_file = GHE_CONFIG_FILE or ghe_find_config_file()

    if config_file and Path(config_file).is_file():
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                content = f.read()
            # Extract value from YAML frontmatter
            pattern = rf'^{re.escape(key)}:\s*["\']?([^"\'\n]+)["\']?'
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                value = match.group(1).strip()
                if value:
                    return value
        except (IOError, OSError):
            pass

    return default


def ghe_gh(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """
    Run gh commands from the correct repo directory

    Args:
        *args: Arguments to pass to gh command
        capture: If True, capture output

    Returns:
        CompletedProcess instance
    """
    global GHE_REPO_ROOT
    repo_root = GHE_REPO_ROOT or ghe_get_repo_path()

    return subprocess.run(
        ['gh'] + list(args),
        cwd=repo_root,
        capture_output=capture,
        text=True,
        check=False
    )


def ghe_git(*args: str, capture: bool = False) -> subprocess.CompletedProcess:
    """
    Run git commands on the correct repo

    Args:
        *args: Arguments to pass to git command
        capture: If True, capture output

    Returns:
        CompletedProcess instance
    """
    global GHE_REPO_ROOT
    repo_root = GHE_REPO_ROOT or ghe_get_repo_path()

    return subprocess.run(
        ['git', '-C', repo_root] + list(args),
        capture_output=capture,
        text=True,
        check=False
    )


def ghe_init() -> None:
    """
    Initialize GHE environment variables
    Call this at the start of each script
    """
    global GHE_CONFIG_FILE, GHE_REPO_ROOT, GHE_ENABLED
    global GHE_CURRENT_ISSUE, GHE_CURRENT_PHASE, GHE_AUTO_TRANSCRIBE

    # Set config file
    GHE_CONFIG_FILE = os.environ.get('GHE_CONFIG_FILE') or ghe_find_config_file()

    # Set repo root
    GHE_REPO_ROOT = os.environ.get('GHE_REPO_ROOT') or ghe_get_repo_path(GHE_CONFIG_FILE)

    # Read settings
    GHE_ENABLED = ghe_get_setting("enabled", "false")
    GHE_CURRENT_ISSUE = ghe_get_setting("current_issue", "")
    GHE_CURRENT_PHASE = ghe_get_setting("current_phase", "")
    GHE_AUTO_TRANSCRIBE = ghe_get_setting("auto_transcribe", "false")

    # Also export to environment for subprocess compatibility
    os.environ['GHE_CONFIG_FILE'] = GHE_CONFIG_FILE or ""
    os.environ['GHE_REPO_ROOT'] = GHE_REPO_ROOT or ""
    os.environ['GHE_ENABLED'] = GHE_ENABLED
    os.environ['GHE_CURRENT_ISSUE'] = GHE_CURRENT_ISSUE
    os.environ['GHE_CURRENT_PHASE'] = GHE_CURRENT_PHASE
    os.environ['GHE_AUTO_TRANSCRIBE'] = GHE_AUTO_TRANSCRIBE


def ghe_info(*args: Any) -> None:
    """Print info message with green [GHE] prefix"""
    message = ' '.join(str(arg) for arg in args)
    print(f"{GHE_GREEN}[GHE]{GHE_NC} {message}")


def ghe_warn(*args: Any) -> None:
    """Print warning message with yellow [GHE] prefix to stderr"""
    message = ' '.join(str(arg) for arg in args)
    print(f"{GHE_YELLOW}[GHE]{GHE_NC} {message}", file=sys.stderr)


def ghe_error(*args: Any) -> None:
    """Print error message with red [GHE] prefix to stderr"""
    message = ' '.join(str(arg) for arg in args)
    print(f"{GHE_RED}[GHE]{GHE_NC} {message}", file=sys.stderr)


def run_command(cmd: List[str], cwd: Optional[str] = None,
                capture: bool = True, check: bool = False) -> subprocess.CompletedProcess:
    """
    Run a command and return the result

    Args:
        cmd: Command and arguments as list
        cwd: Working directory
        capture: Capture stdout/stderr
        check: Raise exception on non-zero exit

    Returns:
        CompletedProcess instance
    """
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=capture,
        text=True,
        check=check
    )


def ensure_directory(path: str) -> bool:
    """
    Ensure a directory exists, create if not

    Args:
        path: Directory path

    Returns:
        True if directory exists or was created
    """
    try:
        Path(path).mkdir(parents=True, exist_ok=True)
        return True
    except (OSError, PermissionError):
        return False


def read_file(path: str) -> Optional[str]:
    """
    Read a file and return its contents

    Args:
        path: File path

    Returns:
        File contents or None if error
    """
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except (IOError, OSError):
        return None


def write_file(path: str, content: str) -> bool:
    """
    Write content to a file

    Args:
        path: File path
        content: Content to write

    Returns:
        True if successful
    """
    try:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except (IOError, OSError):
        return False


# Export all public symbols
__all__ = [
    # Constants
    'GHE_PLUGIN_ROOT',
    'GHE_RED', 'GHE_GREEN', 'GHE_YELLOW', 'GHE_BLUE', 'GHE_CYAN', 'GHE_NC',
    # Agent configuration
    'GHE_AGENT_AVATARS', 'GHE_AGENT_NAMES',
    # State variables
    'GHE_CONFIG_FILE', 'GHE_REPO_ROOT', 'GHE_ENABLED',
    'GHE_CURRENT_ISSUE', 'GHE_CURRENT_PHASE', 'GHE_AUTO_TRANSCRIBE',
    # Core functions
    'ghe_find_config_file', 'ghe_get_repo_path', 'ghe_get_setting',
    'ghe_gh', 'ghe_git', 'ghe_init',
    # GitHub functions
    'ghe_get_github_repo', 'ghe_get_github_user',
    'ghe_get_avatar_base_url', 'ghe_get_avatar_url',
    # Logging functions
    'ghe_info', 'ghe_warn', 'ghe_error',
    # Utility functions
    'run_command', 'ensure_directory', 'read_file', 'write_file',
]
