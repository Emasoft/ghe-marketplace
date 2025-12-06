---
req_id: REQ-XXX
version: 1.0.0
status: draft
created: YYYY-MM-DD
updated: YYYY-MM-DD
epic: null
wave: null
linked_issues: []
author: @username
---

# REQ-XXX: [Feature Name]

## 1. Overview

[Brief description of the feature/change. What problem does it solve? Why is it needed?]

## 2. User Story

**As a** [type of user],
**I want** [goal/desire],
**So that** [benefit/value].

### User Personas Affected
- [ ] Developer
- [ ] End User
- [ ] Administrator
- [ ] Other: ___

## 3. Acceptance Criteria

Each criterion must be specific, measurable, and testable.

- [ ] **AC-1**: [First acceptance criterion - specific and verifiable]
- [ ] **AC-2**: [Second acceptance criterion]
- [ ] **AC-3**: [Third acceptance criterion]
- [ ] **AC-4**: [Add more as needed]

## 4. Technical Requirements

### 4.1 Functional Requirements

- **FR-1**: [What the system must DO]
- **FR-2**: [Another functional requirement]
- **FR-3**: [Add more as needed]

### 4.2 Non-Functional Requirements

- **NFR-1**: Performance - [e.g., "Response time < 200ms"]
- **NFR-2**: Security - [e.g., "Input must be sanitized"]
- **NFR-3**: Scalability - [e.g., "Handle 1000 concurrent users"]
- **NFR-4**: Maintainability - [e.g., "Code coverage > 80%"]

## 5. External References

### 5.1 API Endpoints & Services

| Service | Endpoint | Documentation | Purpose |
|---------|----------|---------------|---------|
| [Service Name] | `https://api.example.com/v1/resource` | [API Docs](URL) | [What it's used for] |
| | | | |

### 5.2 Libraries & Frameworks

| Library | Version | Documentation | Why Chosen |
|---------|---------|---------------|------------|
| [Library Name] | `^X.Y.Z` | [Docs](URL) | [Rationale for selection] |
| | | | |

### 5.3 Related Issues (External Projects)

Links to issues from other repositories that inform or affect this requirement:

| Project | Issue | Relevance |
|---------|-------|-----------|
| [owner/repo](https://github.com/owner/repo) | [#123](https://github.com/owner/repo/issues/123) | [How it relates to this requirement] |
| | | |

### 5.4 Data Sources & Datasets

| Dataset | Location | Format | Schema Reference |
|---------|----------|--------|------------------|
| [Dataset Name] | `path/to/data` or URL | JSON/CSV/SQL | [schema.json](path) |
| | | | |

## 6. Supporting Assets

### 6.1 Design Documents

| Document | Path | Description |
|----------|------|-------------|
| Schema | `docs/schemas/feature-schema.json` | Data structure definition |
| Diagram | `docs/diagrams/feature-flow.mmd` | Mermaid flow diagram |
| | | |

### 6.2 Visual Assets

| Asset | Path | Format | Purpose |
|-------|------|--------|---------|
| UI Mockup | `assets/mockups/feature-ui.pdf` | PDF | Designer sketch |
| Icons | `assets/icons/feature-*.svg` | SVG | UI icons |
| | | | |

### 6.3 Audio/Video Assets

| Asset | Path | Format | Purpose |
|-------|------|--------|---------|
| Demo Video | `assets/video/feature-demo.mp4` | MP4 | User guide |
| Sound Effect | `assets/audio/notification.wav` | WAV | UI feedback |
| | | | |

### 6.4 3D/Interactive Assets

| Asset | Path | Format | Purpose |
|-------|------|--------|---------|
| 3D Model | `assets/models/component.glb` | GLB | Visualization |
| | | | |

## 7. Atomic Changes

Break down into the smallest implementable units. Each change should be:
- Independently testable
- Completable in one TDD cycle
- Committable as a single atomic commit

1. **CHANGE-1**: [Description]
   - Creates: `path/to/new_file.py`
   - Modifies: `path/to/existing.py`
   - Test: `tests/test_change1.py`

2. **CHANGE-2**: [Description]
   - Creates: `path/to/another_file.py`
   - Test: `tests/test_change2.py`

3. **CHANGE-3**: [Description]
   - Modifies: `config/settings.yaml`
   - Test: `tests/test_config.py`

[Add more atomic changes as needed - aim for 3-7 per requirement]

## 8. Test Requirements (TDD)

**CRITICAL**: Tests MUST be written BEFORE implementation (Red-Green-Refactor).

### 8.1 Recommended Unit Tests

| Test ID | Target | Input | Expected Output | Priority |
|---------|--------|-------|-----------------|----------|
| UT-1 | `function_name()` | [input] | [output] | High |
| UT-2 | `ClassName.method()` | [input] | [output] | Medium |
| | | | | |

### 8.2 Edge Cases to Test

| Test ID | Scenario | Expected Behavior |
|---------|----------|-------------------|
| EC-1 | Empty input | Returns empty/default |
| EC-2 | Null/undefined | Throws/handles gracefully |
| EC-3 | Max boundary | Handles limit correctly |
| | | |

### 8.3 Integration Tests

| Test ID | Components | Scenario | Expected Outcome |
|---------|------------|----------|------------------|
| IT-1 | A + B | [End-to-end scenario] | [Expected result] |
| | | | |

### 8.4 Test Execution Order

Recommended order to run tests during TDD:

1. [ ] UT-1 (Core functionality)
2. [ ] UT-2 (Secondary functionality)
3. [ ] EC-1, EC-2, EC-3 (Edge cases)
4. [ ] IT-1 (Integration)

## 9. Dependencies

### Requires (Blockers)
- [ ] REQ-XXX: [Description - must be completed first]
- [ ] External: [Any external dependency]

### Blocks (Dependents)
- [ ] REQ-YYY: [Description - depends on this requirement]

### Related Requirements
- REQ-ZZZ: [Related but not blocking]

## 10. Design Notes

### Architecture Impact
[Describe any architectural changes or considerations]

### API Changes
[Document any API additions/modifications]

```
# New endpoints
POST /api/v1/resource
GET /api/v1/resource/{id}
```

### Database Changes
[Document any schema changes]

```sql
-- New table or column
ALTER TABLE users ADD COLUMN new_field VARCHAR(255);
```

### Configuration Changes
[Document any new configuration options]

## 11. UI/UX Design (if applicable)

### Design System Integration
- [ ] Uses existing design tokens
- [ ] Follows accessibility guidelines (WCAG 2.1 AA)
- [ ] Responsive breakpoints defined

### Interaction Patterns
[Describe user interactions, animations, transitions]

### Accessibility Requirements
- [ ] Screen reader compatible
- [ ] Keyboard navigable
- [ ] Color contrast compliant
- [ ] Focus indicators visible

## 12. Performance Considerations

**PRINCIPLE**: "Premature optimization is the root of all bugs."

### Phase 1: Make It Work
Focus on correctness first. Implement the feature with clean, readable code.

### Phase 2: Make It Right
Refactor for maintainability. Apply proper patterns and abstractions.

### Phase 3: Make It Fast (ONLY if needed)
Optimize ONLY after:
- [ ] Feature is fully functional
- [ ] Tests pass and coverage is adequate
- [ ] Profiling shows actual bottleneck
- [ ] User reports performance issue

### Performance Targets (if identified)
| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| Response time | < X ms | [How to measure] |
| Memory usage | < X MB | [How to measure] |
| | | |

## 13. Out of Scope

Explicitly state what is NOT included:
- [Feature/behavior explicitly excluded]
- [Another exclusion]

## 14. Open Questions

Questions that need resolution before implementation:

1. [ ] [Question 1 - needs stakeholder input]
2. [ ] [Question 2 - technical decision needed]

## 15. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| [Risk 1] | High/Med/Low | High/Med/Low | [Mitigation strategy] |
| [Risk 2] | Med | Low | [Mitigation] |

## 16. Revision History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | YYYY-MM-DD | @author | Initial version |
| | | | |

---

## Approval

- [ ] **Product Owner**: @name - [Date]
- [ ] **Tech Lead**: @name - [Date]
- [ ] **Architect**: @name - [Date] (if architectural impact)

---

## GitHub Issue Checklist

When creating the DEV issue from this requirement, include this checklist:

```markdown
## Implementation Checklist

### Acceptance Criteria
- [ ] AC-1: [Criterion]
- [ ] AC-2: [Criterion]
- [ ] AC-3: [Criterion]

### Atomic Changes
- [ ] CHANGE-1: [Description]
- [ ] CHANGE-2: [Description]
- [ ] CHANGE-3: [Description]

### Tests (TDD - write BEFORE implementation)
- [ ] UT-1: [Test description]
- [ ] UT-2: [Test description]
- [ ] EC-1: [Edge case]
- [ ] IT-1: [Integration test]

### Final Verification
- [ ] All tests pass
- [ ] Code reviewed
- [ ] Documentation updated
```

---

*Template version: 2.0.0*
*Last updated: 2025-01-01*
