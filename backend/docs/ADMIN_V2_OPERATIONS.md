# Admin V2 Production Operations Runbook

**Status:** Active production runbook
**Updated:** 2026-07-31
**Public UI:** `https://practenture.com/admin/v2/`
**API boundary:** `/api/admin/v2/`

## 1. Purpose

This runbook covers safe operation of the deployed Admin V2 control plane, with emphasis on Administrator MFA, release traceability, health verification, backup/rollback evidence, and secret handling. The backend and its persisted state are authoritative.

Architecture references:

- [System Architecture](../../docs/architecture/SYSTEM_ARCHITECTURE.md)
- [Administrator Database LLD](../../docs/architecture/ADMIN_DATABASE_LLD.md)
- [Administrator MFA LLD](../../docs/architecture/ADMIN_MFA_LLD.md)

## 2. Access and session model

1. Open `https://practenture.com/admin/v2/`.
2. Sign in with the Administrator account.
3. Complete the TOTP challenge with a fresh authenticator code.
4. Admin V2 creates an opaque server-managed session in a `Secure`, `HttpOnly`, `SameSite=Strict` cookie.
5. The browser receives a CSRF token for mutation requests. Neither value belongs in logs, screenshots, tickets, or documentation.
6. Sensitive operations may require recent authentication or explicit password and current-factor proof.

Never place privileged bearer tokens or enrollment material in browser storage, shell history, support chat, or monitoring metadata.

## 3. Administrator MFA lifecycle

### Initial enrollment

1. Sign in and choose **Account security** in the left navigation.
2. Choose **Set up MFA** and enter the current Administrator password.
3. Scan the QR code with the approved authenticator. The manual key is a fallback and must be treated as a credential.
4. Enter a fresh six-digit TOTP to confirm possession.
5. Store the one-time recovery codes in an approved offline or encrypted credential vault.
6. Acknowledge storage and close the one-time disclosure.
7. Sign out, sign back in, and complete a fresh TOTP challenge.

Enrollment remains pending until step 4 succeeds. Do not insert or enable a seed directly in the database.

### Regenerate recovery codes

Use only when the existing set may be unavailable or exposed:

1. Confirm at least one working authenticator factor before beginning.
2. In **Account security**, choose recovery-code regeneration.
3. Provide current password and a current factor.
4. Store the newly returned codes before closing the disclosure.
5. Treat every previous code as invalid immediately.

Do not regenerate codes as a routine smoke test.

### Disable MFA

Disabling MFA reduces control-plane assurance and is not a routine support action. It requires:

- an authenticated, CSRF-protected Admin session;
- current password;
- a current TOTP or unused recovery code;
- a documented recovery/re-enrollment plan;
- post-change audit review and session verification.

Do not disable MFA during deployment verification.

### Lost authenticator

1. Use one recovery code through the normal login challenge.
2. Immediately regenerate the recovery-code set after login.
3. Re-establish an authenticator through the supported Account security lifecycle.
4. Review the audit trail and active sessions for unexpected activity.

If no valid factor remains, stop. Do not bypass MFA with direct SQL. Use the reviewed emergency recovery process with verified backup, named authorization, complete audit evidence, and immediate credential rotation.

## 4. Non-destructive MFA verification

Routine checks may verify only:

- MFA enabled boolean;
- encrypted-at-rest format boolean;
- recovery-code count and hash-format boolean;
- replay-state presence and timestamp ordering;
- redacted audit-event names/outcomes;
- fresh password-plus-TOTP login success.

Routine checks must not:

- decrypt or print the TOTP seed;
- print provisioning URIs or QR payloads;
- print or consume a recovery code;
- disable MFA;
- alter throttle records;
- rotate credentials unexpectedly.

## 5. Release qualification

Every source or documentation change produces a new candidate SHA. A production candidate is authorized only when:

1. The local tree contains exactly the intended tracked changes and no `.env`, database, credential helper, scan report, or downloaded CI evidence.
2. Focused tests and the complete backend/release suite pass.
3. JavaScript/shell syntax, Docker Compose validation, and `git diff --check` pass where applicable.
4. Secret scanning reports no tracked-source leak.
5. The candidate is committed and pushed to `origin/main`.
6. All five GitHub Actions jobs pass for that exact SHA.
7. GitHub Check annotations are zero.
8. Mandatory iOS Golden Formula parity passes; it cannot be skipped or retried away.
9. Deterministic release artifacts built from the same source are byte-identical.

Cancelled, superseded, stale-SHA, or partially green runs do not authorize deployment.

## 6. Deployment

The only approved production promotion path is:

```bash
./ec2-deploy.sh deploy
```

Do not replace containers, release symlinks, or database files manually.

The deployment must preserve and verify:

- exact source SHA and release-manifest checksum;
- predeployment online database backup;
- backup checksum and isolated restore drill;
- Alembic migration status;
- immutable release image and rollback image;
- atomic release-symlink promotion;
- internal backend and Nginx health;
- public HTTPS health and HTTP-to-HTTPS redirect;
- source/image revision equality.

## 7. Post-deployment verification

Perform non-destructive checks in this order:

1. Public `https://practenture.com/api/health` succeeds.
2. HTTP redirects to HTTPS.
3. TLS certificate verification succeeds and the certificate is within its validity period.
4. `/admin/v2/` responds and security headers are present.
5. Backend and Nginx containers are healthy.
6. Running source/image revision equals the exact CI-qualified SHA.
7. SQLite `PRAGMA integrity_check` returns `ok`.
8. SQLite `PRAGMA foreign_key_check` returns zero rows.
9. Predeployment backup, restore-drill evidence, release pointer, and immutable rollback image exist.
10. Administrator can complete a fresh password-plus-TOTP login.
11. Audit events contain no secret material.

## 8. Rollback

Rollback is appropriate when public health, migrations, schema invariants, Admin authentication, or source-revision checks fail after promotion.

1. Stop further administrative mutations.
2. Preserve logs and request IDs without copying credentials.
3. Identify the last exact-SHA-qualified rollback image and matching release manifest.
4. Use the rollback operation provided by `ec2-deploy.sh`; do not improvise container replacement.
5. Restore database state only when required and only from the verified predeployment backup after an isolated restore drill.
6. Re-run internal/public health, source revision, database integrity, foreign-key, Admin login, and audit checks.
7. Record the incident and exact source/backup identifiers, never secret values.

## 9. Current qualified baseline

The Administrator MFA implementation baseline deployed on 2026-07-31 is:

- source SHA: `1abb1aaee2dd49b59790a4b3c232cacdb3e2848a`;
- GitHub Actions run: `30670330492`;
- local backend/release suite: 502 passed;
- all five exact-SHA CI jobs passed with zero annotations;
- iOS Golden Formula parity passed;
- production enrollment and fresh TOTP login passed;
- database integrity passed with zero foreign-key violations.

A documentation-only commit after this baseline does not alter production runtime. If documentation changes are deployed as source, that new SHA requires its own exact-SHA CI qualification before promotion.
