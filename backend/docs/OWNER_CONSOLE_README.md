# Practenture Owner Console — Operations Manual

**Version:** 1.0  
**Date:** 2026-07-26  
**Status:** Production Deployed

---

## Overview

The Owner Console is the administrative control plane for Practenture. It provides secure, audited access to:

- **Professor Invitations** — Create, track, and revoke onboarding invitations
- **Account Administration** — Suspend, reactivate, and force password resets
- **System Health** — Database integrity, connectivity, and domain invariant checks
- **Audit Trail** — Complete history of all Owner operations with before/after state
- **Backup & Restore** — Status monitoring and verified restore drills
- **Scoped Cleanup** — Safe test data removal with backup gates

**Access:** `https://practenture.com/owner`  
**API Base:** `https://api.practenture.com/api/owner`

---

## Quick Start

### Prerequisites
- [ ] Owner role account
- [ ] MFA enabled (TOTP)
- [ ] Recent authentication (< 15 min)

### First Login
1. Sign in at `https://practenture.com/owner`
2. Complete MFA challenge
3. Redirected to Dashboard

---

## Navigation

| Shortcut | Route | Description |
|---|---|---|
| `D` | `/owner` | Dashboard overview |
| `P` | `/owner/professors` | Professor & invitation management |
| `U` | `/owner/users` | User account administration |
| `H` | `/owner/system-health` | Database health checks |
| `A` | `/owner/audit` | Audit log viewer |
| `B` | `/owner/cleanup` | Backup status & cleanup plans |

---

## Core Workflows

### 🎓 Create Professor Invitation

1. Go to **Professors** → **Create Invitation**
2. Fill form:
   - **Organization** (required)
   - **Email** (required)
   - **Expires In** (1-168 hours, default 48)
   - **Max Uses** (default 1)
   - **Notes** (internal tracking)
   - **Change Ticket** (optional CM reference)
3. Click **Create Invitation**
4. **⚠️ COPY SECRET IMMEDIATELY** — Format: `PROF-ABCD-EFGH`
   - Secret shown **once only**
   - Send via secure channel to professor
5. Professor signs up at `/signup` with invitation code

### 👤 Pre-create Professor Account

1. Go to **Professors** → **Pre-create Professor**
2. Fill: Email, Name, Organization, Temporary Password
3. Account created in `pending` status
4. Professor sets own password on first login

### ⛔ Suspend/Reactivate User

1. Go to **Users** → Search for user
2. Click **Suspend** or **Reactivate**
3. Enter reason (required)
4. Confirm with MFA + recent auth
5. Action logged in audit trail

### 🔄 Force Password Reset

1. Go to **Users** → Select user
2. Click **Force Password Reset**
3. User must change password on next login
6. Audit event: `password_reset_forced`

---

## System Health Checks

Run: **System Health** → **Run Full Check** (10-30 sec)

| Check | Description | Threshold |
|---|---|---|
| `db_connectivity` | Query latency | < 100ms |
| `foreign_keys` | Zero FK violations | 0 |
| `unique_constraints` | Zero duplicate keys | 0 |
| `not_null` | Required columns populated | 0 |
| `session_professor_link` | All sessions have professor | 0 orphans |
| `team_membership` | Students in 1 team/session | 100% |
| `decision_round_bounds` | Decisions in valid rounds | 0 violations |
| `invitation_counters` | use_count ≤ max_uses | Valid |
| `account_status` | Status in enum | Valid |
| `backup_age` | Last backup < 24h | < 24h |
| `restore_drill` | Last drill < 7 days, passed | < 7d & PASS |

**Results:** ✅ Pass | ⚠️ Warning | ❌ Fail (critical)

---

## Audit Log

**Filters:** Actor, Action, Target Type, Date Range, Organization

### Key Actions Logged

| Action | Trigger |
|---|---|
| `invitation_created` | New invitation |
| `invitation_revoked` | Invitation disabled |
| `invitation_redeemed` | Professor claims |
| `professor_precreated` | Pre-create account |
| `user_suspended` | Account suspended |
| `user_reactivated` | Account restored |
| `password_reset_forced` | Reset required |
| `cleanup_plan_created` | Plan defined |
| `cleanup_plan_executed` | Cleanup run |

### Event Details
- **Before/After State** — JSON diff (secrets redacted)
- **Request Context** — IP, UA, Request ID
- **Idempotency Key** — If provided
- **Outcome** — Success/failure + error

**Export:** Filter → **Export CSV**

---

## Backup & Cleanup

### Backup Status
- Last backup time & duration
- File size & S3 location
- SHA-256 checksum
- Integrity check result
- Last restore drill: PASS/FAIL + date

### Cleanup Plans ⚠️ DESTRUCTIVE

**Create Plan:**
```
1. Cleanup → Create Cleanup Plan
2. Define scope (JSON):
{
  "organizations": ["org-uuid"],
  "sessionStatus": ["completed"],
  "olderThanDays": 90,
  "includeResults": true,
  "includeDecisions": true,
  "includeTeams": false
}
3. Preview → Review row counts
4. Create Plan → Generates hash
```

**Execute Plan:**
1. Select plan → **Execute**
2. Type: `DELETE TEST DATA PERMANENTLY`
3. Requires: Recent auth + MFA
4. Monitor in Cleanup Plans table

### Plan Status
| Status | Meaning |
|---|---|
| `pending` | Created, not executed |
| `executing` | Currently running |
| `completed` | Finished successfully |
| `failed` | Error (check audit log) |

---

## Security

### Required for Mutations
- ✅ Valid Owner token
- ✅ MFA enabled
- ✅ Recent auth (< 15 min)
- ✅ Idempotency key (unique per operation)

### Idempotency Key
```
curl -X POST https://api.practenture.com/api/owner/users/123/suspend \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: suspend-user-123-20260726-001"
```
- Unique per operation
- Stored 24 hours
- Prevents duplicate on retry

### Never Logged
- Passwords & token hashes
- Access/refresh tokens
- MFA secrets
- Invitation secrets
- Database credentials

---

## Status Reference

### User Status
| Status | Login | Data | Badge |
|---|---|---|---|
| `active` | ✅ | ✅ | <span style="background:#dcfce7;color:#166534;padding:2px 8px;border-radius:9999px;font-size:12px">active</span> |
| `suspended` | ❌ | ✅ | <span style="background:#fee2e2;color:#991b1b;padding:2px 8px;border-radius:9999px;font-size:12px">suspended</span> |
| `pending` | ✅ (first) | ✅ | <span style="background:#fef3c7;color:#92400e;padding:2px 8px;border-radius:9999px;font-size:12px">pending</span> |
| `disabled` | ❌ | ✅ (archived) | <span style="background:#f3f4f6;color:#374151;padding:2px 8px;border-radius:9999px;font-size:12px">disabled</span> |

### Invitation Status
| Status | Redeemable |
|---|---|
| `active` | ✅ |
| `redeemed` | ❌ |
| `expired` | ❌ |
| `revoked` | ❌ |

---

## API Reference

### Invitations
```
POST   /api/owner/professor-invitations
GET    /api/owner/professor-invitations
GET    /api/owner/professor-invitations/{id}
POST   /api/owner/professor-invitations/{id}/revoke
POST   /api/owner/professors/pre-create
```

### Users
```
GET    /api/owner/users?role=&status=&organizationId=&cursor=
GET    /api/owner/users/{id}
POST   /api/owner/users/{id}/suspend
POST   /api/owner/users/{id}/reactivate
POST   /api/owner/users/{id}/force-password-reset
```

### Health & Status
```
GET    /api/owner/system-health
GET    /api/owner/backup-status
```

### Audit
```
GET    /api/owner/audit-events?actor=&action=&targetType=&startDate=&endDate=
GET    /api/owner/audit-events/export
```

### Cleanup
```
POST   /api/owner/cleanup-plans
GET    /api/owner/cleanup-plans
POST   /api/owner/cleanup-plans/{id}/execute
```

### Headers Required
- `Authorization: Bearer <token>`
- `Idempotency-Key: <unique-key>` (mutations)

---

## Troubleshooting

| Issue | Resolution |
|---|---|
| "MFA required" | Enable MFA in profile |
| "Recent auth required" | Sign out → sign in |
| "Idempotency conflict" | Generate new unique key |
| "Org not found" | Verify org ID + permissions |
| "Invitation exists" | Revoke existing or use different email |
| Health check fails | Check DB connectivity, run `alembic current` |

---

## Emergency Contacts

- **Platform Support:** platform-support@practenture.com
- **Owner Escalation:** +1-XXX-XXX-XXXX
- **Rollback Procedure:** `docs/ROLLBACK_PLAN.md`

---

## Related Documentation

- **Low-Level Design:** `docs/architecture/ADMIN_DATABASE_LLD.md`
- **Implementation Summary:** `docs/IMPLEMENTATION_SUMMARY.md`
- **Rollback Plan:** `docs/ROLLBACK_PLAN.md`
- **Quick Reference:** `docs/OWNER_CONSOLE_QUICKREF.md`
- **HTML Help:** `/owner/help` (in console)

---

*Owner Console Operations Manual v1.0 — 2026-07-26*