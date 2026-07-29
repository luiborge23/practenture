# Admin V2 Password-Reset Boundary

**Date:** 2026-07-28  
**Branch:** `admin-console-v2`  
**Verdict:** **PASS** — password-reset token consumption, password update, refresh revocation, and owner Admin V2 session revocation are one transaction.

## Implementation

`Database.complete_password_reset()` now owns the security-sensitive reset unit of work on a dedicated SQLite connection:

1. `BEGIN IMMEDIATE` serializes competing token completions.
2. SHA-256 hashes and locates one unexpired, unused token joined to its user.
3. Conditionally consumes the token exactly once.
4. Updates the target password hash.
5. Revokes all active legacy refresh tokens for that user.
6. For an owner, revokes every active `admin_sessions` row with reason `password_reset` in the same transaction.
7. Commits only after all steps succeed; every exception rolls back all prior mutations.

The legacy `/api/auth/reset-password` route retains its existing response contract: `{"status":"password_reset"}` on success and HTTP 400 with `"Invalid or expired reset token"` for invalid, expired, or already-used tokens. Password complexity validation remains HTTP 400. No token or password is logged or returned. A legacy schema without `admin_sessions` is detected through `sqlite_master` and safely completes the legacy password/refresh reset without runtime DDL.

## Boundary tests

Added `backend/tests/admin_v2/test_password_reset_boundary.py` proving:

- an owner Admin V2 cookie authenticates before reset and returns 401 afterward;
- owner refresh credentials and all active Admin V2 sessions are revoked;
- two concurrent completions produce exactly one 200 and one 400, with the final password hash belonging to the winner;
- a forced downstream owner-session revocation failure rolls back token use, password update, refresh revocation, and session revocation;
- professor reset revokes that professor's refresh token but does not revoke an owner's active Admin V2 session;
- invalid and expired tokens mutate no password, reset-token, refresh-token, or Admin V2 session state;
- owner reset remains safe against a pre-Admin-V2 database with no `admin_sessions` table.

## Verification

```text
Focused:  tests/admin_v2/test_password_reset_boundary.py
          6 passed, 3 warnings in 2.95s

Admin V2: tests/admin_v2
          80 passed, 9 warnings in 31.45s

Legacy:   test_backend.py test_phase5.py
          31 passed, 1 skipped, 1 warning in 8.11s

Controller: tests/admin_v2 test_backend.py test_phase5.py
            111 passed, 1 skipped, 9 warnings in 38.68s
```

`git diff --check` passed. `backend/data.db` remained byte-stable at SHA-256 `6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263`.
