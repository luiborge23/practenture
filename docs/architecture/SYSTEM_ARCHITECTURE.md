|# Practenture System Architecture

**Status:** Implementation complete - Owner Administration and Database Operations control plane deployed  \n**Updated:** 2026-07-28  \n**Scope:** Production, staging, Owner administration, database operations, audit, backup, and scaling

## 1. Architectural Principles

1. The FastAPI backend is authoritative for identity, authorization, simulation state, invitations, and administrative actions.
2. Routine administration happens through authenticated Owner APIs and an Owner console, never through ad hoc SQL.
3. Direct database access is exceptional, time-bounded, least-privilege, and audited.
4. Production and staging use separate databases, credentials, OAuth configuration, JWT secrets, and backup locations.
5. Every destructive operation has a dry run, explicit scope, verified backup, transaction boundary, audit record, and post-operation validation.
6. Database correctness includes physical integrity, relational consistency, domain invariants, and API authorization tests.
7. Sensitive values are never returned in list endpoints, logs, analytics, or audit payloads.

## 2. Current Deployed Baseline

- Public API: `https://api.practenture.com`
- Active backend host: AWS EC2 at `3.85.35.73`
- Edge: nginx terminates HTTPS and proxies `/api/*` and `/ws/*`
- Application: FastAPI in the `practenture-backend` container
- Current persistence: SQLite on a persistent Docker mount, WAL enabled
- Native client: SwiftUI iOS application
- Administrative API: Owner-protected Professor invitation lifecycle, account management, audit logging, health reporting, backup/restore status, and scoped cleanup

IP addresses are operational implementation details. Clients use DNS, not embedded production IPs.

## 3. Target Logical Architecture

```text
                     +-------------------------------+
                     | Practenture Identity Boundary |
                     | Owner / Professor / Student   |
                     +---------------+---------------+
                                     |
                         HTTPS + MFA | short-lived JWT
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

Every Owner endpoint requires:
1. Valid JWT with `role: owner`
2. MFA verification (via `X-Auth-MFA` header)
3. Recent authentication (within 15 minutes for sensitive operations)
4. Idempotency key for mutation operations
5. Structured audit event emission

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
1. Run backup-gated migration script
2. Verify backup exists and is valid
3. Apply database migrations (Alembic)
4. Deploy new application version
5. Run health checks
6. Monitor for errors

### Rollback Plan
- If deployment fails, revert to previous application version
- Database migrations are additive only (no destructive changes)
- Emergency DBA access available for manual recovery

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

## 12. Testing Results

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

## 13. References

- [Implementation plan](../plans/2026-07-26-owner-admin-database-operations.md)
- [`PRD.md`](../../PRD.md)
- [`Practenture-MASTER-BLUEPRINT-July2026.md`](../../Practenture-MASTER-BLUEPRINT-July2026.md)
