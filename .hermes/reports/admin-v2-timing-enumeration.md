# Admin V2 Owner Hash Timing Enumeration Fix

**Date:** 2026-07-28  
**Branch:** `admin-console-v2`  
**Scope:** P1-2 only — owner username/stored-hash-state timing equalization

## Result

Fixed the fast-failure oracle for legacy SHA-256 and malformed/non-bcrypt owner password hashes without sleeps or wall-clock assertions.

`AdminAuthService._verify_owner_password` now has these deterministic primitive-call contracts:

| Stored account/hash path | Failed-login verification work |
|---|---|
| Unknown user | exactly one fixed cost-12 dummy bcrypt verification |
| Legacy SHA-256 | one SHA-256 verification, then exactly one fixed dummy bcrypt verification |
| Malformed/non-bcrypt | exactly one fixed dummy bcrypt verification |
| Genuine bcrypt | exactly its real bcrypt verification; no additional dummy |

Successful legacy SHA-256 verification still transparently migrates the password to bcrypt and does not perform unnecessary dummy work.

A strict, total `is_bcrypt_hash` helper classifies complete supported bcrypt encodings, including valid revision, cost, length, alphabet, and canonical final salt character. Invalid values (including non-strings and bcrypt-looking malformed salts) therefore enter the fixed dummy path.

All public credential failures remain HTTP 401 `ADMIN_INVALID_CREDENTIALS` with `Invalid credentials`; tests assert no username/hash disclosure.

## Files

- Modified `backend/security.py`
- Modified `backend/admin_v2/service.py`
- Added `backend/tests/admin_v2/test_login_timing_contract.py`

## Deterministic verification

No timing benchmark or wall-clock sleep was added. Tests monkeypatch/spy on password verification primitives and assert exact call order and count.

```text
Focused timing contracts: 16 passed, 2 warnings in 0.21s
All Admin V2:            65 passed, 9 warnings in 27.83s
Legacy suites:           31 passed, 1 skipped, 1 warning in 8.00s
```

## Artifact and hygiene checks

- `backend/data.db` SHA-256 before and after: `6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263`
- Restored test-generated `backend/uv.lock` changes.
- `git diff --check` passed for the targeted files.
- No network, production environment, source worktree, or commit operations performed.
