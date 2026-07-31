# Owner Console — Quick Reference Card

> **Superseded for live operations — 2026-07-31:** Use [`ADMIN_V2_OPERATIONS.md`](ADMIN_V2_OPERATIONS.md). Admin V2 is served at `https://practenture.com/admin/v2/` and uses opaque cookie sessions plus CSRF and TOTP MFA; the legacy `/owner` routes and bearer-token examples below are historical.

## Access
**URL:** `https://practenture.com/owner`  
**API:** `https://api.practenture.com/api/owner`  
**Requires:** Owner role + MFA + Recent auth (< 15 min)

---

## Keyboard Shortcuts

| Key | Route | Section |
|-----|-------|---------|
| `D` | `/owner` | Dashboard |
| `P` | `/owner/professors` | Professors & Invitations |
| `U` | `/owner/users` | User Accounts |
| `H` | `/owner/system-health` | System Health |
| `A` | `/owner/audit` | Audit Log |
| `B` | `/owner/cleanup` | Backup & Cleanup |
| `?` | `/owner/help` | This Reference |

---

## Common Workflows

### 🎓 Create Professor Invitation
```
1. P → Create Invitation
2. Fill: Org, Email, Expires (hrs), Max Uses
3. Create → COPY SECRET IMMEDIATELY
   Format: PROF-ABCD-EFGH
   (Shown ONCE only)
4. Send securely to professor
```

### 👤 Pre-create Professor
```
1. P → Pre-create Professor
2. Fill: Email, Name, Org, Temp Password
3. Creates account in 'pending' status
```

### ⛔ Suspend User
```
1. U → Search user
2. Click user → Suspend
3. Reason + MFA + Recent Auth
4. Audit: user_suspended
```

### 🔄 Reactivate User
```
1. U → Find suspended user
2. Click → Reactivate
3. MFA + Recent Auth
```

### 🔐 Force Password Reset
```
1. U → Select user
2. Force Password Reset
3. User changes on next login
4. Audit: password_reset_forced
```

---

## System Health Checks

Run: **H → Run Full Check** (10-30s)

| Check | Pass Criteria |
|-------|---------------|
| `db_connectivity` | Query < 100ms |
| `foreign_keys` | 0 violations |
| `unique_constraints` | 0 duplicates |
| `not_null` | 0 NULLs in required |
| `session_professor_link` | 0 orphans |
| `team_membership` | 1 team/student/session |
| `decision_round_bounds` | 0 violations |
| `invitation_counters` | use ≤ max |
| `account_status` | Valid enum |
| `backup_age` | < 24h |
| `restore_drill` | < 7d, PASS |

**Results:** ✅ Pass | ⚠️ Warning | ❌ Fail

---

## Audit Log Filters

- **Actor** — Owner email
- **Action** — Operation type
- **Target** — user, invitation, cleanup_plan...
- **Date Range** — Start/End
- **Organization** — Scope

### Key Actions
| Action | Description |
|--------|-------------|
| `invitation_created` | New invitation |
| `invitation_revoked` | Disabled |
| `invitation_redeemed` | Claimed |
| `professor_precreated` | Pre-create |
| `user_suspended` | Suspended |
| `user_reactivated` | Restored |
| `password_reset_forced` | Reset required |
| `cleanup_plan_created` | Plan defined |
| `cleanup_plan_executed` | Cleanup run |

**Export:** Filter → **Export CSV**

---

## Backup & Cleanup

### Backup Status
- Last backup time & duration
- Size & S3 location
- SHA-256 checksum
- Integrity: ✅/❌
- Last restore drill: PASS/FAIL + date

### Cleanup Plans ⚠️ DESTRUCTIVE

**Create:**
```
B → Create Cleanup Plan
Scope (JSON):
{
  "organizations": ["org-uuid"],
  "sessionStatus": ["completed"],
  "olderThanDays": 90,
  "includeResults": true,
  "includeDecisions": true,
  "includeTeams": false
}
Preview → Review counts → Create Plan
```

**Execute:**
1. Select plan → Execute
2. Type: `DELETE TEST DATA PERMANENTLY`
3. MFA + Recent Auth required
4. Monitor in Cleanup Plans table

### Plan Status
| Status | Meaning |
|--------|---------|
| `pending` | Created, not run |
| `executing` | Running now |
| `completed` | Success |
| `failed` | Error (check audit) |

---

## Security Essentials

### Required for Mutations
- ✅ Valid Owner token
- ✅ MFA enabled
- ✅ Recent auth (< 15 min)
- ✅ Idempotency-Key (unique per op)

### Idempotency Example
```bash
curl -X POST https://api.practenture.com/api/owner/users/123/suspend \
  -H "Authorization: Bearer <token>" \
  -H "Idempotency-Key: suspend-123-20260726-001"
```

### Never Logged
- Passwords & token hashes
- Access/refresh tokens
- MFA secrets
- Invitation secrets
- DB credentials

---

## Status Badges

### User Status
| Status | Login | Badge |
|--------|-------|-------|
| `active` | ✅ | 🟢 active |
| `suspended` | ❌ | 🔴 suspended |
| `pending` | First only | 🟡 pending |
| `disabled` | ❌ | ⚫ disabled |

### Invitation Status
| Status | Redeemable |
|--------|------------|
| `active` | ✅ |
| `redeemed` | ❌ |
| `expired` | ❌ |
| `revoked` | ❌ |

---

## Rate Limits

| Endpoint | Limit |
|----------|-------|
| API | 60 req/min |
| Auth | 10 req/min |
| Cleanup execute | 1/hr |

---

## Quick Fixes

| Error | Fix |
|-------|-----|
| "MFA required" | Enable MFA in profile |
| "Recent auth required" | Sign out → sign in |
| "Idempotency conflict" | New unique key |
| "Org not found" | Verify org ID + perms |
| "Invitation exists" | Revoke old or use diff email |
| Health check fails | Check DB, `alembic current` |

---

## Emergency

- **Support:** platform-support@practenture.com
- **Escalation:** +1-XXX-XXX-XXXX
- **Rollback:** `docs/ROLLBACK_PLAN.md`

---

## Files

| Doc | Path |
|-----|------|
| LLD | `docs/architecture/ADMIN_DATABASE_LLD.md` |
| Implementation | `docs/IMPLEMENTATION_SUMMARY.md` |
| Rollback | `docs/ROLLBACK_PLAN.md` |
| Full Manual | `docs/OWNER_CONSOLE_README.md` |
| HTML Help | `/owner/help` |

---

*v1.0 — 2026-07-26*