# Admin V2 Corrected Auth/Session Security-Conformance Verdict

**Date:** 2026-07-28  
**Branch:** `admin-console-v2`  
**Review mode:** bounded, read-only defensive conformance review  
**Scope:** `backend/admin_v2`, `backend/auth.py`, `backend/database.py::complete_password_reset`, `backend/security.py`, `backend/mfa.py`, migration `003`, and their focused tests  
**Verdict:** **PASS — no P0/P1 defect found in the corrected slice.**

## Decision

The corrected auth/session slice implements the documented controls with no release-blocking security-conformance defect. It is acceptable as the parallel, pre-cutover Admin V2 foundation. This verdict does **not** approve production cutover: owner MFA must be enrolled and mandatory before the legacy owner surface is replaced.

## Requirement-to-evidence matrix

| Control | Result | Implementation and focused evidence |
|---|---|---|
| Opaque sessions and CSRF; no raw secret persistence | PASS | Random session token in `admin_v2/service.py:125-128`; only SHA-256 token/CSRF hashes stored by `admin_v2/repository.py:292-309`; deterministic session-bound CSRF uses configured HMAC secret at `service.py:58-64`; persistence assertions in `test_auth_vertical_slice.py`. |
| Cookie flags and scope | PASS | `HttpOnly`, Secure-by-default, `SameSite=Strict`, path `/api/admin/v2`, absolute `Max-Age`, and matching deletion attributes in `admin_v2/routes.py:45-53,71-77`; explicit production-safe override logic at `service.py:214-221`. |
| Controlled errors, no-store, request IDs | PASS | Stable Admin V2 envelopes and controlled 500 handling in `main.py:108-187`; `Cache-Control: no-store` and correlated `X-Request-ID` in `main.py:73-83,108-129`; protocol headers are preserved; focused 404/405/validation/500 tests in `test_auth_vertical_slice.py`. |
| MFA and one-time TOTP/backup behavior | PASS for accepted pre-cutover contract | Enabled MFA is checked in the same `BEGIN IMMEDIATE` transaction as replay-state consumption, backup-code consumption, session creation, and login-counter reset (`admin_v2/repository.py:199-316`). TOTP counters are resolved newest-first (`mfa.py:49-73`) and accepted only when newer than persisted state. Focused sequential, concurrent, rollback, TOTP, and backup tests are in `test_totp_replay.py` and `test_mfa_security.py`. MFA-disabled login remains intentionally allowed only during parallel enrollment. |
| Generic password failures and deterministic work | PASS | Unknown, malformed, failed legacy, and bcrypt paths are bounded and equalized in `admin_v2/service.py:66-88`; strict bcrypt classification is in `security.py:29-36,60-67`; public invalid-password response is generic at `service.py:117-119`; primitive-call and disclosure contracts are tested in `test_login_timing_contract.py`. |
| Bounded pair + identity + client failure counters | PASS | Durable normalized three-dimensional buckets, atomic reservation, bounded indexed cleanup, and longest active `Retry-After` are implemented in `admin_v2/repository.py:63-164`; cross-instance/concurrency, normalization, client-rotation, spoofed forwarding-header, and reset behavior are covered by `test_layered_login_throttling.py` and `test_login_throttling.py`. |
| Presented-cookie-only rotation | PASS | Only the cookie actually presented to login is passed as the replacement candidate (`admin_v2/routes.py:35-44`). Revocation requires its hash, the authenticated owner, and a currently unrevoked row (`repository.py:281-291`). Absent, unknown, fixed, revoked, or foreign-owner cookies cannot cause owner-wide revocation; concurrent successful responses remain valid per `test_concurrent_login_rotation.py`. |
| Idle, absolute expiry, revocation | PASS | Atomic active-state check/touch, fixed absolute expiry, monotonic idle/last-seen updates, expiry revocation, logout revocation, and current role/status revalidation are in `repository.py:318-374` and `service.py:164-211`; deterministic concurrency/expiry coverage is in `test_session_concurrency.py` and `test_auth_vertical_slice.py`. |
| Atomic password reset and all credential boundaries | PASS | `database.py:1228-1297` uses a separately owned connection and `BEGIN IMMEDIATE` to atomically consume the reset token, update the password and precise `password_changed_at`, revoke all refresh tokens, and revoke owner Admin sessions, with rollback on downstream failure. JWT issuers add precise `iat`, and verification rejects missing/malformed or pre-boundary `iat` when a boundary exists (`auth.py:74-86,89-145`). Concurrency, rollback, role isolation, legacy-schema compatibility, old access-token rejection, and new-token acceptance are tested in both password-reset focused files. |
| Additive migration and data safety | PASS | Revision `003` only creates new session/throttle/replay tables and indexes (`003_add_admin_v2_sessions.py:14-78`); downgrade intentionally retains security state (`:81-83`). `test_migration_003.py` verifies representative revision-002 schema/data preservation through upgrade and non-destructive downgrade. Runtime repository code does not own schema creation. |

## Severity disposition

- **P0:** None.
- **P1:** None.
- **P2 implementation defects in this bounded slice:** None identified.

### P2 hardening opportunities (non-blocking)

1. Consider storing backup codes as individually salted password-style hashes rather than reversible/plain values in `mfa_secrets.backup_codes`, while preserving transactional one-time consumption.
2. Protect stored TOTP seeds with an application-managed encryption/key-rotation scheme and restrict database backup access. This is defense in depth; replay prevention and one-time acceptance are already correct.
3. Document the intentional no-op migration downgrade prominently in operator runbooks so rollback does not create an incorrect expectation that security-state tables are removed.

## Verification basis and exclusions

- Existing controller gate supplied for this corrected state: **115 passed, 1 skipped**.
- Existing final specification review: **PASS**.
- This bounded pass independently inspected the listed implementation and focused test contracts; per instruction, it did not run tests, perform network activity, install dependencies, modify application code, or inspect unrelated surfaces.

## Cutover prerequisites (not current-slice failures)

1. **Mandatory owner MFA:** enroll the unique production owner and fail closed for missing/disabled/malformed enrollment before production `/admin` cutover.
2. Complete the remaining Admin V2 resource/frontend parity work and mutation/audit coupling required by the governing plan.
3. Rehearse migration, backup/restore, rollback, browser/accessibility smoke checks, monitoring, and incident procedures in staging.
4. Retire the legacy owner surface only after parity and rollback confidence are demonstrated.

## Final conclusion

**PASS.** The corrected auth/session slice has no P0/P1 blocker under the accepted parallel-enrollment contract. Production cutover remains blocked until owner MFA is mandatory and the deferred release gates are complete.
