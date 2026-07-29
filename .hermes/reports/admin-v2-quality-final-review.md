# Admin V2 corrected auth/session slice — final backend correctness/performance review

## Verdict: PASS

**Release gate:** PASS because this bounded review found **no P0 or P1 correctness, security, concurrency, or performance defects** in the corrected auth/session slice.

This verdict is limited to:

- `backend/admin_v2/{repository.py,service.py,routes.py,dependencies.py,schemas.py,errors.py}`
- `backend/database.py` (`connect` and `complete_password_reset` paths)
- `backend/auth.py` (access-token issue/verify and `password_changed_at` boundary)
- `backend/security.py` (hash classification)
- `backend/mfa.py` (TOTP counter resolution)
- `backend/migrations/versions/003_add_admin_v2_sessions.py`
- `backend/tests/admin_v2`

No unrelated console, deployment, or production code was reviewed. Per the bounded-review constraint, no tests, network access, installation, `uv`, production access, or broad commands were run. The execution evidence supplied by the controller remains **115 passed, 1 skipped**, with final specification review **PASS**, expected `data.db` SHA-256 prefix `6fb836...` unchanged, and accepted diff hygiene clean.

## P0 / P1 findings

None.

## P2 findings (non-blocking)

### P2-1 — Persisted sliding idle expiry can exceed absolute expiry

- **Evidence:** `backend/admin_v2/service.py:170-176` always proposes `now + IDLE_TIMEOUT`; `backend/admin_v2/repository.py:338-354` monotonically stores that proposal without capping it at `absolute_expires_at`.
- **Impact:** During the final 15 minutes of an eight-hour session, the persisted/API-reported `idleExpiresAt` can be later than `absoluteExpiresAt`. This does **not** extend authentication past the absolute limit because both the pre-check (`repository.py:330`) and guarded update (`repository.py:345`) require the absolute expiry to remain in the future. It is therefore a state/contract inconsistency, not an authorization bypass.
- **Smallest fix:** calculate the candidate as `min(now + IDLE_TIMEOUT, absolute_expires_at)` inside the transaction (or express the cap in SQL), and add a near-absolute-boundary regression test asserting `idle_expires_at <= absolute_expires_at`.

### P2-2 — Every successful session authentication is a SQLite write transaction

- **Evidence:** `backend/admin_v2/service.py:170-176` calls `touch_active` on every authentication; `backend/admin_v2/repository.py:324-364` uses `BEGIN IMMEDIATE`, performs an `UPDATE`, and then re-reads the row. Login also immediately calls the same write path after session creation (`service.py:157-159`).
- **Impact:** Read-only Admin API traffic serializes on SQLite's single-writer lock and produces WAL/page churn. This is bounded for expected low-volume owner-console usage and has a five-second busy timeout, so it is not a release blocker, but it limits horizontal/concurrent throughput and amplifies writes.
- **Smallest fix:** coalesce activity writes (for example, update only when `last_seen_at` is older than a short threshold), return the inserted session directly on login, and preserve the existing monotonic/expiry predicates when coalescing. Add a SQL trace/count test for repeated reads within the coalescing window.

### P2-3 — Admin session rows have no bounded retention path

- **Evidence:** revision 003 provides expiry indexes (`backend/migrations/versions/003_add_admin_v2_sessions.py:73-78`), and expired access marks rows revoked (`repository.py:330-336`), but the reviewed repository contains no deletion/archival policy for expired or long-revoked `admin_sessions`. In contrast, throttle buckets receive indexed retention cleanup (`repository.py:104-112`).
- **Impact:** Session history grows without bound over long deployments. Token lookups remain indexed and correctness is unaffected, but database size, backup time, and maintenance cost grow over time.
- **Smallest fix:** add an indexed, bounded cleanup operation for rows whose absolute expiry/revocation timestamp is older than an explicit audit-retention period; run it out of the request hot path or with a strict row limit. Document whether security/audit policy requires archival instead of deletion.

## P3 findings

None material in this bounded slice.

## Correctness/performance evidence matrix

| Requirement | Result | Source evidence | Test evidence inspected |
|---|---|---|---|
| Dedicated transaction ownership and rollback | PASS | `Database.connect` creates separately owned, consistently configured connections (`database.py:66-80`); repository units use `BEGIN IMMEDIATE`, commit/rollback, and close (`repository.py:49-61`); reset does the same and rolls back on every exception (`database.py:1230-1304`). | `test_transaction_isolation.py` proves connection separation, rollback visibility, and isolation from a concurrent legacy writer; reset rollback coverage is in `test_password_reset_boundary.py`. |
| Cross-process/session concurrency | PASS | SQLite write serialization plus conditional updates prevent lost/revived session state (`repository.py:324-374`). Sliding timestamps use monotonic `CASE` expressions. | `test_session_concurrency.py`, `test_transaction_isolation.py`, `test_concurrent_login_rotation.py`. |
| Idle and absolute expiry enforcement | PASS with P2-1 | Both expiries are checked before touch and in the update predicate (`repository.py:330-345`); absolute expiry is never updated. | `test_auth_vertical_slice.py`, `test_session_concurrency.py`. Near-boundary ordering is not covered. |
| TOTP one-time counter | PASS | Counter is resolved newest-first (`mfa.py:49-74`), compared with strict `candidate > last`, persisted in the same transaction as session insertion (`repository.py:224-309`). | `test_totp_replay.py` covers newest resolution, sequential replay, separate-connection concurrency, next step, and rollback. |
| Concurrent login scoped rotation | PASS | Rotation targets only the presented hash and authenticated owner, while each fresh session is inserted independently in the same transaction (`repository.py:281-309`). | `test_concurrent_login_rotation.py` covers independent login, same-old-cookie concurrency, sequential rotation, fixed cookie, and foreign cookie. |
| Password-work equalization and strict hash classification | PASS | Unknown, malformed, and failed legacy paths perform a current-cost dummy bcrypt check; valid bcrypt performs one real check (`service.py:66-88`). Bcrypt syntax is strictly classified (`security.py:30-35,60-68`). | Deterministic primitive-call/classification tests in the bounded Admin V2 suite were inspected via the supplied test corpus/evidence. |
| Pair + identity + client throttle | PASS | Three normalized dimensions are reserved atomically (`repository.py:80-164`); success resets pair/identity and removes only its own client reservation (`repository.py:166-197`); stale unlocked buckets are retained for a bounded interval then removed through an indexed predicate. | `test_login_throttling.py` and `test_layered_login_throttling.py` cover normalization, spoof-resistant route signal, concurrency, rollback, layered budgets, and reset behavior. |
| Atomic reset revocation | PASS | Token consume, password/boundary update, refresh revocation, and owner Admin-session revocation share one `BEGIN IMMEDIATE` transaction (`database.py:1228-1304`); missing Admin V2 table is handled for legacy DBs. | `test_password_reset_boundary.py` covers one winner, complete rollback, cross-role isolation, invalid/expired no-op, and legacy DB compatibility. |
| Pre-reset JWT invalidation | PASS | All production access-token issuers use precise UTC `iat`; verification rejects missing/malformed or strictly older `iat` once a boundary exists (`auth.py:74-145`); reset advances the boundary in the revocation transaction. | `test_password_reset_access_token_revocation.py` covers pre-reset rejection, failed-reset preservation, strict equality, and legacy no-boundary compatibility. |
| Migration ownership | PASS | Admin V2 schema exists only in revision 003; repository performs no runtime DDL (`repository.py:1-4`). Revision 003 is additive and intentionally non-destructive on downgrade. | `test_migration_003.py` validates upgrade from 002, schema/index shape, legacy-data preservation, and non-destructive downgrade. |
| Retention and write amplification | PASS with P2-2/P2-3 | Throttle retention is bounded/indexed, but session touches write per request and session-history cleanup is absent. | Existing tests establish correctness under concurrency but do not set a write-count or long-term session-retention performance contract. |

## Final assessment

The corrected implementation closes the previously identified P1 transaction, replay, rotation, timing, throttling, reset-atomicity, and JWT-boundary failures. Its remaining issues are bounded operational/state-quality concerns: cap the reported idle expiry, reduce touch write amplification, and define Admin-session retention. None permits authentication beyond the absolute deadline, revives revoked credentials, breaks atomic reset semantics, or creates a realistic release-blocking failure in the stated owner-console workload.
