# Admin V2 Auth/Session Final Specification Compliance Review

**Date:** 2026-07-28  
**Branch:** `admin-console-v2`  
**Scope:** Corrected first Admin V2 authentication/session security slice only  
**Governing plan:** `docs/plans/2026-07-28-admin-console-v2.md`  
**Verdict:** **PASS**

## Decision

No P0 or P1 specification-compliance defect was found in the current auth/session slice. The corrected implementation satisfies the slice's authentication, server-side session, CSRF, expiry, replay, concurrency, throttling, password-reset boundary, error-envelope, and additive-migration contracts. The production `/admin` cutover remains gated on owner MFA enrollment/enforcement and the later full-console work identified by the plan; that gate does not make the explicitly parallel, pre-cutover slice noncompliant.

## Review boundaries and evidence

Reviewed read-only:

- plan and current branch state/diff;
- `admin_v2/` routes, service, repository, dependencies, schemas, and errors;
- migration `003_add_admin_v2_sessions.py`;
- integration changes in `database.py`, `main.py`, `mfa.py`, `routers/auth.py`, `security.py`, and `tests/conftest.py`;
- all tests in `tests/admin_v2/`, plus the permitted legacy regression files `test_backend.py` and `test_phase5.py`.

Verification command:

```text
.venv/bin/python -m pytest -q tests/admin_v2 test_backend.py test_phase5.py
```

Result:

```text
111 passed, 1 skipped, 9 warnings in 38.12s
```

Production database guard:

```text
before: 6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263
after:  6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263
stable: true
```

`git diff --check` passed. Repository-wide pytest and every `test_code_only*` file were intentionally not run.

## Compliance matrix

| Requirement | Result | Evidence |
|---|---|---|
| Additive `/api/admin/v2` implementation; legacy `/admin` and `/api/owner` remain during parallel build | PASS | `main.py:261-263`; plan parallel-build/cutover requirements |
| Owner-only credential verification, active-status check, opaque server-managed cookie | PASS | `admin_v2/service.py:66-162`; `admin_v2/routes.py:35-55` |
| Unknown, malformed, and failed legacy hashes receive deterministic current-cost bcrypt work without public account/hash disclosure | PASS | `admin_v2/service.py:66-88`; `tests/admin_v2/test_login_timing_contract.py:50-117` includes the explicit unknown-user dummy-hash contract |
| Legacy SHA-256 password compatibility and transparent bcrypt migration | PASS | `admin_v2/service.py:73-82`; timing-contract test for successful migration |
| Durable layered pair + identity + client throttling; atomic reservations under concurrency; spoofed forwarding headers ignored | PASS | `admin_v2/repository.py:50-60,80-164`; `tests/admin_v2/test_layered_login_throttling.py` including cross-repository oversubscription and spoof tests |
| Dedicated SQLite connection for each auth mutation and `BEGIN IMMEDIATE` transaction ownership | PASS | `admin_v2/repository.py:49-60`; transaction-isolation and concurrency tests |
| Atomic TOTP step replay state and session creation, including one winner across connections and rollback on downstream failure | PASS | `admin_v2/repository.py:199-285`; `tests/admin_v2/test_totp_replay.py:79-155` |
| Presented-cookie-scoped login rotation; independent concurrent sessions survive; fixed/foreign cookie cannot revoke another owner | PASS | `admin_v2/service.py:90-149`; repository replacement-token predicate; `tests/admin_v2/test_concurrent_login_rotation.py` |
| Server-side session idle and absolute expiry, role/status revalidation, revocation, and logout | PASS | `admin_v2/service.py:164-210`; session-concurrency and auth vertical-slice tests |
| HttpOnly, Secure-by-default, SameSite=Strict cookie scoped to `/api/admin/v2`; no session token in browser storage/API body | PASS | `admin_v2/routes.py:45-54,71-78`; auth vertical-slice tests |
| CSRF required for cookie-authenticated mutations; constant-time CSRF comparison | PASS | `admin_v2/dependencies.py`; `admin_v2/service.py:190-202`; auth/MFA security tests |
| Atomic password reset, token consumption, password update, refresh revocation, and owner Admin-session revocation with rollback | PASS | `database.py:1217-1284`; `tests/admin_v2/test_password_reset_boundary.py` |
| Stable Admin V2 error envelope, request ID, generic auth failures, 429 `Retry-After`, and 405 `Allow` preservation | PASS | `main.py:106-181`, especially `main.py:142-149`; Admin V2 contract tests |
| Additive migration preserves revision-002 schema/data and intentionally retains security state on downgrade | PASS | `migrations/versions/003_add_admin_v2_sessions.py:14-83`; `tests/admin_v2/test_migration_003.py:133-256` verifies representative data before/after upgrade and non-destructive rollback policy |
| No test mutation of production `data.db` | PASS | SHA-256 remained stable across the complete permitted gate |

## MFA reconciliation

The current login code deliberately permits an otherwise valid owner whose MFA is not yet enabled. This is compliant with the first parallel `/admin-v2` slice: the accepted pre-cutover contract explicitly permits MFA-disabled owners while the new console is built alongside the legacy surface.

This is **not** approval to cut production `/admin` over in that state. The plan's release gate still requires the unique owner to have MFA enrolled and required before production cutover. Cutover must remain blocked until that operational/data precondition is demonstrated. MFA-enabled owners are already enforced correctly: a missing code is rejected, invalid codes are rejected, and an accepted TOTP step cannot be replayed sequentially or concurrently.

## Findings by severity

### P0

None.

### P1

None.

### P2 within this slice

No actionable P2 implementation defect was found.

### Deferred full-console work / release gates (not slice failures)

1. **Owner MFA cutover gate:** enroll and require MFA for the unique production owner before replacing legacy `/admin`.
2. **Remaining Admin V2 resources:** users, classes, sessions, AI connections, audit APIs, exports, frontend workflows, and their mutation/audit transaction coupling remain later plan tasks.
3. **Broader migration/cutover validation:** perform staging migration rehearsal, production backup/restore drill, complete release checklist, browser smoke tests, accessibility checks, and rollback rehearsal before cutover.
4. **Legacy removal:** remove legacy `/admin` and legacy owner surface only after feature parity, monitoring, and rollback confidence satisfy the plan.

## Non-blocking observations

- The test run emits nine deprecation warnings from Alembic path configuration and the TestClient compatibility layer. They do not affect this slice's correctness but should be cleaned up during dependency/tooling maintenance.
- Migration `003` intentionally uses a no-op downgrade to preserve security state. This matches the tested non-destructive rollback policy; operators must understand that application rollback does not remove the additive tables.

## Final conclusion

**PASS — the corrected Admin V2 auth/session slice has no P0/P1 blocker.** It is suitable to continue as the parallel Admin V2 foundation. This verdict does not authorize production `/admin` cutover until owner MFA and the plan's deferred full-console/release gates are complete.
