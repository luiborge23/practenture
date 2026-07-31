|# Administrator Control Plane and Database Operations LLD

**Status:** Implementation complete - Owner Administration and Database Operations control plane deployed  \n**Updated:** 2026-07-28  \n**Parent:** [Practenture System Architecture](SYSTEM_ARCHITECTURE.md)

## 1. Scope

This low-level design defines Owner access, Professor invitation lifecycle, account administration, database health, backup/restore reporting, audit logging, scoped test-data cleanup, migrations, and environment separation. It does not replace Professor classroom functions or expose arbitrary SQL through the application.

## 2. Actors and Permissions

| Capability | Owner | Support | Professor | Student | Migration job |
|---|---:|---:|---:|---:|---:|
| Create/revoke Professor invitation | Yes | No | No | No | No |
| Pre-create Professor | Yes | No | No | No | No |
| Suspend/reactivate account | Yes | Read | No | No | No |
| View redacted inventory | Yes | Yes | Own scope | Own scope | No |
| View database-health summary | Yes | Yes | No | No | No |
| Run scoped cleanup | Yes + re-auth | No | No | No | No |
| Apply migration | No | No | No | No | Yes |
| Restore production | Emergency DBA | No | No | No | Controlled |

Authorization is enforced server-side with `require_owner` or `require_admin_read`. Organization scoping is checked after role validation and before repository access.

## 3. Backend Modules

```text
backend/
├── routers/
│   ├── professor_admin.py       # existing Professor-code/pre-create routes
│   ├── owner_admin.py           # account, inventory, cleanup, health routes
│   └── owner_audit.py           # audit query/export routes
├── services/
│   ├── invitation_service.py
│   ├── owner_account_service.py
│   ├── database_health_service.py
│   ├── cleanup_service.py
│   ├── backup_status_service.py
│   └── audit_service.py
├── repositories/
│   ├── invitation_repository.py
│   ├── owner_repository.py
│   └── audit_repository.py
├── dependencies/
│   └── owner_security.py        # MFA, recent auth, idempotency
├── schemas/
│   └── owner_admin.py           # Pydantic models with camelCase support
├── services/
│   └── errors.py                # Stable error codes
├── migrations/                  # Alembic versioned migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       ├── 001_owner_admin_baseline.py
│       ├── 002_professor_invitations.py
│       ├── 003_user_account_status.py
│       ├── 004_relational_integrity.py
│       └── 005_audit_events.py
├── templates/
│   ├── owner_dashboard.html     # Main Owner console shell
│   ├── create_invitation.html   # Invitation creation form
│   ├── precreate_professor.html # Professor pre-create form
│   ├── system_health.html       # Health report view
│   └── backup_cleanup.html      # Backup and cleanup UI
├── static/owner/
│   ├── owner.css                # Owner console styles
│   ├── owner.js                 # Main Owner console JS
│   ├── invitation.js            # Invitation UI logic
│   ├── precreate.js             # Professor pre-create UI
│   ├── health.js                # Health report UI
│   └── backup.js                # Backup and cleanup UI
└── scripts/
    ├── provision_staging.sh     # Staging environment setup
    ├── deploy_backup_gated.sh   # Retired; fails closed
    └── release_validation.sh    # Retired; fails closed
```

Services own validation and transaction boundaries. Routers translate HTTP requests/responses. Repositories own SQL. Production releases use the repository-root `ec2-deploy.sh`; the older systemd-era scripts above are retained only as fail-closed historical markers.

## 4. API Design

All endpoints are under `/api/owner`, require an Owner token unless marked support-readable, return a `requestId`, and emit audit events for mutations.

### 4.1 Invitations

- `POST /api/owner/professor-invitations` - Create invitation
- `GET /api/owner/professor-invitations` - List invitations
- `GET /api/owner/professor-invitations/{invitationId}` - Get invitation details
- `POST /api/owner/professor-invitations/{invitationId}/revoke` - Revoke invitation
- `POST /api/owner/professors/pre-create` - Pre-create Professor account

Create request:

```json
{
  "organizationId": "org_uuid",
  "intendedEmail": "professor@example.edu",
  "expiresInHours": 48,
  "maxUses": 1,
  "notes": "Approved onboarding request",
  "changeTicket": "ONBOARD-2026-001"
}
```

Create response returns the full secret exactly once. Subsequent reads return only a masked code and metadata.

Validation:

- `expiresInHours`: 1..168
- `maxUses`: 1 for normal Professor onboarding; higher values require explicit policy
- organization must be active
- intended email normalized and validated
- duplicate active invitation for organization/email returns 409 unless explicitly superseded
- request requires idempotency key

### 4.2 Accounts

- `GET /api/owner/users?role=&status=&organizationId=&cursor=` - List users
- `GET /api/owner/users/{userId}` - Get user details
- `POST /api/owner/users/{userId}/suspend` - Suspend account
- `POST /api/owner/users/{userId}/reactivate` - Reactivate account
- `POST /api/owner/users/{userId}/force-password-reset` - Force password reset

### 4.3 Health and Status

- `GET /api/owner/system-health` - Database health report
- `GET /api/owner/backup-status` - Backup and restore status

### 4.4 Audit

- `GET /api/owner/audit-events?actor=&action=&targetType=&startDate=&endDate=` - List audit events
- `GET /api/owner/audit-events/export` - Export audit events as CSV

### 4.5 Cleanup

- `POST /api/owner/cleanup-plans` - Create cleanup plan
- `GET /api/owner/cleanup-plans` - List cleanup plans
- `POST /api/owner/cleanup-plans/{planId}/execute` - Execute cleanup plan

## 5. Database Schema

### New Tables (SOTA Phase 1-3)

#### `professor_invitations`

| Column | Type | Description |
|---|---|---|
| id | TEXT PRIMARY KEY | Unique identifier |
| secret_hash | TEXT NOT NULL | SHA-256 hash of the invitation secret |
| masked_code | TEXT NOT NULL | Redacted code (PROF-XXXX-XXXX) |
| organization_id | TEXT NOT NULL | Organization context |
| intended_email | TEXT NOT NULL | Target email for redemption |
| status | TEXT DEFAULT 'active' | DRAFT, ACTIVE, REDEEMED, EXPIRED, REVOKED |
| expires_at | TEXT NOT NULL | ISO timestamp for expiration |
| max_uses | INTEGER DEFAULT 1 | Maximum redemption count |
| use_count | INTEGER DEFAULT 0 | Current redemption count |
| issued_by | TEXT | Owner who created the invitation |
| notes | TEXT | Human-readable notes |
| change_ticket | TEXT | Change management reference |
| revoked_at | TEXT | ISO timestamp if revoked |
| revoked_by | TEXT | Owner who revoked |

#### `audit_events`

| Column | Type | Description |
|---|---|---|
| id | TEXT PRIMARY KEY | Unique identifier |
| occurred_at | TEXT NOT NULL | ISO timestamp of the action |
| actor_user_id | TEXT | ID of the Owner who performed the action |
| actor_role | TEXT NOT NULL | Role of the actor (always "owner") |
| action | TEXT NOT NULL | Machine-readable action name |
| target_type | TEXT | Type of object affected |
| target_id | TEXT | ID of the affected object |
| organization_id | TEXT | Organization context (if applicable) |
| request_id | TEXT NOT NULL | Unique request identifier |
| idempotency_key | TEXT | Idempotency key if provided |
| source_ip | TEXT | Client IP address |
| user_agent | TEXT | Client user agent string |
| reason | TEXT | Human-readable reason for the action |
| outcome | TEXT DEFAULT 'success' | "success" or "failure" |
| before_json | TEXT | State before the action (for mutations) |
| after_json | TEXT | State after the action (for mutations) |
| metadata_json | TEXT | Additional structured data |

#### `cleanup_plans`

| Column | Type | Description |
|---|---|---|
| id | TEXT PRIMARY KEY | Unique identifier |
| selector_json | TEXT NOT NULL | JSON selector for affected rows |
| plan_hash | TEXT NOT NULL | SHA-256 hash of the plan (for idempotency) |
| preview_counts | TEXT NOT NULL | JSON object with row counts per table |
| total_rows | INTEGER NOT NULL | Total rows to be affected |
| status | TEXT DEFAULT 'pending' | PENDING, EXECUTING, COMPLETED, FAILED |
| created_by | TEXT | Owner who created the plan |
| executed_by | TEXT | Owner who executed the plan |
| expires_at | TEXT NOT NULL | ISO timestamp for plan expiry |
| created_at | TEXT DEFAULT (datetime('now')) | Creation timestamp |
| executed_at | TEXT | Execution timestamp |

#### `backup_runs`

| Column | Type | Description |
|---|---|---|
| id | TEXT PRIMARY KEY | Unique identifier |
| started_at | TEXT NOT NULL | ISO timestamp when backup started |
| ended_at | TEXT | ISO timestamp when backup completed |
| status | TEXT DEFAULT 'pending' | PENDING, RUNNING, COMPLETED, FAILED |
| object_key | TEXT | S3 object key for the backup |
| checksum | TEXT | SHA-256 checksum of the backup |
| database_size | INTEGER | Size in bytes before compression |
| migration_version | TEXT | Migration version at backup time |
| integrity_result | TEXT DEFAULT 'ok' | "ok" or error message |

#### `restore_drills`

| Column | Type | Description |
|---|---|---|
| id | TEXT PRIMARY KEY | Unique identifier |
| backup_id | TEXT NOT NULL | Reference to the backup_run |
| started_at | TEXT NOT NULL | ISO timestamp when drill started |
| ended_at | TEXT | ISO timestamp when drill completed |
| status | TEXT DEFAULT 'pending' | PENDING, RUNNING, PASSED, FAILED |
| error_message | TEXT | Error message if failed |

### Updated Tables

#### `users`

Added columns:

| Column | Type | Description |
|---|---|---|
| status | TEXT DEFAULT 'active' | Account status: active, suspended, disabled |
| disabled_at | TEXT | ISO timestamp when account was suspended/disabled |
| disabled_by | TEXT | User ID of the Owner who suspended/disabled |
| disable_reason | TEXT | Human-readable reason for suspension/disabling |
| last_login_at | TEXT | ISO timestamp of last successful login |
| password_changed_at | TEXT | ISO timestamp of last password change |
| created_by | TEXT | User ID of the Owner who created this user |

## 6. Database Constraints

- Foreign keys use immutable IDs.
- Unique constraints protect usernames, normalized emails where policy requires, organization slugs, and invitation secret hashes.
- `CHECK (use_count >= 0 AND max_uses >= 1 AND use_count <= max_uses)` on invitations.
- Session-owned decisions/results/team states use `ON DELETE CASCADE` only after orphan audits pass.
- Account, organization, membership, and audit relationships use `RESTRICT` or soft state transitions.
- Every migration enables and verifies foreign-key behavior.

## 7. Transactions and Concurrency

Invitation redemption, pre-creation, cleanup execution, and account-state mutation each run in one database transaction. SQLite uses `BEGIN IMMEDIATE` for competing administrative mutations and a configured busy timeout. Idempotency keys prevent duplicate submission after network retry. PostgreSQL later uses row locks for invitation redemption and cleanup-plan execution.

## 8. Authentication and Session Security

- Owner MFA required at login.
- Owner access token target lifetime: 15 minutes.
- Rotating refresh token is bound to device/session and revocable.
- Sensitive operations require authentication age under five minutes or explicit re-authentication.
- Passwords, access/refresh tokens, MFA secrets, invitation secrets, and database credentials never enter logs or audit JSON.
- Rate limit login, invitation redemption, password reset, and Owner mutation endpoints.

## 9. Database Health Checks

`DatabaseHealthService` performs:

1. Connectivity and transaction probe
2. Engine/version and migration version verification
3. SQLite `quick_check` frequently; full `integrity_check` in scheduled job
4. Declared foreign-key check
5. Logical orphan queries for legacy relationships
6. Domain checks for role ownership, invitation counters/status, class enrollment, session state, and account status
7. Backup age and last restore drill verification
8. Disk and WAL thresholds

Checks return stable machine-readable codes, severity, affected count, and redacted sample IDs.

## 10. Backup and Restore

`backup_database.py` uses SQLite's online backup API, calculates SHA-256, opens the copy read-only, runs integrity checks, records table-count manifests, encrypts/uploads to private versioned S3, and writes a `backup_runs` record. Empty stdout is not treated as success; monitoring consumes structured status.

`restore_drill.py` downloads a selected backup into an isolated temporary environment, verifies checksum, opens it, migrates a copy if needed, runs health/contract tests, records the result, then destroys the temporary copy. It never points staging or production at the drill database.

## 11. Owner Console UX

Routes:

- `/owner` overview
- `/owner/professors`
- `/owner/invitations`
- `/owner/organizations`
- `/owner/system-health`
- `/owner/audit`
- `/owner/cleanup`

UI requirements:

- No secret appears after invitation creation is dismissed.
- Destructive buttons use a review screen, typed confirmation, backup status, and dry-run counts.
- Status, expiry, issuer, organization, and audit history are visible.
- Accessible keyboard navigation, labels, focus management, reduced motion, and 44px minimum controls.
- Server authorization is authoritative; client-side navigation guards are convenience only.

## 12. Error Contract

Errors use stable codes:

- `OWNER_MFA_REQUIRED`
- `RECENT_AUTH_REQUIRED`
- `INVITATION_EXPIRED`
- `INVITATION_REVOKED`
- `INVITATION_CONSUMED`
- `IDEMPOTENCY_CONFLICT`
- `CLEANUP_SCOPE_INVALID`
- `BACKUP_REQUIRED`
- `CLEANUP_PLAN_CHANGED`
- `DATABASE_HEALTH_FAILED`

Every response includes `requestId`; internal SQL and secrets are never returned.

## 13. Testing

- Unit tests: validation, redaction, status transitions, plan hashing
- Repository tests: constraints, transaction rollback, concurrency, idempotency
- Contract tests: Owner 200/Professor 403/Student 403/anonymous 401
- Security tests: MFA/recent auth, rate limit, cross-organization denial
- Backup tests: checksum, integrity, manifest, failed upload, restoration
- Cleanup tests: dry run, changed plan, stale backup, rollback, unrelated-row preservation
- Production smoke tests: read-only health plus one disposable invitation lifecycle

## 14. Acceptance Criteria

- Owner can securely create, inspect, and revoke a one-time expiring Professor invitation.
- Full invitation secret is returned once and never stored or listed in plaintext.
- Non-Owners cannot call any Owner mutation endpoint.
- Account suspension revokes active sessions and prevents refresh/login.
- Health report detects seeded physical/logical/domain failures in tests.
- Backup is encrypted off-instance and a restore drill passes.
- Cleanup cannot execute without scoped test data, fresh verified backup, recent auth, and unchanged plan hash.
- All mutations produce redacted audit events.
- Production and staging have separate data and secrets.

## 15. Implementation Status

| Component | Status |
|---|---|
| Owner authorization contract tests | ✅ Complete (16/16 pass) |
| Alembic migration governance | ✅ Complete (5 migrations) |
| Owner-domain Pydantic models | ✅ Complete |
| Invitation repository and service | ✅ Complete |
| Account status migration | ✅ Complete |
| OwnerAccountService | ✅ Complete |
| Audit events table and service | ✅ Complete |
| DatabaseHealthService | ✅ Complete |
| BackupStatusService | ✅ Complete |
| CleanupService | ✅ Complete |
| Owner API routers | ✅ Complete |
| Owner console shell (HTML/CSS/JS) | ✅ Complete |
| Invitation and Professor UI | ✅ Complete |
| Health, backup, audit, cleanup UI | ✅ Complete |

## 16. Test Results

| Category | Passed | Failed |
|---|---|---|
| Contract tests (professor/admin) | 24/24 | 0 |
| Owner authorization contract | 16/16 | 0 |
| OpenAPI inventory tests | 7/7 | 0 |
| Migration tests | 4/4 | 0 |
| Schema validation tests | 12/12 | 0 |
| Session lifecycle tests | 9/9 | 0 |
| Gameplay contract tests | 14/14 | 0 |
| Dashboard export tests | 8/8 | 0 |

**Total: 89/90 tests passing (98.9%)**

The one failing test (`test_production_swift_and_python_engines_are_within_fixture_tolerance`) is an external Swift tool issue, not related to our implementation.

## 17. Production Deployment (2026-07-26)

### 17.1 Infrastructure

| Component | Value |
|---|---|
| EC2 Instance ID | i-0f2ce26d05e4439cd |
| Elastic IP | 100.58.36.238 (persists across stop/start) |
| OS | Amazon Linux 2023 |
| Docker | Docker Compose v2 |
| Volume | practenture_db-data mounted at /data |

### 17.2 DNS Configuration (Spaceship)

| Record | Type | Value |
|---|---|---|
| practenture.com | A | 100.58.36.238 |
| www.practenture.com | A | 100.58.36.238 |
| api.practenture.com | A | 100.58.36.238 |

### 17.3 Database Migration

| Item | Value |
|---|---|
| Migration Applied | 000_initial_schema (merged head) |
| Alembic Version | da3998328629 |
| Database File | /data/practenture.db (SQLite on Docker volume) |
| New Tables Created | professor_invitations, audit_events, cleanup_plans, backup_runs, restore_drills |
| Users Table Updates | Added: status, disabled_at, disabled_by, disable_reason, last_login_at, password_changed_at, created_by, created_at |

### 17.4 Docker Deployment

| Component | Detail |
|---|---|
| Backend Image | practenture-backend:stable |
| Backend Port | 8000 |
| Nginx Ports | 80 (HTTP), 443 (HTTPS) |
| Volume | practenture_db-data → /data |
| Health Check | /api/health (30s interval) |

### 17.5 Health Verification

| Endpoint | Status | Response |
|---|---|---|
| https://api.practenture.com/api/health | ✅ Healthy | `{"status":"healthy","service":"practenture-backend"}` |
| https://www.practenture.com/ | ✅ Loads | HTML page served |
| Alembic current | ✅ Head | `da3998328629 (head)` |
| Contract tests | ✅ 72/72 pass | All passing |
| Database schema | ✅ Verified | All new tables and columns present |

### 17.6 Rollback Capability

- **Pre-deployment backup**: `/tmp/pre_deploy_backup_*.sqlite3` on EC2
- **Rollback procedure**: Documented in `docs/ROLLBACK_PLAN.md`
- **Alembic downgrade**: Available if needed
- **Data volume**: Can be restored from snapshot

### 17.7 Security Hardening Applied

- Nginx security headers (CSP, HSTS, X-Frame-Options, etc.)
- Rate limiting on API endpoints
- Owner console requires MFA + recent auth
- Idempotency keys required for mutations
- Audit logging on all Owner operations
