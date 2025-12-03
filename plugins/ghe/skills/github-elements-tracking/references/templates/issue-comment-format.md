# Issue Comment Format Template

This template defines the standard format for posting conversation exchanges to GitHub Issue threads.

## Avatar URLs

| Role | Avatar URL |
|------|------------|
| **Emasoft (Owner)** | `https://avatars.githubusercontent.com/u/713559?v=4&s=77` |
| **Claude (Orchestrator)** | `https://robohash.org/claude-code-orchestrator.png?size=77x77&set=set3` |
| **dev-thread-manager** | `https://robohash.org/ghe-dev-thread-manager.png?size=77x77&set=set3` |
| **test-thread-manager** | `https://robohash.org/ghe-test-thread-manager.png?size=77x77&set=set3` |
| **review-thread-manager** | `https://robohash.org/ghe-review-thread-manager.png?size=77x77&set=set3` |
| **orchestrator** | `https://robohash.org/ghe-orchestrator.png?size=77x77&set=set3` |
| **phase-gate** | `https://robohash.org/ghe-phase-gate.png?size=77x77&set=set3` |
| **memory-sync** | `https://robohash.org/ghe-memory-sync.png?size=77x77&set=set3` |
| **enforcement** | `https://robohash.org/ghe-enforcement.png?size=77x77&set=set3` |
| **reporter** | `https://robohash.org/ghe-reporter.png?size=77x77&set=set3` |
| **ci-issue-opener** | `https://robohash.org/ghe-ci-issue-opener.png?size=77x77&set=set3` |
| **pr-checker** | `https://robohash.org/ghe-pr-checker.png?size=77x77&set=set3` |

## Comment Template

```markdown
<img src="AVATAR_URL" width="77" align="left"/>

**NAME said:**
<br>

CONTENT_HERE

---
```

## Template Variables

- `AVATAR_URL`: The avatar URL from the table above
- `NAME`: The display name (e.g., "Emasoft", "Claude (Orchestrator)", "ghe:dev-thread-manager")
- `CONTENT_HERE`: The message content (use `>` for quotes)

## Example: User Message

```markdown
<img src="https://avatars.githubusercontent.com/u/713559?v=4&s=77" width="77" align="left"/>

**Emasoft said:**
<br>

> This is a quoted message from the user.
> It can span multiple lines.

Additional context or details here.

---
```

## Example: Agent Response

```markdown
<img src="https://robohash.org/claude-code-orchestrator.png?size=77x77&set=set3" width="77" align="left"/>

**Claude (Orchestrator) said:**
<br>

Response content here.

**Actions taken:**
- Action 1
- Action 2

---
```

## Important Notes

1. **Empty line after avatar**: Always leave an empty line after the `<img>` tag
2. **`<br>` after name**: Always add `<br>` after "**Name said:**" to create spacing
3. **Separator**: Always end with `---` horizontal rule
4. **Avatar size**: Always use `width="77"` for consistency
5. **Alignment**: Always use `align="left"` for the avatar

## Usage by Agents

When posting to issue threads, agents should:

1. Read this template
2. Replace variables with actual values
3. Use `gh issue comment NUMBER --body "..."` to post
