# Practenture System Architecture

**Status:** Implementation complete — Admin V2 control plane and Administrator MFA deployed
**Updated:** 2026-07-31
**Scope:** Production, staging, Administrator control plane, database operations, audit, backup, and scaling

## 1. Architectural Principles

1. The FastAPI backend is authoritative for identity, authorization, simulation state, invitations, and administrative actions.
2. Routine administration happens through authenticated Owner APIs and an Owner console, never through ad hoc SQL.
3. Direct database access is exceptional, time-bounded, least-privilege, and audited.
4. Production and staging use separate databases, credentials, OAuth configuration, JWT secrets, and backup locations.
5. Every destructive operation has a dry run, explicit scope, verified backup, transaction boundary, audit record, and post-operation validation.
6. Database correctness includes physical integrity, relational consistency, domain invariants, and API authorization tests.
7. Sensitive values are never returned in list endpoints, logs, analytics, or audit payloads.

## 2. Current Deployed Baseline

- Public application and API origin: `https://practenture.com`
- Active backend host: AWS EC2 at `100.58.36.238` (operational detail; clients use DNS)
- Edge: nginx terminates HTTPS and proxies `/api/*` and `/ws/*`
- Application: FastAPI in the `practenture-backend` container
- Current persistence: SQLite on a persistent Docker mount, WAL enabled
- Native client: SwiftUI iOS application
- Administrative API: Admin V2 opaque-session control plane with Administrator TOTP MFA, Professor invitation lifecycle, account management, audit logging, health reporting, backup/restore status, and scoped cleanup

IP addresses are operational implementation details. Clients use DNS, not embedded production IPs.

## 3. Target Logical Architecture

```text
                     +-------------------------------+
                     | Practenture Identity Boundary |
                     | Owner / Professor / Student   |
                     +---------------+---------------+
                                     |
                  HTTPS + role auth | Admin opaque session + MFA
                                     v
+-------------------+       +--------+---------+       +--------------------+
| iOS Student /     |       | nginx / WAF      |       | Owner Admin Console|
| Professor Client  +------>+ api.practenture  +<------+ admin.practenture  |
+-------------------+       +--------+---------+       +----------+---------+
                                    |                            |
                                    | private container network  | Owner APIs only
                                    v                            v
                          +---------+------------------------------+
                          | FastAPI Application                    |
                          |                                        |
                          | AuthN/AuthZ   Simulation   Admin API    |
                          | Invitation    Organization Audit       |
                          | Data Health   Backup Status Cleanup     |
                          +---------+------------------+-----------+
                                    |                  |
                          transactions|                  | structured events
                                    v                  v
                         +-----------+------+   +-------+-------------+
                         | Persistence      |   | Audit/Observability |
                         | SQLite now       |   | append-only events  |
                         | PostgreSQL target|   | metrics + alerts    |
                         +------+-----------+   +---------------------+
                                |
                                | encrypted online backups
                                v
                         +------+-------------------+
                         | Private versioned S3     |
                         | retention + restore tests|
                         +--------------------------+
```

## 4. Trust Zones

| Zone | Components | Rules |
|---|---|---|
| Public client | iOS and browser | No database credentials; API only |
| Edge | DNS, TLS, nginx/WAF | HTTPS only; request IDs; rate limits |
| Application | FastAPI container | Role and tenant authorization on every request |
| Administrative | Owner console/API | MFA, shorter sessions, re-authentication for destructive actions |
| Data | SQLite persistent mount; future RDS | Not publicly reachable; encrypted backup/export |
| Operations | AWS SSM, CI/CD, migration job | Named users, least privilege, complete audit trail |

## 5. Administrative Control Plane

The Owner console is a separate route and authorization surface from the Professor dashboard. It provides:

- **Professor invitation lifecycle**: creation, listing, expiration, revocation, and redemption status
- **Professor pre-creation**: with forced password change on first login
- **Organization and membership management**: multi-tenant support
- **Account administration**: suspension/reactivation without destructive deletion
- **Read-only inventory**: users, classes, sessions, and test records
- **Database health reporting**: schema consistency, foreign key integrity, last backup status
- **Backup and restore status**: verifiable online backups with S3 retention
- **Scoped cleanup workflow**: explicitly tagged disposable data with dry-run preview
- **Searchable administrative audit log**: all Owner actions recorded

Every Admin V2 endpoint requires the assurance appropriate to its operation:
1. A server-managed opaque session in a `Secure`, `HttpOnly`, `SameSite=Strict` cookie with `role: owner`.
2. CSRF validation for every mutation.
3. Recent password plus current TOTP/recovery-factor proof for high-assurance changes.
4. Durable account/client throttling around password and factor verification.
5. Idempotency where retrying a mutation could duplicate work.
6. Structured, redacted audit event emission in the mutation transaction.

Administrator MFA uses a pending-enrollment state, AES-GCM-protected TOTP seeds, hashed one-time recovery codes, transactional replay protection, and atomic challenge/session creation. See [Administrator MFA LLD](ADMIN_MFA_LLD.md).

Hiding an Owner button is not authorization - all endpoints enforce server-side checks.

## 6. Professor Invitation Lifecycle

```text
DRAFT -> ACTIVE -> REDEEMED
                 -> EXPIRED
                 -> REVOKED
```

- **DRAFT**: Invitation created but not yet sent (internal state)
- **ACTIVE**: Invitation is valid and can be redeemed
- **REDEEMED**: Invitation successfully used to create a professor account
- **EXPIRED**: Time-to-live has passed without redemption
- **REVOKED**: Manually revoked by Owner before redemption

Each invitation has:
- `max_uses`: Number of times the secret can be redeemed (default: 1)
- `use_count`: Current redemption count
- `expires_at`: ISO timestamp for expiration

## 7. Account Status Model

Users have a status field with the following values:

| Status | Description |
|---|---|
| `active` | User can authenticate and use the system normally |
| `suspended` | User cannot authenticate; requires Owner action to reactivate |
| `disabled` | User account is disabled (e.g., permanent ban) |

Suspension includes:
- `disabled_at`: ISO timestamp when suspension occurred
- `disabled_by`: User ID of the Owner who suspended
- `disable_reason`: Human-readable reason for suspension

## 8. Audit Events Schema

All administrative actions emit structured audit events with:

| Field | Description |
|---|---|
| `occurred_at` | ISO timestamp of the action |
| `actor_user_id` | ID of the Owner who performed the action |
| `actor_role` | Role of the actor (always "owner" for Owner actions) |
| `action` | Machine-readable action name (e.g., "invitation_created", "user_suspended") |
| `target_type` | Type of object affected (e.g., "invitation", "user") |
| `target_id` | ID of the affected object |
| `organization_id` | Organization context (if applicable) |
| `request_id` | Unique request identifier for correlation |
| `idempotency_key` | Idempotency key if provided |
| `source_ip` | Client IP address |
| `user_agent` | Client user agent string |
| `reason` | Human-readable reason for the action |
| `outcome` | "success" or "failure" |
| `before_json` | State before the action (for mutations) |
| `after_json` | State after the action (for mutations) |

## 9. Backup and Restore

### Online Backups
- SQLite database backed up to S3 with versioned retention
- Checksum verification for integrity
- Migration version recorded for restore compatibility

### Restore Drills
- Automated restore to isolated environment on a schedule
- Database health verification after restore
- Results recorded in `restore_drills` table

### Backup Gates
- All destructive Owner operations require verified backup within retention window
- Cleanup operations require backup before execution

## 10. Deployment Pipeline

### Staging Environment
- Isolated from production (separate database, credentials)
- Same codebase as production
- Used for final validation before production deployment

### Production Deployment
1. Qualify the exact source SHA through all five required CI jobs with zero Check annotations.
2. Build and compare deterministic release artifacts.
3. Promote only with `./ec2-deploy.sh deploy`.
4. Verify the predeployment backup checksum and isolated restore drill.
5. Apply Alembic migrations through the deployment transaction.
6. Atomically promote the release symlink and immutable image.
7. Verify internal containers, public HTTPS/TLS, source/image revision, database integrity, and rollback evidence.

### Rollback Plan
- Use the rollback operation provided by `ec2-deploy.sh`; do not replace containers manually.
- Roll back to the previous exact-SHA-qualified immutable image and release manifest.
- Restore database state only from a verified predeployment backup after isolated restore validation.
- Re-run public/internal health, source revision, database integrity, Admin login, and audit checks.

## 11. Implementation Status

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
| Administrator MFA lifecycle and Account security UI | ✅ Complete and enrolled in production |
| Durable MFA throttling, replay, and recovery-code races | ✅ Complete |

## 12. Testing Results

Release `1abb1aaee2dd49b59790a4b3c232cacdb3e2848a` passed the full local backend/release suite (**502 tests**) and all five exact-SHA CI jobs in run `30670330492`, with zero GitHub Check annotations. The required iOS Golden Formula parity test passed on Xcode 26.5 with iOS runtime 26.5. Production deployment, Administrator enrollment, fresh TOTP login, database integrity, public HTTPS health, backup, and rollback evidence all passed.

## 13. References

- [Implementation plan](../plans/2026-07-26-owner-admin-database-operations.md)
- [Administrator MFA LLD](ADMIN_MFA_LLD.md)
- [`PRD.md`](../../PRD.md)
- [`Practenture-MASTER-BLUEPRINT-July2026.md`](../../Practenture-MASTER-BLUEPRINT-July2026.md)
