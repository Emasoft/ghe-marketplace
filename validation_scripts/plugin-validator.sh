#!/bin/bash
# Plugin Validator - Comprehensive validation for Claude Code plugins
# Inspired by validate-agent.sh and validate-skill.py patterns

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Counters
error_count=0
warning_count=0
info_count=0

# Component counters
agents_found=0
agents_valid=0
skills_found=0
skills_valid=0
commands_found=0
commands_valid=0
hooks_valid=0
scripts_found=0

# Usage
show_usage() {
  echo -e "${CYAN}Plugin Validator - Comprehensive validation for Claude Code plugins${NC}"
  echo ""
  echo "Usage: $0 <path/to/plugin>"
  echo ""
  echo "Validates:"
  echo "  - Plugin structure and organization"
  echo "  - plugin.json manifest"
  echo "  - Commands (commands/*.md)"
  echo "  - Agents (agents/*.md)"
  echo "  - Skills (skills/*/SKILL.md)"
  echo "  - Hooks (hooks/hooks.json)"
  echo "  - Scripts (scripts/*)"
  echo "  - Security checks"
  echo ""
  echo "Options:"
  echo "  -h, --help     Show this help"
  echo "  -v, --verbose  Verbose output"
  echo "  -q, --quiet    Only show errors"
  exit 0
}

# Logging functions
log_error() {
  echo -e "${RED}❌ $1${NC}"
  ((error_count++)) || true
}

log_warning() {
  echo -e "${YELLOW}⚠️  $1${NC}"
  ((warning_count++)) || true
}

log_success() {
  echo -e "${GREEN}✅ $1${NC}"
}

log_info() {
  echo -e "${BLUE}💡 $1${NC}"
  ((info_count++)) || true
}

log_section() {
  echo ""
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${CYAN}$1${NC}"
  echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Parse arguments
VERBOSE=0
QUIET=0
PLUGIN_PATH=""

while [[ $# -gt 0 ]]; do
  case $1 in
    -h|--help)
      show_usage
      ;;
    -v|--verbose)
      VERBOSE=1
      shift
      ;;
    -q|--quiet)
      QUIET=1
      shift
      ;;
    *)
      PLUGIN_PATH="$1"
      shift
      ;;
  esac
done

if [ -z "$PLUGIN_PATH" ]; then
  show_usage
fi

# Resolve to absolute path
PLUGIN_PATH=$(cd "$PLUGIN_PATH" 2>/dev/null && pwd)

log_section "🔍 Plugin Validation: $PLUGIN_PATH"

# ============================================
# Step 1: Validate Plugin Structure
# ============================================
log_section "Step 1: Plugin Structure"

# Check plugin directory exists
if [ ! -d "$PLUGIN_PATH" ]; then
  log_error "Plugin directory not found: $PLUGIN_PATH"
  exit 1
fi
log_success "Plugin directory exists"

# Check for .claude-plugin directory
if [ ! -d "$PLUGIN_PATH/.claude-plugin" ]; then
  log_error "Missing .claude-plugin/ directory"
  exit 1
fi
log_success ".claude-plugin/ directory exists"

# Check for plugin.json
MANIFEST="$PLUGIN_PATH/.claude-plugin/plugin.json"
if [ ! -f "$MANIFEST" ]; then
  log_error "Missing plugin.json manifest"
  exit 1
fi
log_success "plugin.json manifest exists"

# ============================================
# Step 2: Validate Manifest (plugin.json)
# ============================================
log_section "Step 2: Manifest Validation"

# Check JSON syntax
if ! jq empty "$MANIFEST" 2>/dev/null; then
  log_error "Invalid JSON syntax in plugin.json"
  exit 1
fi
log_success "JSON syntax valid"

# Check required field: name
PLUGIN_NAME=$(jq -r '.name // empty' "$MANIFEST")
if [ -z "$PLUGIN_NAME" ]; then
  log_error "Missing required field: name"
else
  log_success "name: $PLUGIN_NAME"

  # Validate name format (kebab-case)
  if ! [[ "$PLUGIN_NAME" =~ ^[a-z][a-z0-9-]*[a-z0-9]$ ]]; then
    log_warning "name should be kebab-case (lowercase, hyphens, start/end with letter/number)"
  fi
fi

# Check optional fields
VERSION=$(jq -r '.version // empty' "$MANIFEST")
if [ -n "$VERSION" ]; then
  if [[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    log_success "version: $VERSION (valid semver)"
  else
    log_warning "version '$VERSION' is not semantic versioning (X.Y.Z)"
  fi
else
  log_info "version: not specified"
fi

DESCRIPTION=$(jq -r '.description // empty' "$MANIFEST")
if [ -n "$DESCRIPTION" ]; then
  desc_len=${#DESCRIPTION}
  log_success "description: $desc_len characters"
  if [ $desc_len -lt 10 ]; then
    log_warning "description too short (recommend 10+ characters)"
  fi
else
  log_info "description: not specified"
fi

AUTHOR=$(jq -r '.author.name // empty' "$MANIFEST")
if [ -n "$AUTHOR" ]; then
  log_success "author: $AUTHOR"
fi

LICENSE=$(jq -r '.license // empty' "$MANIFEST")
if [ -n "$LICENSE" ]; then
  log_success "license: $LICENSE"
else
  log_warning "license: not specified (recommended)"
fi

# Check hooks reference
HOOKS_REF=$(jq -r '.hooks // empty' "$MANIFEST")
if [ -n "$HOOKS_REF" ]; then
  HOOKS_FILE="$PLUGIN_PATH/$HOOKS_REF"
  if [ -f "$HOOKS_FILE" ]; then
    log_success "hooks reference: $HOOKS_REF (file exists)"
  else
    log_error "hooks reference: $HOOKS_REF (file NOT found)"
  fi
fi

# ============================================
# Step 3: Validate Commands
# ============================================
log_section "Step 3: Commands Validation"

COMMANDS_DIR="$PLUGIN_PATH/commands"
if [ -d "$COMMANDS_DIR" ]; then
  while IFS= read -r -d '' cmd_file; do
    ((commands_found++)) || true
    cmd_name=$(basename "$cmd_file" .md)

    # Check frontmatter exists
    if ! head -1 "$cmd_file" | grep -q '^---$'; then
      log_error "Command '$cmd_name': Missing YAML frontmatter"
      continue
    fi

    # Check frontmatter closed
    if ! tail -n +2 "$cmd_file" | grep -q '^---$'; then
      log_error "Command '$cmd_name': Frontmatter not closed"
      continue
    fi

    # Extract frontmatter
    frontmatter=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$cmd_file")

    # Check description
    if ! echo "$frontmatter" | grep -q '^description:'; then
      log_warning "Command '$cmd_name': Missing description"
    fi

    ((commands_valid++)) || true
    [ $VERBOSE -eq 1 ] && log_success "Command '$cmd_name': Valid"
  done < <(find "$COMMANDS_DIR" -name "*.md" -print0 2>/dev/null)

  log_success "Commands: $commands_found found, $commands_valid valid"
else
  log_info "No commands/ directory"
fi

# ============================================
# Step 4: Validate Agents
# ============================================
log_section "Step 4: Agents Validation"

AGENTS_DIR="$PLUGIN_PATH/agents"
if [ -d "$AGENTS_DIR" ]; then
  while IFS= read -r -d '' agent_file; do
    ((agents_found++)) || true
    agent_name=$(basename "$agent_file" .md)
    agent_valid=1

    # Check frontmatter exists
    if ! head -1 "$agent_file" | grep -q '^---$'; then
      log_error "Agent '$agent_name': Missing YAML frontmatter"
      agent_valid=0
      continue
    fi

    # Check frontmatter closed
    if ! tail -n +2 "$agent_file" | grep -q '^---$'; then
      log_error "Agent '$agent_name': Frontmatter not closed"
      agent_valid=0
      continue
    fi

    # Extract frontmatter
    frontmatter=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$agent_file")

    # Check required fields
    if ! echo "$frontmatter" | grep -q '^name:'; then
      log_error "Agent '$agent_name': Missing name field"
      agent_valid=0
    fi

    if ! echo "$frontmatter" | grep -q '^description:'; then
      log_error "Agent '$agent_name': Missing description field"
      agent_valid=0
    fi

    # Check model field
    model=$(echo "$frontmatter" | grep '^model:' | sed 's/model: *//')
    if [ -z "$model" ]; then
      log_warning "Agent '$agent_name': Missing model field"
    elif ! [[ "$model" =~ ^(inherit|sonnet|opus|haiku)$ ]]; then
      log_warning "Agent '$agent_name': Unknown model '$model'"
    fi

    # Check color field
    color=$(echo "$frontmatter" | grep '^color:' | sed 's/color: *//')
    if [ -z "$color" ]; then
      log_warning "Agent '$agent_name': Missing color field"
    elif ! [[ "$color" =~ ^(blue|cyan|green|yellow|magenta|red|orange|purple)$ ]]; then
      log_warning "Agent '$agent_name': Unknown color '$color'"
    fi

    # Check system prompt exists and has content
    system_prompt=$(awk '/^---$/{i++; next} i>=2' "$agent_file")
    if [ -z "$system_prompt" ]; then
      log_error "Agent '$agent_name': Empty system prompt"
      agent_valid=0
    else
      prompt_len=${#system_prompt}
      if [ $prompt_len -lt 50 ]; then
        log_warning "Agent '$agent_name': System prompt very short ($prompt_len chars)"
      fi
    fi

    if [ $agent_valid -eq 1 ]; then
      ((agents_valid++)) || true
      [ $VERBOSE -eq 1 ] && log_success "Agent '$agent_name': Valid"
    fi
  done < <(find "$AGENTS_DIR" -name "*.md" -print0 2>/dev/null)

  log_success "Agents: $agents_found found, $agents_valid valid"
else
  log_info "No agents/ directory"
fi

# ============================================
# Step 5: Validate Skills
# ============================================
log_section "Step 5: Skills Validation"

SKILLS_DIR="$PLUGIN_PATH/skills"
if [ -d "$SKILLS_DIR" ]; then
  while IFS= read -r -d '' skill_file; do
    ((skills_found++)) || true
    skill_dir=$(dirname "$skill_file")
    skill_name=$(basename "$skill_dir")
    skill_valid=1

    # Check frontmatter exists
    if ! head -1 "$skill_file" | grep -q '^---$'; then
      log_error "Skill '$skill_name': Missing YAML frontmatter"
      skill_valid=0
      continue
    fi

    # Check frontmatter closed
    if ! tail -n +2 "$skill_file" | grep -q '^---$'; then
      log_error "Skill '$skill_name': Frontmatter not closed"
      skill_valid=0
      continue
    fi

    # Extract frontmatter
    frontmatter=$(sed -n '/^---$/,/^---$/{ /^---$/d; p; }' "$skill_file")

    # Check required fields
    if ! echo "$frontmatter" | grep -q '^name:'; then
      log_error "Skill '$skill_name': Missing name field"
      skill_valid=0
    fi

    if ! echo "$frontmatter" | grep -q '^description:'; then
      log_error "Skill '$skill_name': Missing description field"
      skill_valid=0
    fi

    # Check for references directory
    if [ -d "$skill_dir/references" ]; then
      ref_count=$(find "$skill_dir/references" -type f | wc -l)
      [ $VERBOSE -eq 1 ] && log_info "Skill '$skill_name': $ref_count reference files"
    fi

    if [ $skill_valid -eq 1 ]; then
      ((skills_valid++)) || true
      [ $VERBOSE -eq 1 ] && log_success "Skill '$skill_name': Valid"
    fi
  done < <(find "$SKILLS_DIR" -name "SKILL.md" -print0 2>/dev/null)

  log_success "Skills: $skills_found found, $skills_valid valid"
else
  log_info "No skills/ directory"
fi

# ============================================
# Step 6: Validate Hooks
# ============================================
log_section "Step 6: Hooks Validation"

HOOKS_FILE="$PLUGIN_PATH/hooks/hooks.json"
if [ -f "$HOOKS_FILE" ]; then
  # Check JSON syntax
  if ! jq empty "$HOOKS_FILE" 2>/dev/null; then
    log_error "Invalid JSON syntax in hooks.json"
  else
    log_success "hooks.json: Valid JSON"

    # Check hooks array exists
    hooks_count=$(jq '.hooks | length' "$HOOKS_FILE" 2>/dev/null || echo 0)
    log_success "hooks.json: $hooks_count hooks defined"

    # Validate each hook
    for i in $(seq 0 $((hooks_count - 1))); do
      event=$(jq -r ".hooks[$i].event // empty" "$HOOKS_FILE")
      hook_type=$(jq -r ".hooks[$i].type // empty" "$HOOKS_FILE")

      # Validate event name
      if [ -z "$event" ]; then
        log_error "Hook $i: Missing event"
      elif ! [[ "$event" =~ ^(PreToolUse|PostToolUse|Stop|SubagentStop|SessionStart|SessionEnd|UserPromptSubmit|PreCompact|Notification)$ ]]; then
        log_warning "Hook $i: Unknown event '$event'"
      fi

      # Validate hook type
      if [ -z "$hook_type" ]; then
        log_error "Hook $i: Missing type"
      elif ! [[ "$hook_type" =~ ^(command|prompt)$ ]]; then
        log_warning "Hook $i: Unknown type '$hook_type'"
      fi
    done

    hooks_valid=1
  fi
else
  log_info "No hooks/hooks.json"
fi

# ============================================
# Step 7: Validate Scripts
# ============================================
log_section "Step 7: Scripts Validation"

SCRIPTS_DIR="$PLUGIN_PATH/scripts"
if [ -d "$SCRIPTS_DIR" ]; then
  while IFS= read -r -d '' script_file; do
    ((scripts_found++)) || true
    script_name=$(basename "$script_file")

    # Check executable permission for .sh files
    if [[ "$script_file" == *.sh ]]; then
      if [ ! -x "$script_file" ]; then
        log_warning "Script '$script_name': Not executable (chmod +x)"
      fi
    fi

    [ $VERBOSE -eq 1 ] && log_success "Script '$script_name': Found"
  done < <(find "$SCRIPTS_DIR" -type f \( -name "*.sh" -o -name "*.py" -o -name "*.js" \) -print0 2>/dev/null)

  log_success "Scripts: $scripts_found found"
else
  log_info "No scripts/ directory"
fi

# ============================================
# Step 8: Security Checks
# ============================================
log_section "Step 8: Security Checks"

# Check for hardcoded credentials patterns
SECURITY_PATTERNS=(
  'password\s*[:=]\s*["\047][^"\047]+'
  'api_key\s*[:=]\s*["\047][^"\047]+'
  'secret\s*[:=]\s*["\047][^"\047]+'
  'token\s*[:=]\s*["\047][^"\047]+'
  'sk-[a-zA-Z0-9]{20,}'
  'ghp_[a-zA-Z0-9]{36}'
)

security_issues=0
for pattern in "${SECURITY_PATTERNS[@]}"; do
  matches=$(grep -rliE "$pattern" "$PLUGIN_PATH" --include="*.md" --include="*.json" --include="*.sh" --include="*.py" 2>/dev/null | head -5 || true)
  if [ -n "$matches" ]; then
    log_warning "Potential credentials found (pattern: $pattern)"
    ((security_issues++)) || true
  fi
done

if [ $security_issues -eq 0 ]; then
  log_success "No obvious credential patterns found"
fi

# Check for absolute paths
abs_paths=$(grep -rh '/Users/\|/home/\|C:\\' "$PLUGIN_PATH" --include="*.md" --include="*.json" 2>/dev/null | head -3 || true)
if [ -n "$abs_paths" ]; then
  log_warning "Absolute paths found - use \${CLAUDE_PLUGIN_ROOT} for portability"
fi

# ============================================
# Step 9: File Organization
# ============================================
log_section "Step 9: File Organization"

# Check README
if [ -f "$PLUGIN_PATH/README.md" ]; then
  readme_size=$(wc -c < "$PLUGIN_PATH/README.md")
  if [ $readme_size -lt 500 ]; then
    log_warning "README.md is short ($readme_size bytes) - consider expanding"
  else
    log_success "README.md: Present ($readme_size bytes)"
  fi
else
  log_warning "README.md: Missing (recommended)"
fi

# Check LICENSE
if [ -f "$PLUGIN_PATH/LICENSE" ] || [ -f "$PLUGIN_PATH/LICENSE.md" ]; then
  log_success "LICENSE: Present"
else
  log_warning "LICENSE: Missing (recommended for distribution)"
fi

# Check .gitignore
if [ -f "$PLUGIN_PATH/.gitignore" ]; then
  log_success ".gitignore: Present"
else
  log_info ".gitignore: Not present"
fi

# Check for unwanted files
unwanted_files=$(find "$PLUGIN_PATH" -name ".DS_Store" -o -name "node_modules" -o -name "__pycache__" -o -name "*.pyc" 2>/dev/null | head -5)
if [ -n "$unwanted_files" ]; then
  log_warning "Unwanted files found (consider .gitignore):"
  echo "$unwanted_files" | while read -r f; do echo "  - $f"; done
fi

# ============================================
# Summary Report
# ============================================
log_section "📊 Validation Summary"

echo ""
echo -e "${CYAN}Plugin:${NC} $PLUGIN_NAME"
echo -e "${CYAN}Location:${NC} $PLUGIN_PATH"
echo ""
echo -e "${CYAN}Components:${NC}"
echo "  Commands: $commands_found found, $commands_valid valid"
echo "  Agents:   $agents_found found, $agents_valid valid"
echo "  Skills:   $skills_found found, $skills_valid valid"
echo "  Hooks:    $([ $hooks_valid -eq 1 ] && echo 'Valid' || echo 'Not present/Invalid')"
echo "  Scripts:  $scripts_found found"
echo ""
echo -e "${CYAN}Issues:${NC}"
echo -e "  ${RED}Errors:${NC}   $error_count"
echo -e "  ${YELLOW}Warnings:${NC} $warning_count"
echo -e "  ${BLUE}Info:${NC}     $info_count"
echo ""

# Final verdict
if [ $error_count -eq 0 ]; then
  if [ $warning_count -eq 0 ]; then
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${GREEN}✅ VALIDATION PASSED - Plugin is ready for distribution${NC}"
    echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
  else
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}⚠️  VALIDATION PASSED with $warning_count warning(s)${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    exit 0
  fi
else
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${RED}❌ VALIDATION FAILED with $error_count error(s)${NC}"
  echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  exit 1
fi
