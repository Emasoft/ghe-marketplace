#!/usr/bin/env python3
"""
Plugin Validator - Comprehensive validation for Claude Code plugins
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import NamedTuple

# ANSI colors
RED = '\033[0;31m'
GREEN = '\033[0;32m'
YELLOW = '\033[1;33m'
BLUE = '\033[0;34m'
CYAN = '\033[0;36m'
NC = '\033[0m'  # No Color


class ValidationResult(NamedTuple):
    errors: list[str]
    warnings: list[str]
    info: list[str]


def log_error(msg: str) -> None:
    print(f"{RED}  {msg}{NC}")


def log_warning(msg: str) -> None:
    print(f"{YELLOW}  {msg}{NC}")


def log_success(msg: str) -> None:
    print(f"{GREEN}  {msg}{NC}")


def log_info(msg: str) -> None:
    print(f"{BLUE}  {msg}{NC}")


def log_section(msg: str) -> None:
    print()
    print(f"{CYAN}{'=' * 50}{NC}")
    print(f"{CYAN}{msg}{NC}")
    print(f"{CYAN}{'=' * 50}{NC}")


def parse_yaml_frontmatter(content: str) -> tuple[dict | None, str | None]:
    """Parse YAML frontmatter from markdown content.

    Returns (frontmatter_dict, body) or (None, error_message) if invalid.
    """
    lines = content.split('\n')

    if not lines or lines[0].strip() != '---':
        return None, "Missing opening ---"

    # Find closing ---
    closing_idx = None
    for i, line in enumerate(lines[1:], 1):
        if line.strip() == '---':
            closing_idx = i
            break

    if closing_idx is None:
        return None, "Missing closing ---"

    # Extract frontmatter YAML
    frontmatter_lines = lines[1:closing_idx]
    frontmatter_text = '\n'.join(frontmatter_lines)

    # Simple YAML parsing (key: value)
    frontmatter = {}
    current_key = None
    current_value_lines = []

    for line in frontmatter_lines:
        # Check for multiline continuation (starts with spaces and not a new key)
        if line.startswith('  ') or line.startswith('\t'):
            if current_key:
                current_value_lines.append(line.strip())
            continue

        # Save previous key-value if exists
        if current_key:
            if current_value_lines:
                frontmatter[current_key] = '\n'.join(current_value_lines)
            current_key = None
            current_value_lines = []

        # Parse new key: value
        if ':' in line:
            parts = line.split(':', 1)
            key = parts[0].strip()
            value = parts[1].strip() if len(parts) > 1 else ''

            if value == '|' or value == '>':
                # Multiline value follows
                current_key = key
                current_value_lines = []
            elif value:
                frontmatter[key] = value
            else:
                frontmatter[key] = ''

    # Handle last multiline value
    if current_key and current_value_lines:
        frontmatter[current_key] = '\n'.join(current_value_lines)

    body = '\n'.join(lines[closing_idx + 1:])
    return frontmatter, body


def validate_plugin_structure(plugin_path: Path) -> ValidationResult:
    """Validate plugin directory structure."""
    errors = []
    warnings = []
    info = []

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
    errors = []
    warnings = []
    info = []
    plugin_name = ""

    log_section("Step 2: Manifest Validation")

    manifest_path = plugin_path / ".claude-plugin" / "plugin.json"

    try:
        with open(manifest_path, 'r') as f:
            manifest = json.load(f)
        log_success("JSON syntax valid")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON syntax: {e}")
        log_error(f"Invalid JSON syntax: {e}")
        return ValidationResult(errors, warnings, info), ""

    # Check name
    plugin_name = manifest.get('name', '')
    if not plugin_name:
        errors.append("Missing required field: name")
        log_error("Missing required field: name")
    else:
        log_success(f"name: {plugin_name}")
        if not re.match(r'^[a-z][a-z0-9-]*[a-z0-9]$', plugin_name):
            warnings.append("name should be kebab-case")
            log_warning("name should be kebab-case (lowercase, hyphens)")

    # Check version
    version = manifest.get('version', '')
    if version:
        if re.match(r'^\d+\.\d+\.\d+$', version):
            log_success(f"version: {version} (valid semver)")
        else:
            warnings.append(f"version '{version}' is not semantic versioning")
            log_warning(f"version '{version}' is not semantic versioning (X.Y.Z)")
    else:
        info.append("version: not specified")
        log_info("version: not specified")

    # Check description
    description = manifest.get('description', '')
    if description:
        log_success(f"description: {len(description)} characters")
        if len(description) < 10:
            warnings.append("description too short")
            log_warning("description too short (recommend 10+ characters)")
    else:
        info.append("description: not specified")
        log_info("description: not specified")

    # Check author
    author = manifest.get('author', {})
    if isinstance(author, dict):
        author_name = author.get('name', '')
        if author_name:
            log_success(f"author: {author_name}")

    # Check license
    license_val = manifest.get('license', '')
    if license_val:
        log_success(f"license: {license_val}")
    else:
        warnings.append("license: not specified")
        log_warning("license: not specified (recommended)")

    # Check hooks reference
    hooks_ref = manifest.get('hooks', '')
    if hooks_ref:
        hooks_path = plugin_path / hooks_ref.lstrip('./')
        if hooks_path.exists():
            log_success(f"hooks reference: {hooks_ref} (file exists)")
        else:
            errors.append(f"hooks reference: {hooks_ref} (file NOT found)")
            log_error(f"hooks reference: {hooks_ref} (file NOT found)")

    return ValidationResult(errors, warnings, info), plugin_name


def validate_commands(plugin_path: Path) -> ValidationResult:
    """Validate commands."""
    errors = []
    warnings = []
    info = []
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

        if 'description' not in fm:
            warnings.append(f"Command '{cmd_name}': Missing description")
            log_warning(f"Command '{cmd_name}': Missing description")

        commands_valid += 1

    log_success(f"Commands: {commands_found} found, {commands_valid} valid")
    return ValidationResult(errors, warnings, info)


def validate_agents(plugin_path: Path) -> ValidationResult:
    """Validate agents."""
    errors = []
    warnings = []
    info = []
    agents_found = 0
    agents_valid = 0

    log_section("Step 4: Agents Validation")

    agents_dir = plugin_path / "agents"
    if not agents_dir.exists():
        log_info("No agents/ directory")
        return ValidationResult(errors, warnings, info)

    valid_colors = {'blue', 'cyan', 'green', 'yellow', 'magenta', 'red', 'orange', 'purple'}
    valid_models = {'inherit', 'sonnet', 'opus', 'haiku'}

    for agent_file in agents_dir.rglob("*.md"):
        agents_found += 1
        agent_name = agent_file.stem
        agent_valid = True

        content = agent_file.read_text()
        fm, body = parse_yaml_frontmatter(content)

        if fm is None:
            errors.append(f"Agent '{agent_name}': {body}")
            log_error(f"Agent '{agent_name}': {body}")
            continue

        # Check required fields
        if 'name' not in fm:
            errors.append(f"Agent '{agent_name}': Missing name field")
            log_error(f"Agent '{agent_name}': Missing name field")
            agent_valid = False

        if 'description' not in fm:
            errors.append(f"Agent '{agent_name}': Missing description field")
            log_error(f"Agent '{agent_name}': Missing description field")
            agent_valid = False

        # Check model
        model = fm.get('model', '')
        if not model:
            warnings.append(f"Agent '{agent_name}': Missing model field")
            log_warning(f"Agent '{agent_name}': Missing model field")
        elif model not in valid_models:
            warnings.append(f"Agent '{agent_name}': Unknown model '{model}'")
            log_warning(f"Agent '{agent_name}': Unknown model '{model}'")

        # Check color
        color = fm.get('color', '')
        if not color:
            warnings.append(f"Agent '{agent_name}': Missing color field")
            log_warning(f"Agent '{agent_name}': Missing color field")
        elif color not in valid_colors:
            warnings.append(f"Agent '{agent_name}': Unknown color '{color}'")
            log_warning(f"Agent '{agent_name}': Unknown color '{color}'")

        # Check system prompt
        if body is not None:
            body_stripped = body.strip()
            if not body_stripped:
                errors.append(f"Agent '{agent_name}': Empty system prompt")
                log_error(f"Agent '{agent_name}': Empty system prompt")
                agent_valid = False
            elif len(body_stripped) < 50:
                warnings.append(f"Agent '{agent_name}': System prompt very short")
                log_warning(f"Agent '{agent_name}': System prompt very short ({len(body_stripped)} chars)")

        if agent_valid:
            agents_valid += 1

    log_success(f"Agents: {agents_found} found, {agents_valid} valid")
    return ValidationResult(errors, warnings, info)


def validate_skills(plugin_path: Path) -> ValidationResult:
    """Validate skills."""
    errors = []
    warnings = []
    info = []
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

        content = skill_file.read_text()
        fm, body = parse_yaml_frontmatter(content)

        if fm is None:
            errors.append(f"Skill '{skill_name}': {body}")
            log_error(f"Skill '{skill_name}': {body}")
            continue

        # Check required fields
        if 'name' not in fm:
            errors.append(f"Skill '{skill_name}': Missing name field")
            log_error(f"Skill '{skill_name}': Missing name field")
            skill_valid = False

        if 'description' not in fm:
            errors.append(f"Skill '{skill_name}': Missing description field")
            log_error(f"Skill '{skill_name}': Missing description field")
            skill_valid = False

        # Check for references directory
        refs_dir = skill_file.parent / "references"
        if refs_dir.exists():
            ref_count = len(list(refs_dir.iterdir()))
            info.append(f"Skill '{skill_name}': {ref_count} reference files")

        if skill_valid:
            skills_valid += 1

    log_success(f"Skills: {skills_found} found, {skills_valid} valid")
    return ValidationResult(errors, warnings, info)


def validate_hooks(plugin_path: Path) -> ValidationResult:
    """Validate hooks."""
    errors = []
    warnings = []
    info = []

    log_section("Step 6: Hooks Validation")

    hooks_file = plugin_path / "hooks" / "hooks.json"
    if not hooks_file.exists():
        log_info("No hooks/hooks.json")
        return ValidationResult(errors, warnings, info)

    try:
        with open(hooks_file, 'r') as f:
            hooks_data = json.load(f)
        log_success("hooks.json: Valid JSON")
    except json.JSONDecodeError as e:
        errors.append(f"Invalid JSON syntax in hooks.json: {e}")
        log_error(f"Invalid JSON syntax in hooks.json: {e}")
        return ValidationResult(errors, warnings, info)

    valid_events = {
        'PreToolUse', 'PostToolUse', 'Stop', 'SubagentStop',
        'SessionStart', 'SessionEnd', 'UserPromptSubmit',
        'PreCompact', 'Notification'
    }
    valid_types = {'command', 'prompt'}

    hooks = hooks_data.get('hooks', [])
    log_success(f"hooks.json: {len(hooks)} hooks defined")

    for i, hook in enumerate(hooks):
        event = hook.get('event', '')
        hook_type = hook.get('type', '')

        if not event:
            errors.append(f"Hook {i}: Missing event")
            log_error(f"Hook {i}: Missing event")
        elif event not in valid_events:
            warnings.append(f"Hook {i}: Unknown event '{event}'")
            log_warning(f"Hook {i}: Unknown event '{event}'")

        if not hook_type:
            errors.append(f"Hook {i}: Missing type")
            log_error(f"Hook {i}: Missing type")
        elif hook_type not in valid_types:
            warnings.append(f"Hook {i}: Unknown type '{hook_type}'")
            log_warning(f"Hook {i}: Unknown type '{hook_type}'")

    return ValidationResult(errors, warnings, info)


def validate_scripts(plugin_path: Path) -> ValidationResult:
    """Validate scripts."""
    errors = []
    warnings = []
    info = []

    log_section("Step 7: Scripts Validation")

    scripts_dir = plugin_path / "scripts"
    if not scripts_dir.exists():
        log_info("No scripts/ directory")
        return ValidationResult(errors, warnings, info)

    scripts = list(scripts_dir.rglob("*"))
    scripts = [s for s in scripts if s.is_file()]
    log_success(f"Scripts: {len(scripts)} found")

    return ValidationResult(errors, warnings, info)


def validate_security(plugin_path: Path) -> ValidationResult:
    """Basic security checks."""
    errors = []
    warnings = []
    info = []

    log_section("Step 8: Security Checks")

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
        if file.suffix in ['.md', '.json', '.sh', '.py', '.js', '.ts']:
            try:
                content = file.read_text()
                for pattern in credential_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        suspicious_files.append(str(file))
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
    errors = []
    warnings = []
    info = []

    log_section("Step 9: File Organization")

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
    unwanted = ['.DS_Store', 'node_modules', '__pycache__', '.env']
    found_unwanted = []
    for pattern in unwanted:
        matches = list(plugin_path.rglob(pattern))
        if matches:
            found_unwanted.extend(matches)

    if found_unwanted:
        warnings.append(f"Unwanted files found: {len(found_unwanted)}")
        log_warning(f"Unwanted files found (consider .gitignore): {[str(f) for f in found_unwanted[:3]]}")

    return ValidationResult(errors, warnings, info)


def main():
    if len(sys.argv) < 2:
        print(f"{CYAN}Plugin Validator - Comprehensive validation for Claude Code plugins{NC}")
        print()
        print(f"Usage: {sys.argv[0]} <path/to/plugin>")
        sys.exit(0)

    plugin_path = Path(sys.argv[1]).resolve()

    print(f"\n{CYAN}{'=' * 50}{NC}")
    print(f"{CYAN}Plugin Validation: {plugin_path}{NC}")
    print(f"{CYAN}{'=' * 50}{NC}")

    all_errors = []
    all_warnings = []
    all_info = []

    # Run all validations
    result = validate_plugin_structure(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    if result.errors:
        # Fatal error, can't continue
        print(f"\n{RED}VALIDATION FAILED - Cannot continue{NC}")
        sys.exit(1)

    result, plugin_name = validate_manifest(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = validate_commands(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = validate_agents(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = validate_skills(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = validate_hooks(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = validate_scripts(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = validate_security(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    result = validate_file_organization(plugin_path)
    all_errors.extend(result.errors)
    all_warnings.extend(result.warnings)
    all_info.extend(result.info)

    # Summary
    log_section("Validation Summary")
    print(f"\n{CYAN}Plugin:{NC} {plugin_name}")
    print(f"{CYAN}Location:{NC} {plugin_path}")
    print()
    print(f"{CYAN}Issues:{NC}")
    print(f"  {RED}Errors:{NC}   {len(all_errors)}")
    print(f"  {YELLOW}Warnings:{NC} {len(all_warnings)}")
    print(f"  {BLUE}Info:{NC}     {len(all_info)}")

    if all_errors:
        print(f"\n{RED}{'=' * 50}{NC}")
        print(f"{RED}VALIDATION FAILED with {len(all_errors)} error(s){NC}")
        print(f"{RED}{'=' * 50}{NC}")
        sys.exit(1)
    elif all_warnings:
        print(f"\n{YELLOW}{'=' * 50}{NC}")
        print(f"{YELLOW}VALIDATION PASSED with {len(all_warnings)} warning(s){NC}")
        print(f"{YELLOW}{'=' * 50}{NC}")
        sys.exit(0)
    else:
        print(f"\n{GREEN}{'=' * 50}{NC}")
        print(f"{GREEN}VALIDATION PASSED{NC}")
        print(f"{GREEN}{'=' * 50}{NC}")
        sys.exit(0)


if __name__ == "__main__":
    main()
