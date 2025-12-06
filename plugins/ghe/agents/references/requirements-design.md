# Requirements Design Reference

This reference covers Athena's requirements output format, domain detection, and domain-specific patterns (mathematical, game mechanics, financial/legal, distributed systems, security, UI/UX, API, data sources, assets).

## Athena's Output: Requirements Design Files

**CRITICAL**: Athena produces **REQUIREMENTS DESIGN FILES**, not code.

### ONLY Athena Creates Requirements

**No other agent creates requirements files. Only Athena.**

| Agent | Creates Requirements? | Role |
|-------|----------------------|------|
| **Athena** | **YES - ONLY ATHENA** | Translates user intent into precise specifications |
| Hephaestus | NO | Reads requirements, writes code |
| Artemis | NO | Tests against requirements |
| Hera | NO | Reviews against requirements |
| Themis | NO | Validates requirements exist |

### Requirements Are Free-Form

**CRITICAL**: Requirements are NOT constrained by templates.

Every domain has unique needs:
- **Mathematical specs** need formal notation, proofs, invariants
- **Game mechanics** need state machines, physics parameters, feel descriptions
- **Financial systems** need legal bounds, compliance protocols, audit trails
- **Distributed systems** need consistency models, failure modes, CAP tradeoffs
- **Security specs** need threat models, attack surfaces, trust boundaries
- **UI/UX features** need wireframes, accessibility, responsive behavior

**Athena writes requirements in whatever structure best serves the domain.**

The `ghe-design` skill and `REQ-TEMPLATE.md` provide **reference patterns**, not mandatory structures. Use what's relevant, ignore what's not, add what's missing.

### Mandatory Elements (Domain-Independent)

Despite free-form structure, every requirement MUST have:

1. **REQ-NNN**: Clear identification with version
2. **What**: Unambiguous description of what to build
3. **Why**: User story or business justification
4. **Acceptance**: Testable criteria to verify completion
5. **References**: Links to APIs, specs, assets, related issues

Everything else is domain-dependent.

### Philosophy: Performance

**"Premature optimization is the root of all bugs."**
- Specify WHAT, not HOW FAST
- Defer performance targets until feature works
- Optimize only when profiling reveals actual bottlenecks
- Requirements should focus on correctness first, performance second
- Add performance targets ONLY when profiling reveals bottlenecks
- Avoid speculative optimizations that complicate code

---

## Progressive Disclosure: Requirements Deep Dive

**Start simple. Reveal complexity only when needed.**

The following sections provide comprehensive guidance for writing requirements in specialized domains. Use them as references when the feature demands it.

### Skill References

Before writing requirements, consider invoking these skills:

| Skill | When to Use | What It Provides |
|-------|-------------|------------------|
| **ghe-design** | Any feature requiring requirements | Free-form requirements patterns, examples, templates (NOT constraints) |
| **Design style skill** | UI/UX features with visual design needs | Anthropic's design style guide for wireframes, accessibility, responsive behavior |
| **REQ-TEMPLATE.md** | Reference for requirements structure | Example structure (NOT mandatory - adapt as needed) |

**Trigger design style skill when:**
- User mentions "wireframe", "mockup", "visual design", "user interface"
- Feature involves user-facing UI components
- Accessibility (WCAG) compliance is needed
- Responsive design across devices is required

**Pattern**: Requirements should be DOMAIN-DRIVEN, not TEMPLATE-DRIVEN.

---

## Domain Detection & Specialized Requirements

**CRITICAL**: Detect the feature domain early. Different domains need fundamentally different requirement styles.

### Domain Detection Logic

When analyzing a feature request, identify its domain:

```
User Request → Domain Analysis → Specialized Requirements Pattern
```

| Domain Indicators | Domain Type | Specialized Requirements Needed |
|------------------|-------------|--------------------------------|
| "algorithm", "calculation", "mathematical" | **Mathematical/Algorithmic** | Formal notation, proofs, invariants, complexity bounds |
| "game", "physics", "collision", "animation" | **Game Mechanics** | State machines, physics parameters, feel descriptions, frame timing |
| "payment", "transaction", "compliance", "audit" | **Financial/Legal** | Legal bounds, compliance protocols, audit trails, regulatory references |
| "distributed", "cluster", "replication", "consistency" | **Distributed Systems** | CAP tradeoffs, consistency models, failure modes, partition tolerance |
| "authentication", "authorization", "encryption", "vulnerability" | **Security** | Threat models, trust boundaries, attack surfaces, cryptographic specs |
| "interface", "screen", "button", "layout", "responsive" | **UI/UX** | Wireframes, accessibility (WCAG), responsive breakpoints, user flows |
| "API", "endpoint", "webhook", "integration" | **API Integration** | Endpoint documentation, auth methods, rate limits, error codes |
| "dataset", "schema", "query", "migration" | **Data Systems** | Schema definitions, data pipelines, ETL processes, migration paths |
| "audio", "video", "3D", "image", "asset" | **Media/Assets** | Format specs, resolution, compression, asset references |

---

## Specialized Requirements Patterns

### Mathematical/Algorithmic Features

**When to use**: Computational algorithms, numerical processing, data structures, cryptography.

**Mandatory elements**:
```markdown
## Mathematical Specification

### Formal Definition
[Mathematical notation using LaTeX if complex]
f(x) = ∑(i=1 to n) w_i * x_i

### Invariants
- **INV-1**: Output range is bounded [min, max]
- **INV-2**: Function is monotonically increasing
- **INV-3**: Precision maintained within ε = 1e-6

### Complexity
- **Time**: O(n log n) worst case
- **Space**: O(n) auxiliary space
- **Correctness proof**: [Link to formal proof or reasoning]

### Edge Cases
- Empty input → default value
- NaN/Infinity → error with clear message
- Integer overflow → saturation or error

### Numerical Stability
[If floating-point operations involved]
- Precision requirements
- Rounding behavior
- Cancellation prevention strategies
```

**Example**: Sorting algorithm requirements
```markdown
## REQ-042: Stable Sort Implementation

### Mathematical Specification
Given array A[1..n], produce A'[1..n] such that:
- A'[i] ≤ A'[i+1] for all i ∈ [1, n-1]
- If A[i] = A[j] and i < j, then A'[i] appears before A'[j] (stability)

### Complexity Bounds
- **Time**: O(n log n) average and worst case
- **Space**: O(n) auxiliary (NOT in-place)

### Invariants
- **INV-1**: Length preserved: |A'| = |A|
- **INV-2**: Elements preserved: multiset(A') = multiset(A)
- **INV-3**: Stability maintained for equal elements
```

---

### Game Mechanics Features

**When to use**: Games, simulations, interactive physics, animations.

**Mandatory elements**:
```markdown
## Game Mechanics Specification

### State Machine
[Visual diagram or textual description]
States: {Idle, Running, Jumping, Falling, Landing}
Transitions:
- Idle → Running: on movement input
- Running → Jumping: on jump input (grounded)
- Jumping → Falling: when vertical velocity < 0
- Falling → Landing: on ground collision
- Landing → Idle: after 0.2s recovery

### Physics Parameters
| Parameter | Value | Unit | Tweakable? | Rationale |
|-----------|-------|------|-----------|-----------|
| Jump force | 12.0 | m/s | Yes | Feels responsive |
| Gravity | -30.0 | m/s² | No | Matches platform genre |
| Terminal velocity | -50.0 | m/s | Yes | Prevents falling too fast |
| Ground friction | 0.8 | coefficient | Yes | Snappy controls |

### Feel Description
**The jump should feel...**
- Responsive: instant feedback on button press
- Floaty at apex: hang time for mid-air corrections
- Weighty on descent: acceleration into landing
- Snappy on ground: quick transition to next action

### Frame Timing
- Input polling: every frame (60 FPS target)
- Physics update: fixed timestep (16.67ms)
- Animation blending: 0.1s crossfade between states

### Edge Cases
- Jump buffering: accept input 0.1s before landing
- Coyote time: allow jump 0.1s after leaving ledge
- Double-jump prevention: clear on landing only
```

---

### Financial/Legal Features

**When to use**: Payment processing, financial calculations, legal compliance, audit requirements.

**Mandatory elements**:
```markdown
## Legal & Compliance Specification

### Regulatory References
- **PCI-DSS**: v4.0 compliance for payment data handling
- **GDPR**: Article 17 (Right to erasure) for user data deletion
- **SOX**: Section 404 (Internal controls) for audit trails
- **[Jurisdiction]**: [Specific regulations]

### Compliance Protocols
| Requirement | Standard | Implementation | Verification |
|-------------|----------|----------------|--------------|
| Data encryption at rest | AES-256 | Database-level encryption | Annual audit |
| Access logging | NIST 800-53 | Immutable audit log | Real-time monitoring |
| Data retention | 7 years | Archive after 90 days | Automated policy |

### Audit Trail Requirements
**EVERY transaction MUST log**:
- Timestamp (UTC, millisecond precision)
- User ID (authenticated)
- Action type (CREATE/READ/UPDATE/DELETE)
- Resource affected (table.id)
- Previous state (JSON snapshot)
- New state (JSON snapshot)
- IP address
- Session ID
- Request ID (distributed tracing)

### Legal Bounds
- **Minimum age**: 18 years (verified via ID)
- **Maximum transaction**: $10,000 USD (AML compliance)
- **Data retention**: 7 years (tax law)
- **Breach notification**: 72 hours (GDPR)

### Compliance Verification
- [ ] Legal review completed (attach review doc)
- [ ] Security audit passed (attach audit report)
- [ ] Penetration testing completed (no critical findings)
- [ ] Privacy impact assessment filed
```

---

### Distributed Systems Features

**When to use**: Microservices, distributed databases, cluster management, replication.

**Mandatory elements**:
```markdown
## Distributed Systems Specification

### CAP Theorem Tradeoffs
**Chosen**: AP (Availability + Partition Tolerance)
**Sacrificed**: Strong consistency (eventual consistency accepted)

**Justification**: User-facing feature tolerates stale reads (up to 5s) but requires availability during network partitions.

### Consistency Model
- **Type**: Eventual consistency with causal ordering
- **Convergence time**: 5 seconds (99th percentile)
- **Conflict resolution**: Last-write-wins (LWW) with vector clocks
- **Acceptable staleness**: 5 seconds for reads

### Failure Modes

| Failure Type | Detection Time | Recovery Strategy | User Impact |
|--------------|----------------|-------------------|-------------|
| Node crash | 3s (heartbeat) | Redirect to replica | None (transparent) |
| Network partition | 10s (quorum loss) | Serve stale data with warning | Stale reads allowed |
| Split brain | 30s (quorum vote) | Fence minority partition | Partial unavailability |
| Data corruption | On read (checksum) | Restore from replica | Retry with backoff |

### Partition Tolerance
- **Quorum**: Majority (N/2 + 1) for writes
- **Read preference**: Nearest replica (stale reads acceptable)
- **Split-brain prevention**: Raft consensus (leader election)
- **Network partition behavior**: Serve reads (stale), reject writes (minority)

### Scalability Characteristics
- **Horizontal scaling**: Yes (add nodes dynamically)
- **Vertical scaling**: Limited (bounded by coordinator capacity)
- **Bottlenecks**: Coordinator node (single writer pattern)
- **Mitigation**: Sharding by user ID (consistent hashing)

### Observability Requirements
- Distributed tracing (OpenTelemetry)
- Latency percentiles (p50, p95, p99)
- Error rate per service
- Partition detection alerts
```

---

### Security Features

**When to use**: Authentication, authorization, encryption, security hardening.

**Mandatory elements**:
```markdown
## Security Specification

### Threat Model
**Assets**:
- User credentials (passwords, API keys)
- Personal data (email, profile)
- Session tokens (JWT)

**Threat Actors**:
- **External attacker**: Unauthenticated, attempts brute force, SQL injection
- **Malicious user**: Authenticated, attempts privilege escalation, data exfiltration
- **Compromised admin**: Insider threat, abuse of admin privileges

**Attack Vectors**:
1. Credential stuffing (leaked password databases)
2. Session hijacking (XSS, token theft)
3. Privilege escalation (IDOR, broken access control)
4. Data exfiltration (SQL injection, API abuse)

### Trust Boundaries
```
UNTRUSTED                           TRUSTED
│                                   │
User Input ──► Validation Layer ───► Business Logic ──► Database
│              (sanitize, validate) │  (authorized)   │  (encrypted)
│                                   │                 │
Public API ──► Authentication ──────► Internal API ───► Secrets Store
│              (JWT verify)         │  (mTLS)        │  (vault)
```

### Attack Surfaces
| Surface | Exposure | Mitigations |
|---------|----------|-------------|
| Public API | Internet-facing | Rate limiting, WAF, input validation |
| Admin panel | Internal network | VPN-only, MFA required, audit logging |
| Database | Private subnet | Encryption at rest, least privilege, no direct access |
| Session tokens | Cookie (HttpOnly) | Short expiry (15min), refresh rotation, CSRF protection |

### Cryptographic Specifications
- **Password hashing**: Argon2id (m=64MB, t=3, p=4)
- **Token signing**: HMAC-SHA256 (256-bit key)
- **Data encryption**: AES-256-GCM (authenticated encryption)
- **TLS**: TLS 1.3 only (no TLS 1.2, disable weak ciphers)

### Security Controls
- [ ] Input validation (whitelist, escape, sanitize)
- [ ] Output encoding (context-aware escaping)
- [ ] Authentication (multi-factor for admin)
- [ ] Authorization (principle of least privilege)
- [ ] Rate limiting (per-user, per-IP)
- [ ] Audit logging (immutable, tamper-proof)
- [ ] Secret management (vault, rotation)
- [ ] Security headers (CSP, HSTS, X-Frame-Options)

### Penetration Testing Requirements
- **Scope**: Full application (API + frontend)
- **Methodology**: OWASP Top 10 + custom business logic
- **Acceptance**: No critical/high findings
- **Report**: Attach findings + remediation plan
```

---

### UI/UX Features

**When to use**: User interfaces, visual design, interaction patterns, accessibility.

**Trigger design style skill**: When user mentions wireframes, mockups, visual design.

**Mandatory elements**:
```markdown
## UI/UX Specification

### Wireframes
[Attach wireframe images or ASCII art for simple layouts]

**Desktop Layout** (1920x1080):
┌────────────────────────────────────────┐
│ [Logo]  Navigation  [User]  [Settings]│
├────────────────────────────────────────┤
│ ┌────────────┐ ┌──────────────────────┐│
│ │  Sidebar   │ │   Main Content       ││
│ │            │ │                      ││
│ │  - Item 1  │ │  [Title]             ││
│ │  - Item 2  │ │  [Description...]    ││
│ │  - Item 3  │ │                      ││
│ └────────────┘ └──────────────────────┘│
└────────────────────────────────────────┘

**Mobile Layout** (375x667):
┌──────────────────┐
│ [☰]  [Logo]  [⚙]│
├──────────────────┤
│  [Title]         │
│  [Description...]│
│                  │
│  [Action Button] │
├──────────────────┤
│ Bottom Nav       │
└──────────────────┘

### Accessibility (WCAG 2.1 Level AA)
| Criterion | Requirement | How to Verify |
|-----------|-------------|---------------|
| **1.4.3 Contrast** | 4.5:1 minimum for text | Use contrast checker tool |
| **2.1.1 Keyboard** | All functionality via keyboard | Tab through all elements |
| **2.4.7 Focus Visible** | Clear focus indicators | Inspect :focus styles |
| **4.1.2 Name, Role, Value** | Proper ARIA labels | Screen reader testing |

**ARIA Labels**:
- Buttons: `aria-label="Close dialog"` (when icon-only)
- Forms: `aria-labelledby` for inputs + labels
- Live regions: `aria-live="polite"` for status updates
- Landmarks: `<nav>`, `<main>`, `<aside>` (semantic HTML)

### Responsive Breakpoints
| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| Mobile | 320px - 767px | Single column, hamburger menu, stacked content |
| Tablet | 768px - 1023px | Two columns, collapsible sidebar, touch targets 44px |
| Desktop | 1024px+ | Multi-column, hover states, keyboard shortcuts |

### Interaction Patterns
**Loading States**:
- Initial load: Skeleton screens (avoid spinners if >1s)
- Button actions: Disable + spinner inside button (preserve layout)
- Errors: Toast notifications (auto-dismiss 5s) + persistent banner for critical

**Form Validation**:
- On blur: Validate field (show errors immediately)
- On submit: Validate all fields (focus first error)
- Error messages: Below field (red text + icon)
- Success states: Green checkmark (transient)

### User Flows
```
1. User Authentication Flow
   START → [Login page] → [Enter credentials] → [2FA prompt] → [Dashboard]
           ↓ (forgot pwd)
           [Reset email] → [Check email] → [New password] → [Login page]

2. Purchase Flow
   [Browse] → [Add to cart] → [Review cart] → [Checkout] → [Payment] → [Confirmation]
              ↓ (continue shopping)
              [Browse]
```

### Visual Design Requirements (if design style skill invoked)
**Color Palette**:
- Primary: #3B82F6 (blue, interactive elements)
- Secondary: #8B5CF6 (purple, accents)
- Success: #10B981 (green, confirmations)
- Error: #EF4444 (red, destructive actions)
- Warning: #F59E0B (amber, caution)
- Neutral: #6B7280 (gray, text)

**Typography**:
- Headings: Inter, 700 weight, 24px/32px/40px
- Body: Inter, 400 weight, 16px line-height 1.5
- Code: Fira Code, 400 weight, 14px

**Spacing**:
- Base unit: 8px (all spacing multiples of 8)
- Component padding: 16px (2 units)
- Section margins: 32px (4 units)

**Animations**:
- Micro-interactions: 200ms ease-out (hover, focus)
- Transitions: 300ms ease-in-out (page changes)
- Loading: 500ms delay before showing spinner (avoid flashing)
```

---

### API Integration Features

**When to use**: External API integrations, webhooks, third-party services.

**Mandatory elements**:
```markdown
## API Integration Specification

### API Endpoints
| Endpoint | Method | Purpose | Rate Limit |
|----------|--------|---------|------------|
| `/v1/users` | GET | List users | 100/min |
| `/v1/users/{id}` | GET | Get user details | 1000/min |
| `/v1/users` | POST | Create user | 10/min |
| `/v1/users/{id}` | PUT | Update user | 50/min |
| `/v1/users/{id}` | DELETE | Delete user | 10/min |

**Base URL**: `https://api.example.com`
**API Version**: v1 (deprecation: v0 sunset 2026-01-01)

### Authentication Methods
**Primary**: OAuth 2.0 (Authorization Code Flow with PKCE)
```
1. Redirect to /oauth/authorize?client_id=XXX&redirect_uri=YYY&code_challenge=ZZZ
2. User authorizes → redirected to redirect_uri?code=ABC
3. Exchange code for token: POST /oauth/token {code, code_verifier}
4. Store access_token (1h expiry) + refresh_token (30d expiry)
5. Use: Authorization: Bearer {access_token}
6. Refresh: POST /oauth/refresh {refresh_token} → new access_token
```

**Fallback**: API Key (for server-to-server)
```
Header: X-API-Key: {api_key}
Rotation: Every 90 days (automated)
Storage: Environment variable (never commit)
```

### Rate Limits
| Tier | Requests/minute | Burst | Handling |
|------|-----------------|-------|----------|
| Free | 60 | 10 | HTTP 429 + Retry-After header |
| Pro | 600 | 100 | Same |
| Enterprise | 6000 | 1000 | Same |

**Rate Limit Headers**:
- `X-RateLimit-Limit`: Total allowed
- `X-RateLimit-Remaining`: Requests left
- `X-RateLimit-Reset`: Unix timestamp when limit resets

**Retry Strategy**:
- 429 (rate limit): Exponential backoff (1s, 2s, 4s, 8s, give up)
- 5xx (server error): Retry 3x with jitter
- 4xx (client error): No retry (log + alert)

### Error Codes
| Code | Meaning | Client Action |
|------|---------|---------------|
| 400 | Bad request (invalid JSON) | Fix request format |
| 401 | Unauthorized (missing/invalid token) | Re-authenticate |
| 403 | Forbidden (insufficient permissions) | Request access |
| 404 | Not found | Verify resource exists |
| 429 | Rate limited | Exponential backoff |
| 500 | Internal server error | Retry with backoff |
| 503 | Service unavailable | Retry with backoff |

**Error Response Format**:
```json
{
  "error": {
    "code": "INVALID_INPUT",
    "message": "Field 'email' is required",
    "field": "email",
    "request_id": "req_abc123"
  }
}
```

### API Documentation
- **Official docs**: https://docs.example.com/api/v1
- **OpenAPI spec**: https://api.example.com/openapi.json
- **Postman collection**: [Link to collection]
- **SDK**: https://github.com/example/sdk-js

### Webhooks (if applicable)
**Endpoint**: User provides URL
**Events**: `user.created`, `user.updated`, `user.deleted`
**Payload**:
```json
{
  "event": "user.created",
  "timestamp": "2025-01-15T10:30:00Z",
  "data": { "id": 123, "email": "user@example.com" }
}
```

**Verification**: HMAC-SHA256 signature in `X-Webhook-Signature` header
**Retry**: 3 attempts (1min, 10min, 1h delays)

### Testing Strategy
- **Sandbox environment**: https://sandbox.example.com/api/v1
- **Test credentials**: Provided in developer portal
- **Mock server**: Use Postman Mock or WireMock for CI/CD
```

---

### Data Sources & Database Features

**When to use**: Database schemas, data migrations, ETL pipelines, datasets.

**Mandatory elements**:
```markdown
## Data Sources Specification

### Database Schema
**Tables**:

**users**
| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| id | BIGSERIAL | PRIMARY KEY | Clustered | Auto-incrementing ID |
| email | VARCHAR(255) | UNIQUE NOT NULL | B-tree | User email (login) |
| password_hash | VARCHAR(255) | NOT NULL | - | Argon2id hash |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | B-tree | Account creation |
| updated_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | - | Last modification |
| deleted_at | TIMESTAMPTZ | NULL | Partial (WHERE deleted_at IS NOT NULL) | Soft delete |

**sessions**
| Column | Type | Constraints | Index | Description |
|--------|------|-------------|-------|-------------|
| id | UUID | PRIMARY KEY | Clustered | Session ID |
| user_id | BIGINT | FK(users.id) NOT NULL | B-tree | Owner |
| expires_at | TIMESTAMPTZ | NOT NULL | B-tree | Expiry time |
| created_at | TIMESTAMPTZ | NOT NULL DEFAULT NOW() | - | Session start |

**Relationships**:
- users 1 ─→ N sessions (one user, many sessions)

**Indexes**:
- `idx_users_email`: B-tree on users(email) - fast login lookups
- `idx_sessions_expires`: B-tree on sessions(expires_at) - cleanup expired sessions
- `idx_sessions_user_id`: B-tree on sessions(user_id) - user's active sessions

### Data Migration Path
**Current State**: PostgreSQL 14, schema v1 (single users table)
**Target State**: PostgreSQL 16, schema v2 (users + sessions)

**Migration Steps**:
1. **Schema changes** (DDL):
   - Create `sessions` table
   - Add `deleted_at` to `users` (soft delete)
   - Create indexes
2. **Data migration** (DML):
   - Migrate existing sessions from Redis to `sessions` table
   - Backfill `deleted_at` = NULL for active users
3. **Rollback plan**:
   - Keep Redis sessions for 7 days (dual-write during migration)
   - If issues, revert code to read from Redis

**Migration Script**: `migrations/v2_sessions_table.sql`
**Estimated duration**: 2 hours (15M users)
**Downtime**: Zero (blue-green deployment)

### ETL Processes (if applicable)
**Pipeline**: User analytics ETL (daily)
1. **Extract**: Query production DB (read replica) for yesterday's signups
2. **Transform**: Aggregate by country, device type
3. **Load**: Insert into data warehouse (Snowflake)

**Schedule**: Daily at 2 AM UTC
**Tools**: Apache Airflow (DAG: `user_analytics_etl`)
**Monitoring**: PagerDuty alert if job fails

### Datasets (if applicable)
**Training Data**: User behavior dataset
- **Source**: Production logs (anonymized)
- **Size**: 500 GB (1 year)
- **Format**: Parquet (columnar)
- **Location**: S3 bucket `s3://company/datasets/user-behavior/`
- **Schema**: [Link to schema docs]
- **Access**: IAM role `data-scientist` (read-only)

### Data Quality Requirements
- **Completeness**: No NULL in required fields (validated on insert)
- **Uniqueness**: Email unique per user (DB constraint)
- **Accuracy**: Phone numbers validated with regex
- **Consistency**: Foreign keys enforced (cascading deletes)
- **Timeliness**: Replicas lag < 1 second (monitored)
```

---

### Asset Management Features

**When to use**: Media assets (audio, video, images, 3D models, fonts).

**Mandatory elements**:
```markdown
## Asset Management Specification

### Audio Assets
| Asset | Format | Sample Rate | Bit Depth | Duration | Size | Purpose |
|-------|--------|-------------|-----------|----------|------|---------|
| `background_music.mp3` | MP3 (320kbps) | 44.1 kHz | 16-bit | 3:45 | 8.5 MB | Menu background |
| `jump_sound.wav` | WAV (uncompressed) | 48 kHz | 24-bit | 0.2s | 200 KB | Player jump SFX |
| `ambient_forest.ogg` | OGG Vorbis (q7) | 44.1 kHz | - | Loop | 4.2 MB | Forest ambience |

**Asset Location**: `assets/audio/`
**Streaming**: Use for background music >1 MB (load on demand)
**Preloading**: SFX < 500 KB (load at startup)

### Video Assets
| Asset | Format | Resolution | FPS | Duration | Codec | Size | Purpose |
|-------|--------|------------|-----|----------|-------|------|---------|
| `intro_cutscene.mp4` | MP4 | 1920x1080 | 30 | 1:30 | H.264 | 45 MB | Intro sequence |
| `tutorial.webm` | WebM | 1280x720 | 60 | 2:00 | VP9 | 25 MB | Tutorial video |

**Asset Location**: `assets/video/`
**Compression**: CRF 23 (H.264), CRF 30 (VP9)
**Fallback**: Provide MP4 for Safari (WebM not supported)

### Image Assets
| Asset | Format | Resolution | Compression | Size | Purpose |
|-------|--------|------------|-------------|------|---------|
| `logo.svg` | SVG | Vector | - | 5 KB | Scalable logo |
| `hero_banner.jpg` | JPEG | 1920x600 | 85% quality | 120 KB | Hero image |
| `icon_sprite.png` | PNG-8 | 512x512 | Indexed (256 colors) | 15 KB | UI icon sprite |
| `profile_photo.webp` | WebP | 400x400 | 80% quality | 25 KB | User avatars |

**Asset Location**: `assets/images/`
**Responsive Images**:
- Desktop: 1920px width (hero_banner@2x.jpg)
- Tablet: 1024px width (hero_banner@1x.jpg)
- Mobile: 640px width (hero_banner_mobile.jpg)

**Lazy Loading**: All images below fold (loading="lazy" attribute)

### 3D Model Assets
| Asset | Format | Polygons | Textures | Size | Purpose |
|-------|--------|----------|----------|------|---------|
| `character.glb` | glTF 2.0 Binary | 15K tris | 2K diffuse + normal | 2.5 MB | Player model |
| `environment.gltf` | glTF 2.0 JSON | 50K tris | 4K diffuse | 8.0 MB | Game world |

**Asset Location**: `assets/models/`
**LOD Levels**: 3 (high/medium/low detail based on distance)
**Format**: glTF 2.0 (Khronos standard, widely supported)

### Font Assets
| Font | Format | Weights | License | Size | Purpose |
|------|--------|---------|---------|------|---------|
| `Inter.woff2` | WOFF2 | 400, 700 | OFL | 250 KB | UI text |
| `FiraCode.woff2` | WOFF2 | 400 | OFL | 180 KB | Code snippets |

**Asset Location**: `assets/fonts/`
**Subsetting**: Latin charset only (reduce size by 70%)
**Loading**: `font-display: swap` (avoid FOIT)

### Asset Delivery
- **CDN**: CloudFront (global edge caching)
- **Cache headers**: `Cache-Control: public, max-age=31536000, immutable` (1 year)
- **Versioning**: Filename hashing (`logo.a3f9c2.svg`) for cache busting
- **Compression**: Brotli for text assets (SVG, JSON), gzip fallback

### Asset References in Code
**Absolute paths** (not relative):
- ✅ `const logo = '/assets/images/logo.svg'`
- ❌ `const logo = '../images/logo.svg'`

**Asset manifest** (for versioned filenames):
```json
{
  "logo.svg": "/assets/images/logo.a3f9c2.svg",
  "hero_banner.jpg": "/assets/images/hero_banner.f8d1e4.jpg"
}
```
```

---

### External GitHub Issues References

**When to use**: Feature depends on work from another project, or references external bugs/enhancements.

**Mandatory elements**:
```markdown
## External Dependencies

### GitHub Issues from Other Projects
| Issue | Project | Status | Why It Matters | Blocking? |
|-------|---------|--------|---------------|-----------|
| user/repo#123 | `user/repo` | Open | Upstream bug affects our API integration | **YES** (blocker) |
| org/lib#456 | `org/lib` | Closed (merged) | Feature we need is now available in v2.3.0 | No |
| example/tool#789 | `example/tool` | In Progress | Performance improvement we're waiting for | No (workaround exists) |

**Monitoring**:
- Subscribe to blocking issues (GitHub notifications)
- Weekly check for status updates
- Fallback plan if blocked issue stalls

**Communication**:
- Comment on external issue: "We're tracking this for our feature [link]"
- Tag issue in our requirements: `blocked-by:user/repo#123` label

### Related Work in Our Project
| Issue | Relationship | Why It Matters |
|-------|--------------|----------------|
| #42 | Prerequisite | Must complete authentication before authorization |
| #56 | Parallel | Can develop simultaneously (different components) |
| #78 | Conflicting | Refactors same code (coordinate with owner) |

**Dependency Graph**:
```
#42 (Auth) ──► #THIS (Authz) ──► #99 (Admin Panel)
               ▲
               │
               #56 (Logging - parallel)
```
```
