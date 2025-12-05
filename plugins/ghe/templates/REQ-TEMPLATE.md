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

## 5. Atomic Changes

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

## 6. Test Requirements

For each atomic change, define the test requirements:

- **TEST-1** for CHANGE-1: [What specifically to test]
  - Input: [test input]
  - Expected: [expected output/behavior]

- **TEST-2** for CHANGE-2: [What to test]
  - Input: [test input]
  - Expected: [expected output]

- **TEST-3** for CHANGE-3: [What to test]
  - Edge case: [describe edge case]
  - Expected: [expected behavior]

### Integration Tests
- **ITEST-1**: [End-to-end scenario to test]

## 7. Dependencies

### Requires (Blockers)
- [ ] REQ-XXX: [Description - must be completed first]
- [ ] External: [Any external dependency]

### Blocks (Dependents)
- [ ] REQ-YYY: [Description - depends on this requirement]

### Related Requirements
- REQ-ZZZ: [Related but not blocking]

## 8. Design Notes

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

## 9. Out of Scope

Explicitly state what is NOT included:
- [Feature/behavior explicitly excluded]
- [Another exclusion]

## 10. Open Questions

Questions that need resolution before implementation:

1. [ ] [Question 1 - needs stakeholder input]
2. [ ] [Question 2 - technical decision needed]

## 11. Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| [Risk 1] | High/Med/Low | High/Med/Low | [Mitigation strategy] |
| [Risk 2] | Med | Low | [Mitigation] |

## 12. Revision History

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

*Template version: 1.0.0*
*Last updated: 2024-01-01*
