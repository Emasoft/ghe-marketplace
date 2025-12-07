#!/usr/bin/env python3
"""
Plugin Validator - Comprehensive validation for Claude Code plugins
Integrates all validation logic from individual validators
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from collections.abc import Callable
from typing import Any, NamedTuple

# ANSI colors
RED = "\033[0;31m"
GREEN = "\033[0;32m"
YELLOW = "\033[1;33m"
BLUE = "\033[0;34m"
CYAN = "\033[0;36m"
NC = "\033[0m"  # No Color

# Global flag for URL checking (set by command line)
CHECK_URLS_REACHABLE = False


class ValidationResult(NamedTuple):
    errors: list[str]
    warnings: list[str]
    info: list[str]


def log_error(msg: str) -> None:
    print(f"{RED}  ✗ {msg}{NC}")


def log_warning(msg: str) -> None:
    print(f"{YELLOW}  ⚠ {msg}{NC}")


def log_success(msg: str) -> None:
    print(f"{GREEN}  ✓ {msg}{NC}")


def log_info(msg: str) -> None:
    print(f"{BLUE}  ℹ {msg}{NC}")


def log_section(msg: str) -> None:
    print()
    print(f"{CYAN}{'=' * 70}{NC}")
    print(f"{CYAN}{msg}{NC}")
    print(f"{CYAN}{'=' * 70}{NC}")


def parse_yaml_frontmatter(content: str) -> tuple[dict[str, str] | None, str | None]:
    """Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body) or (None, error_message) if invalid.
    """
    lines = content.split("\n")

    if not lines or lines[0].strip() != "---":
        return None, "Missing opening ---"

    # Check for duplicate frontmatter blocks
    # Only count --- that could be frontmatter delimiters:
    # - Line must be exactly '---' (no extra content)
    # - Must not be inside a code block
    in_code_block = False
    frontmatter_marker_count = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        # Track code blocks (``` markers)
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            continue
        # Only count --- outside code blocks
        if stripped == "---" and not in_code_block:
            frontmatter_marker_count += 1
            # After finding the closing frontmatter (2nd marker), stop counting
            # because subsequent --- are horizontal rules, not frontmatter
            if frontmatter_marker_count == 2:
                break

    # If we found the expected 2 markers, that's fine
    # If we found < 2, the other checks will catch it

    # Find closing ---
    closing_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == "---":
            closing_idx = i
            break

    if closing_idx is None:
        return None, "Missing closing ---"

    # Extract frontmatter YAML
    frontmatter_lines = lines[1:closing_idx]
    frontmatter_text = "\n".join(frontmatter_lines)

    # Check for duplicate keys before parsing
    keys_found = re.findall(r"^([a-z_][a-z0-9_]*):", frontmatter_text, re.MULTILINE)
    duplicates = [k for k in set(keys_found) if keys_found.count(k) > 1]
    if duplicates:
        return (
            None,
            f"MALFORMED: Duplicate keys in frontmatter: {', '.join(duplicates)}",
        )

    # Simple YAML parsing (key: value)
    frontmatter: dict[str, str] = {}
    current_key: str | None = None
    current_value_lines: list[str] = []

    for line in frontmatter_lines:
        # Check for multiline continuation (starts with spaces and not a new key)
        if line.startswith("  ") or line.startswith("\t"):
            if current_key:
                current_value_lines.append(line.strip())
            continue

        # Save previous key-value if exists
        if current_key:
            if current_value_lines:
                frontmatter[current_key] = "\n".join(current_value_lines)
            current_key = None
            current_value_lines = []

        # Parse new key: value
        if ":" in line:
            parts = line.split(":", 1)
            key = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ""

            if value == "|" or value == ">":
                # Multiline value follows
                current_key = key
                current_value_lines = []
            elif value:
                frontmatter[key] = value
            else:
                frontmatter[key] = ""

    # Handle last multiline value
    if current_key and current_value_lines:
        frontmatter[current_key] = "\n".join(current_value_lines)

    body = "\n".join(lines[closing_idx + 1 :])
    return frontmatter, body


def validate_plugin_structure(plugin_path: Path) -> ValidationResult:
    """Validate plugin directory structure."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    log_section("Step 1: Plugin Structure")

    if not plugin_path.exists():
        errors.append(f"Plugin directory not found: {plugin_path}")
        log_error(f"Plugin directory not found: {plugin_path}")
        return ValidationResult(errors, warnings, info)
    log_success("Plugin directory exists")

    claude_plugin = plugin_path / ".claude-plugin"
    if not claude_plugin.exists():
        errors.append("Missing .claude-plugin/ directory")
        log_error("Missing .claude-plugin/ directory")
        return ValidationResult(errors, warnings, info)
    log_success(".claude-plugin/ directory exists")

    manifest = claude_plugin / "plugin.json"
    if not manifest.exists():
        errors.append("Missing plugin.json manifest")
        log_error("Missing plugin.json manifest")
        return ValidationResult(errors, warnings, info)
    log_success("plugin.json manifest exists")

    return ValidationResult(errors, warnings, info)


def validate_manifest(plugin_path: Path) -> tuple[ValidationResult, str]:
    """Validate plugin.json manifest."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    plugin_name = ""

    log_section("Step 2: Manifest Validation")

    manifest_path = plugin_path / ".claude-plugin" / "plugin.json"

    try:
        with open(manifest_path, "r") as f:
            manifest = json.load(f)
        log_success("JSON syntax valid")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON syntax: {e}")
        log_error(f"Invalid JSON syntax: {e}")
        return ValidationResult(errors, warnings, info), ""

    # Check name
    plugin_name = manifest.get("name", "")
    if not plugin_name:
        errors.append("Missing required field: name")
        log_error("Missing required field: name")
    else:
        log_success(f"name: {plugin_name}")
        if not re.match(r"^[a-z][a-z0-9-]*[a-z0-9]$", plugin_name):
            warnings.append("name should be kebab-case")
            log_warning("name should be kebab-case (lowercase, hyphens)")

    # Check version
    version = manifest.get("version", "")
    if version:
        if re.match(r"^\d+\.\d+\.\d+$", version):
            log_success(f"version: {version} (valid semver)")
        else:
            warnings.append(f"version '{version}' is not semantic versioning")
            log_warning(f"version '{version}' is not semantic versioning (X.Y.Z)")
    else:
        info.append("version: not specified")
        log_info("version: not specified")

    # Check description
    description = manifest.get("description", "")
    if description:
        log_success(f"description: {len(description)} characters")
        if len(description) < 10:
            warnings.append("description too short")
            log_warning("description too short (recommend 10+ characters)")
    else:
        info.append("description: not specified")
        log_info("description: not specified")

    # Check author
    author = manifest.get("author", {})
    if isinstance(author, dict):
        author_name = author.get("name", "")
        if author_name:
            log_success(f"author: {author_name}")

    # Check license
    license_val = manifest.get("license", "")
    if license_val:
        log_success(f"license: {license_val}")
    else:
        warnings.append("license: not specified")
        log_warning("license: not specified (recommended)")

    # Check hooks reference
    hooks_ref = manifest.get("hooks", "")
    if hooks_ref:
        hooks_path = plugin_path / hooks_ref.lstrip("./")
        if hooks_path.exists():
            log_success(f"hooks reference: {hooks_ref} (file exists)")
        else:
            errors.append(f"hooks reference: {hooks_ref} (file NOT found)")
            log_error(f"hooks reference: {hooks_ref} (file NOT found)")

    # Validate component paths start with ./ (per Anthropic docs)
    # "All paths must be relative to plugin root and start with ./"
    path_fields = ["commands", "agents", "hooks", "mcpServers"]
    for field in path_fields:
        value = manifest.get(field)
        if not value:
            continue

        # Value can be string or array
        paths_to_check = []
        if isinstance(value, str):
            paths_to_check = [value]
        elif isinstance(value, list):
            paths_to_check = [p for p in value if isinstance(p, str)]

        for path in paths_to_check:
            # Skip inline objects (hooks and mcpServers can be inline)
            if not isinstance(path, str):
                continue
            # Per Anthropic docs: must start with ./
            if not path.startswith("./"):
                errors.append(
                    f"Manifest '{field}': Path '{path}' must start with './' (relative to plugin root)"
                )
                log_error(f"Manifest '{field}': Path '{path}' must start with './'")

    return ValidationResult(errors, warnings, info), plugin_name


def validate_commands(plugin_path: Path) -> ValidationResult:
    """Validate commands."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    commands_found = 0
    commands_valid = 0

    log_section("Step 3: Commands Validation")

    commands_dir = plugin_path / "commands"
    if not commands_dir.exists():
        log_info("No commands/ directory")
        return ValidationResult(errors, warnings, info)

    for cmd_file in commands_dir.rglob("*.md"):
        commands_found += 1
        cmd_name = cmd_file.stem

        content = cmd_file.read_text()
        fm, body = parse_yaml_frontmatter(content)

        if fm is None:
            errors.append(f"Command '{cmd_name}': {body}")
            log_error(f"Command '{cmd_name}': {body}")
            continue

        if "description" not in fm:
            warnings.append(f"Command '{cmd_name}': Missing description")
            log_warning(f"Command '{cmd_name}': Missing description")

        commands_valid += 1

    log_success(f"Commands: {commands_found} found, {commands_valid} valid")
    return ValidationResult(errors, warnings, info)


def validate_agents(plugin_path: Path) -> ValidationResult:
    """Validate agents with comprehensive checks from validate-agent.sh."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    agents_found = 0
    agents_valid = 0
    total_checks = 0

    log_section("Step 4: Agents Validation")

    agents_dir = plugin_path / "agents"
    if not agents_dir.exists():
        log_info("No agents/ directory")
        return ValidationResult(errors, warnings, info)

    # color is NOT in official Anthropic docs but commonly used in practice
    valid_colors = {
        "blue",
        "cyan",
        "green",
        "yellow",
        "magenta",
        "red",
        "orange",
        "purple",
    }
    # Per Anthropic docs: model aliases
    valid_models = {"inherit", "sonnet", "opus", "haiku"}
    # Per Anthropic docs: valid permissionMode values
    valid_permission_modes = {
        "default",
        "acceptEdits",
        "bypassPermissions",
        "plan",
        "ignore",
    }

    # Check for references directory (documentation, not agents)
    refs_dir = agents_dir / "references"
    if refs_dir.exists():
        ref_count = len(list(refs_dir.rglob("*.md")))
        if ref_count > 0:
            log_info(f"agents/references/: {ref_count} reference docs (not agents)")

    for agent_file in agents_dir.rglob("*.md"):
        # CRITICAL: Skip files in references/ subdirectory - these are docs, not agents
        if "references" in agent_file.parts:
            continue
        agents_found += 1
        agent_name = agent_file.stem
        agent_valid = True

        print(f"\n  {CYAN}Checking agent: {agent_name}{NC}")

        content = agent_file.read_text()
        fm, body = parse_yaml_frontmatter(content)

        if fm is None:
            errors.append(f"Agent '{agent_name}': {body}")
            log_error(f"Agent '{agent_name}': {body}")
            continue

        # Check required field: name
        total_checks += 1
        if "name" not in fm:
            errors.append(f"Agent '{agent_name}': Missing name field")
            log_error("Missing name field")
            agent_valid = False
        else:
            name_value = fm["name"]
            log_success(f"name: {name_value}")

            # Validate name format
            total_checks += 1
            if not re.match(r"^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$", name_value):
                errors.append(
                    f"Agent '{agent_name}': name must start/end with alphanumeric and contain only letters, numbers, hyphens"
                )
                log_error(
                    "name must start/end with alphanumeric and contain only letters, numbers, hyphens"
                )
                agent_valid = False

            # Validate name length
            total_checks += 1
            name_len = len(name_value)
            if name_len < 3:
                errors.append(
                    f"Agent '{agent_name}': name too short (minimum 3 characters)"
                )
                log_error("name too short (minimum 3 characters)")
                agent_valid = False
            elif name_len > 50:
                errors.append(
                    f"Agent '{agent_name}': name too long (maximum 50 characters)"
                )
                log_error("name too long (maximum 50 characters)")
                agent_valid = False

            # Check for generic names
            total_checks += 1
            if name_value.lower() in {"helper", "assistant", "agent", "tool"}:
                warnings.append(
                    f"Agent '{agent_name}': name is too generic: {name_value}"
                )
                log_warning(f"name is too generic: {name_value}")

        # Check required field: description
        total_checks += 1
        if "description" not in fm:
            errors.append(f"Agent '{agent_name}': Missing description field")
            log_error("Missing description field")
            agent_valid = False
        else:
            desc = fm["description"]
            desc_len = len(desc)
            log_success(f"description: {desc_len} characters")

            # Check description length
            total_checks += 1
            if desc_len < 10:
                errors.append(
                    f"Agent '{agent_name}': description too short (minimum 10 characters)"
                )
                log_error("description too short (minimum 10 characters)")
                agent_valid = False
            elif desc_len > 5000:
                warnings.append(
                    f"Agent '{agent_name}': description very long (over 5000 characters)"
                )
                log_warning("description very long (over 5000 characters)")

            # Check for example blocks
            total_checks += 1
            if "<example>" not in desc:
                warnings.append(
                    f"Agent '{agent_name}': description should include <example> blocks"
                )
                log_warning(
                    "description should include <example> blocks for triggering"
                )

            # Check for "Use this agent when" pattern
            total_checks += 1
            if "use this agent when" not in desc.lower():
                warnings.append(
                    f"Agent '{agent_name}': description should start with 'Use this agent when...'"
                )
                log_warning("description should start with 'Use this agent when...'")

            # Check for angle brackets outside example blocks
            total_checks += 1
            # Remove example blocks first, then check for remaining angle brackets
            desc_without_examples = re.sub(
                r"<example>.*?</example>", "", desc, flags=re.DOTALL
            )
            if "<" in desc_without_examples or ">" in desc_without_examples:
                warnings.append(
                    f"Agent '{agent_name}': description contains angle brackets outside example blocks"
                )
                log_warning(
                    "description contains angle brackets outside example blocks"
                )

        # Check model
        total_checks += 1
        model = fm.get("model", "")
        if not model:
            warnings.append(f"Agent '{agent_name}': Missing model field")
            log_warning("Missing model field")
        elif model not in valid_models:
            warnings.append(
                f"Agent '{agent_name}': Unknown model '{model}' (valid: inherit, sonnet, opus, haiku)"
            )
            log_warning(
                f"Unknown model '{model}' (valid: inherit, sonnet, opus, haiku)"
            )
        else:
            log_success(f"model: {model}")

        # Check color
        total_checks += 1
        color = fm.get("color", "")
        if not color:
            warnings.append(f"Agent '{agent_name}': Missing color field")
            log_warning("Missing color field")
        elif color not in valid_colors:
            warnings.append(
                f"Agent '{agent_name}': Unknown color '{color}' (valid: {', '.join(sorted(valid_colors))})"
            )
            log_warning(
                f"Unknown color '{color}' (valid: {', '.join(sorted(valid_colors))})"
            )
        else:
            log_success(f"color: {color}")

        # Check tools field (informational)
        total_checks += 1
        tools = fm.get("tools", "")
        if tools:
            log_info(f"tools: {tools}")
        else:
            log_info("tools: not specified (agent has access to all tools)")

        # Check permissionMode (per Anthropic docs)
        total_checks += 1
        permission_mode = fm.get("permissionMode", "")
        if permission_mode:
            if permission_mode not in valid_permission_modes:
                errors.append(
                    f"Agent '{agent_name}': Invalid permissionMode '{permission_mode}' (valid: {', '.join(sorted(valid_permission_modes))})"
                )
                log_error(
                    f"Invalid permissionMode '{permission_mode}' (valid: {', '.join(sorted(valid_permission_modes))})"
                )
                agent_valid = False
            else:
                log_success(f"permissionMode: {permission_mode}")

        # Check system prompt
        total_checks += 1
        if body is not None:
            body_stripped = body.strip()
            if not body_stripped:
                errors.append(f"Agent '{agent_name}': Empty system prompt")
                log_error("Empty system prompt")
                agent_valid = False
            else:
                prompt_len = len(body_stripped)
                log_success(f"system prompt: {prompt_len} characters")

                # Check system prompt length
                total_checks += 1
                if prompt_len < 20:
                    errors.append(
                        f"Agent '{agent_name}': System prompt too short (minimum 20 characters)"
                    )
                    log_error(
                        f"System prompt too short ({prompt_len} chars, minimum 20)"
                    )
                    agent_valid = False
                elif prompt_len < 50:
                    warnings.append(f"Agent '{agent_name}': System prompt very short")
                    log_warning(f"System prompt very short ({prompt_len} chars)")
                elif prompt_len > 10000:
                    warnings.append(f"Agent '{agent_name}': System prompt very long")
                    log_warning("System prompt very long (over 10,000 characters)")

                # Check for second person
                total_checks += 1
                if not re.search(r"\b(You are|You will|Your)\b", body_stripped):
                    warnings.append(
                        f"Agent '{agent_name}': System prompt should use second person (You are..., You will...)"
                    )
                    log_warning(
                        "System prompt should use second person (You are..., You will...)"
                    )

                # Check for structure keywords
                total_checks += 1
                if not re.search(
                    r"\b(responsibilities|process|steps)\b",
                    body_stripped,
                    re.IGNORECASE,
                ):
                    log_info("Consider adding clear responsibilities or process steps")

                # Check for output format
                total_checks += 1
                if not re.search(r"\boutput\b", body_stripped, re.IGNORECASE):
                    log_info("Consider defining output format expectations")

        if agent_valid:
            agents_valid += 1

    print()
    log_success(
        f"Agents: {agents_found} found, {agents_valid} valid, {total_checks} checks performed"
    )
    return ValidationResult(errors, warnings, info)


def validate_references_toc(
    content: str, refs_dir: Path, component_name: str
) -> ValidationResult:
    """Validate that reference files are linked in the main content (TOC discoverability).

    Args:
        content: Main file content (skill body or agent description)
        refs_dir: Path to references/ directory
        component_name: Name of skill/agent for error messages

    Returns:
        ValidationResult with any issues found
    """
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    if not refs_dir.exists():
        return ValidationResult(errors, warnings, info)

    ref_files = list(refs_dir.rglob("*.md"))
    if not ref_files:
        return ValidationResult(errors, warnings, info)

    # Check each reference file is linked somewhere in the content
    unlinked_refs = []
    for ref_file in ref_files:
        ref_name = ref_file.name
        ref_stem = ref_file.stem

        # Check for various link patterns:
        # - [text](references/file.md)
        # - references/file.md
        # - file.md (just filename)
        # - file (just stem)
        patterns_to_check = [
            f"references/{ref_name}",
            f"references/{ref_stem}",
            ref_name,
            ref_stem.replace("-", " "),  # "my-reference" -> "my reference"
        ]

        is_linked = False
        for pattern in patterns_to_check:
            if pattern.lower() in content.lower():
                is_linked = True
                break

        if not is_linked:
            unlinked_refs.append(ref_name)

    if unlinked_refs:
        for ref in unlinked_refs:
            warnings.append(
                f"{component_name}: Reference file '{ref}' not linked in main content (poor discoverability)"
            )
            log_warning(f"Reference '{ref}' not linked in main content")

    linked_count = len(ref_files) - len(unlinked_refs)
    if linked_count > 0:
        log_success(f"{linked_count}/{len(ref_files)} reference files are linked")

    return ValidationResult(errors, warnings, info)


def validate_web_urls(
    content: str, component_name: str, check_reachable: bool = False
) -> ValidationResult:
    """Validate web URLs found in content.

    Args:
        content: Content to scan for URLs
        component_name: Name of component for error messages
        check_reachable: If True, actually check if URLs are reachable (slower)

    Returns:
        ValidationResult with any issues found
    """
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    # Find all URLs in content (http:// and https://)
    url_pattern = r'https?://[^\s<>\[\]()"\'\`]+'
    urls = re.findall(url_pattern, content)

    if not urls:
        return ValidationResult(errors, warnings, info)

    # Remove duplicates while preserving order
    seen = set()
    unique_urls = []
    for url in urls:
        # Clean trailing punctuation that might have been captured
        url = url.rstrip(".,;:!?)")
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    info.append(f"{component_name}: {len(unique_urls)} unique URL(s) found")

    if not check_reachable:
        return ValidationResult(errors, warnings, info)

    # Check if URLs are reachable (only if explicitly requested)
    unreachable = []
    for url in unique_urls[:10]:  # Limit to first 10 to avoid long validation times
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Claude-Code-Plugin-Validator/1.0"},
                method="HEAD",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status >= 400:
                    unreachable.append((url, f"HTTP {response.status}"))
        except urllib.error.HTTPError as e:
            if e.code == 405:  # Method not allowed, try GET
                try:
                    req = urllib.request.Request(
                        url, headers={"User-Agent": "Claude-Code-Plugin-Validator/1.0"}
                    )
                    with urllib.request.urlopen(req, timeout=5) as response:
                        pass  # URL is reachable
                except Exception:
                    unreachable.append((url, f"HTTP {e.code}"))
            else:
                unreachable.append((url, f"HTTP {e.code}"))
        except urllib.error.URLError as e:
            unreachable.append((url, str(e.reason)[:50]))
        except Exception as e:
            unreachable.append((url, str(e)[:50]))

    if unreachable:
        for url, reason in unreachable:
            warnings.append(
                f"{component_name}: URL may be unreachable: {url[:60]}... ({reason})"
            )
            log_warning(f"URL may be unreachable: {url[:40]}...")

    reachable_count = len(unique_urls[:10]) - len(unreachable)
    if reachable_count > 0 and check_reachable:
        log_success(f"{reachable_count}/{min(10, len(unique_urls))} URLs are reachable")

    return ValidationResult(errors, warnings, info)


def validate_skills(plugin_path: Path) -> ValidationResult:
    """Validate skills with enhanced checks from validate-skill.py."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []
    skills_found = 0
    skills_valid = 0

    log_section("Step 5: Skills Validation")

    skills_dir = plugin_path / "skills"
    if not skills_dir.exists():
        log_info("No skills/ directory")
        return ValidationResult(errors, warnings, info)

    for skill_file in skills_dir.rglob("SKILL.md"):
        skills_found += 1
        skill_name = skill_file.parent.name
        skill_valid = True

        print(f"\n  {CYAN}Checking skill: {skill_name}{NC}")

        content = skill_file.read_text()
        fm, body = parse_yaml_frontmatter(content)

        if fm is None:
            errors.append(f"Skill '{skill_name}': {body}")
            log_error(f"Skill '{skill_name}': {body}")
            continue

        # Check required field: name (per Anthropic docs: max 64 characters)
        if "name" not in fm:
            errors.append(f"Skill '{skill_name}': Missing name field")
            log_error("Missing name field")
            skill_valid = False
        else:
            name_value = fm["name"]
            log_success(f"name: {name_value}")

            # Validate name format (hyphen-case)
            if not re.match(r"^[a-z0-9-]+$", name_value):
                errors.append(
                    f"Skill '{skill_name}': name should be hyphen-case (lowercase letters, digits, and hyphens only)"
                )
                log_error(
                    "name should be hyphen-case (lowercase letters, digits, and hyphens only)"
                )
                skill_valid = False

            # Check name cannot start/end with hyphen or have consecutive hyphens
            if (
                name_value.startswith("-")
                or name_value.endswith("-")
                or "--" in name_value
            ):
                errors.append(
                    f"Skill '{skill_name}': name cannot start/end with hyphen or contain consecutive hyphens"
                )
                log_error(
                    "name cannot start/end with hyphen or contain consecutive hyphens"
                )
                skill_valid = False

            # Per Anthropic docs: max 64 characters for name
            if len(name_value) > 64:
                errors.append(
                    f"Skill '{skill_name}': name too long (max 64 characters, got {len(name_value)})"
                )
                log_error(f"name too long (max 64 characters, got {len(name_value)})")
                skill_valid = False

        # Check required field: description (per Anthropic docs: max 1024 characters)
        if "description" not in fm:
            errors.append(f"Skill '{skill_name}': Missing description field")
            log_error("Missing description field")
            skill_valid = False
        else:
            desc = fm["description"]
            log_success(f"description: {len(desc)} characters")

            # Per Anthropic docs: max 1024 characters for description
            if len(desc) > 1024:
                errors.append(
                    f"Skill '{skill_name}': description too long (max 1024 characters, got {len(desc)})"
                )
                log_error(
                    f"description too long (max 1024 characters, got {len(desc)})"
                )
                skill_valid = False

            # Check for angle brackets in description
            if "<" in desc or ">" in desc:
                errors.append(
                    f"Skill '{skill_name}': description cannot contain angle brackets (< or >)"
                )
                log_error("description cannot contain angle brackets (< or >)")
                skill_valid = False

        # Check for references directory
        refs_dir = skill_file.parent / "references"
        if refs_dir.exists():
            ref_count = len(list(refs_dir.iterdir()))
            info.append(f"Skill '{skill_name}': {ref_count} reference files")
            log_info(f"references/ directory: {ref_count} files")

            # Validate reference TOC discoverability
            full_content = content  # Use full SKILL.md content for link checking
            if body:
                full_content = content  # Include both frontmatter description and body
            toc_result = validate_references_toc(
                full_content, refs_dir, f"Skill '{skill_name}'"
            )
            warnings.extend(toc_result.warnings)
            errors.extend(toc_result.errors)
            info.extend(toc_result.info)

        # Validate web URLs in skill content
        url_result = validate_web_urls(
            content, f"Skill '{skill_name}'", CHECK_URLS_REACHABLE
        )
        warnings.extend(url_result.warnings)
        errors.extend(url_result.errors)
        info.extend(url_result.info)

        if skill_valid:
            skills_valid += 1

    print()
    log_success(f"Skills: {skills_found} found, {skills_valid} valid")
    return ValidationResult(errors, warnings, info)


def validate_hooks(plugin_path: Path) -> ValidationResult:
    """Validate hooks with comprehensive checks from validate-hook-schema.sh and hook-linter.sh."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    log_section("Step 6: Hooks Validation")

    hooks_file = plugin_path / "hooks" / "hooks.json"
    if not hooks_file.exists():
        log_info("No hooks/hooks.json")
        return ValidationResult(errors, warnings, info)

    try:
        with open(hooks_file, "r") as f:
            hooks_data = json.load(f)
        log_success("hooks.json: Valid JSON")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON syntax in hooks.json: {e}")
        log_error(f"Invalid JSON syntax in hooks.json: {e}")
        return ValidationResult(errors, warnings, info)

    # Valid hook events per Anthropic docs
    valid_events = {
        "PreToolUse",
        "PermissionRequest",
        "PostToolUse",
        "Stop",
        "SubagentStop",
        "SessionStart",
        "SessionEnd",
        "UserPromptSubmit",
        "PreCompact",
        "Notification",
    }
    valid_types = {"command", "prompt"}

    # Claude Code format: hooks is a dict where keys are event names
    hooks_dict = hooks_data.get("hooks", {})

    # Handle both old format (list) and new format (dict)
    if isinstance(hooks_dict, list):
        # Legacy format: list of {event, type, ...} objects
        log_success(f"hooks.json: {len(hooks_dict)} hooks defined (legacy format)")
        for i, hook in enumerate(hooks_dict):
            event = hook.get("event", "")
            hook_type = hook.get("type", "")

            if not event:
                errors.append(f"Hook {i}: Missing event")
                log_error(f"Hook {i}: Missing event")
            elif event not in valid_events:
                warnings.append(
                    f"Hook {i}: Unknown event '{event}' (valid: {', '.join(sorted(valid_events))})"
                )
                log_warning(
                    f"Hook {i}: Unknown event '{event}' (valid: {', '.join(sorted(valid_events))})"
                )

            if not hook_type:
                errors.append(f"Hook {i}: Missing type")
                log_error(f"Hook {i}: Missing type")
            elif hook_type not in valid_types:
                warnings.append(
                    f"Hook {i}: Unknown type '{hook_type}' (valid: command, prompt)"
                )
                log_warning(
                    f"Hook {i}: Unknown type '{hook_type}' (valid: command, prompt)"
                )

    elif isinstance(hooks_dict, dict):
        # Claude Code format: dict where keys are event names
        total_hooks = 0
        for event_name, hook_groups in hooks_dict.items():
            # Validate event name
            if event_name not in valid_events:
                warnings.append(
                    f"Unknown event type: '{event_name}' (valid: {', '.join(sorted(valid_events))})"
                )
                log_warning(
                    f"Unknown event type: '{event_name}' (valid: {', '.join(sorted(valid_events))})"
                )

            if not isinstance(hook_groups, list):
                errors.append(f"Event '{event_name}': Expected list of hook groups")
                log_error(f"Event '{event_name}': Expected list of hook groups")
                continue

            for group_idx, hook_group in enumerate(hook_groups):
                if not isinstance(hook_group, dict):
                    errors.append(
                        f"Event '{event_name}' group {group_idx}: Expected object"
                    )
                    log_error(
                        f"Event '{event_name}' group {group_idx}: Expected object"
                    )
                    continue

                # Check for matcher (optional, used in PreToolUse/PostToolUse)
                matcher = hook_group.get("matcher")
                if event_name in {"PreToolUse", "PostToolUse"}:
                    if not matcher:
                        warnings.append(
                            f"Event '{event_name}' group {group_idx}: Missing matcher (should specify which tools this hook applies to)"
                        )
                        log_warning(
                            f"Event '{event_name}' group {group_idx}: Missing matcher"
                        )
                elif matcher:
                    warnings.append(
                        f"Event '{event_name}': matcher only valid for PreToolUse/PostToolUse"
                    )
                    log_warning(
                        f"Event '{event_name}': matcher only valid for PreToolUse/PostToolUse"
                    )

                # Check for hooks array
                if "hooks" not in hook_group:
                    errors.append(
                        f"Event '{event_name}' group {group_idx}: Missing 'hooks' array"
                    )
                    log_error(
                        f"Event '{event_name}' group {group_idx}: Missing 'hooks' array"
                    )
                    continue

                # Validate individual hooks in the group
                inner_hooks = hook_group.get("hooks", [])
                if not isinstance(inner_hooks, list):
                    errors.append(
                        f"Event '{event_name}' group {group_idx}: 'hooks' should be a list"
                    )
                    log_error(
                        f"Event '{event_name}' group {group_idx}: 'hooks' should be a list"
                    )
                    continue

                for hook_idx, hook in enumerate(inner_hooks):
                    total_hooks += 1
                    hook_type = hook.get("type", "")

                    if not hook_type:
                        errors.append(
                            f"Event '{event_name}' hook {hook_idx}: Missing type"
                        )
                        log_error(f"Event '{event_name}' hook {hook_idx}: Missing type")
                    elif hook_type not in valid_types:
                        warnings.append(
                            f"Event '{event_name}' hook {hook_idx}: Unknown type '{hook_type}' (valid: command, prompt)"
                        )
                        log_warning(
                            f"Event '{event_name}' hook {hook_idx}: Unknown type '{hook_type}'"
                        )
                    elif hook_type == "command":
                        # Validate command hook
                        if not hook.get("command"):
                            errors.append(
                                f"Event '{event_name}' hook {hook_idx}: Command hook missing 'command' field"
                            )
                            log_error(
                                f"Event '{event_name}' hook {hook_idx}: Command hook missing 'command' field"
                            )
                        else:
                            command = hook["command"]
                            # Check for hardcoded paths
                            if (
                                command.startswith("/")
                                and "${CLAUDE_PLUGIN_ROOT}" not in command
                            ):
                                warnings.append(
                                    f"Event '{event_name}' hook {hook_idx}: Hardcoded absolute path. Use ${{CLAUDE_PLUGIN_ROOT}}"
                                )
                                log_warning(
                                    f"Event '{event_name}' hook {hook_idx}: Hardcoded path (use ${{CLAUDE_PLUGIN_ROOT}})"
                                )

                            # Check if script exists (if it's a file reference)
                            script_match = re.search(
                                r"\$\{CLAUDE_PLUGIN_ROOT\}/(.+?)(?:\s|$)", command
                            )
                            if script_match:
                                script_rel_path = script_match.group(1)
                                script_path = plugin_path / script_rel_path
                                if not script_path.exists():
                                    errors.append(
                                        f"Event '{event_name}' hook {hook_idx}: Script not found: {script_rel_path}"
                                    )
                                    log_error(
                                        f"Event '{event_name}' hook {hook_idx}: Script not found: {script_rel_path}"
                                    )
                                elif not os.access(script_path, os.X_OK):
                                    warnings.append(
                                        f"Event '{event_name}' hook {hook_idx}: Script not executable: {script_rel_path}"
                                    )
                                    log_warning(
                                        f"Event '{event_name}' hook {hook_idx}: Script not executable (chmod +x)"
                                    )

                        # Check timeout
                        timeout = hook.get("timeout")
                        if timeout is not None:
                            if not isinstance(timeout, (int, float)):
                                errors.append(
                                    f"Event '{event_name}' hook {hook_idx}: Timeout must be a number"
                                )
                                log_error(
                                    f"Event '{event_name}' hook {hook_idx}: Timeout must be a number"
                                )
                            elif timeout > 30000:
                                warnings.append(
                                    f"Event '{event_name}' hook {hook_idx}: Timeout {timeout}ms is very high (max 30000ms)"
                                )
                                log_warning(
                                    f"Event '{event_name}' hook {hook_idx}: Timeout {timeout}ms very high"
                                )
                            elif timeout < 0:
                                errors.append(
                                    f"Event '{event_name}' hook {hook_idx}: Timeout must be >= 0"
                                )
                                log_error(
                                    f"Event '{event_name}' hook {hook_idx}: Timeout must be >= 0"
                                )

                    elif hook_type == "prompt":
                        # Validate prompt hook
                        if not hook.get("prompt"):
                            errors.append(
                                f"Event '{event_name}' hook {hook_idx}: Prompt hook missing 'prompt' field"
                            )
                            log_error(
                                f"Event '{event_name}' hook {hook_idx}: Prompt hook missing 'prompt' field"
                            )

        log_success(f"hooks.json: {len(hooks_dict)} events, {total_hooks} total hooks")

        # Now lint any referenced scripts
        scripts_to_lint = []
        for event_name, hook_groups in hooks_dict.items():
            if isinstance(hook_groups, list):
                for hook_group in hook_groups:
                    if isinstance(hook_group, dict):
                        inner_hooks = hook_group.get("hooks", [])
                        for hook in inner_hooks:
                            if hook.get("type") == "command":
                                command = hook.get("command", "")
                                script_match = re.search(
                                    r"\$\{CLAUDE_PLUGIN_ROOT\}/(.+?)(?:\s|$)", command
                                )
                                if script_match:
                                    script_rel_path = script_match.group(1)
                                    script_path = plugin_path / script_rel_path
                                    if (
                                        script_path.exists()
                                        and script_path not in scripts_to_lint
                                    ):
                                        scripts_to_lint.append(script_path)

        # Lint hook scripts
        if scripts_to_lint:
            print(f"\n  {CYAN}Linting {len(scripts_to_lint)} hook script(s)...{NC}")
            for script_path in scripts_to_lint:
                lint_result = lint_hook_script(script_path, plugin_path)
                errors.extend(lint_result.errors)
                warnings.extend(lint_result.warnings)
                info.extend(lint_result.info)

    else:
        errors.append("hooks.json: 'hooks' should be an object or array")
        log_error("hooks.json: 'hooks' should be an object or array")

    return ValidationResult(errors, warnings, info)


def lint_script(
    script_path: Path, plugin_path: Path, is_hook: bool = False
) -> ValidationResult:
    """Lint a shell script for common issues and syntax errors.

    Args:
        script_path: Path to the script
        plugin_path: Plugin root for relative path display
        is_hook: If True, apply hook-specific checks (exit codes)
    """
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    script_name = script_path.relative_to(plugin_path)

    try:
        content = script_path.read_text()
        lines = content.split("\n")

        # Check shebang
        if lines and not lines[0].startswith("#!"):
            errors.append(f"Script '{script_name}': Missing shebang (e.g., #!/usr/bin/env python3 or #!/bin/bash)")
            log_error(f"Script '{script_name}': Missing shebang")
        else:
            shebang = lines[0]
            # Detect script type from shebang
            is_bash = "bash" in shebang or "sh" in shebang
            is_python = "python" in shebang
            is_node = "node" in shebang

            # Bash syntax check using bash -n
            if is_bash:
                try:
                    result = subprocess.run(
                        ["bash", "-n", str(script_path)],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode != 0:
                        error_msg = result.stderr.strip() or "Syntax error"
                        errors.append(
                            f"Script '{script_name}': Bash syntax error: {error_msg}"
                        )
                        log_error(f"Script '{script_name}': Bash syntax error")
                    else:
                        log_success(f"Script '{script_name}': Bash syntax OK")
                except subprocess.TimeoutExpired:
                    warnings.append(f"Script '{script_name}': Syntax check timed out")
                    log_warning(f"Script '{script_name}': Syntax check timed out")
                except FileNotFoundError:
                    info.append(
                        f"Script '{script_name}': Could not run bash -n (bash not found)"
                    )

            # Python syntax check using python -m py_compile
            elif is_python:
                try:
                    result = subprocess.run(
                        ["python3", "-m", "py_compile", str(script_path)],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode != 0:
                        error_msg = result.stderr.strip() or "Syntax error"
                        errors.append(
                            f"Script '{script_name}': Python syntax error: {error_msg}"
                        )
                        log_error(f"Script '{script_name}': Python syntax error")
                    else:
                        log_success(f"Script '{script_name}': Python syntax OK")
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

            # JavaScript/TypeScript syntax and lint check
            elif is_node or script_path.suffix in {".js", ".ts", ".mjs", ".cjs"}:
                # Try ESLint first (if available)
                eslint_checked = False
                try:
                    result = subprocess.run(
                        [
                            "npx",
                            "eslint",
                            "--no-error-on-unmatched-pattern",
                            "--format",
                            "compact",
                            str(script_path),
                        ],
                        capture_output=True,
                        text=True,
                        timeout=30,
                        cwd=plugin_path,
                    )
                    eslint_checked = True
                    if result.returncode != 0 and (
                        result.stdout.strip() or result.stderr.strip()
                    ):
                        output = result.stdout + result.stderr
                        # Count actual ESLint errors vs warnings in output
                        # ESLint compact format: "file: line:col - error message"
                        # Or standard format contains "error" and "warning" labels
                        error_count = output.lower().count(" error")
                        warning_count = output.lower().count(" warning")

                        if error_count > 0:
                            # ESLint found actual errors - this should fail validation
                            errors.append(
                                f"Script '{script_name}': ESLint found {error_count} error(s)"
                            )
                            log_error(
                                f"Script '{script_name}': ESLint found {error_count} error(s)"
                            )
                        elif warning_count > 0:
                            # Only warnings - don't fail validation
                            warnings.append(
                                f"Script '{script_name}': ESLint found {warning_count} warning(s)"
                            )
                            log_warning(
                                f"Script '{script_name}': ESLint found {warning_count} warning(s)"
                            )
                        else:
                            # Couldn't parse output, treat as error to be safe
                            errors.append(
                                f"Script '{script_name}': ESLint failed (exit code {result.returncode})"
                            )
                            log_error(f"Script '{script_name}': ESLint failed")
                    elif result.returncode == 0:
                        log_success(f"Script '{script_name}': ESLint OK")
                except (subprocess.TimeoutExpired, FileNotFoundError):
                    pass

                # For TypeScript, also check with tsc
                if script_path.suffix in {".ts", ".tsx"}:
                    try:
                        result = subprocess.run(
                            [
                                "npx",
                                "tsc",
                                "--noEmit",
                                "--allowJs",
                                "--checkJs",
                                str(script_path),
                            ],
                            capture_output=True,
                            text=True,
                            timeout=30,
                            cwd=plugin_path,
                        )
                        if result.returncode != 0:
                            error_msg = (
                                result.stderr.strip()
                                or result.stdout.strip()
                                or "Type error"
                            )
                            # Only first line of error
                            first_line = (
                                error_msg.split("\n")[0] if error_msg else "Type error"
                            )
                            errors.append(
                                f"Script '{script_name}': TypeScript error: {first_line}"
                            )
                            log_error(f"Script '{script_name}': TypeScript error")
                        else:
                            log_success(f"Script '{script_name}': TypeScript OK")
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        if not eslint_checked:
                            info.append(
                                f"Script '{script_name}': Could not lint (eslint/tsc not found)"
                            )

                # Fallback: basic Node.js syntax check
                elif not eslint_checked and script_path.suffix in {
                    ".js",
                    ".mjs",
                    ".cjs",
                }:
                    try:
                        result = subprocess.run(
                            ["node", "--check", str(script_path)],
                            capture_output=True,
                            text=True,
                            timeout=10,
                        )
                        if result.returncode != 0:
                            error_msg = result.stderr.strip() or "Syntax error"
                            errors.append(
                                f"Script '{script_name}': Node.js syntax error: {error_msg}"
                            )
                            log_error(f"Script '{script_name}': Node.js syntax error")
                        else:
                            log_success(f"Script '{script_name}': Node.js syntax OK")
                    except (subprocess.TimeoutExpired, FileNotFoundError):
                        pass

        # Check for set -euo pipefail (bash scripts only)
        if "bash" in (lines[0] if lines else "") or "sh" in (lines[0] if lines else ""):
            if "set -euo pipefail" not in content and "set -e" not in content:
                warnings.append(
                    f"Script '{script_name}': Missing 'set -e' or 'set -euo pipefail' (recommended)"
                )
                log_warning(
                    f"Script '{script_name}': Missing 'set -e' or 'set -euo pipefail'"
                )

        # Check for hardcoded paths
        if re.search(r"^[^#]*/home/|^[^#]*/Users/", content, re.MULTILINE):
            warnings.append(
                f"Script '{script_name}': Hardcoded user paths (use $CLAUDE_PLUGIN_ROOT)"
            )
            log_warning(f"Script '{script_name}': Hardcoded user paths")

        # Hook-specific checks
        if is_hook:
            # Check for exit codes (hooks should use exit 0 to approve, exit 2 to block)
            if "exit 0" not in content and "exit 2" not in content:
                warnings.append(
                    f"Script '{script_name}': No explicit exit codes (hooks should exit 0 or 2)"
                )
                log_warning(f"Script '{script_name}': No explicit exit codes")

        # Check for common dangerous patterns
        dangerous_patterns = [
            (r"\brm\s+-rf\s+/[^$]", "Dangerous rm -rf with absolute path"),
            (r"\beval\s+\$", "Potentially dangerous eval of variable"),
            (r">\s*/dev/null\s+2>&1\s*$", "Silencing all output (may hide errors)"),
        ]
        for pattern, desc in dangerous_patterns:
            if re.search(pattern, content):
                warnings.append(f"Script '{script_name}': {desc}")
                log_warning(f"Script '{script_name}': {desc}")

    except Exception as e:
        errors.append(f"Script '{script_name}': Error reading file: {e}")
        log_error(f"Script '{script_name}': Error reading: {e}")

    return ValidationResult(errors, warnings, info)


def lint_hook_script(script_path: Path, plugin_path: Path) -> ValidationResult:
    """Lint a hook script for common issues (from hook-linter.sh)."""
    return lint_script(script_path, plugin_path, is_hook=True)


def validate_settings_files(plugin_path: Path) -> ValidationResult:
    """Validate .local.md settings files (from validate-settings.sh)."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    log_section("Step 7: Settings Files Validation")

    # Look for .local.md files
    settings_files = list(plugin_path.glob(".claude/*.local.md"))

    if not settings_files:
        log_info("No .local.md settings files found")
        return ValidationResult(errors, warnings, info)

    for settings_file in settings_files:
        settings_name = settings_file.name
        print(f"\n  {CYAN}Checking settings: {settings_name}{NC}")

        try:
            content = settings_file.read_text()
            lines = content.split("\n")

            # Check for frontmatter markers
            marker_count = sum(1 for line in lines if line.strip() == "---")
            if marker_count < 2:
                errors.append(
                    f"Settings '{settings_name}': Invalid frontmatter (found {marker_count} '---' markers, need at least 2)"
                )
                log_error(
                    f"Invalid frontmatter (found {marker_count} '---' markers, need 2)"
                )
                continue

            # Check first marker is on line 1
            if not lines or lines[0].strip() != "---":
                errors.append(
                    f"Settings '{settings_name}': First '---' marker must be on line 1"
                )
                log_error("First '---' marker must be on line 1")
                continue

            log_success("Frontmatter markers present")

            # Extract frontmatter
            fm, body = parse_yaml_frontmatter(content)

            if fm is None:
                errors.append(f"Settings '{settings_name}': {body}")
                log_error(f"{body}")
                continue

            # Check frontmatter not empty
            if not fm:
                errors.append(f"Settings '{settings_name}': Empty frontmatter")
                log_error("Empty frontmatter")
                continue

            log_success(f"Frontmatter not empty ({len(fm)} fields)")

            # Validate common boolean fields
            for field in ["enabled", "strict_mode"]:
                if field in fm:
                    value = fm[field].lower()
                    if value not in {"true", "false"}:
                        warnings.append(
                            f"Settings '{settings_name}': Field '{field}' should be boolean (true/false), got: {fm[field]}"
                        )
                        log_warning(
                            f"Field '{field}' should be boolean (true/false), got: {fm[field]}"
                        )

            # Check body exists
            if body and body.strip():
                body_lines = len(body.strip().split("\n"))
                log_success(f"Markdown body present ({body_lines} lines)")
            else:
                log_info("No markdown body (frontmatter only)")

        except Exception as e:
            errors.append(f"Settings '{settings_name}': Error reading file: {e}")
            log_error(f"Error reading file: {e}")

    return ValidationResult(errors, warnings, info)


def validate_scripts(plugin_path: Path) -> ValidationResult:
    """Validate all scripts in the plugin (scripts/ directory)."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    log_section("Step 8: Scripts Validation")

    scripts_dir = plugin_path / "scripts"
    if not scripts_dir.exists():
        log_info("No scripts/ directory")
        return ValidationResult(errors, warnings, info)

    # Find all script files (by extension or executable bit)
    script_extensions = {".sh", ".bash", ".py", ".js", ".ts"}
    scripts = []
    for f in scripts_dir.rglob("*"):
        if f.is_file():
            # Include by extension or executable bit
            if f.suffix in script_extensions or os.access(f, os.X_OK):
                scripts.append(f)

    if not scripts:
        log_info("No scripts found in scripts/ directory")
        return ValidationResult(errors, warnings, info)

    log_success(f"Found {len(scripts)} script(s) to validate")

    scripts_valid = 0
    for script_path in scripts:
        result = lint_script(script_path, plugin_path, is_hook=False)
        errors.extend(result.errors)
        warnings.extend(result.warnings)
        info.extend(result.info)
        if not result.errors:
            scripts_valid += 1

    print()
    log_success(f"Scripts: {len(scripts)} found, {scripts_valid} passed validation")

    return ValidationResult(errors, warnings, info)


def validate_mcp_config(plugin_path: Path) -> ValidationResult:
    """Validate MCP server configuration (.mcp.json)."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    log_section("Step 9: MCP Configuration")

    mcp_file = plugin_path / ".mcp.json"
    if not mcp_file.exists():
        log_info("No .mcp.json file (no MCP servers)")
        return ValidationResult(errors, warnings, info)

    try:
        with open(mcp_file, "r") as f:
            mcp_data = json.load(f)
        log_success(".mcp.json: Valid JSON")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON syntax in .mcp.json: {e}")
        log_error(f"Invalid JSON syntax in .mcp.json: {e}")
        return ValidationResult(errors, warnings, info)

    # Validate mcpServers structure
    servers = mcp_data.get("mcpServers", {})
    if not servers:
        warnings.append(".mcp.json: No mcpServers defined")
        log_warning(".mcp.json: No mcpServers defined")
        return ValidationResult(errors, warnings, info)

    log_success(f".mcp.json: {len(servers)} server(s) defined")

    for server_name, server_config in servers.items():
        print(f"\n  {CYAN}Checking MCP server: {server_name}{NC}")

        if not isinstance(server_config, dict):
            errors.append(f"MCP server '{server_name}': Config should be an object")
            log_error("Config should be an object")
            continue

        # Check for command
        command = server_config.get("command")
        if not command:
            errors.append(f"MCP server '{server_name}': Missing 'command' field")
            log_error("Missing 'command' field")
        else:
            log_success(f"command: {command}")

        # Check for args
        args = server_config.get("args", [])
        if not isinstance(args, list):
            errors.append(f"MCP server '{server_name}': 'args' should be a list")
            log_error("'args' should be a list")
        else:
            # Check if any args reference plugin root
            uses_plugin_root = any("${CLAUDE_PLUGIN_ROOT}" in str(arg) for arg in args)
            if args and not uses_plugin_root:
                warnings.append(
                    f"MCP server '{server_name}': Consider using ${{CLAUDE_PLUGIN_ROOT}} for portable paths"
                )
                log_warning("Consider using ${CLAUDE_PLUGIN_ROOT} for portable paths")
            elif args:
                log_success(
                    f"args: {len(args)} argument(s), uses ${{CLAUDE_PLUGIN_ROOT}}"
                )

            # Check if referenced files exist
            for arg in args:
                if "${CLAUDE_PLUGIN_ROOT}" in str(arg):
                    rel_path = str(arg).replace("${CLAUDE_PLUGIN_ROOT}/", "")
                    full_path = plugin_path / rel_path
                    if not full_path.exists():
                        errors.append(
                            f"MCP server '{server_name}': Referenced file not found: {rel_path}"
                        )
                        log_error(f"Referenced file not found: {rel_path}")

        # Check for env
        env = server_config.get("env", {})
        if isinstance(env, dict) and env:
            # Check for hardcoded secrets
            for key, value in env.items():
                if isinstance(value, str) and not value.startswith("${"):
                    if any(
                        secret_word in key.lower()
                        for secret_word in ["key", "secret", "token", "password"]
                    ):
                        warnings.append(
                            f"MCP server '{server_name}': Possible hardcoded secret in env.{key}"
                        )
                        log_warning(f"Possible hardcoded secret in env.{key}")

    return ValidationResult(errors, warnings, info)


def validate_security(plugin_path: Path) -> ValidationResult:
    """Basic security checks."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    log_section("Step 10: Security Checks")

    # Check for obvious credential patterns
    credential_patterns = [
        r'password\s*=\s*["\'][^"\']+["\']',
        r'api[_-]?key\s*=\s*["\'][^"\']+["\']',
        r'secret\s*=\s*["\'][^"\']+["\']',
        r'token\s*=\s*["\'][^"\']+["\']',
    ]

    suspicious_files = []
    for file in plugin_path.rglob("*"):
        if not file.is_file():
            continue
        if file.suffix in [".md", ".json", ".sh", ".py", ".js", ".ts"]:
            try:
                content = file.read_text()
                for pattern in credential_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        suspicious_files.append(str(file.relative_to(plugin_path)))
                        break
            except Exception:
                pass

    if suspicious_files:
        for f in suspicious_files:
            warnings.append(f"Possible credentials in: {f}")
            log_warning(f"Possible credentials in: {f}")
    else:
        log_success("No obvious credential patterns found")

    return ValidationResult(errors, warnings, info)


def validate_file_organization(plugin_path: Path) -> ValidationResult:
    """Check file organization."""
    errors: list[str] = []
    warnings: list[str] = []
    info: list[str] = []

    log_section("Step 11: File Organization")

    # Check README
    readme = plugin_path / "README.md"
    if readme.exists():
        size = readme.stat().st_size
        log_success(f"README.md: Present ({size} bytes)")
    else:
        warnings.append("README.md: Missing")
        log_warning("README.md: Missing (recommended)")

    # Check LICENSE
    license_file = plugin_path / "LICENSE"
    if license_file.exists():
        log_success("LICENSE: Present")
    else:
        warnings.append("LICENSE: Missing")
        log_warning("LICENSE: Missing (recommended for distribution)")

    # Check .gitignore
    gitignore = plugin_path / ".gitignore"
    if gitignore.exists():
        log_success(".gitignore: Present")
    else:
        info.append(".gitignore: not present")
        log_info(".gitignore: not present")

    # Check for unwanted files
    unwanted = [".DS_Store", "node_modules", "__pycache__", ".env"]
    found_unwanted = []
    for pattern in unwanted:
        matches = list(plugin_path.rglob(pattern))
        if matches:
            found_unwanted.extend(matches)

    if found_unwanted:
        warnings.append(f"Unwanted files found: {len(found_unwanted)}")
        log_warning(
            f"Unwanted files found (consider .gitignore): {[str(f.relative_to(plugin_path)) for f in found_unwanted[:3]]}"
        )

    return ValidationResult(errors, warnings, info)


def main() -> None:
    # Parse command line arguments
    check_urls = False
    plugin_path_arg: str | None = None

    args = sys.argv[1:]
    for arg in args:
        if arg in ("--check-urls", "-u"):
            check_urls = True
        elif arg in ("--help", "-h"):
            plugin_path_arg = None
            break
        elif not arg.startswith("-"):
            plugin_path_arg = arg

    if not plugin_path_arg:
        print(
            f"{CYAN}Plugin Validator - Comprehensive validation for Claude Code plugins{NC}"
        )
        print()
        print(f"Usage: {sys.argv[0]} [options] <path/to/plugin>")
        print()
        print("Options:")
        print("  --check-urls, -u  Check if web URLs in content are reachable (slower)")
        print("  --help, -h        Show this help message")
        print()
        print("Validates (11 steps):")
        print("  1. Plugin structure")
        print("  2. Manifest (plugin.json)")
        print("  3. Commands")
        print("  4. Agents (skips references/ subdirectory)")
        print("  5. Skills (validates reference TOC discoverability)")
        print("  6. Hooks (schema + script linting)")
        print("  7. Settings files (.local.md)")
        print("  8. Scripts (syntax checking for .sh, .py, .js, .ts)")
        print("  9. MCP configuration")
        print("  10. Security")
        print("  11. File organization")
        sys.exit(0)

    plugin_path = Path(plugin_path_arg).resolve()

    # Set global flag for URL checking
    global CHECK_URLS_REACHABLE
    CHECK_URLS_REACHABLE = check_urls

    print(f"\n{CYAN}{'=' * 70}{NC}")
    print(f"{CYAN}Plugin Validation: {plugin_path.name}{NC}")
    if check_urls:
        print(f"{CYAN}URL reachability checking: ENABLED{NC}")
    print(f"{CYAN}{'=' * 70}{NC}")

    # Track results per category for summary table
    category_results: dict[str, dict[str, Any]] = {}

    def run_validation(
        name: str, validator: Callable[[Path], ValidationResult]
    ) -> ValidationResult:
        """Run a validation and track results."""
        result = validator(plugin_path)
        category_results[name] = {
            "errors": len(result.errors),
            "warnings": len(result.warnings),
            "info": len(result.info),
            "status": "FAIL"
            if result.errors
            else ("WARN" if result.warnings else "PASS"),
        }
        return result

    all_errors: list[str] = []
    all_warnings: list[str] = []
    all_info: list[str] = []

    # Step 1: Plugin Structure
    result = run_validation("Structure", validate_plugin_structure)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    if result.errors:
        # Fatal error, can't continue
        print(f"\n{RED}{'=' * 70}{NC}")
        print(f"{RED}VALIDATION FAILED - Cannot continue{NC}")
        print(f"{RED}{'=' * 70}{NC}")
        sys.exit(1)

    # Step 2: Manifest
    manifest_result, plugin_name = validate_manifest(plugin_path)
    category_results["Manifest"] = {
        "errors": len(manifest_result.errors),
        "warnings": len(manifest_result.warnings),
        "info": len(manifest_result.info),
        "status": "FAIL"
        if manifest_result.errors
        else ("WARN" if manifest_result.warnings else "PASS"),
    }
    all_errors.extend(manifest_result.errors)
    all_warnings.extend(manifest_result.warnings)
    all_info.extend(manifest_result.info)

    # Steps 3-11
    result = run_validation("Commands", validate_commands)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = run_validation("Agents", validate_agents)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = run_validation("Skills", validate_skills)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = run_validation("Hooks", validate_hooks)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = run_validation("Settings", validate_settings_files)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = run_validation("Scripts", validate_scripts)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = run_validation("MCP Config", validate_mcp_config)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = run_validation("Security", validate_security)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = run_validation("Files", validate_file_organization)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    # Summary
    log_section("Validation Summary")
    print(f"\n{CYAN}Plugin:{NC} {plugin_name if plugin_name else plugin_path.name}")
    print(f"{CYAN}Location:{NC} {plugin_path}")

    # Print summary table
    print(f"\n{CYAN}Results by Category:{NC}")
    print(f"  {'Category':<12} {'Status':<6} {'Errors':<7} {'Warnings':<9} {'Info':<5}")
    print(f"  {'-' * 12} {'-' * 6} {'-' * 7} {'-' * 9} {'-' * 5}")
    for category, data in category_results.items():
        status = data["status"]
        if status == "PASS":
            status_str = f"{GREEN}PASS{NC}"
        elif status == "WARN":
            status_str = f"{YELLOW}WARN{NC}"
        else:
            status_str = f"{RED}FAIL{NC}"
        errors_str = (
            f"{RED}{data['errors']}{NC}" if data["errors"] else str(data["errors"])
        )
        warnings_str = (
            f"{YELLOW}{data['warnings']}{NC}"
            if data["warnings"]
            else str(data["warnings"])
        )
        print(
            f"  {category:<12} {status_str:<15} {errors_str:<16} {warnings_str:<18} {data['info']:<5}"
        )

    print()
    print(f"{CYAN}Totals:{NC}")
    print(f"  {RED}Errors:{NC}   {len(all_errors)}")
    print(f"  {YELLOW}Warnings:{NC} {len(all_warnings)}")
    print(f"  {BLUE}Info:{NC}     {len(all_info)}")

    if all_errors:
        print(f"\n{CYAN}Error Details:{NC}")
        for i, error in enumerate(all_errors[:15], 1):  # Show first 15
            print(f"  {i}. {error}")
        if len(all_errors) > 15:
            print(f"  ... and {len(all_errors) - 15} more")

    if all_errors:
        print(f"\n{RED}{'=' * 70}{NC}")
        print(f"{RED}VALIDATION FAILED with {len(all_errors)} error(s){NC}")
        print(f"{RED}{'=' * 70}{NC}")
        sys.exit(1)
    elif all_warnings:
        print(f"\n{YELLOW}{'=' * 70}{NC}")
        print(f"{YELLOW}VALIDATION PASSED with {len(all_warnings)} warning(s){NC}")
        print(f"{YELLOW}{'=' * 70}{NC}")
        sys.exit(0)
    else:
        print(f"\n{GREEN}{'=' * 70}{NC}")
        print(f"{GREEN}VALIDATION PASSED - All checks successful!{NC}")
        print(f"{GREEN}{'=' * 70}{NC}")
        sys.exit(0)


if __name__ == "__main__":
    main()
