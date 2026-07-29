# Admin V2 durable login-throttling adversarial tests

## Scope

Bounded TDD stage on branch `admin-console-v2`; no network, production, source worktree, or commit operations.

## Baseline

- `git branch --show-current && git status --short`: confirmed `admin-console-v2`; existing Admin V2 work is untracked/in-progress.
- `python -m pytest tests/admin_v2 -q`: environment interpreter lacked Alembic (`ModuleNotFoundError`), so verification uses the repository virtualenv at `backend/.venv/bin/python`.

## Added coverage

`backend/tests/admin_v2/test_login_throttling.py` exercises normalized identity/client keys, peer-derived route signal versus forwarding headers, pairwise host isolation, exact threshold and integer Retry-After semantics, controlled-time expiry, failure/MFA accounting, successful reset, cross-instance SQLite durability, concurrent atomic reservation, bounded anti-DoS behavior, and transaction rollback.

## Verification log

- Initial `python -m pytest tests/admin_v2 -q` and `./.venv/bin/python -m pytest ...` could not collect because those environments lacked Alembic. This was an environment-only blocker; no source workaround was made.
- `uv run --with-requirements requirements.txt --with pytest python -m pytest tests/admin_v2/test_login_throttling.py -q` → **8 passed**, 3 dependency deprecation warnings.
- `uv run --with-requirements requirements.txt --with pytest python -m pytest tests/admin_v2 -q` → **33 passed**, 9 dependency deprecation warnings (the prior 25 plus 8 throttling tests).
- Final rerun used `PYTHONDONTWRITEBYTECODE=1` and reproduced **8 passed** focused and **33 passed** full Admin V2.
- `git diff --check` → clean.
- Restored all tracked test-generated `*.pyc` files and the incidental `backend/uv.lock` environment change with `git checkout -- ...`; no pre-existing source changes were restored.

## Findings

The existing implementation satisfied every added adversarial contract. SQLite `BEGIN IMMEDIATE` made cross-connection reservations atomic, persisted counters were visible from separate `Database`/repository instances, route throttling used normalized `Request.client.host` rather than forwarding headers, and failed session creation rolled back without clearing the reserved counter. No production implementation change was justified.
