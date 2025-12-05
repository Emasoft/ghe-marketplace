# auto_approve.sh Security Model

This document describes the complete security model used by the `auto_approve.sh` PreToolUse hook script.

## Permission Decisions

The hook returns one of three decisions:

| Decision | Effect | When Used |
|----------|--------|-----------|
| `allow` | Operation proceeds without user prompt | Safe operations |
| `deny` | Operation is blocked | Dangerous operations |
| `ask` | User is prompted for approval | Unknown operations |

## Always ALLOW (Safe Read-Only Operations)

These tools are always approved because they have no side effects:

```
Read            - Read file contents
Glob            - Find files by pattern
Grep            - Search file contents
LS              - List directory contents
Task            - Spawn subagents
WebFetch        - Fetch web content
WebSearch       - Search the web
TodoWrite       - Update todo list
TodoRead        - Read todo list
ListMcpResourcesTool - List MCP resources
ReadMcpResourceTool  - Read MCP resources
Skill           - Execute skills
SlashCommand    - Execute slash commands
```

## Path-Based Approval (Write Operations)

These tools are approved only if the target path is safe:

```
Write           - Write file
Edit            - Edit file
MultiEdit       - Edit multiple locations
NotebookEdit    - Edit Jupyter notebooks
```

### Safe Paths

A path is considered safe if:

1. **Empty path** - Some tools don't specify paths
2. **Relative path** - Does not start with `/` (within project)
3. **Project path** - Starts with the project directory
4. **Temp path** - Starts with `/tmp/`

### Unsafe Paths (DENIED)

Any absolute path outside the project directory:

```
/etc/*          - System configuration
/usr/*          - System binaries
/var/*          - System data
/root/*         - Root home
~/*             - User home (outside project)
/home/*         - Other users
```

## Bash Command Whitelist

### Git Operations (ALLOW)

```bash
git *           - All git commands
gh *            - GitHub CLI commands
```

### File Inspection - Read Only (ALLOW)

```bash
ls *            - List files
cat *           - Display file contents
head *          - Show file start
tail *          - Show file end
wc *            - Word/line count
file *          - Detect file type
stat *          - File statistics
find *          - Find files
grep *          - Search content
which *         - Locate command
```

### Development Runtimes (ALLOW)

```bash
python*         - Python interpreter
uv *            - UV package manager
node *          - Node.js
npm *           - NPM package manager
pnpm *          - PNPM package manager
yarn *          - Yarn package manager
cargo *         - Rust package manager
go *            - Go toolchain
```

### Linters and Formatters (ALLOW)

```bash
ruff *          - Python linter/formatter
pytest*         - Python testing
mypy *          - Python type checker
eslint *        - JavaScript linter
prettier *      - Code formatter
tsc *           - TypeScript compiler
rustfmt *       - Rust formatter
```

### Safe Utilities (ALLOW)

```bash
echo *          - Print text
printf *        - Format and print
mkdir *         - Create directories
touch *         - Create/update files
cp *            - Copy files
mv *            - Move files
chmod *         - Change permissions
date*           - Show date/time
pwd*            - Print working directory
cd *            - Change directory
sleep *         - Wait
```

### Build Tools (ALLOW)

```bash
make *          - Make build system
cmake *         - CMake
ninja *         - Ninja build
```

## Always DENY (Dangerous Commands)

These patterns are always blocked:

```bash
sudo *          - Privilege escalation
*rm -rf /*      - Recursive force delete root
*chmod 777 *    - Insecure permissions
*> /dev/*       - Device manipulation
*dd if=*        - Disk operations
```

## Unknown Operations (ASK)

Any tool or command not matching the above rules will prompt the user for approval. This ensures new or unexpected operations are reviewed.

## Hook Output Format

The hook outputs JSON in this format:

```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "allow|deny|ask",
    "permissionDecisionReason": "Human-readable reason"
  }
}
```

## Logging

When `BACKGROUND_AGENT_LOG` is set (default: `/tmp/background_agent_hook.log`), decisions are logged:

```
[Fri Dec  5 10:46:28 CET 2025] Tool: Write, Path: /project/file.md, Cmd: 
[Fri Dec  5 10:46:28 CET 2025] ALLOW: Write within project directory
```

## Customizing the Whitelist

To add custom approvals, edit `scripts/auto_approve.sh`:

### Adding a Tool

```bash
case "$TOOL_NAME" in
    # Add your custom tool
    "MyCustomTool")
        approve "Custom tool description"
        ;;
esac
```

### Adding a Bash Command

```bash
case "$COMMAND" in
    # Add your custom command pattern
    mycustomcmd\ *)
        approve "Custom command" ;;
esac
```

## Security Considerations

1. **Project Sandbox**: All write operations are restricted to the project directory
2. **No Privilege Escalation**: sudo and similar commands are always blocked
3. **Explicit Whitelist**: Only known-safe commands are auto-approved
4. **Logging**: All decisions can be audited via log file
5. **Fallback to User**: Unknown operations always prompt the user
