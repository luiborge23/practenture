# Admin V2 MFA Security Tests — Incremental Evidence

## Scope

Bounded TDD stage adding only `backend/tests/admin_v2/test_mfa_security.py`. No Admin V2 implementation edit was required.

## Increment 1 — focused MFA security coverage

Added seven isolated tests using the existing migrated pytest database, unique owner usernames, `hash_password`, and per-test cleanup of owner, MFA, session, and throttle rows.

Coverage:

1. MFA-enabled password-only login returns `401 ADMIN_MFA_REQUIRED`, creates no session, and preserves backup codes.
2. Invalid TOTP returns `401 ADMIN_INVALID_MFA`, creates no session, and preserves backup codes.
3. Invalid backup code returns `401 ADMIN_INVALID_MFA`, preserves backup codes, and does not rotate/revoke an existing active session.
4. Deterministic valid current TOTP returns 200 and creates exactly one active session.
5. Valid backup code returns 200 and is consumed; reuse returns `401 ADMIN_INVALID_MFA` without rotating/revoking the active session.
6. MFA-disabled owner returns 200 and creates exactly one active session.
7. A forced session-insert integrity failure rolls back backup-code consumption and active-session rotation, proving the repository transaction is atomic.

Initial environment probe:

```text
$ python3 -m pytest tests/admin_v2/test_mfa_security.py -q
ImportError ... ModuleNotFoundError: No module named 'alembic'
Exit code: 4 (collection did not start)
```

The project dependency set was then used through `uv`:

```text
$ uv run --with-requirements requirements.txt python -m pytest tests/admin_v2/test_mfa_security.py -q
.......                                                                  [100%]
7 passed, 3 warnings in 6.18s
```

## Increment 2 — Admin V2 regression suite

```text
$ uv run --with-requirements requirements.txt python -m pytest tests/admin_v2 -q
.........................                                                [100%]
25 passed, 9 warnings in 13.70s
```

Exact suite count: **25 passed** = existing **18** + new MFA **7**.

Warnings were pre-existing Alembic configuration deprecations and the FastAPI/Starlette TestClient compatibility warning; no test failed.

## Hygiene and implementation finding

- Restored all tracked Python 3.11 bytecode files modified by test execution and restored the generated `backend/uv.lock` change.
- Preserved the pre-existing modification to `backend/__pycache__/main.cpython-314.pyc` rather than overwriting unrelated work.
- No implementation root-cause defect was exposed: current `AdminSessionRepository.create_after_mfa` correctly verifies/consumes MFA, rotates active sessions, inserts the replacement session, and resets the login attempt in one SQLite transaction.
