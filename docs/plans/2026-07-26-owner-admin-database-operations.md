# Owner Administration and Database Operations Implementation Plan

> **For Paul:** Use subagent-driven-development to implement this plan task-by-task with specification and code-quality review.

**Goal:** Build a secure Owner control plane for Professor onboarding, account administration, database correctness, backup/restore evidence, auditing, and scoped test-data cleanup.

**Architecture:** Extend FastAPI with thin Owner routers, domain services, repositories, versioned migrations, and a server-rendered Owner console. Keep SQLite safe for the current single-writer deployment while creating a repository/migration boundary for managed PostgreSQL. Mutations are transactional, idempotent, MFA/recent-auth protected, and audited.

**Tech Stack:** Python 3.11, FastAPI, Pydantic, SQLite, pytest, existing JWT/MFA infrastructure, nginx, Docker, AWS S3/SSM; PostgreSQL migration-ready abstractions.

**Design references:**
- `docs/architecture/SYSTEM_ARCHITECTURE.md`
- `docs/architecture/ADMIN_DATABASE_LLD.md`

---

## Delivery Rules

- Develop on a branch; never test destructive behavior against production.
- TDD for every service and endpoint.
- Use synthetic data and temporary databases in tests.
- Preserve existing `/api/professor/codes` behavior through a compatibility facade until iOS/web clients migrate.
- No production deployment until backup and restore gates pass.
- Never commit credentials, tokens, invitation secrets, private keys, database copies, or provider configuration.

## Phase 0 — Baseline and Safety

### Task 1: Capture the active schema and administrative contract

**Objective:** Turn current production-compatible behavior into executable regression tests before refactoring.

**Files:**
- Modify: `backend/tests/contracts/test_professor_admin_contract.py`
- Create: `backend/tests/contracts/test_owner_authorization_contract.py`
- Create: `backend/tests/fixtures/admin_data.py`

**Steps:**
1. Add tests for Owner success and Professor/Student/anonymous denial on existing Professor-code and pre-create endpoints.
2. Add tests asserting organization, membership, password-change, and audit side effects.
3. Run:
   ```bash
   cd backend
   BIZSIMAI_JWT_SECRET=test-only-secret DATABASE_URL=sqlite+aiosqlite:///:memory: PYTHONPATH=$PWD .venv/bin/pytest tests/contracts/test_professor_admin_contract.py tests/contracts/test_owner_authorization_contract.py -v
   ```
4. Expected: existing positive behavior passes; missing authorization/audit guarantees fail explicitly.
5. Commit: `test: lock owner administration contracts`.

### Task 2: Introduce migration governance

**Objective:** Replace implicit startup schema mutation for new Owner features with versioned migrations.

**Files:**
- Create: `backend/migrations/README.md`
- Create: `backend/migrations/versions/001_owner_admin_baseline.py`
- Modify: `backend/alembic_config.py`
- Test: `backend/tests/test_migrations.py`

**Steps:**
1. Write a failing test that upgrades a copy of the legacy schema and validates row preservation.
2. Add the baseline migration with explicit upgrade and documented downgrade/forward-repair behavior.
3. Test upgrade from empty and populated legacy fixtures.
4. Run `backend/.venv/bin/pytest backend/tests/test_migrations.py -v` from repository root.
5. Commit: `build: establish versioned database migrations`.

## Phase 1 — Domain and Persistence

### Task 3: Add Owner-domain models and stable error codes

**Objective:** Define typed requests/responses and domain errors before endpoints.

**Files:**
- Create: `backend/schemas/owner_admin.py`
- Create: `backend/services/errors.py`
- Test: `backend/tests/unit/test_owner_schemas.py`

**Steps:** Test validation for expiration 1..168 hours, one-use default, normalized email, required reason/ticket, cursors, redacted responses, and stable error codes; then implement minimal Pydantic models. Commit `feat: add owner administration contracts`.

### Task 4: Migrate Professor codes into invitation lifecycle records

**Objective:** Support active, redeemed, expired, and revoked invitations without losing legacy codes.

**Files:**
- Create: `backend/migrations/versions/002_professor_invitations.py`
- Create: `backend/repositories/invitation_repository.py`
- Test: `backend/tests/repositories/test_invitation_repository.py`

**Steps:**
1. Test migration of unused and used legacy rows.
2. Test uniqueness, usage counters, expiry, revocation, and no plaintext secret in list/read models.
3. Implement secret hashing and masked display.
4. Test transaction rollback on duplicate redemption.
5. Commit: `feat: add secure professor invitation persistence`.

### Task 5: Implement InvitationService

**Objective:** Centralize issuance, listing, revocation, pre-creation, and atomic redemption.

**Files:**
- Create: `backend/services/invitation_service.py`
- Modify: `backend/routers/professor_admin.py`
- Test: `backend/tests/unit/test_invitation_service.py`

**Steps:** Write failing state-transition, idempotency, expiration, organization, and concurrency tests; implement the service; route legacy endpoints through it; rerun existing contracts. Commit `feat: enforce professor invitation lifecycle`.

### Task 6: Add account status and suspension

**Objective:** Let Owners suspend/reactivate accounts without deleting history.

**Files:**
- Create: `backend/migrations/versions/003_user_account_status.py`
- Create: `backend/services/owner_account_service.py`
- Modify: `backend/auth.py`
- Modify: `backend/routers/auth.py`
- Test: `backend/tests/contracts/test_account_suspension.py`

**Steps:** Test suspended login, token refresh, and protected-route rejection; test reactivation; implement status checks and refresh-token revocation; verify unrelated users remain active. Commit `feat: add auditable account suspension`.

### Task 7: Add declared relationships incrementally

**Objective:** Detect and prevent orphaned business records while preserving current data.

**Files:**
- Create: `backend/migrations/versions/004_relational_integrity.py`
- Create: `backend/scripts/preflight_foreign_keys.py`
- Test: `backend/tests/test_relational_integrity.py`

**Steps:** Add preflight orphan reports, fail migration on unresolved rows, rebuild SQLite tables with declared constraints, verify cascade only for session-owned data, and test restrictions for users/organizations/audit. Commit `db: enforce relational integrity`.

## Phase 2 — Audit and Security

### Task 8: Implement append-only structured auditing

**Objective:** Record every Owner mutation without leaking secrets.

**Files:**
- Create: `backend/services/audit_service.py`
- Create: `backend/repositories/audit_repository.py`
- Create: `backend/migrations/versions/005_audit_events.py`
- Test: `backend/tests/unit/test_audit_redaction.py`

**Steps:** Test recursive redaction for password/token/secret/code/MFA fields; add event persistence; prevent application update/delete methods; include request ID and outcome; integrate first with invitation and account services. Commit `feat: add redacted owner audit events`.

### Task 9: Enforce Owner MFA, recent auth, and idempotency

**Objective:** Add stronger controls to high-risk administrative operations.

**Files:**
- Create: `backend/dependencies/owner_security.py`
- Create: `backend/services/idempotency_service.py`
- Create: `backend/migrations/versions/006_idempotency_keys.py`
- Test: `backend/tests/security/test_owner_security.py`

**Steps:** Test missing MFA, stale auth, replayed same request, conflicting replay, Professor denial, and redacted errors; implement dependencies and apply them to mutations. Commit `security: harden owner mutations`.

## Phase 3 — Health, Backup, and Cleanup

### Task 10: Build DatabaseHealthService

**Objective:** Produce bounded, machine-readable physical, relational, domain, backup, and migration health results.

**Files:**
- Create: `backend/services/database_health_service.py`
- Create: `backend/scripts/database_health_check.py`
- Test: `backend/tests/unit/test_database_health_service.py`

**Steps:** Seed each violation in an isolated database; assert stable check codes and counts; implement quick/full modes; redact sample identifiers; add timeout limits. Commit `feat: add database correctness reporting`.

### Task 11: Implement verifiable online backup

**Objective:** Create encrypted off-instance backups with checksums and manifests.

**Files:**
- Create: `backend/scripts/backup_database.py`
- Create: `backend/services/backup_status_service.py`
- Create: `backend/migrations/versions/007_backup_runs.py`
- Test: `backend/tests/operations/test_backup_database.py`

**Steps:** Test SQLite online-copy consistency during writes, checksum, integrity check, manifest, failed upload, and secret-free logs; upload to a test S3 bucket; record status. Commit `ops: add verified encrypted database backups`.

### Task 12: Implement automated restore drills

**Objective:** Prove backups restore into an isolated environment.

**Files:**
- Create: `backend/scripts/restore_drill.py`
- Create: `backend/migrations/versions/008_restore_drills.py`
- Test: `backend/tests/operations/test_restore_drill.py`

**Steps:** Test checksum failure, corrupt backup, successful restore/migrate/health sequence, cleanup of temporary data, and status recording. Commit `ops: add isolated backup restore drills`.

### Task 13: Implement two-step scoped cleanup

**Objective:** Delete only explicitly tagged disposable records with a fresh backup and unchanged preview.

**Files:**
- Create: `backend/services/cleanup_service.py`
- Create: `backend/repositories/cleanup_repository.py`
- Create: `backend/migrations/versions/009_cleanup_plans.py`
- Test: `backend/tests/security/test_scoped_cleanup.py`

**Steps:** Test rejection of unbounded selectors, dry-run counts, unrelated-row preservation, plan hash changes, stale/missing backup, transaction rollback, replay, and post-check failure. Implement preview and execute methods. Commit `feat: add backup-gated scoped cleanup`.

## Phase 4 — Owner API and Console

### Task 14: Add Owner API routers

**Objective:** Expose the approved service functions through a consistent API.

**Files:**
- Create: `backend/routers/owner_admin.py`
- Create: `backend/routers/owner_audit.py`
- Modify: `backend/main.py`
- Test: `backend/tests/contracts/test_owner_api_contract.py`

**Steps:** Test all response schemas, pagination, role matrix, organization scope, request IDs, audit side effects, and error codes; register routers; verify OpenAPI contains no secret-bearing list schema. Commit `feat: expose owner administration api`.

### Task 15: Build the Owner console shell

**Objective:** Give the Owner a dedicated accessible interface separate from Professor functions.

**Files:**
- Create: `backend/templates/owner_dashboard.html`
- Create: `backend/static/owner/owner.css`
- Create: `backend/static/owner/owner.js`
- Modify: `backend/main.py`
- Test: `backend/tests/ui/test_owner_dashboard.py`

**Steps:** Test Owner access and non-Owner denial; implement overview, invitations, Professors, organizations, health, audit, and cleanup navigation; ensure keyboard/focus/labels/44px targets; add CSP-compatible assets. Commit `feat: add owner administration console`.

### Task 16: Build invitation and Professor administration UI

**Objective:** Complete secure Professor onboarding and account-state workflows.

**Files:** Modify the three Owner-console files; test `backend/tests/ui/test_owner_professor_flows.py`.

**Steps:** Test one-time secret display, expiration, revocation, suspension, recent-auth prompt, API errors, and no secret persistence in DOM/storage; implement views; run browser accessibility checks. Commit `feat: add owner professor workflows`.

### Task 17: Build health, backup, audit, and cleanup UI

**Objective:** Expose operational evidence without arbitrary SQL.

**Files:** Modify Owner-console assets; test `backend/tests/ui/test_owner_operations_flows.py`.

**Steps:** Test stale backup warnings, restore status, health violations, audit filters, dry-run review, typed confirmation, changed-plan rejection, and unrelated-data preservation. Commit `feat: add owner operations workflows`.

## Phase 5 — Environment and Production Readiness

### Task 18: Provision isolated staging

**Objective:** Prevent production data from serving as the normal test environment.

**Files:**
- Create: `backend/docker-compose.staging.yml`
- Create: `backend/.env.staging.example`
- Modify: `.github/workflows/ci-cd.yml`
- Create: `docs/operations/STAGING.md`

**Steps:** Provision separate DNS/database/secrets/OAuth/backup prefix; seed only synthetic data; test staging cannot access production storage; run API E2E. Commit `ops: add isolated staging environment`.

### Task 19: Harden nginx and operational access

**Objective:** Enforce TLS/security headers, rate limits, and named operational access.

**Files:**
- Modify: `backend/nginx.conf`
- Create: `docs/operations/ADMIN_ACCESS.md`
- Create: `docs/operations/INCIDENT_DATABASE_ACCESS.md`
- Test: `backend/tests/security/test_edge_security.py`

**Steps:** Add CORS allow-list configuration, HSTS/CSP/security headers, endpoint-specific rate limits, request IDs, SSM-first access procedure, and emergency-access expiry. Commit `security: harden owner edge and operations access`.

### Task 20: Execute full release validation

**Objective:** Prove the feature and its rollback before production deployment.

**Files:**
- Create: `backend/tests/e2e/test_owner_administration_e2e.py`
- Create: `docs/operations/OWNER_ADMIN_RELEASE_CHECKLIST.md`

**Steps:**
1. Run unit, contract, repository, security, migration, backup, restore, cleanup, and UI tests.
2. Run the established backend contract suite with required test-only environment variables.
3. Run staging E2E: Owner MFA -> invitation -> Professor activation -> suspension/reactivation -> audit lookup.
4. Run a backup and isolated restore drill.
5. Capture row-count/integrity manifests.
6. Verify rollback on a staging copy.
7. Commit: `test: add owner administration release gate`.

## Phase 6 — Deployment

### Task 21: Deploy through a backup-gated migration

**Objective:** Release with verified rollback and no uncontrolled production changes.

**Steps:**
1. Review production dependency map and active Docker mounts.
2. Create and verify a timestamped online backup and off-instance upload.
3. Record pre-deployment health and table-count manifest.
4. Deploy application image without embedding secrets.
5. Apply reviewed migrations once through the migration job.
6. Restart one backend instance and verify readiness using `/openapi.json` and authenticated smoke tests; do not rely on an absent route.
7. Verify Owner authorization matrix, one disposable invitation lifecycle, database health, audit emission, backup status, and unrelated records.
8. Roll back application if acceptance gates fail; prefer forward database repair, using restore only when explicitly approved.
9. Record release, migration, backup, smoke-test, and rollback identifiers.

## Full Verification Commands

```bash
cd backend
export BIZSIMAI_JWT_SECRET='test-only-secret'
export DATABASE_URL='sqlite+aiosqlite:///:memory:'
export PYTHONPATH="$PWD"
.venv/bin/pytest tests/unit tests/repositories tests/contracts tests/security tests/operations tests/e2e -v
```

```bash
python -m compileall backend
```

```bash
curl -fsS https://staging-api.practenture.com/openapi.json >/dev/null
```

Expected final evidence:

- All existing and new backend tests pass.
- Non-Owner role matrix is 401/403 as designed.
- Invitation secret is one-time and absent from storage/list/log/audit output.
- A suspended account cannot log in or refresh.
- Seeded integrity violations are detected.
- Backup checksum/integrity/manifest pass and isolated restore succeeds.
- Scoped cleanup removes only tagged fixtures and preserves unrelated rows.
- Staging and production have distinct secrets, data, and backup prefixes.
- Production deployment includes verified backup and rollback evidence.
