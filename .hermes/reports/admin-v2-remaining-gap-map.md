# Admin Console V2 — Remaining Gap Map

**Audit date:** 2026-07-28  
**Baseline:** `docs/plans/2026-07-28-admin-console-v2.md` (canonical API, UI, and Tasks 2–11)  
**Scope:** read-only source audit. No tests, network calls, application imports, or product edits were performed. This report is the only file created.

## Executive result

Admin V2 is an **auth-only vertical slice**, not an implemented console.

- Canonical V2 operations: **36**.
- Implemented at the canonical method/path: **3** — login, session, logout.
- Missing at the canonical method/path: **33**.
- Task 2 (session authentication) is substantially implemented and heavily unit-tested, but its MFA-verify, recent-auth, password-change, and recovery endpoints/workflows remain absent.
- Task 3 has a strong standalone redaction utility, but transactional audit and route idempotency are not wired into Admin V2 mutations.
- Tasks 4–9 have no V2 API/UI implementation. Legacy `/api/owner` code and domain tables/services are possible inputs, not V2 completion.
- Tasks 10–11 are incomplete. In particular, the deployed `www` nginx `/api/` rule strips `/api`, and there is no `/admin-v2` location; the current V2 API/shell therefore are not correctly routed from the frontend host.

## What is implemented

### V2 skeleton and auth slice

- `backend/main.py` mounts `admin_v2_router` at `/api/admin/v2`, serves `/admin-v2`, and retains `/admin` plus legacy `/api/owner` routes.
- `backend/admin_v2/router.py` composes only the auth router.
- `backend/admin_v2/routes.py` implements:
  - `POST /api/admin/v2/auth/login`
  - `GET /api/admin/v2/auth/session`
  - `POST /api/admin/v2/auth/logout`
- `backend/admin_v2/schemas.py` contains only auth/session/error models (`AdminLoginRequest`, `AdminSessionResponse`, `AdminLoginResponse`, `AdminLogoutResponse`, `AdminErrorEnvelope`). It does not contain the domain/list/mutation contracts needed by the other 33 operations.
- `backend/admin_v2/repository.py`, `service.py`, and migration `backend/migrations/versions/003_add_admin_v2_sessions.py` implement server-side hashed sessions, CSRF hashes, idle/absolute expiry, revocation, layered login throttling, and TOTP replay state.
- `backend/admin_v2/errors.py` provides the stable V2 error envelope and exception handling.
- `backend/admin_v2/redaction.py` is a substantial recursive, bounded redactor.
- The 13 tests in `backend/tests/admin_v2/` cover only auth/session/throttling/MFA-at-login/password-reset boundaries/migration 003/redaction. There are no V2 organization, invitation, user-management, overview/session-visibility, operations, audit API, UI, or release-routing tests.

### Existing non-V2 building blocks (reusable only after correction and V2 wrapping)

- `backend/database.py` already creates organizations, memberships, professor invitations, audit events, cleanup plans, backup runs, and idempotency tables.
- Legacy `/api/owner` exposes invitations, user administration, health/backup reads, cleanup, and audit reads in `backend/routers/owner_admin.py`.
- Existing services/repositories include invitation, cleanup, audit, account, idempotency, and database-health modules under `backend/services/` and `backend/repositories/`.
- These do **not** satisfy V2: they use bearer auth rather than Admin V2 cookie/CSRF/recent-auth, mostly raw `dict` contracts, noncanonical paths/envelopes, offset/no real cursor pagination, and incomplete transactional audit/idempotency. Some code is unsafe or factually incomplete (for example `DatabaseHealthService.check_backup_status()` returns an `unknown` placeholder; legacy cleanup has global/unbounded deletion paths and inconsistent serialization/parsing; invitation creation stores the generated secret directly in `secret_hash`). Do not mount the legacy router under V2.

## Exact canonical endpoint inventory

Status is based on an exact method/path match in the V2 router, not on a similar legacy endpoint.

### Task 2 — authentication and recovery (3 implemented, 5 missing)

| Canonical operation | Status | Remaining work |
|---|---|---|
| `POST /api/admin/v2/auth/login` | Implemented | Existing login supports MFA code/backup code in the login body and returns `mfaRequired`; keep contract stable while adding the canonical verification flow. |
| `POST /api/admin/v2/auth/mfa/verify` | Missing | Add challenge-bound MFA completion; do not turn it into an unauthenticated free-standing TOTP oracle. |
| `GET /api/admin/v2/auth/session` | Implemented | Existing typed session + cookie authentication. |
| `POST /api/admin/v2/auth/reauthenticate` | Missing | Recent-auth grant/state required before sensitive mutations. |
| `POST /api/admin/v2/auth/password/change` | Missing | Owner password change, atomic session invalidation/rotation, audit. |
| `POST /api/admin/v2/auth/recovery/start` | Missing | Non-enumerating request, hashed expiring token, rate limit, delivery boundary. |
| `POST /api/admin/v2/auth/recovery/complete` | Missing | Single-use atomic completion and full owner-session revocation. Existing generic `/api/auth/forgot-password` and `/api/auth/reset-password` are not V2 routes. |
| `POST /api/admin/v2/auth/logout` | Implemented | Existing CSRF-protected revocation and cookie deletion. |

### Tasks 4 and 7 — overview, organizations, and session visibility (0 implemented, 6 missing)

| Canonical operation | Status | Required behavior |
|---|---|---|
| `GET /api/admin/v2/overview` | Missing | Typed aggregate counts/operational summary. |
| `GET /api/admin/v2/organizations` | Missing | Search/filter/sort/cursor envelope. |
| `POST /api/admin/v2/organizations` | Missing | Validation, uniqueness, idempotency, audit. |
| `GET /api/admin/v2/organizations/{organizationId}` | Missing | Organization detail and safe aggregates. |
| `PATCH /api/admin/v2/organizations/{organizationId}` | Missing | Optimistic concurrency/version conflict, recent-auth as specified, audit. |
| `GET /api/admin/v2/sessions` | Missing | Read-only cursor-paginated operational search/detail fields with sensitive data redacted; no simulation mutation. |

### Task 5 — invitations (0 implemented, 5 missing)

| Canonical operation | Status | Required behavior |
|---|---|---|
| `GET /api/admin/v2/invitations` | Missing | Typed cursor list and lifecycle status. |
| `POST /api/admin/v2/invitations` | Missing | Hashed one-time secret, initial reveal only, idempotency, audit. |
| `GET /api/admin/v2/invitations/{invitationId}` | Missing | Never reveal secret after creation. |
| `POST /api/admin/v2/invitations/{invitationId}/revoke` | Missing | Atomic lifecycle transition, reason/recent-auth, audit. |
| `POST /api/admin/v2/invitations/{invitationId}/resend` | Missing | Rotate/reissue safely, one-time reveal/delivery boundary, audit. |

### Task 6 — users (0 implemented, 7 missing)

| Canonical operation | Status | Required behavior |
|---|---|---|
| `GET /api/admin/v2/users` | Missing | Cursor search/filter/sort with organization membership. |
| `POST /api/admin/v2/users/precreate` | Missing | Typed professor precreation; no plaintext temporary-password persistence/logging; idempotency/audit. |
| `GET /api/admin/v2/users/{userId}` | Missing | Typed detail and membership/status data. |
| `POST /api/admin/v2/users/{userId}/suspend` | Missing | Atomic suspension plus immediate denial of login/token/session/protected use; recent-auth/audit. |
| `POST /api/admin/v2/users/{userId}/reactivate` | Missing | Atomic transition, idempotency/audit. |
| `POST /api/admin/v2/users/{userId}/require-password-reset` | Missing | Flag requirement and enforce it at authentication boundary; audit. |
| `POST /api/admin/v2/users/{userId}/revoke-sessions` | Missing | Revoke both applicable legacy access/refresh state and Admin V2 session state where relevant; audit. |

### Task 8 — health, backup, restore evidence, and cleanup (0 implemented, 8 missing)

| Canonical operation | Status | Required behavior |
|---|---|---|
| `GET /api/admin/v2/operations/health` | Missing | Physical, relational, migration, orphan/domain, WAL/disk, backup-age layers; typed/degraded results, not unconditional `healthy`. |
| `GET /api/admin/v2/operations/backups` | Missing | Typed backup history/status. |
| `POST /api/admin/v2/operations/backups` | Missing | SQLite online backup API; non-empty/checksum/open/integrity/count-manifest verification; idempotency/audit. |
| `GET /api/admin/v2/operations/restore-drills` | Missing | Persisted restore-drill evidence/history. |
| `POST /api/admin/v2/operations/cleanup-plans` | Missing | Bounded selectors, exact dry-run counts, deterministic plan hash, expiry, fresh verified-backup gate. |
| `GET /api/admin/v2/operations/cleanup-plans/{planId}` | Missing | Typed plan/preview/evidence. |
| `POST /api/admin/v2/operations/cleanup-plans/{planId}/execute` | Missing | Recompute/hash check, confirmation + recent-auth, one transaction, rollback, unrelated-row preservation, idempotency/audit. |

### Tasks 3 and 9 — audit read/export (0 implemented, 3 missing)

| Canonical operation | Status | Required behavior |
|---|---|---|
| `GET /api/admin/v2/audit-events` | Missing | Typed cursor filtering/search with redacted immutable event data. |
| `GET /api/admin/v2/audit-events/{eventId}` | Missing | Typed redacted detail. |
| `POST /api/admin/v2/audit-events/exports` | Missing | Controlled export job/artifact, redaction, authorization/recent-auth, audit of export. |

**Total:** 36 canonical operations = 3 implemented + 33 missing.

## Cross-cutting backend gaps

1. **Task 2 completion:** MFA verify/challenge state, recent-auth state/gates, owner password change, and V2 recovery contracts/storage/routes/tests are absent. Migration 003 contains session/throttle/replay tables only.
2. **Transactional audit (Task 3):** `redact_secrets()` exists, but Admin V2 has no audit writer/middleware and no mutation writes domain change + audit event in one transaction. Request ID, actor, reason, before/after, outcome, and metadata need one canonical path.
3. **Idempotency (Task 3):** no V2 dependency/service integration, replay envelope, payload-hash conflict handling, or atomic coupling to mutation/audit. The legacy service is not wired into V2.
4. **Contracts:** schemas are auth-only. Define camelCase request/response/error/list envelopes, bounded filters, cursor semantics, documented statuses, ETags/version fields, confirmation/reason fields, and one-time-secret responses before UI work.
5. **Persistence/migration:** an additive next migration is needed for any absent recovery/MFA challenge/recent-auth, organization versioning, restore-drill/evidence, export-job, and strengthened idempotency/audit fields or indexes. Existing bootstrap `CREATE TABLE IF NOT EXISTS` statements are not a substitute for versioned populated upgrades and rollback evidence.
6. **Repository/service layer:** `admin_v2/repository.py` and `service.py` are auth-only. No V2 domain repositories/services exist.
7. **Authorization/CSRF:** every new read needs owner-cookie authorization; every state change needs CSRF; sensitive changes need recent-auth. Similar legacy bearer endpoints cannot be reused as routes.
8. **Suspension enforcement:** the mutation alone is insufficient; all token/session verification boundaries must reject suspended users immediately.
9. **OpenAPI:** the frozen `backend/tests/contracts/openapi_route_manifest.json` predates the V2 mount (its 96-operation inventory contains no `/api/admin/v2` operations). It must be deliberately regenerated/reviewed after contracts are frozen, with duplicate-route and typed-success checks.

## UI and E2E gaps

- `backend/admin_v2/shell.py` returns a minimal static placeholder containing only “Admin Console V2” and “Authentication foundation is active.”
- There are no Admin V2 CSS/JS assets under `backend/static`, no V2 templates under `backend/templates`, no frontend package/build configuration, and no Playwright/browser suite.
- All canonical workflows are missing: login→MFA→forced password change→dashboard; overview; organization create/edit; invitation create/one-time reveal/list/revoke/resend; professor precreate/detail/suspend/reactivate/reset/session revoke; operational session search/detail; health/backup/restore/cleanup; audit filter/detail/export; logout/expiry recovery.
- Missing UI system behavior: responsive navigation, desktop/mobile layouts, loading/empty/error states, confirmations/reason collection, recent-auth modal, cursor paging/filter/sort state, one-time secret handling, actionable stable-error rendering, and automatic 401/session-expiry recovery.
- Missing evidence: browser console/network checks, trace, desktop/mobile full-page screenshots, accessibility/keyboard verification, and failed-API UX.

## Release/routing gaps

1. `nginx-practenture.conf` has exact `/admin` and `/api/owner/` rules but **no `/admin-v2` or Admin V2 static rule**.
2. On the `www` server, `location /api/ { proxy_pass .../; }` strips the `/api` prefix. Thus `/api/admin/v2/...` reaches FastAPI as `/admin/v2/...`, not the mounted `/api/admin/v2/...`. The API-domain catch-all preserves it, but the same-origin frontend flow is not correctly routed.
3. The `www` SPA fallback captures `/admin-v2`, so it does not reach FastAPI’s V2 shell.
4. No nginx tests prove exact V2 shell/API routing or `/api` prefix preservation. No container smoke covers Admin V2 anonymous/owner/CSRF paths.
5. `docker-compose.yml` publishes only nginx port 80 while the supplied config redirects HTTP to HTTPS and its HTTPS servers require mounted certificates that compose does not mount/publish. This pre-existing deployment inconsistency must be resolved in the release lane, not silently inherited by V2.
6. `ec2-deploy.sh` checks only `/api/health`; it has no Admin V2 route/auth smoke or browser flow. `backend/scripts/deploy_backup_gated.sh` checks `/health` (different from the application’s `/api/health`) and does not gate on Admin V2 tests.
7. Missing Task 10/11 artifacts: Admin V2 runbook, migration preflight and schema manifests, verified online backup/restore-drill evidence, exact test reports, browser artifacts, deployment revision, tested rollback revision, production tagged-data smoke, and post-deploy monitoring evidence.

## Fastest dependency-ordered execution map

### Backend API

**B0 — Freeze contracts and storage delta (serial, prerequisite for every lane)**

1. Convert the 36-operation canonical inventory into typed request/response/status/security contracts and cursor conventions.
2. Specify challenge/recent-auth/recovery state, optimistic organization versioning, backup/restore evidence, audit export, and idempotency persistence deltas.
3. Add one additive migration plus clean/populated/failure/application-rollback tests.

**Gate:** schema migration and frozen V2 OpenAPI shape reviewed before domain routes or UI clients.

**B1 — Complete Task 2 and Task 3 foundations (serial where transaction/session state overlaps)**

1. Finish MFA challenge verification, reauthentication, password change, recovery start/complete.
2. Add a shared owner-cookie/read dependency, CSRF mutation dependency, and recent-auth dependency.
3. Add one transaction/unit-of-work abstraction that couples domain mutation, redacted immutable audit event, and idempotency record/replay.
4. Add shared list/cursor/error/one-time-secret schemas and foundation tests.

**Gate:** auth/security matrix, audit rollback, redaction, idempotent replay/conflict, and concurrency tests pass.

**B2 — Parallel domain APIs after B1**

- **Lane O (organizations + overview base):** organization repository/service/schemas/routes; uniqueness/versioning/audit.
- **Lane I (invitations):** lifecycle, hashed secret, one-time reveal, revoke/resend/concurrent redemption.
- **Lane U (users):** list/detail/precreate/transitions/reset/session revocation and enforcement tests.
- **Lane S (session visibility):** redacted read-only session list/detail projection; no simulation mutations.
- **Lane A (audit reads):** cursor list/detail. Defer export creation until the operations artifact abstraction is known.

These lanes are parallel-safe only if each owns domain-specific files and does not edit router composition, shared schemas, migration, OpenAPI manifest, or common transaction/auth code.

**B3 — Operations API (after B1; backup before cleanup execute)**

1. Health layers and typed degradation.
2. SQLite online backup creation and independent verification; persist checksum/count/integrity evidence.
3. Restore drill and persisted evidence/history.
4. Cleanup plan preview/hash with bounded selector.
5. Cleanup execute with verified-fresh-backup/recent-auth/confirmation/recompute/transaction/idempotency/audit gates.
6. Audit export artifact using the verified artifact/storage pattern.

**B4 — Serial integration gate**

Compose all domain routers once; freeze/regenerate the OpenAPI manifest; run duplicate route, typed response, auth matrix, migration, concurrency, full backend, contract, simulation-parity, and iOS-regression gates. Record exact commands/counts.

### UI / E2E

**U0 (parallel with B2 after contracts freeze):** build the responsive shell, route/navigation state, typed API client, cookie/CSRF/session handling, stable-error mapping, recent-auth modal, shared table/filter/cursor/modal/confirmation components, and login/MFA/forced-password-change flow using frozen contracts/mocks.

**U1 (parallel views, each with exclusive files):**

- Organizations + overview.
- Invitations + one-time reveal.
- Users + status/session actions.
- Session visibility.
- Audit list/detail (export waits for B3).
- Operations health/backups/restore/cleanup (workflow activation waits for B3).

**U2 (after live B2/B3 APIs):** replace mocks, run real browser journeys, verify actionable failures and expiry/logout recovery, inspect console/network, and capture desktop/mobile screenshots. Fix clipping/overflow/accessibility regressions before release.

### Release

**R0 (parallel with U2):** add exact nginx rules for `/admin-v2`, V2 assets, and `/api/admin/v2/` with prefix preservation; repair health-route and compose TLS/listener consistency; add nginx/container routing tests.

**R1:** write runbook/rollback; run image/container smoke for anonymous 401, non-owner 403, owner session, CSRF denial/success, and representative read/mutation; generate migration/schema/backup/restore evidence.

**R2 (serial quiescence gate):** clean ownership report → full central regression suite → verified online production backup → additive migration/V2 deploy while `/admin` remains legacy → real-browser V2 smoke → monitoring.

**R3 (only after R2 passes):** switch `/admin` to V2, retain a tested nonpublic rollback path/image revision, repeat authenticated/browser smoke, and prove application/nginx rollback without destructive DB downgrade.

## Parallel-safe ownership map

| Lane | Exclusive files/directories | Must not edit until integration |
|---|---|---|
| Foundation/auth | existing `backend/admin_v2/{routes,repository,service,dependencies,schemas,errors}.py`, next migration, shared test helpers | Domain files owned by other lanes |
| Organizations | new domain-specific org schema/repository/service/routes/tests | `admin_v2/router.py`, `main.py`, migration, shared schemas |
| Invitations | new domain-specific invitation files/tests | same shared integration files |
| Users | new domain-specific user files/tests | same shared integration files; auth enforcement changes coordinated through foundation owner |
| Sessions/overview | new read-model files/tests | simulation routers/database behavior |
| Operations | new health/backup/restore/cleanup files/tests | deployment files; shared integration files |
| Audit read/export | new audit query/export files/tests; reuse redactor | shared audit writer/transaction owned by foundation |
| UI shell | V2-only shell/client/shared assets | legacy `/admin` templates/assets |
| UI feature lanes | separate V2 view/component/test files per domain | shared shell/client without owner approval |
| Release | nginx, compose, deploy scripts, runbooks, routing/container tests | application/domain code |
| Integrator (single owner) | `backend/admin_v2/router.py`, `backend/main.py`, OpenAPI manifest, shared route registry, final release evidence | domain implementation during parallel phase |

## Completion gates

Do not call Admin V2 complete until all 36 operations match the frozen manifest, all UI journeys run against live APIs, nginx preserves exact paths, the full regression count is recorded, backup/restore evidence is verified, production smoke passes, and rollback has been exercised. Existing auth internals need no redesign; remaining work should build on that slice rather than re-review it.
