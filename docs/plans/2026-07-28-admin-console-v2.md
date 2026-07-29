# Practenture Admin Console V2 — Architecture, LLD, and Implementation Plan

> **Execution:** Use subagent-driven development with TDD, spec review, code-quality review, and controller-run integration gates.

**Goal:** Replace the incomplete `practenture.com/admin` console with a secure, complete, responsive Owner control plane while preserving all simulation behavior and production data.

**Architecture:** Build V2 beside the legacy implementation under a dedicated `/api/admin/v2` boundary and initially expose its UI at `/admin-v2`. V2 uses typed FastAPI routes, domain services, repositories, explicit transactions, immutable audit events, and server-managed sessions. Production cutover changes only the `/admin` UI route after V2 passes backup, migration, security, E2E, browser, and rollback gates.

**Tech stack:** Existing FastAPI/Pydantic/SQLite backend, Jinja shell with modular vanilla JavaScript/CSS (no new Node build dependency), pytest/TestClient, Playwright or browser automation, Alembic migrations, nginx, Docker Compose.

---

## 1. Frozen Scope

### In scope

1. Owner authentication, logout, session expiry, forced password change, and recovery.
2. Dashboard overview and operational health.
3. Organizations.
4. Professor invitation lifecycle.
5. Professor/staff account creation and management.
6. User search, status, suspension, reactivation, and forced password reset.
7. Sessions read-only operational visibility.
8. Immutable redacted audit trail and export.
9. Verified backup status, restore-drill evidence, and database health.
10. Scoped, backup-gated cleanup plans.
11. Responsive desktop/tablet/mobile UI, accessibility, errors, loading, and empty states.
12. Nginx routing, deployment, observability, rollback, and end-to-end tests.

### Explicitly out of scope

- Simulation formulas, scenario packs, iOS API contracts, professor gameplay, student gameplay, or production record rewriting.
- Arbitrary SQL, generic “delete all,” remote shell, secret viewing, or editing historical audit records.
- Migration to PostgreSQL during this rebuild. V2 must use repositories so that migration remains possible later.

### Preservation rules

- No existing table or column is removed during V2 introduction.
- Existing records are never bulk transformed without a reviewed migration preflight and verified online backup.
- Legacy `/api/admin` and `/admin` stay available until V2 acceptance passes.
- Unrelated dirty files in the current `implement-wearable` worktree must not be overwritten, reverted, staged, or committed by this project.

---

## 2. Current-State Findings Driving the Rebuild

1. Two frontend generations coexist: `dashboard.js`/`admin_dashboard.html` and `admin.js`/new static assets.
2. Legacy UI response assumptions conflict with backend envelopes.
3. Navigation and account creation workflows are incomplete or placeholders.
4. `/api/` nginx rewriting can remove the API prefix from canonical backend routes.
5. `/health`, `/openapi.json`, and `/docs` are shadowed by the marketing SPA.
6. Password recovery currently has an unauthenticated reset path without a recovery token.
7. Owner/admin behavior is mixed across `main.py`, `routers/owner_admin.py`, `routers/owner_audit.py`, existing professor routes, templates, and scripts.
8. Audit routes overlap and use multiple persistence concepts (`audit_logs` and `audit_events`).
9. `database.py` mixes schema creation, runtime schema evolution, repositories, and domain behavior.
10. Existing Admin tests prove only page rendering and two unauthenticated denials; they do not prove successful workflows.
11. Current Admin work is uncommitted on the `implement-wearable` branch, together with unrelated changes, so V2 needs isolated ownership and commits.

---

## 3. Target Architecture

```text
Browser
  |
  | HTTPS + Secure/HttpOnly/SameSite cookie + CSRF token
  v
nginx
  |-- /admin-v2, /admin-v2/*  -> FastAPI Admin V2 UI
  |-- /api/admin/v2/*         -> FastAPI Admin V2 API (prefix preserved)
  |-- /api/*                  -> existing canonical API (prefix preserved)
  `-- /*                      -> marketing site

FastAPI Admin V2 Router
  -> shared request ID / rate limit / CSRF / recent-auth dependencies
  -> Admin domain services
  -> repositories
  -> one SQLite transaction per mutation
  -> redacted immutable audit event in the same transaction
  -> typed response + stable error code

Operational services
  -> SQLite online backup API
  -> integrity/schema/domain checks
  -> restore-drill evidence
  -> scoped cleanup planner/executor
```

### Trust zones

- Public: login initiation and token-based recovery completion only.
- Authenticated Owner: routine administrative read operations.
- Recently re-authenticated Owner: invitations, account mutations, exports, backup/cleanup actions.
- Migration process: schema changes only; cannot serve web requests.
- Deployment process: image/config/nginx replacement and health verification; no normal data administration.

### Authentication model

- Prefer a server-managed opaque Admin session in an `HttpOnly`, `Secure`, `SameSite=Strict` cookie.
- Do not store privileged bearer tokens in `localStorage`.
- Rotate session ID on login, password change, MFA completion, and privilege change.
- Short idle timeout and bounded absolute timeout; revoke all sessions after password reset or suspension.
- Require CSRF protection for every mutation.
- Rate-limit login and recovery by normalized account plus IP without account enumeration.
- Owner MFA is required before production cutover. If MFA delivery is not yet configured, V2 cannot become the production `/admin` route.

### Password recovery

- Remove the public direct password-reset operation.
- Start recovery with a generic response regardless of account existence.
- Store only a hash of a one-time, expiring, single-use token.
- Recovery completion requires the token, enforces password policy, revokes sessions, and writes a redacted audit event.
- Never return or log passwords, reset tokens, invitation secrets, cookies, JWTs, MFA seeds, or recovery codes.

### Authorization

Roles:

- `owner`: full Admin V2 authority subject to recent-auth/MFA gates.
- `support`: redacted read-only health and user diagnostics only.
- `professor` and `student`: denied from Admin V2 server-side.

Every V2 route uses shared dependencies; UI visibility is not an authorization control.

---

## 4. Module and File Design

Create these new files; do not grow `owner_admin.py` into another monolith.

```text
backend/admin_v2/
  __init__.py
  router.py                  # mounts all V2 API routers
  dependencies.py            # session, role, CSRF, MFA, recent-auth, idempotency
  errors.py                  # stable code/requestId/detail envelope
  redaction.py               # recursive secret redaction
  schemas/
    auth.py
    organizations.py
    invitations.py
    users.py
    operations.py
    audit.py
  repositories/
    admin_sessions.py
    organizations.py
    invitations.py
    users.py
    audit_events.py
    operations.py
  services/
    auth_service.py
    organization_service.py
    invitation_service.py
    user_service.py
    health_service.py
    backup_service.py
    cleanup_service.py
  routes/
    auth.py
    overview.py
    organizations.py
    invitations.py
    users.py
    sessions.py
    operations.py
    audit.py
backend/templates/admin_v2/index.html
backend/static/admin_v2/admin.css
backend/static/admin_v2/app.js
backend/static/admin_v2/api.js
backend/static/admin_v2/views/*.js
backend/migrations/versions/008_admin_v2_control_plane.py
backend/tests/admin_v2/
  conftest.py
  test_auth.py
  test_authorization.py
  test_organizations.py
  test_invitations.py
  test_users.py
  test_sessions_view.py
  test_audit.py
  test_health_backup.py
  test_cleanup.py
  test_openapi_contract.py
  test_secret_redaction.py
  test_migration.py
  test_nginx_contract.py
docs/admin/ADMIN_V2_RUNBOOK.md
docs/admin/ADMIN_V2_ROLLBACK.md
```

Integration files, modified only after focused tests pass:

- `backend/main.py`: mount V2 router and `/admin-v2` shell.
- `nginx-practenture.conf`: preserve `/api` prefix; add exact V2 and health routes.
- `docker-compose.yml`: V2 health check and immutable deployment settings.
- Deployment workflow/script: migration preflight, online backup, deploy, smoke, rollback.

---

## 5. Canonical API Contract

All JSON uses one naming convention: **camelCase externally**, snake_case internally via explicit Pydantic aliases. Every endpoint has a typed request and response model.

### Common response/error rules

Success responses use a typed resource or `{items, page}` envelope. Errors use:

```json
{
  "error": {
    "code": "ADMIN_AUTH_REQUIRED",
    "message": "Authentication required",
    "requestId": "opaque-id",
    "fieldErrors": []
  }
}
```

Mutation requests require `X-CSRF-Token`; high-assurance mutations also require `Idempotency-Key` and recent authentication.

### Auth

- `POST /api/admin/v2/auth/login`
- `POST /api/admin/v2/auth/mfa/verify`
- `GET /api/admin/v2/auth/session`
- `POST /api/admin/v2/auth/reauthenticate`
- `POST /api/admin/v2/auth/password/change`
- `POST /api/admin/v2/auth/recovery/start`
- `POST /api/admin/v2/auth/recovery/complete`
- `POST /api/admin/v2/auth/logout`

### Overview and organizations

- `GET /api/admin/v2/overview`
- `GET /api/admin/v2/organizations`
- `POST /api/admin/v2/organizations`
- `GET /api/admin/v2/organizations/{organizationId}`
- `PATCH /api/admin/v2/organizations/{organizationId}`

### Invitations

- `GET /api/admin/v2/invitations`
- `POST /api/admin/v2/invitations`
- `GET /api/admin/v2/invitations/{invitationId}`
- `POST /api/admin/v2/invitations/{invitationId}/revoke`
- `POST /api/admin/v2/invitations/{invitationId}/resend`

Lifecycle: `ACTIVE -> REDEEMED | EXPIRED | REVOKED`. Full secret is returned once, hashed at rest, and absent from list/detail/audit/logging.

### Users

- `GET /api/admin/v2/users`
- `POST /api/admin/v2/users/precreate`
- `GET /api/admin/v2/users/{userId}`
- `POST /api/admin/v2/users/{userId}/suspend`
- `POST /api/admin/v2/users/{userId}/reactivate`
- `POST /api/admin/v2/users/{userId}/require-password-reset`
- `POST /api/admin/v2/users/{userId}/revoke-sessions`

Historical users are suspended, not deleted.

### Operational visibility

- `GET /api/admin/v2/sessions` — read-only, paginated, redacted.
- `GET /api/admin/v2/operations/health`
- `GET /api/admin/v2/operations/backups`
- `POST /api/admin/v2/operations/backups`
- `GET /api/admin/v2/operations/restore-drills`
- `POST /api/admin/v2/operations/cleanup-plans`
- `GET /api/admin/v2/operations/cleanup-plans/{planId}`
- `POST /api/admin/v2/operations/cleanup-plans/{planId}/execute`

Cleanup requires bounded selectors, a plan hash, typed confirmation, recent verified backup, recent authentication, idempotency, one transaction, and post-cleanup health validation.

### Audit

- `GET /api/admin/v2/audit-events`
- `GET /api/admin/v2/audit-events/{eventId}`
- `POST /api/admin/v2/audit-events/exports`

Audit events are append-only and recursively redacted.

---

## 6. Data Design and Migration Safety

Migration `008_admin_v2_control_plane.py` may add, but not remove:

- `admin_sessions`: opaque session hash, owner ID, CSRF hash, MFA/recent-auth timestamps, idle/absolute expiry, revocation metadata.
- `admin_recovery_tokens`: token hash, owner ID, expiry, consumed/revoked timestamps.
- `admin_idempotency_keys`: actor, operation, key hash, request hash, stored result reference, expiry.
- missing invitation lifecycle/hash fields if not already represented.
- normalized audit columns required by V2.

Requirements:

1. Inspect the actual production schema and Alembic revision before writing the migration.
2. Preflight duplicate/orphan/invalid-state reports; mutation is blocked if unresolved.
3. Online SQLite backup before migration.
4. Upgrade tested against an anonymized copy and a production-structure snapshot.
5. Downgrade removes only empty V2-owned tables/indexes; production rollback should normally revert application/nginx while retaining additive tables.
6. `PRAGMA quick_check`, `integrity_check`, declared foreign-key check, logical orphan checks, and domain invariants run after upgrade.

---

## 7. UI Product Specification

### Navigation

- Overview
- Organizations
- Invitations
- Users
- Sessions
- Operations
- Audit
- Profile/Security

### Required behavior for every view

- Real route/view loading; no title-only navigation.
- Loading, empty, error, permission-denied, and stale-data states.
- Search/filter/sort/pagination reflected in URL state.
- Destructive actions use a review screen, typed confirmation where appropriate, server-provided impact summary, and result receipt.
- Keyboard navigation, visible focus, semantic labels, WCAG AA contrast, reduced-motion support.
- Desktop, tablet, and mobile layouts verified by full-page screenshots.
- No inline handlers; event binding is centralized.
- No secrets in DOM after the one-time reveal is dismissed.

### Dashboard overview

Cards come from one typed `/overview` response: active users by role/status, organizations, active invitations, current sessions, database health, backup freshness, restore-drill freshness, and recent audit events. Each card links to the filtered source view.

---

## 8. Acceptance Matrix

### Security

- Anonymous receives 401; Professor/Student receive 403; Owner succeeds.
- Cookies are HttpOnly/Secure/SameSite; privileged tokens never enter localStorage.
- CSRF failures, expired sessions, idle timeout, absolute timeout, replay, and session fixation are tested.
- MFA and recent-auth gates block sensitive mutations.
- Recovery does not enumerate users; token is expiring, single-use, hashed, and revokes sessions.
- Suspension immediately blocks login, refresh/session use, and protected calls.
- Invitation and recovery secrets are absent from DB plaintext, responses after initial reveal, logs, and audit.
- Stable rate limiting is tested without cross-test global leakage.

### Contracts and domain behavior

- Frozen V2 OpenAPI manifest exactly matches runtime routes, models, methods, security, and documented statuses.
- Invitation active/redeemed/expired/revoked and concurrent redemption cases pass.
- User precreation, duplicate conflict, suspension/reactivation, reset requirement, and idempotent replay pass.
- Pagination/filtering/sorting envelopes match the frontend exactly.
- No duplicate method/path registrations.

### Data and operations

- Clean upgrade, populated upgrade, failed-upgrade rollback, and application rollback pass.
- Physical, relational, migration, logical-orphan, domain, WAL/disk, backup-age, and authenticated-API health layers are tested.
- Backup file is non-empty, checksummed, independently openable, integrity-checked, count-manifested, and restore-drilled.
- Cleanup dry run, changed hash, stale backup, unbounded selector, transaction rollback, idempotency, and unrelated-row preservation pass.

### UI/E2E

- Login -> MFA -> forced password change -> dashboard.
- Organization create/edit.
- Invitation create/one-time reveal/list/revoke.
- Professor precreate/manage/suspend/reactivate/require reset.
- Session operational search/detail.
- Health/backup/cleanup workflows.
- Audit filter/detail/export.
- Logout and expired-session recovery.
- Browser console has no errors; failed APIs display actionable errors.
- Full-page desktop/mobile screenshots have no clipping, overflow, broken grids, illegible contrast, or inconsistent spacing.

### Regression

- Full backend suite passes with exact count recorded.
- Existing iOS contract, golden simulation parity, Monte Carlo, and 20-student API E2E remain unchanged and passing.
- Production smoke uses a dedicated tagged test organization/account and removes it only through scoped cleanup.

---

## 9. Implementation Sequence (TDD and Review Gates)

### Task 0 — Worktree isolation and baseline

**Files:** no product changes.

1. Record all pre-existing modified/untracked files and ownership.
2. Create a separate git worktree/branch from the agreed baseline so wearable and prior Admin changes cannot be mixed into V2.
3. Run and record baseline backend, contract, simulation parity, and deployment-config tests.
4. Freeze current runtime route inventory and production schema metadata with secrets redacted.
5. Commit only baseline manifests and this design document.

**Gate:** abort if baseline, worktree ownership, or production schema/revision is unknown.

### Task 1 — V2 skeleton and error contract

1. Write failing tests for mount path, duplicate routes, typed error envelope, request IDs, and anonymous denial.
2. Create `backend/admin_v2` skeleton and schemas.
3. Mount `/api/admin/v2` and `/admin-v2` without changing `/admin`.
4. Run focused tests, then full regressions.
5. Spec review, quality/security review, commit.

### Task 2 — Session authentication, CSRF, MFA, and recovery

Implement in small TDD slices: session repository; secure cookie; login rotation; CSRF; timeout/revocation; MFA; recent-auth; password change; recovery start/complete; logout. Remove/disable the insecure reset route only when V2 recovery tests pass and production cutover is scheduled.

### Task 3 — Audit/redaction/idempotency foundation

Write redaction property tests first. Then implement immutable audit writes in the same mutation transaction and idempotency replay/conflict behavior.

### Task 4 — Organizations

Repository/service/routes/UI, with uniqueness, optimistic concurrency, and audit tests.

### Task 5 — Invitations

Lifecycle, hashed one-time secret, concurrent redemption, resend/revoke, UI, and secret-leak tests.

### Task 6 — Users

Paginated search/detail, precreation, suspension/reactivation, reset requirement, session revocation, UI, and audit tests.

### Task 7 — Sessions visibility and overview

Read-only redacted sessions repository plus aggregated overview. No simulation mutation endpoints are added.

### Task 8 — Health, backup, restore evidence, and cleanup

Implement health layers; SQLite online backup and verification; restore-drill recording; cleanup dry-run/hash/execute transaction. Test all failure gates before UI actions.

### Task 9 — Complete responsive UI

Build shell and each view against frozen API contracts. Run automated browser journeys and inspect full-page desktop/mobile screenshots iteratively.

### Task 10 — Nginx and deployment

1. Add tests proving `/api` prefix preservation and exact Admin V2 routing.
2. Correct health/OpenAPI routing without exposing documentation unintentionally.
3. Build image, run container smoke tests, and verify health.
4. Write runbook and rollback commands.

### Task 11 — Staging and production cutover

1. Quiescence barrier: all implementers finished; inspect diff; rerun all gates centrally.
2. Backup production using SQLite online backup API and verify it independently.
3. Deploy additive migration and V2 without replacing `/admin`; run production V2 smoke.
4. Exercise the complete Owner flow in a real browser and inspect console/network/screenshots.
5. Switch `/admin` to V2; retain legacy route temporarily at a nonpublic rollback path or image revision.
6. Repeat authenticated smoke and health checks.
7. Monitor errors, latency, auth failures, database locks/WAL, and backup status.

**Rollback:** revert nginx/application image to the prior revision; retain additive V2 tables; verify legacy health and data counts. Do not restore the database unless a verified data mutation requires it.

---

## 10. Release Evidence Required Before Declaring Success

- Git branch/worktree and clean ownership report.
- Reviewed migration preflight and before/after schema manifests.
- Verified production backup path, checksum, integrity result, table-count manifest, and restore-drill evidence (no secrets).
- Exact focused and full test commands, exit codes, and pass/fail counts.
- Frozen OpenAPI diff result and duplicate-route result.
- Security test report.
- Browser E2E trace plus desktop/mobile screenshots.
- Production HTTP/auth workflow results and browser-console/network evidence.
- Deployment revision and tested rollback revision.
- Confirmation that unrelated simulation/iOS behavior and production data were preserved.

The console is not “done” because source files exist or unit tests pass. It is done only when the authenticated production workflow succeeds end to end and rollback has been proven.
