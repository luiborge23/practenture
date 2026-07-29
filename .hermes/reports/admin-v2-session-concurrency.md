# Admin V2 Session/CSRF Concurrency Evidence

Date: 2026-07-28  
Branch: `admin-console-v2`  
Scope: bounded Admin V2 session/CSRF adversarial TDD stage

## Test coverage added

`backend/tests/admin_v2/test_session_concurrency.py` adds five deterministic tests using unique owners, isolated session rows, `threading.Barrier`, `ThreadPoolExecutor`, and five-second future/barrier timeouts:

1. Two concurrent `GET /auth/session` requests for one cookie both return 200, the same CSRF token, and that token remains usable on a later GET (no destructive GET rotation).
2. Concurrent authenticate + logout produces only contract-valid 200/204/401/403 outcomes, stable V2 error envelopes, no 500, and a definitively revoked final state.
3. Two concurrent logout attempts produce exactly one 204 and one controlled 401 `ADMIN_AUTH_REQUIRED`, never 500.
4. `touch_active` is exercised through separate `AdminSessionRepository` and `Database` instances connected to the same SQLite file; both reads return non-`None` active records and the persisted touch is monotonic.
5. Revoked/expired rows never return active; idle expiry slides; absolute expiry and persisted CSRF hash remain unchanged.

Fixtures use unique owner/session identities and delete their users, MFA rows, throttle rows, and admin-session rows after each test. Independent database connections are explicitly closed.

## TDD finding and repair

Initial focused run: **4 passed, 1 failed**.

The independent-connection test exposed a real last-writer regression in `AdminSessionRepository.touch_active`: an older request that acquired SQLite's write lock after a newer request could overwrite `last_seen_at` and `idle_expires_at` with earlier values. The transaction made update+read atomic, but did not make sliding timestamps monotonic.

Smallest implementation repair: changed the conditional UPDATE in `backend/admin_v2/repository.py` to retain the greater existing/candidate `last_seen_at` and `idle_expires_at` values with SQL `CASE` expressions. Absolute expiry and CSRF state are not modified.

## Verification

Commands were run from `backend/` with the locked requirements supplied to `uv`:

```text
uv run --with-requirements requirements.txt --with pytest python -m pytest tests/admin_v2/test_session_concurrency.py -q
..... [100%]
5 passed, 3 warnings in 4.12s
```

```text
uv run --with-requirements requirements.txt --with pytest python -m pytest tests/admin_v2 -q
...................................... [100%]
38 passed, 9 warnings in 19.23s
```

Warnings are pre-existing Alembic path-separator deprecations and a FastAPI/Starlette TestClient deprecation; no test failures or hangs occurred.

Verification modified tracked `backend/uv.lock`; it was confirmed as generated test-run drift and restored. No tracked bytecode remained changed.

## Result

**PASS** — all five new adversarial contracts and all 38 Admin V2 tests pass. No uncontrolled 500, `record=None` authenticated result, destructive CSRF rotation, revoked/expired active return, or absolute-expiry extension was observed.
