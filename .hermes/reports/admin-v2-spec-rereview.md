# Admin V2 security-correction specification rereview

Date: 2026-07-28  
Branch/worktree reviewed: `admin-console-v2` at `/Users/luisborges/2026/Practenture-admin-v2`  
Disposition: **CHANGES REQUIRED — not PASS**

## Independent verification

- Read the authoritative `docs/plans/2026-07-28-admin-console-v2.md` and reviewed the actual uncommitted implementation/diff, migration, and all Admin V2 tests.
- Ran the controller gate from `backend/` with the repository root Python 3.11 virtualenv:
  - `PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m pytest tests/admin_v2 test_backend.py test_phase5.py -q`
  - Result: **69 passed, 1 skipped, 9 warnings**.
- Ran focused Admin V2 suite independently: **38 passed, 9 warnings**.
- `git diff --check`: clean.
- `backend/data.db` SHA-256 before and after the controller gate: `6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263` (unchanged).
- Confirmed source-level positives: normalized durable `(identity, Request.client.host)` throttling; integer `Retry-After`; `BEGIN IMMEDIATE` reservation/transaction behavior; sync FastAPI route/dependency functions for blocking SQLite/bcrypt; non-destructive CSRF session GET; conditional atomic touch/read with monotonic timestamps; one-time atomic backup-code consumption; migration-only ownership of the two new tables; migrated temporary test DB; V2 exception-handler header propagation; valid dummy bcrypt execution for unknown identities; no changes to legacy route handlers.

## Exact blocking gaps

### P1 — MFA is optional for owners without an enabled MFA row

`backend/admin_v2/repository.py:165-201` verifies MFA only when a row exists and `enabled == 1`; otherwise execution falls through and creates an owner session at `:202-228`. `backend/tests/admin_v2/test_mfa_security.py:158-166` explicitly locks this behavior in by requiring an MFA-disabled owner to receive 200.

This does not enforce the plan's owner-MFA prerequisite/cutover requirement. A missing or disabled MFA enrollment is treated as authentication success rather than fail-closed enrollment-required/MFA-required behavior. Backup-code one-time and rollback semantics are correct only for already-enabled MFA users; they do not close this bypass.

### P1 — Login “rotation” revokes every active owner session, allowing successful concurrent logins to return already-revoked credentials

`backend/admin_v2/repository.py:202-208` unconditionally revokes **all** active sessions for the owner before every insert. The sequential test at `backend/tests/admin_v2/test_auth_vertical_slice.py:103-114` asserts this global revocation, but there is no concurrent-login test.

An independent two-connection/barrier probe against a fresh migrated temporary DB produced:

```text
both_create_results= [(1, 'created'), (2, 'created')]
session_rows= [('id-1', None, None), ('id-2', '2026-07-28T12:00:01+00:00', 'login_rotation')]
active_count= 1
```

Thus both authentication transactions report `created`, while one transaction's returned credentials have already been revoked by the peer. At HTTP level the immediate `touch_active` narrows but does not eliminate the race: revocation can occur after touch and before the 200 response. This violates the security-correction invariant that a successful auth response must not carry invalidated session state. It also conflates fixation-safe token rotation with revoking unrelated sessions; the plan reserves revoke-all behavior for password reset/suspension, while exposing sessions as a plural resource.

## Additional specification/test gaps

### P2 — Alembic downgrade does not implement the specified empty-table rollback

The plan requires downgrade to remove only empty V2-owned tables/indexes and retain populated security state. `backend/migrations/versions/003_add_admin_v2_sessions.py:53-55` is an unconditional no-op. `backend/tests/admin_v2/test_migration_003.py:171-197` tests only the populated-retention branch and never tests empty-table removal. An explicit downgrade can therefore stamp revision `002` while leaving an empty revision-003 schema behind.

### P2 — Required defenses are implemented but not regression-proven precisely

- Unknown-user dummy bcrypt: `admin_v2.service` uses a valid dummy bcrypt hash and unknown-identity route tests exercise the path, but no test instruments/asserts that a bcrypt verification occurs for an unknown user. Removing the timing equalization would leave the current assertions passing.
- HTTP header preservation: the exception handler propagates `HTTPException.headers`, but `backend/tests/admin_v2/test_auth_vertical_slice.py:142-145` checks the 405 envelope and `Cache-Control` only; it does not assert the framework `Allow` header. The throttling suite does assert `Retry-After`, so that specific header is covered.
- Failed-upgrade rollback is not injected/tested. The migration test proves revision-002 data preservation and populated downgrade retention, but not rollback after a deliberately failed upgrade as required by the plan acceptance criteria.

## Verdict

**NOT PASS.** The green 69/1 gate is reproducible, but it does not detect the two P1 security/session-contract defects above, and several explicit rollback/header/timing requirements remain incompletely tested.
