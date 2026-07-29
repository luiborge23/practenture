# Admin V2 Task 3A — Recursive Secret-Redaction Foundation

## Scope delivered

Created a standalone Admin V2 redaction foundation only. No audit persistence, idempotency, production access, network access, or commit was performed.

- `backend/admin_v2/redaction.py`
  - Recursively copies and sanitizes dicts, lists, tuples, sets, and frozensets.
  - Detects password, token, authorization/cookie, secret, MFA/TOTP, backup/recovery, private-key, and API-key labels case- and separator-insensitively.
  - Replaces every detected secret value as a whole with the stable `[REDACTED]` marker.
  - Redacts nested Bearer, Authorization, Cookie, and Set-Cookie string values.
  - Preserves safe JSON scalars and converts dates/times, UUIDs, and Decimals predictably.
  - Preserves dict/list/tuple ordering and deterministically orders set output.
  - Does not mutate inputs; shared acyclic references remain ordinary values.
  - Uses cycle, depth, item, and scalar-size bounds. Set selection also bounds temporary allocation.
  - Converts unsupported objects to a bounded type-only marker without calling object `repr` or `str`.
- `backend/tests/admin_v2/test_secret_redaction.py`
  - 45 property-style parametrized/contract tests; no dependency was added because Hypothesis is absent from the manifests.
  - Covers all required secret classes, nested header/cookie values, reasonable metric/ID false positives, JSON safety, ordering, immutability, deterministic tuple/set handling, cycles, shared references, hostile depth/items/scalar size, and unknown objects.

## TDD evidence

RED:

```text
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m pytest tests/admin_v2/test_secret_redaction.py -q
ERROR: ModuleNotFoundError: No module named 'admin_v2.redaction'
```

GREEN (final):

```text
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m pytest tests/admin_v2/test_secret_redaction.py -q
45 passed, 2 warnings in 0.25s
```

Admin V2 focused suite:

```text
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m pytest tests/admin_v2 -q
129 passed, 9 warnings in 34.31s
```

Controller suite (final implementation):

```text
PYTHONDONTWRITEBYTECODE=1 ../.venv/bin/python -m pytest tests/admin_v2 test_backend.py test_phase5.py -q
160 passed, 1 skipped, 9 warnings in 42.03s
```

Warnings are pre-existing Alembic path-separator deprecations and a Starlette/httpx deprecation.

## Hygiene evidence

- Branch: `admin-console-v2`.
- `git diff --check`: clean.
- `backend/data.db` SHA-256 before and after: `6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263`.
- No `uv.lock`, database, or generated redaction bytecode changes.
- Preserved the baseline tracked deletion: `backend/__pycache__/database.cpython-311.pyc`.
- AST parsing succeeded for both created Python files.
