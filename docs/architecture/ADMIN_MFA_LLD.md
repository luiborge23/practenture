# Administrator Multi-Factor Authentication LLD

**Status:** Implemented in current source; Section 12 records the last deployed baseline
**Updated:** 2026-07-31
**Parent:** [Practenture System Architecture](SYSTEM_ARCHITECTURE.md)
**Release:** `1abb1aaee2dd49b59790a4b3c232cacdb3e2848a`

## 1. Scope

This low-level design defines the Administrator TOTP lifecycle in Admin V2: enrollment, possession confirmation, login challenge, replay protection, one-time recovery codes, recovery-code regeneration, disablement, reauthentication, throttling, session authorization, audit behavior, and browser handling.

The design reuses the shared cryptographic primitives in `backend/mfa.py` while retaining Admin V2's stronger opaque-session, CSRF, recent-authentication, idempotency, transaction, and account-wide throttling controls. Professor endpoint and session semantics are not reused.

## 2. Security invariants

1. MFA is not enabled when a seed is generated. A valid current TOTP must confirm possession.
2. TOTP seeds are encrypted at rest with AES-256-GCM using a key derived from the configured MFA/application secret.
3. Recovery codes are returned only at enrollment confirmation or regeneration and are stored only as `sha256$...` digests.
4. A recovery code is consumed transactionally and can succeed only once.
5. A TOTP counter cannot be accepted twice for the same Administrator, including concurrent requests.
6. All management mutations require an authenticated opaque Admin session and CSRF token.
7. Setup, recovery-code regeneration, disablement, and reauthentication place password/factor verification inside a durable throttle boundary.
8. Successful verification resets the applicable durable bucket; normal successful management cannot self-lock the Administrator.
9. The active session, active Owner account, and current password hash are rechecked in the same `BEGIN IMMEDIATE` transaction as the security mutation.
10. Passwords, session tokens, CSRF tokens, MFA seeds, OTP values, and recovery codes never enter logs or audit metadata.
11. Browser storage is not used for the seed or recovery codes. Sensitive responses are marked `Cache-Control: no-store`.
12. The backend is authoritative. UI state changes only after the corresponding API response succeeds.

## 3. Components

```text
Browser: Account security workspace
  |
  | HTTPS + Secure/HttpOnly/SameSite=Strict opaque session cookie
  | X-CSRF-Token on mutations
  v
backend/admin_v2/routes.py
  -> session / CSRF / recent-auth dependencies
  -> backend/admin_v2/service.py
       -> backend/mfa.py (TOTP, AES-GCM, URI/QR inputs, recovery primitives)
       -> backend/admin_v2/repository.py
       -> AdminMutationRepository (BEGIN IMMEDIATE + audit + idempotency)
  -> SQLite
       mfa_secrets
       admin_mfa_replay_state
       privileged_login_buckets
       admin_sessions
       admin_audit_events
```

Primary implementation files:

- `backend/admin_v2/routes.py` — HTTP contracts and security dependencies.
- `backend/admin_v2/schemas.py` — camelCase request/response models.
- `backend/admin_v2/service.py` — lifecycle orchestration and security policy.
- `backend/admin_v2/repository.py` — transactional verification, replay, recovery consumption, sessions, and throttle persistence.
- `backend/migrations/versions/007_track_admin_mfa_login_reservation.py` — preserves the original password-stage identity, identity/client pair, and client reservation window markers across the MFA challenge boundary so each successful reservation can be released exactly even if the client address changes. The migration invalidates transient pre-007 challenges, which lack that metadata, and requires those users to restart login.
- `backend/mfa.py` — shared cryptographic primitives.
- `backend/static/admin_v2/admin-workspaces.js` — Account security UI.
- `backend/tests/admin_v2/test_admin_mfa_lifecycle.py` — lifecycle and adversarial coverage.

## 4. API contract

All paths are below `/api/admin/v2/auth`.

| Method | Path | Required assurance | Result |
|---|---|---|---|
| `GET` | `/mfa/status` | Authenticated Admin session | Enabled state and remaining recovery-code count |
| `POST` | `/mfa/setup` | Session + CSRF + current password + durable throttle | Pending encrypted seed, provisioning URI, QR data URI, manual key |
| `POST` | `/mfa/confirm` | Session + CSRF + valid current TOTP + durable throttle | Enables MFA and returns recovery codes once |
| `POST` | `/mfa/recovery-codes` | Session + CSRF + current password + TOTP/recovery factor + durable throttle | Replaces and returns a new recovery-code set once |
| `POST` | `/mfa/disable` | Session + CSRF + current password + TOTP/recovery factor + durable throttle | Disables MFA and clears recovery/replay state |
| `POST` | `/mfa/verify` | Valid one-time login challenge + TOTP/recovery factor + durable throttle | Consumes challenge and creates opaque Admin session |
| `POST` | `/reauthenticate` | Session + CSRF + password + current factor + durable throttle | Extends recent-auth assurance |

Sensitive responses use `Cache-Control: no-store`. Recovery codes and enrollment material never appear in status/list responses.

## 5. State machine

```text
DISABLED
  |
  | POST /mfa/setup + current password
  v
PENDING_ENROLLMENT (encrypted seed, enabled=0)
  |                    |
  | valid current TOTP | setup retried
  v                    `-> same pending seed is resumed
ENABLED (enabled=1, replay counter, hashed recovery codes)
  |             |
  | regenerate  | disable + password + factor
  | codes       v
  `--------> DISABLED
```

A pending seed is resumable so a QR code already scanned by the Administrator is not silently replaced. Confirmation performs a conditional `enabled=0 -> enabled=1` update; concurrent confirmation has one winner.

## 6. Enrollment transaction

### 6.1 Setup

1. Reserve the durable account/client MFA-management attempt before password verification.
2. Enter `BEGIN IMMEDIATE` through `AdminMutationRepository`.
3. Re-read and validate the session, Owner role/status, session expiry/revocation, and current stored password hash.
4. Verify the supplied password. Legacy SHA-256 failures perform dummy bcrypt work to equalize the failure path.
5. Create an encrypted pending seed only if one does not already exist.
6. Build the provisioning URI and QR data URI before commit.
7. Reset the successful throttle reservation in the transaction.
8. Commit pending state and `admin.auth.mfa_enrollment_started` together.

If QR generation or any later step fails, both pending state and the success audit roll back.

### 6.2 Confirmation

1. Reserve the account-wide MFA factor attempt.
2. Revalidate the active session and Owner account in the transaction.
3. Resolve the submitted TOTP to a concrete counter.
4. Conditionally enable the pending row.
5. Persist the accepted counter in `admin_mfa_replay_state`.
6. Generate ten recovery codes, return plaintext once, and store only hashes.
7. Reset the successful throttle reservation.
8. Commit state and `admin.auth.mfa_enabled` together.

Invalid codes leave the durable failure reservation in place and commit no security-state or success-audit change.

## 7. Login challenge and replay protection

Password validation can return an opaque, expiring, single-use MFA challenge rather than a privileged session. `/mfa/verify` processes that challenge transactionally:

- the challenge must be unexpired, unused, and bound to the Owner;
- TOTP verification locks acceptance to a monotonically increasing counter;
- recovery-code verification removes the matching hash in the same transaction;
- challenge consumption and session creation are one atomic operation;
- successful verification resets challenge-specific and account-wide MFA buckets;
- replay, concurrent recovery-code use, and concurrent challenge use have one winner.

A valid code used during enrollment cannot be reused for the next login. The Administrator must submit a fresh authenticator code.

## 8. Durable throttling

Admin MFA uses SQLite-backed attempt records rather than process memory. Policy dimensions include:

- canonical account-wide identity (`mfa-owner:<normalized-owner>`), which survives client/IP rotation;
- client-pair dimensions for additional abuse containment;
- challenge identity for login challenge attempts.

Reservations happen before password or factor checks. Denied reservations return `429` with retry timing. Failed checks remain counted. A completed direct login releases its own password reservation in each identity, pair, and client dimension. A completed challenge login atomically releases both the original password-stage reservation and the challenge/owner factor-stage reservations. Every release matches the reservation's window marker and decrements only that successful request, so concurrent or otherwise unrelated failures remain counted.

## 9. Recovery-code lifecycle

- Ten codes are generated with 48 bits of entropy each and displayed once.
- Formatting is normalized before hashing/comparison.
- Persistence uses only `sha256$<digest>` values.
- Comparison uses constant-time checks.
- A matching code is removed transactionally before a login/session succeeds.
- Regeneration invalidates every previous unused code atomically.
- Disablement clears the stored recovery set.
- Production enrollment verification reads only counts/hash-format booleans; it never reads or prints plaintext codes.

## 10. Browser behavior

The **Account security** workspace provides:

- current enabled/disabled state;
- setup action with password confirmation;
- QR and manual-key enrollment;
- TOTP confirmation;
- one-time recovery-code acknowledgement/copy flow;
- recovery-code regeneration;
- MFA disablement.

Enrollment material exists only in the active in-memory UI state. Closing the dialog discards it. No seed, provisioning URI, recovery code, password, or OTP is written to `localStorage` or `sessionStorage`.

## 11. Audit events

Successful lifecycle mutations emit immutable, redacted events in the same transaction as their state change:

- `admin.auth.mfa_enrollment_started`
- `admin.auth.mfa_enabled`
- `admin.auth.mfa_recovery_codes_regenerated`
- `admin.auth.mfa_disabled`
- `admin.auth.reauthenticated`

Metadata may contain non-secret counts, such as the number of recovery codes issued. It must never contain credential material.

## 12. Verification and release evidence

The core MFA lifecycle baseline, release `1abb1aaee2dd49b59790a4b3c232cacdb3e2848a`, was qualified and deployed on 2026-07-31.

- Full local backend/release suite: **502 passed**.
- Exact-SHA GitHub Actions run: `30670330492`.
- Five required checks: **all successful**.
- GitHub Check annotations: **0**.
- iOS Golden Formula parity: passed on Xcode 26.5 / iOS runtime 26.5.
- Deterministic deployment artifact SHA-256: `4dd0a9e41816aec2952c9ee13fd77cbf9647a33ede7cf79f1b8d2c858d64b2e2`.
- Transactional production deployment: backup, restore drill, migration, internal health, public HTTPS health, source revision, rollback image, and release-pointer checks passed.
- Production Administrator enrollment: completed through Admin V2.
- Fresh post-enrollment password + TOTP login: passed.
- Production state: encrypted seed, ten hashed recovery codes, replay state present, database integrity `ok`, zero foreign-key violations.

Current source additionally ensures a successful challenge login releases both its password-stage and factor-stage throttle reservations atomically. Its regression test belongs to the next exact-SHA qualification; this statement does not imply deployment beyond the baseline identified above.

## 13. Operational rules

- Do not enroll by inserting a database seed.
- Do not inspect or export plaintext enrollment/recovery material from production.
- Do not consume recovery codes in routine smoke tests.
- Do not disable MFA during release verification.
- Do not bypass Admin V2 with direct SQL for normal lifecycle management.
- Any source change requires a new exact SHA, all five CI checks, zero annotations, deterministic artifact proof, and transactional deployment.
