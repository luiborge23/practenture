# Admin V2 atomic TOTP replay prevention

## Outcome

Implemented durable, atomic one-time TOTP counter consumption for Admin V2 owner login.

## Implementation choices

- Added `mfa.resolve_totp_counter()` with the same RFC 6238 SHA-1 / 30-second / six-digit / ±1-window semantics as legacy `verify_totp()`.
- Kept `verify_totp()` as the legacy boolean API, now delegating to the counter resolver.
- Searches newest-to-oldest so an improbable duplicate code in adjacent counters deterministically resolves to the newest valid counter.
- Added V2-owned additive migration state: `admin_mfa_replay_state(owner_user_id PRIMARY KEY, last_accepted_totp_step, accepted_at)` plus accepted-at index.
- `BEGIN IMMEDIATE` now serializes replay comparison/update with backup-code handling, old-session rotation, new-session insertion, and throttle reset.
- A TOTP counter is accepted only when strictly greater than persisted state. Reuse returns stable `ADMIN_MFA_REPLAYED` (HTTP 401); backup-code behavior is unchanged.
- Any later transaction failure rolls back counter consumption and session rotation together.

## Deterministic coverage

`backend/tests/admin_v2/test_totp_replay.py` proves:

1. duplicate-window collisions choose the newest matching counter;
2. sequential same-code login succeeds once, replay is denied without rotating the active session, and the next counter succeeds;
3. two concurrent API logins using independently owned SQLite connections produce exactly one 200 and one controlled replay denial;
4. failed session insertion does not consume the newer TOTP counter.

Migration execution coverage proves the table/index are additive, revision-002 schema/data remain byte-for-byte logically unchanged, new replay state starts empty, and the intentional non-destructive downgrade retains replay state.

## Verification

- Focused replay + migration: **5 passed**
- Full Admin V2: **45 passed**
- Legacy (`test_backend.py test_phase5.py`): **31 passed, 1 skipped**
- `git diff --check`: **clean**
- Tests ran with `PYTHONDONTWRITEBYTECODE=1`; no generated test artifacts were added.

Only pre-existing Alembic configuration and Starlette TestClient deprecation warnings were emitted.
