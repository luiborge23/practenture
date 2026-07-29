# Admin V2 Authentication/Session Security Rereview

**Date:** 2026-07-28  
**Branch:** `admin-console-v2`  
**HEAD:** `33ad34018c90ab97490365079a82c1db10bbdcb7`  
**Verdict:** **FAIL — P1 security issues remain**

## Scope and method

Independent, read-only adversarial review of the additive Admin V2 authentication/session implementation, its Alembic migration, application integration, and tests. I inspected the login/MFA/session state transitions directly and challenged MFA replay/rollback, throttling normalization and multi-worker behavior, credential timing, fixation/rotation, CSRF concurrency, logout races, cookie scope/deletion, expiry, secret storage, error/request-ID/cache behavior, and migration/data safety.

The controller-reported gate was **69 passed, 1 skipped**. My independent focused rerun was:

```text
PYTHONDONTWRITEBYTECODE=1 uv run --with-requirements requirements.txt --with pytest \
  python -m pytest tests/admin_v2 -q
38 passed, 9 warnings in 19.21s
```

The test run temporarily changed generated `backend/uv.lock`; I restored it. Production `backend/data.db` stayed byte-for-byte unchanged before and after review:

```text
SHA-256 6fb8367911e17a9f97291b8c5a96894495372be71bc818bc16cfdac2d00e5263
```

No application source, migration, test, production database, network, or production environment was modified.

## Release-blocking findings

### P1-1 — Distributed-source rotation bypasses the privileged-login throttle

**Evidence**

`AdminSessionRepository.reserve_login_attempt` persists counters under the composite primary key `(identity_key, client_key)` (`backend/admin_v2/repository.py:87-129`; `backend/migrations/versions/003_add_admin_v2_sessions.py:31-40`). The route supplies the immediate peer address (`backend/admin_v2/routes.py:35-42`). Normalizing case/whitespace and ignoring forwarding headers is correct, and `BEGIN IMMEDIATE` makes each individual pair durable and atomic across workers. However, there is no identity-only/global owner limit.

The existing test explicitly codifies pairwise client isolation (`backend/tests/admin_v2/test_login_throttling.py:62+`), so this is not a missing lock; it is a policy bypass under distributed attack.

**Concrete exploit**

1. Attack the same owner identity from source address A and submit five password guesses; the threshold attempt is allowed by design.
2. Move to source B and receive a fresh independent five-attempt budget.
3. Repeat over N bot/proxy addresses for `5 × N` guesses per 15-minute window.
4. Once a guess succeeds, session creation deletes only that identity/client pair (`repository.py:131-140,227`), not other attack state.

Forwarding-header spoofing does not split the counter in the current direct-peer route, but genuinely distributed clients do. Multi-worker durability does not fix the missing identity-wide dimension.

**Impact**

Unbounded online password guessing against the owner console, limited only by available source addresses. MFA reduces impact only for MFA-enabled owners; the implementation explicitly permits MFA-disabled owner login.

**Required correction**

Enforce both an identity-wide durable limit and a client/prefix limit (with bounded storage and atomic reservation), rather than only the pairwise key. Add tests proving address rotation cannot multiply the owner-identity budget while unrelated identities/legitimate clients are not globally locked out.

### P1-2 — Legacy SHA-256 owners are remotely enumerable by a large timing oracle

**Evidence**

For an absent username, `_verify_owner_password` performs bcrypt against a dummy cost-12 hash (`backend/admin_v2/service.py:58-63`). For an existing legacy SHA-256 user, `verify_password` performs only one fast SHA-256 comparison (`backend/security.py:37-49`) and immediately returns on a wrong password (`service.py:65-67`). Invalid/non-bcrypt stored hashes also return quickly.

A local measurement of the exact primitives used by these branches produced:

```text
dummy_bcrypt_mean_seconds=0.174439
legacy_sha256_mean_seconds=0.000003642
ratio=47902x
```

**Concrete exploit**

An unauthenticated attacker sends repeated wrong-password logins for candidate usernames, staying below each pairwise throttle by rotating source addresses as in P1-1. Roughly 174 ms identifies an absent/bcrypt-shaped path; a near-immediate response identifies an existing legacy-SHA (or malformed-hash) record. Network noise is far smaller than the approximately 174 ms branch gap and can be averaged out.

**Impact**

Reliable enumeration of legacy owner usernames and their password-hash migration state, directly improving the distributed guessing attack. Revision 003 deliberately preserves revision-002 production users, so this is relevant to upgraded production data rather than only synthetic records.

**Required correction**

On every failed legacy or malformed-hash verification, also perform the fixed dummy bcrypt check before returning. Add timing-contract tests using instrumented/mock password-verification work rather than flaky wall-clock assertions.

### P1-3 — A TOTP value is reusable for repeated successful logins

**Evidence**

`verify_totp` accepts the current step plus ±1 steps (`backend/mfa.py:49-73`). `create_after_mfa` checks only whether the submitted value matches one of those steps (`backend/admin_v2/repository.py:164-180`). No accepted time-step/counter is stored or atomically rejected on reuse. By contrast, backup-code deletion is transactional and correctly one-time (`repository.py:180-200`). Existing MFA tests cover backup reuse but only one current-TOTP acceptance (`backend/tests/admin_v2/test_mfa_security.py:124+`).

**Concrete interleaving**

1. A valid TOTP for step N is observed/phished together with the password.
2. Login L1 verifies N, creates session S1, and clears that source pair's throttle state.
3. Before N leaves the ±1 acceptance window, login L2 submits the identical password and identical TOTP.
4. L2 verifies N again because no last-used step exists, revokes S1 as `login_rotation`, creates S2, clears its throttle state, and returns 200.
5. The same value can be replayed repeatedly during its acceptance interval; concurrent requests serialize but are still accepted sequentially.

**Impact**

The purported one-time second factor is replayable, enabling repeated session acquisition/rotation and making a captured code useful for substantially longer than one authentication. Successful replay also resets pairwise throttle state.

**Required correction**

Resolve the exact accepted TOTP step and atomically persist a per-user `last_accepted_totp_step`; accept only a step strictly newer than the persisted value in the same transaction as session creation. Define clock-skew/recovery behavior and add sequential plus concurrent same-code replay tests.

## Deferred legacy reset risk (outside the additive V2 route implementation)

No literal `/api/admin/password/reset` route exists in this worktree. The implemented legacy reset endpoint is `/api/auth/reset-password` (`backend/routers/auth.py:376-406`). It verifies a token, updates the password, and only then consumes the token in separate commits (`backend/database.py:1215-1235`); it ignores a failed consume and does not revoke Admin V2 sessions. Two concurrent requests can both verify the same unused token and race password updates, with the last writer winning. A password reset also leaves an already-issued Admin V2 cookie active until logout/idle/absolute expiry.

This is **legacy code, not introduced by the additive V2 slice**, but it crosses the V2 security boundary if owner accounts can use that reset flow. Therefore release impact must be explicit:

- **Release-blocking unless** deployment proves owner accounts cannot reach/use this reset path.
- Otherwise make token validation + password update + token consumption + all-session revocation one transaction, and test concurrent replay and V2-session invalidation.

## Additional hardening finding

### P2 — MFA seeds and backup codes are stored as plaintext

`mfa_secrets.secret` and `backup_codes` are plaintext columns (`backend/database.py:225-231`), and `enable_mfa` stores raw recovery codes as JSON (`database.py:1119-1126`). Admin V2 reads and compares those raw values (`admin_v2/repository.py:165-200`). This storage model predates V2, but V2 relies on it. Hash backup codes individually; protect TOTP seeds with an application-managed encryption scheme and a rotation plan; ensure backups/logs do not expose either.

## Controls that held under review

- **Backup-code atomicity:** backup consumption, old-session revocation, replacement insertion, and pair-counter reset share one `BEGIN IMMEDIATE` transaction; insertion failure rolls everything back.
- **Backup reuse:** consumed backups are removed atomically and cannot be reused through concurrent writers.
- **Session fixation/rotation:** login generates a fresh high-entropy opaque token and does not adopt the inbound cookie; token and CSRF values are persisted only as hashes. Successful login revokes previous active sessions.
- **Session validity:** idle and absolute expiries are checked before touch; absolute expiry is not extended. The corrected SQL preserves monotonic `last_seen_at` and idle expiry across independent connections (`repository.py:230-276`).
- **CSRF:** the only current cookie-authenticated mutation, logout, requires the CSRF header. GET `/auth/session` does not rotate/destructively consume CSRF state, so concurrent GETs remain usable. Session-bound deterministic CSRF values do not permit cross-session replay.
- **Logout/revoke races:** conditional revocation yields one winner and a controlled authentication error for the loser; it does not resurrect sessions.
- **Cookie controls:** session cookie is `Secure` outside the explicit test harness, `HttpOnly`, `SameSite=Strict`, scoped to `/api/admin/v2`, and deleted with the matching path/security attributes (`admin_v2/routes.py:44-52,70-76`).
- **Forwarding headers:** attacker-supplied forwarding headers are not trusted by this route; the immediate peer signal is used. Deployment must preserve that invariant or introduce an explicit trusted-proxy policy.
- **Error/cache/request metadata:** Admin V2 errors use stable envelopes, opaque server-generated request IDs, `Cache-Control: no-store`, and preserve framework `Allow` headers on 405 (`backend/main.py:73-83,108-179`). Sensitive successful auth/session responses are also `no-store`.
- **Migration/data preservation:** revision 003 is additive, migration tests preserve representative revision-002 schema/data, downgrade intentionally retains security tables, and the real `data.db` hash did not change. Pre-deploy migration remains mandatory because runtime code does not create revision-003 tables.

## Final gate

**FAIL.** P1-1, P1-2, and P1-3 must be corrected and covered by adversarial tests before release. The deferred legacy reset route must also be fixed or demonstrably excluded for owner accounts. Passing tests do not override these uncovered exploit paths.
