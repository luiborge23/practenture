# Admin Console V2 Backend Quality Rereview

**Date:** 2026-07-28  
**Scope:** backend correctness, concurrency, transactions, performance, maintainability, migrations, middleware, and test confidence  
**Verdict:** **FAIL** — two P1 release blockers remain. No P0 found.

## Executive summary

The Admin V2 route/dependency/service/repository slice is compact and generally well structured. Its synchronous FastAPI endpoints correctly keep blocking SQLite and bcrypt work in Starlette's worker threadpool. Session rotation, revocation, durable throttle reservations, cross-connection SQLite serialization, monotonic touch updates, stable error envelopes, cookie attributes, and immediate rejection of sessions belonging to a suspended owner are implemented and covered reasonably well.

The slice is not release-ready because its transaction abstraction assumes exclusive ownership of a process-wide SQLite connection that the legacy `Database` API does not enforce. A concurrent legacy password migration can commit an Admin V2 transaction from another thread, defeating rollback. Independently, an accepted TOTP is reusable for repeated logins during its validity window; no consumed time-step/replay state is stored. The current tests pass while missing both interleavings.

## Trace reviewed

- Route: `backend/admin_v2/routes.py`
- Dependencies: `backend/admin_v2/dependencies.py`
- Service: `backend/admin_v2/service.py`
- Repository/transactions: `backend/admin_v2/repository.py`
- Shared database implementation: `backend/database.py`
- MFA implementation: `backend/mfa.py`
- Migration: `backend/migrations/versions/003_add_admin_v2_sessions.py`
- Alembic environment: `backend/migrations/env.py`
- App mounts, exception handlers, and security middleware: `backend/main.py`
- Deployment proxy/process configuration: `backend/Dockerfile`, `nginx.conf`, `nginx-practenture.conf`
- Admin V2 migration/auth/MFA/throttle/concurrency tests under `backend/tests/admin_v2/`

## P1 findings (release blockers)

### P1-1 — Admin transactions can be committed by an unrelated thread on the shared SQLite connection

**Evidence**

- `AdminSessionRepository._transaction()` takes `self._db._lock`, executes `BEGIN IMMEDIATE`, then commits or rolls back (`backend/admin_v2/repository.py:47-58`).
- The process-wide `Database` owns one connection configured with `check_same_thread=False` (`backend/database.py:51-66`).
- The legacy password migration used by Admin V2 login calls `db.update_user_password()` (`backend/admin_v2/service.py:58-71`).
- `update_user_password()` uses the same connection without taking `db._lock` (`backend/database.py:805-813`). Python's SQLite connection context manager commits the connection on normal exit.

**Reproduced invariant violation**

On an isolated migrated temporary database, thread A opened `AdminSessionRepository._transaction()`, inserted a throttle row, and paused before raising an exception. Thread B called the unlocked `db.update_user_password()` on the same `Database` object. Thread B completed inside A's transaction and committed the connection. A then raised and rolled back, but the supposedly rolled-back Admin V2 insert remained:

```text
unlocked_legacy_writer_completed_inside_admin_transaction= True
admin_insert_persisted_after_forced_rollback= 1
password_update_persisted= True
```

**Impact**

The transaction contract in `create_after_mfa()` is not reliable under real threaded execution. Depending on timing, backup-code consumption, old-session revocation, new-session insertion, and throttle reset can be partially or prematurely committed even when the repository later raises. The same connection can also produce transaction-state errors when unlocked legacy methods overlap `BEGIN IMMEDIATE`.

**Required fix**

Do not share a transaction-bearing SQLite connection across request threads. Prefer one connection per unit of work/transaction, with explicit close, busy timeout, and WAL; alternatively, comprehensively enforce the same lock around *every* operation on the shared connection. Add the demonstrated mixed Admin-V2/legacy-writer rollback test. Merely keeping the repository lock is insufficient because legacy writers do not all honor it.

### P1-2 — TOTP replay creates a fresh authenticated session

**Evidence**

- `verify_totp()` accepts the current step and adjacent window but stores no last-consumed step (`backend/mfa.py:56-69`).
- `create_after_mfa()` verifies TOTP and immediately proceeds to revoke/insert; only backup codes are consumed (`backend/admin_v2/repository.py:162-227`).
- Revision 003 adds no TOTP replay/consumption column (`backend/migrations/versions/003_add_admin_v2_sessions.py`).
- `test_mfa_security.py` exercises backup-code single use and concurrency but does not submit the same valid TOTP twice.

**Reproduced behavior**

Using a fixed clock and isolated migrated database, two logins with the exact same valid TOTP were accepted. The second login rotated the first session and created a new active one:

```text
same_totp_second_login_accepted= True
session_rows= [(True, 'login_rotation'), (False, None)]
```

**Impact**

An intercepted or observed TOTP remains a reusable login credential during the accepted time window. Session rotation does not prevent replay; it gives the replayer the newest active session and revokes the legitimate user's prior one.

**Required fix**

Persist and atomically compare/advance a per-user consumed TOTP counter in the same `BEGIN IMMEDIATE` transaction as session rotation/insertion. Reject counters less than or equal to the stored counter. Add sequential and separate-connection concurrent replay tests.

## P2 findings

### P2-1 — MFA backup codes are stored and compared as plaintext

`Database.enable_mfa()` serializes raw codes, and `create_after_mfa()` loads and directly compares those strings (`backend/admin_v2/repository.py:180-200`). The isolated reproduction confirmed `backup_code_stored_as_plaintext_json=True`. Backup codes are password-equivalent recovery secrets; a database read bypasses the second factor. Store only keyed hashes (or slow hashes if operationally acceptable), and remove by hash on use. The TOTP seed also lacks encryption-at-rest, but unlike backup codes must remain recoverable for verification.

### P2-2 — Runtime DDL remains on the application import/startup path

Although `admin_v2/repository.py:1-5` correctly declares that revision 003 owns its two tables, importing the shared singleton constructs `Database`, and `Database.__init__()` calls `_init_db()` (`backend/database.py:51-54`). `_init_db()` executes a large `CREATE TABLE IF NOT EXISTS` script (`backend/database.py:68+`) plus legacy schema evolution. Thus the backend as deployed still performs runtime DDL before Admin V2 can serve requests. This defeats strict migration ownership and complicates multi-worker startup. Move all schema creation/evolution to Alembic and make startup fail clearly on an incompatible revision.

### P2-3 — Durable security/history tables have no retention bound

Every arbitrary username/client tuple creates a durable `privileged_login_attempts` row before password verification (`backend/admin_v2/repository.py:72-129`), but expired rows are only reset when the same tuple returns and are never deleted globally. Every successful rotation also retains the prior `admin_sessions` row indefinitely (`repository.py:202-227`). Arbitrary usernames alone allow unbounded throttle-row growth from one client. Add bounded periodic cleanup/index-supported retention for expired throttle rows and old revoked/expired sessions.

### P2-4 — Every authenticated read is a serialized SQLite write

`authenticate()` always calls `touch_active()` (`backend/admin_v2/service.py:138-150`), and `touch_active()` always takes the process lock, starts `BEGIN IMMEDIATE`, updates the row, and commits (`backend/admin_v2/repository.py:230-276`). This is safe for lost updates but serializes all Admin V2 traffic in-process and across SQLite writers. With Gunicorn threads, one global connection, and future dashboard fan-out, session refresh writes can become the dominant lock/IO path. Consider coalesced touches (write only after a minimum interval) while preserving monotonic/expiry invariants.

### P2-5 — Stored idle expiry is not bounded by absolute expiry

`touch_active()` monotonically takes the greater requested `idle_expires_at` without capping it at `absolute_expires_at` (`backend/admin_v2/repository.py:250-266`). Absolute expiration is still enforced separately, so this is not an authentication bypass, but returned session state can report `idleExpiresAt > absoluteExpiresAt`, contrary to the bounded sliding-expiry contract. Store `min(max(old_idle, requested_idle), absolute_expiry)` and add a near-absolute-boundary test.

### P2-6 — Client-IP throttle behavior depends on undocumented proxy trust

The route intentionally uses only `request.client.host` (`backend/admin_v2/routes.py:35-43`), and the test proves raw forwarding headers cannot split the counter (`test_login_throttling.py:89-120`). This is correct only if the ASGI server is explicitly configured to trust the actual reverse proxy and rewrite the client scope. The repository includes proxy headers in Nginx, but no explicit Gunicorn/Uvicorn trusted-proxy setting is documented in `backend/Dockerfile:29`; `nginx-practenture.conf` also describes a separate backend container. If the proxy is not trusted, all clients collapse to the proxy address, turning per-account/per-client throttling into global account lockout. Make trusted proxy topology explicit and add a deployment-level assertion/test.

## P3 findings

### P3-1 — Test suite proves rollback only without competing connection users

`test_failed_session_transaction_rolls_back_and_does_not_clear_counter` (`test_login_throttling.py:178-210`) induces an integrity error in one thread and correctly proves ordinary rollback. It cannot detect P1-1 because no unlocked legacy method touches the same shared connection during the transaction. Add mixed-API concurrency tests, not only repository-vs-repository tests.

### P3-2 — MFA tests give false confidence on replay and at-rest handling

`test_mfa_security.py` is strong for absent-code denial, malformed seed handling, backup single-use, concurrent backup use, and rollback. It lacks valid-TOTP replay (sequential and concurrent), accepted-window counter ordering, and assertions that recovery credentials are not persisted verbatim.

### P3-3 — Migration downgrade is intentionally a no-op

Revision 003's downgrade retains tables/data. This is data-safe, and the test explicitly requires non-destructive downgrade, but operational tooling will report revision 002 while revision-003 objects still exist. Document this as a forward-only migration policy or use a separate compatibility marker so schema revision remains truthful.

## Correct behaviors confirmed

- **Blocking work:** Auth routes and dependencies are synchronous `def`, so FastAPI executes SQLite and bcrypt work in the worker threadpool rather than the event loop (`admin_v2/routes.py`, `dependencies.py`). Password bcrypt occurs before the session write transaction.
- **Cross-connection session touch:** `BEGIN IMMEDIATE` serializes separate SQLite connections; `CASE` expressions prevent last-seen/idle timestamps from moving backward.
- **Absolute expiry:** Absolute expiry is immutable after insert and checked on each touch even when idle expiry was extended.
- **Rotation:** Concurrent successful logins serialize; each revokes currently active rows before inserting, leaving at most the last committed session active.
- **Logout/revoke:** Conditional `revoked_at IS NULL` updates make duplicate logout/revoke outcomes controlled.
- **Suspension:** `authenticate()` re-reads the owner and revokes a token when role/status is no longer active (`service.py:163-166`). Isolated execution confirmed a suspended owner's existing token is rejected.
- **Throttle reservation:** Reservation happens before bcrypt, is durable, has fixed-window/Retry-After semantics, and separate repository/connection tests cover atomic threshold enforcement.
- **MFA backup atomicity absent P1-1 interference:** Backup consumption and session creation share the repository transaction and normal insert failure rolls back both.
- **Migration/data preservation:** Revision 003 is additive, indexed, and the migration test snapshots revision-002 schema/data before upgrade and after non-destructive downgrade.
- **HTTP contracts:** Current login/session/logout responses set `Cache-Control: no-store`; errors include a stable envelope and `X-Request-ID`; cookie attributes include HttpOnly, SameSite=Strict, scoped Path, Max-Age, and Secure outside explicit tests. Global middleware adds CSP, nosniff, and frame denial.
- **Legacy preservation:** Admin V2 is mounted additively under `/api/admin/v2`; legacy owner/API and body contracts are not replaced by the new router.
- **Test isolation:** `backend/tests/conftest.py` assigns a temporary DB and runs migrations before importing the singleton. The focused Admin V2 run did not mutate tracked `backend/data.db`.

## Verification performed

- Focused suite:

```text
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m pytest -q tests/admin_v2
38 passed, 9 warnings in 19.32s
```

- Two isolated execution probes reproduced P1-1 and P1-2 without touching the repository database.
- `backend/data.db` SHA-256 remained:

```text
6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263
```

- A repository-wide `pytest -q` was not a valid local gate: collection imported `backend/test_code_only_mfa.py`, which attempted an SSH lookup and exited after a 10-second connection timeout. No successful connection occurred. This unrelated collection-time production dependency should itself be quarantined behind an explicit integration marker/environment gate.

## Release decision

**FAIL.** Fix and regression-test P1-1 and P1-2 before release. P2/P3 items should be tracked separately and do not independently determine this verdict.
