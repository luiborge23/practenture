# Admin V2 Layered Login-Throttling Evidence

**Date:** 2026-07-28  
**Branch:** `admin-console-v2`  
**Scope:** local isolated test database only; no network, production, source worktree, or commit operations.

## Evidence

Layered throttling remains covered by `backend/tests/admin_v2/test_login_throttling.py`, including normalized pair, identity, and client budgets; forwarding-header resistance; fixed-window expiry and `Retry-After`; cross-instance durability; concurrent reservation; bounded retention; success reset; and failure rollback.

The delegated pre-reset controller baseline was **105 passed, 1 skipped** after the layered-throttle stage. After adding the six password-reset boundary tests, the current controller was rerun from `backend/`:

```text
PYTHONDONTWRITEBYTECODE=1 uv run --with-requirements requirements.txt --with pytest \
  python -m pytest tests/admin_v2 test_backend.py test_phase5.py -q
111 passed, 1 skipped, 9 warnings in 38.68s
```

The six-test increase is exactly `test_password_reset_boundary.py`; no layered-throttling regression was introduced. Warnings are existing Alembic/Starlette deprecations.

## Hygiene

- `backend/data.db` SHA-256 remained `6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263`.
- Tests used the migrated temporary database configured in `backend/tests/conftest.py`.
- `PYTHONDONTWRITEBYTECODE=1` was used for verification.
