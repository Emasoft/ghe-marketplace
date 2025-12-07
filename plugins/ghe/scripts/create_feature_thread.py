#!/usr/bin/env python3
"""
create_feature_thread.py - Create a new feature/bug thread and spawn agents

This script handles the creation of BACKGROUND feature/bug development threads.
These are SEPARATE from the main conversation thread (user + Claude).

Flow:
1. Create new GitHub issue for the feature/bug
2. Athena posts REQUIREMENTS as the FIRST comment
3. Spawn Hephaestus (DEV) to start implementation
4. Track the thread in background_threads.json
5. Return thread info to main conversation

Usage:
    create_feature_thread.py feature "Title" "Description" [parent-issue]
    create_feature_thread.py bug "Title" "Description" [parent-issue]

Example:
    create_feature_thread.py feature "Add dark mode" "User requested dark mode toggle" 42
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

from ghe_common import (
    ghe_init,
    ghe_gh,
    ghe_git,
    GHE_PLUGIN_ROOT,
    GHE_REPO_ROOT,
    GHE_GREEN,
    GHE_CYAN,
    GHE_RED,
    GHE_NC,
)


def debug_log(message: str, level: str = "INFO") -> None:
    """
    Append debug message to .claude/hook_debug.log in standard log format.
    """
    try:
        log_file = Path(".claude/hook_debug.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S,%f")[:-3]
        with open(log_file, "a") as f:
            f.write(f"{timestamp} {level:<5} [create_feature_thread] - {message}\n")
    except Exception:
        pass


def ensure_threads_file(threads_file: Path) -> None:
    """
    Ensure the threads tracking file exists, create if not.

    Args:
        threads_file: Path to the background threads JSON file
    """
    debug_log(f"ensure_threads_file called with: {threads_file}")
    if not threads_file.exists():
        debug_log(f"Creating new threads file: {threads_file}")
        initial_data = {"threads": [], "last_updated": ""}
        with open(threads_file, "w", encoding="utf-8") as f:
            json.dump(initial_data, f, indent=2)
        debug_log("Threads file created successfully")


def add_thread(
    threads_file: Path,
    issue_num: int,
    thread_type: str,
    title: str,
    parent: Optional[int],
    phase: str,
    timestamp: str,
) -> None:
    """
    Add a thread to the tracking file.

    Args:
        threads_file: Path to the threads JSON file
        issue_num: GitHub issue number
        thread_type: Type of thread (feature/bug)
        title: Issue title
        parent: Parent issue number (optional)
        phase: Current phase
        timestamp: Creation timestamp
    """
    debug_log(
        f"add_thread called: issue={issue_num}, type={thread_type}, title={title}"
    )
    ensure_threads_file(threads_file)

    # Read current data
    with open(threads_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Add new thread
    new_thread = {
        "issue": issue_num,
        "type": thread_type,
        "title": title,
        "parent_issue": parent,
        "phase": phase,
        "status": "active",
        "created": timestamp,
        "updated": timestamp,
    }

    data["threads"].append(new_thread)
    data["last_updated"] = timestamp

    # Write back
    with open(threads_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    debug_log(f"Thread #{issue_num} added successfully")


def update_thread(
    threads_file: Path,
    issue_num: int,
    phase: str,
    status: str = "active",
    timestamp: Optional[str] = None,
) -> None:
    """
    Update a thread's status and phase.

    Args:
        threads_file: Path to the threads JSON file
        issue_num: GitHub issue number
        phase: New phase
        status: New status (default: "active")
        timestamp: Update timestamp
    """
    debug_log(
        f"update_thread called: issue={issue_num}, phase={phase}, status={status}"
    )
    ensure_threads_file(threads_file)

    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Read current data
    with open(threads_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Update thread
    for thread in data["threads"]:
        if thread["issue"] == issue_num:
            thread["phase"] = phase
            thread["status"] = status
            thread["updated"] = timestamp
            debug_log(f"Thread #{issue_num} updated to phase={phase}, status={status}")
            break

    data["last_updated"] = timestamp

    # Write back
    with open(threads_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_active_threads(threads_file: Path) -> list[str]:
    """
    Get list of active threads.

    Args:
        threads_file: Path to the threads JSON file

    Returns:
        List of active thread descriptions
    """
    debug_log(f"get_active_threads called with: {threads_file}")
    ensure_threads_file(threads_file)

    with open(threads_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    active = []
    for thread in data["threads"]:
        if thread["status"] == "active":
            active.append(
                f"Issue #{thread['issue']}: {thread['title']} [{thread['phase']}]"
            )

    debug_log(f"Found {len(active)} active threads")
    return active


def main() -> None:
    """Main entry point for creating feature threads."""
    debug_log("main() started")
    # Parse arguments
    parser = argparse.ArgumentParser(
        description="Create a new feature/bug development thread"
    )
    parser.add_argument(
        "thread_type",
        choices=["feature", "bug", "enhancement", "fix"],
        help="Type of thread to create",
    )
    parser.add_argument("title", help="Issue title")
    parser.add_argument("description", help="Issue description")
    parser.add_argument(
        "parent_issue", nargs="?", type=int, help="Parent conversation issue number"
    )

    args = parser.parse_args()
    debug_log(
        f"Parsed args: type={args.thread_type}, title={args.title}, parent={args.parent_issue}"
    )

    # Initialize GHE environment
    ghe_init()
    debug_log("GHE environment initialized")

    if not GHE_REPO_ROOT:
        debug_log("ERROR: Could not determine repository root", "ERROR")
        print(
            f"{GHE_RED}ERROR: Could not determine repository root{GHE_NC}",
            file=sys.stderr,
        )
        sys.exit(1)

    # Setup paths
    project_root = Path(GHE_REPO_ROOT)
    plugin_root = Path(GHE_PLUGIN_ROOT)
    threads_file = project_root / ".claude" / "ghe-background-threads.json"

    # Timestamps
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # Timestamp for GHE_REPORTS (Brisbane timezone)
    timestamp_short = datetime.now().strftime("%Y%m%d%H%M%SAEST")

    print(f"{GHE_CYAN}Creating {args.thread_type} thread: {args.title}{GHE_NC}")

    # Determine label based on type
    if args.thread_type in ("feature", "enhancement"):
        type_label = "enhancement"
    elif args.thread_type in ("bug", "fix"):
        type_label = "bug"
    else:
        type_label = "enhancement"

    # Build issue body
    body = f"""## Overview

{args.description}

---
**Thread Type**: {args.thread_type}
**Created**: {timestamp}
"""

    if args.parent_issue:
        body += f"**Parent Conversation**: #{args.parent_issue}\n"

    body += """
---
*This is a background development thread managed by GHE agents.*
*Requirements will be posted by Athena below.*"""

    # Create GitHub issue
    print("Creating GitHub issue...")
    debug_log("Creating GitHub issue via gh CLI")

    result = ghe_gh(
        "issue",
        "create",
        "--title",
        args.title,
        "--body",
        body,
        "--label",
        type_label,
        "--label",
        "phase:dev",
        "--json",
        "number",
        "--jq",
        ".number",
        capture=True,
    )

    if result.returncode != 0 or not result.stdout.strip():
        debug_log(
            f"Failed to create GitHub issue: returncode={result.returncode}", "ERROR"
        )
        print(f"{GHE_RED}ERROR: Failed to create GitHub issue{GHE_NC}", file=sys.stderr)
        sys.exit(1)

    new_issue = int(result.stdout.strip())
    debug_log(f"GitHub issue created: #{new_issue}")
    print(f"{GHE_GREEN}Created issue #{new_issue}{GHE_NC}")

    # Add to tracking
    add_thread(
        threads_file,
        new_issue,
        args.thread_type,
        args.title,
        args.parent_issue,
        "REQUIREMENTS",
        timestamp,
    )

    # Create worktree for the feature
    worktree_base = project_root.parent / "ghe-worktrees"
    worktree_path = worktree_base / f"issue-{new_issue}"
    branch_name = f"issue-{new_issue}-dev"

    print("Creating worktree...")
    debug_log(f"Creating worktree at {worktree_path} on branch {branch_name}")
    worktree_base.mkdir(parents=True, exist_ok=True)

    # Check if branch exists
    branch_check = ghe_git(
        "show-ref", "--verify", "--quiet", f"refs/heads/{branch_name}", capture=True
    )

    if branch_check.returncode == 0:
        # Branch exists, add worktree
        debug_log(f"Branch {branch_name} exists, adding worktree")
        ghe_git("worktree", "add", str(worktree_path), branch_name, capture=True)
    else:
        # Create new branch from base
        debug_log(f"Branch {branch_name} does not exist, creating new branch")
        base_branch_result = ghe_git(
            "symbolic-ref", "refs/remotes/origin/HEAD", capture=True
        )

        if base_branch_result.returncode == 0:
            base_branch = base_branch_result.stdout.strip().replace(
                "refs/remotes/origin/", ""
            )
        else:
            base_branch = "main"

        debug_log(f"Creating worktree with new branch from {base_branch}")
        ghe_git(
            "worktree",
            "add",
            str(worktree_path),
            "-b",
            branch_name,
            base_branch,
            capture=True,
        )

    if worktree_path.exists():
        debug_log(f"Worktree created successfully: {worktree_path}")
        print(f"{GHE_GREEN}Worktree created: {worktree_path}{GHE_NC}")

    # Build Athena's prompt for requirements generation
    print("Spawning Athena to write requirements...")

    athena_prompt = f"""You are Athena, the GHE orchestrator.

## CRITICAL TASK: Write Requirements

You MUST write the REQUIREMENTS for issue #{new_issue} as the FIRST substantive comment.

**Issue**: #{new_issue}
**Type**: {args.thread_type}
**Title**: {args.title}
**Description**: {args.description}
**Parent Conversation**: {args.parent_issue if args.parent_issue else "none"}

## Requirements Format

Post a comment to issue #{new_issue} with this structure:

```bash
# Load avatar helper (use Python script)
python3 "{plugin_root}/scripts/post_with_avatar.py"

# Get header
HEADER=$(avatar_header "Athena")

# Post requirements
gh issue comment {new_issue} --body "${{HEADER}}
## Requirements for: {args.title}

### 1. Overview
[Brief description of what this {args.thread_type} will accomplish]

### 2. User Story
**As a** [user type], **I want** [goal], **so that** [benefit].

### 3. Acceptance Criteria
- [ ] **AC-1**: [First criterion]
- [ ] **AC-2**: [Second criterion]
- [ ] **AC-3**: [Third criterion]

### 4. Technical Requirements
#### 4.1 Functional
- **FR-1**: [Functional requirement]

#### 4.2 Non-Functional
- **NFR-1**: [Non-functional requirement]

### 5. Scope
#### In Scope
- [What IS included]

#### Out of Scope
- [What is NOT included]

### 6. Dependencies
- [List any dependencies]

### 7. Test Requirements
- **TEST-1**: [What must be tested]

---
*Requirements written by Athena (Orchestrator)*
*Hephaestus will begin DEV phase after requirements are posted.*
"
```

After posting requirements, call:
```bash
python3 "{plugin_root}/scripts/agent_request_spawn.py" dev-thread-manager {new_issue} "Requirements complete, begin DEV"
```

## Output
Save your work to: GHE_REPORTS/{timestamp_short}_issue_{new_issue}_requirements_(Athena).md"""

    # Spawn Athena in background
    spawn_script = plugin_root / "scripts" / "spawn_background.py"
    debug_log(f"Spawning Athena via {spawn_script}")
    subprocess.Popen(
        ["python3", str(spawn_script), athena_prompt, str(project_root)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    debug_log("Athena spawned successfully")

    # Output summary
    print()
    print(f"{GHE_GREEN}========================================{GHE_NC}")
    print(f"{GHE_GREEN}Feature Thread Created!{GHE_NC}")
    print(f"{GHE_GREEN}========================================{GHE_NC}")
    print()
    print(f"Issue:       {GHE_CYAN}#{new_issue}{GHE_NC}")
    print(f"Title:       {args.title}")
    print(f"Type:        {args.thread_type}")
    print(f"Worktree:    {worktree_path}")
    print(f"Branch:      {branch_name}")
    print()
    print("Workflow:")
    print("  1. Athena is writing requirements (spawned)")
    print("  2. Hephaestus will begin DEV after requirements")
    print("  3. Artemis will run TEST after DEV")
    print("  4. Hera will conduct REVIEW after TEST")
    print()
    if args.parent_issue:
        print(f"Linked to conversation: {GHE_CYAN}#{args.parent_issue}{GHE_NC}")
        print()
    print(f"Track progress: gh issue view {new_issue} --comments")
    print()

    # Output JSON for programmatic use
    result_json = {
        "issue": new_issue,
        "title": args.title,
        "type": args.thread_type,
        "worktree": str(worktree_path),
        "branch": branch_name,
    }
    print(json.dumps(result_json))
    debug_log(f"main() completed successfully: issue #{new_issue}")


if __name__ == "__main__":
    main()
