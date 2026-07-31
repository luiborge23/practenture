# PRD: Practenture Auth Modernization — SOTA Multi-Tenant Authentication

**Date:** 2026-07-11  
**Last implementation update:** 2026-07-31
**Research basis:** RALPH 13-step methodology, SOTA analysis of 8 major auth platforms (Descope, Auth0, WorkOS, Frontegg, Ory, Keycloak, Cognito, SuperTokens) + LMS multi-tenancy patterns

---

## 0. Current implementation status

The tables and unchecked acceptance criteria below preserve the original July 11 gap analysis. They are not the current production-status dashboard.

As of release `1abb1aaee2dd49b59790a4b3c232cacdb3e2848a`:

- password storage uses bcrypt with equalized legacy-hash migration paths;
- durable login and Administrator MFA throttling are implemented;
- Admin V2 uses opaque, revocable, CSRF-protected sessions;
- immutable redacted administrative audit events are implemented;
- organizations, memberships, Professor invitation lifecycle, account status, health, backup, restore-drill, and scoped-cleanup controls are implemented;
- Administrator TOTP enrollment, login challenge, replay protection, hashed one-time recovery codes, regeneration, disablement, and reauthentication are implemented and active in production;
- all 502 local backend/release tests and all five exact-SHA CI jobs passed, including mandatory iOS Golden Formula parity, with zero GitHub Check annotations.

The authoritative Administrator MFA design is [`architecture/ADMIN_MFA_LLD.md`](architecture/ADMIN_MFA_LLD.md).

---

## 1. Deep Research Summary

### Current State (83/83 tests passing)

| Feature | Status | SOTA Comparison |
|---------|--------|-----------------|
| Multi-tenant isolation | ✅ Working (app-level) | SOTA uses DB-level RLS |
| Role-based access | ✅ 3 roles (owner/professor/student) | SOTA uses per-tenant roles + permissions |
| JWT auth | ✅ HS256, 24h expiry | SOTA uses RS256, short access + rotating refresh |
| Password hashing | ⚠️ SHA-256 (no salt) | SOTA uses bcrypt/argon2id |
| Professor code redemption | ✅ Working | SOTA uses invite links with expiry + email binding |
| Apple/Google OAuth | ✅ Working | SOTA matches (PKCE for native apps) |
| `must_change_password` | ✅ Working | SOTA matches |
| Audit logging | ❌ Missing | SOTA requires per-tenant audit trail |
| Rate limiting | ❌ Missing | SOTA requires login + redemption rate limiting |
| Refresh tokens | ❌ Missing | SOTA uses rotating refresh tokens |

### Priority Matrix

| Gap | Severity | Effort | User Stories |
|-----|----------|--------|--------------|
| SHA-256 → bcrypt | P0 Critical | Low | US-001 |
| Login rate limiting | P0 Critical | Low | US-002 |
| Code expiry + rate limiting | P1 High | Medium | US-003 |
| Audit logging | P1 High | Medium | US-004 |
| Organizations + memberships table | P1 High | High | US-005, US-006 |
| JWT tenantId + roles array | P2 Medium | Medium | US-007 |
| Refresh tokens | P2 Medium | Medium | US-008 |
| Password complexity validation | P2 Medium | Low | US-009 |

---

## 2. Goals

1. **Eliminate P0 security risks** — replace SHA-256 with bcrypt, add login rate limiting
2. **Harden professor codes** — add expiry, rate limiting, email binding option
3. **Add audit trail** — every auth event logged for compliance
4. **Evolve toward organization model** — prepare schema for multi-org membership
5. **Maintain backward compatibility** — existing 83 tests must still pass

## 3. Non-Goals

- Migrating from SQLite to PostgreSQL (future phase)
- Implementing SAML SSO (enterprise feature, not needed for classroom)
- Implementing SCIM provisioning (enterprise feature)
- Requiring MFA for student classroom accounts; Administrator MFA is implemented as a separate privileged-control-plane requirement
- Changing the iOS client auth flow (keep same API contract)

---

## 4. User Stories

### US-001: Replace SHA-256 with bcrypt password hashing
**Description:** As a security-conscious developer, I want passwords hashed with bcrypt so that if the DB leaks, passwords are not trivially crackable.

**Acceptance Criteria:**
- [ ] Add `bcrypt` to requirements.txt (or use passlib[bcrypt])
- [ ] Create `hash_password(plain) -> str` and `verify_password(plain, hash) -> bool` helpers
- [ ] Update `create_user`, `upsert_user`, `verify_user` to use bcrypt
- [ ] Add migration path: on login, if hash looks like SHA-256 (64 hex chars), re-hash with bcrypt
- [ ] All 83 existing tests pass
- [ ] New test: bcrypt hash is not 64 hex chars (verify it's bcrypt format)

**Priority:** 1

---

### US-002: Add login rate limiting (5 attempts → 15min lockout)
**Description:** As a security-conscious developer, I want to rate-limit login attempts to prevent brute-force attacks.

**Acceptance Criteria:**
- [ ] Add `login_attempts` table: (username, attempts, last_attempt_at, locked_until)
- [ ] After 5 failed attempts, lock account for 15 minutes
- [ ] Reset counter on successful login
- [ ] Return 429 Too Many Requests with `Retry-After` header when locked
- [ ] Add test: 5 wrong passwords → 6th attempt gets 429
- [ ] Add test: correct password during lockout → still 429
- [ ] Add test: after 15 min, login works again
- [ ] All 83 existing tests pass

**Priority:** 2

---

### US-003: Add expiry + rate limiting to professor codes
**Description:** As an admin, I want professor codes to expire after 7 days and be rate-limited so they can't be brute-forced.

**Acceptance Criteria:**
- [ ] Add `expires_at` column to `professor_codes` table (default 7 days from creation)
- [ ] Add `max_uses` column (default 1)
- [ ] `validate_professor_code` rejects expired codes
- [ ] Add rate limiting on `/api/professor/redeem` (max 10 attempts per IP per hour)
- [ ] Add test: expired code → 404
- [ ] Add test: valid code within 7 days → 200
- [ ] All 83 existing tests pass

**Priority:** 3

---

### US-004: Add audit logging table
**Description:** As an admin, I want an audit trail of all auth events so I can investigate security incidents.

**Acceptance Criteria:**
- [ ] Create `audit_logs` table: (id, actor_username, action, details, ip_address, timestamp)
- [ ] Log events: login_success, login_failure, code_created, code_redeemed, class_created, session_started, password_changed
- [ ] Add `GET /api/audit` endpoint (owner only) with pagination
- [ ] Add test: login produces audit log entry
- [ ] Add test: code redemption produces audit log entry
- [ ] All 83 existing tests pass

**Priority:** 4

---

### US-005: Add organizations table (schema prep, no behavior change)
**Description:** As a developer, I want an organizations table so that the schema is ready for multi-org membership in a future phase.

**Acceptance Criteria:**
- [ ] Create `organizations` table: (id, name, university_name, created_by, created_at)
- [ ] Create `memberships` table: (id, user_id, org_id, role, created_at)
- [ ] When a professor creates a class, auto-create an organization for their university_name if one doesn't exist
- [ ] Auto-create a membership (professor, role=professor) for the class creator
- [ ] This is schema-only — don't change existing query logic yet
- [ ] All 83 existing tests pass (no behavior change)

**Priority:** 5

---

### US-006: Add `tenantId` to JWT claims
**Description:** As a developer, I want the JWT to contain a tenantId so that downstream services can enforce tenant isolation from the token, not just application logic.

**Acceptance Criteria:**
- [ ] Add `tenantId` to JWT payload (derived from the user's primary organization)
- [ ] For professors: tenantId = their organization id
- [ ] For students: tenantId = empty (they can belong to multiple)
- [ ] For owner: tenantId = "platform"
- [ ] Update `_verify_token` to extract and return tenantId
- [ ] Add test: professor JWT contains tenantId
- [ ] Add test: student JWT has no tenantId (or empty)
- [ ] All 83 existing tests pass

**Priority:** 6

---

### US-007: Add refresh tokens
**Description:** As a mobile user, I want my session to last longer than 24h without re-entering my password, using rotating refresh tokens.

**Acceptance Criteria:**
- [ ] Add `refresh_tokens` table: (id, user_id, token_hash, expires_at, created_at, rotated_from)
- [ ] Issue access token (15min) + refresh token (7 days) on login
- [ ] Add `POST /api/auth/refresh` endpoint
- [ ] On refresh: validate old token, issue new pair, mark old token as rotated
- [ ] If a rotated token is used again → token theft detected → revoke all user sessions
- [ ] Add test: refresh produces new access + refresh tokens
- [ ] Add test: old refresh token after rotation → 401
- [ ] Add test: reusing rotated token → all sessions revoked
- [ ] All 83 existing tests pass (with updated login response)

**Priority:** 7

---

### US-008: Password complexity validation
**Description:** As a developer, I want password complexity requirements so that users can't set weak passwords.

**Acceptance Criteria:**
- [ ] Minimum 8 characters
- [ ] At least 1 uppercase, 1 lowercase, 1 digit, 1 special char
- [ ] Reject passwords in common breach list (top 1000: password, 123456, etc.)
- [ ] Apply on: registration, password change, pre-create
- [ ] Return 400 with specific error message explaining which requirement failed
- [ ] Add test: weak password rejected with specific message
- [ ] Add test: strong password accepted
- [ ] All 83 existing tests pass (update test passwords if needed)

**Priority:** 8

---

### US-009: Add CORS hardening
**Description:** As a security-conscious developer, I want CORS restricted to the actual iOS app and known origins instead of `*`.

**Acceptance Criteria:**
- [ ] Replace `allow_origins=["*"]` with configured list
- [ ] Default: `["http://localhost:*", "capacitor://*", "http://localhost"]` for iOS
- [ ] Configurable via `PRACTENTURE_CORS_ORIGINS` env var
- [ ] Add test: request from unknown origin → CORS rejected
- [ ] All 83 existing tests pass

**Priority:** 9

---

## 5. Functional Requirements

- FR-1: Passwords MUST be hashed with bcrypt (cost factor 12)
- FR-2: Login MUST rate-limit after 5 failures (15-min lockout)
- FR-3: Professor codes MUST expire after 7 days
- FR-4: All auth events MUST be logged to audit_logs
- FR-5: JWT MUST include `tenantId` claim for professors
- FR-6: Refresh tokens MUST rotate on use; reuse = theft detection
- FR-7: All changes MUST maintain backward compatibility with 83 existing tests

## 6. Technical Considerations

- **bcrypt on t3.micro**: ~100ms per hash — acceptable for login. Use cost factor 12.
- **SQLite + bcrypt**: No issue, bcrypt is pure Python/C.
- **Migration path**: On login, detect SHA-256 hashes (64 hex chars) and silently re-hash with bcrypt. Zero downtime.
- **No breaking iOS changes**: Login response shape stays the same. New fields are additive (refreshToken, tenantId).

## 7. Success Metrics

- All 83 existing tests pass after every story
- bcrypt hashing: verify no SHA-256 hashes remain after all users have logged in
- Rate limiting: 6th login attempt returns 429 within 1ms
- Audit logs: every auth event produces exactly 1 log entry

## 8. Administrator MFA requirement — delivered

**User story:** As the platform Administrator, I require a second factor so a stolen password cannot immediately expose the privileged control plane.

**Acceptance criteria:**

- [x] Enrollment creates a pending encrypted seed and does not enable MFA before valid TOTP confirmation.
- [x] Setup is resumable without silently replacing a seed already scanned by the Administrator.
- [x] Login uses an opaque, expiring, single-use MFA challenge and creates the privileged session only after factor verification.
- [x] TOTP counters and recovery codes enforce one-winner semantics under concurrent requests.
- [x] Recovery codes are disclosed only at creation/regeneration and stored only as hashes.
- [x] Setup, regeneration, disablement, and reauthentication require CSRF plus current password/current factor as appropriate.
- [x] Password and factor checks are inside durable account-wide throttling boundaries.
- [x] Successful management and challenge verification reset applicable throttle reservations rather than accumulating toward self-lockout.
- [x] Active session, active Owner account, and current password are rechecked transactionally with sensitive state changes.
- [x] Seeds, passwords, OTPs, recovery codes, cookies, and CSRF values are absent from logs, audit metadata, and persistent browser storage.
- [x] Production enrollment and a fresh password-plus-TOTP login were verified without consuming a recovery code.
