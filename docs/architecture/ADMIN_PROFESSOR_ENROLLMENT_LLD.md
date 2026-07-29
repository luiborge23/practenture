# Administrator → Professor Enrollment LLD

**Status:** proposed corrective design; implementation is blocked until all acceptance tests below pass.

## 1. Problem statement

The existing Admin Console can persist an invitation while failing the actual job the Administrator came to perform: deliver usable professor access. The current UI uses a generic, one-time modal and labels a credential rotation endpoint as “resend,” although no mail is sent. That is a broken critical path, not a cosmetic problem.

The mobile client is also inconsistent: it asks for a legacy `PROF-XXXX-XXXX`-shaped value while the Admin invitation secret is a high-entropy URL-safe credential. The server-side activation endpoint is already atomic, but the handoff artifact and UI language are not.

## 2. Canonical actor journey

### Administrator

1. Sign in at `/admin`.
2. From the Overview, select **Create professor access**.
3. If no active organization exists, create one in the same guided flow; do not leave the Administrator at a read-only organization table.
4. Enter the professor’s exact email, optional internal note, and expiry.
5. Confirm the sensitive issuance action with recent authentication.
6. Receive a dedicated **Professor invitation ready** screen, not a transient generic modal. It must show:
   - professor email and organization,
   - expiry and one-use constraint,
   - **Copy invitation code** (for iOS),
   - clear browser-enrollment instructions (the professor opens `/login` and enters the same code), and
   - **Open prepared email** (a `mailto:` draft containing the correct link/code), and
   - **I have sent it securely** acknowledgement before closing.
7. The invitation list shows delivery state as **Created — not sent by Practenture** until the Administrator acknowledges the manual send. It never claims email was sent.
8. If the one-time value was lost or was sent to the wrong party, the Administrator chooses **Replace invitation**. The prior secret becomes invalid and a fresh one-time disclosure is shown. “Resend” is forbidden unless a real configured delivery provider sent the message.

### Professor

1. Receives the Administrator’s message at the exact invited email address.
2. Chooses one route:
   - **iOS:** Open Practenture → Professor access → Redeem professor invitation → paste invitation code; then complete identity/password fields using the same invited email.
   - **Web:** Open `/login`, enter the one-time invitation code, and use the exact invited email.
3. Server atomically validates the still-active invitation and email, creates account/identity/membership, consumes the invitation, and establishes the session.
4. A replay, expiry, email mismatch, revoked invitation, or failure in any account/membership write leaves no partial enrollment and returns a clear non-enumerating error.

## 3. State model

### Invitation lifecycle

`ISSUED` → `DISCLOSED_TO_ADMIN` → `ADMIN_ACKNOWLEDGED_DELIVERY` → `REDEEMED`

Terminal alternatives: `EXPIRED`, `REVOKED`, `SUPERSEDED`.

The secret itself is **never** persisted. The UI may record only metadata that the Administrator acknowledged a delivery handoff; this is evidence of workflow completion, not proof that email was delivered.

### Delivery model

`deliveryMode = MANUAL_EMAIL_DRAFT | MANUAL_COPY | PROVIDER_EMAIL`

Current supported production modes are `MANUAL_EMAIL_DRAFT` and `MANUAL_COPY`. `PROVIDER_EMAIL` is unavailable until a configured, audited outbound mail adapter exists. No UI control may call itself “Send email” before that integration has successful delivery evidence.

## 4. API contract

Existing secure issuance and activation endpoints remain authoritative. Add only explicit lifecycle metadata APIs if needed:

- `POST /api/admin/v2/invitations` → returns invitation metadata plus one-time `secret`.
- `POST /api/admin/v2/invitations/{id}/delivery-acknowledgements` → records chosen manual delivery mode and acknowledgement; requires CSRF/session but not a new secret.
- `POST /api/admin/v2/invitations/{id}/replace` → creates a new secret/hash, supersedes the old one, requires recent authentication and idempotency; returns the new one-time secret.
- `POST /api/auth/password/activate-professor` → continues to atomically consume invitation, create the password identity, organization membership, and authenticated session. The secret is submitted in the request body, never in a URL.

If compatibility requires retaining `/resend`, it must call the replacement behavior but be hidden from the UI and documented as deprecated. The new response/action name is **replace invitation**.

## 5. Security requirements

- Store only a salted/cryptographic hash of the secret; never log or audit the plaintext.
- Bind invitation to normalized email and organization on the server, and compare secret material in constant time.
- Enforce one use atomically and return `409 Invitation was already used` on replay.
- Requiring recent authentication for issue/replace/revoke remains mandatory.
- Use a fresh idempotency key per deliberate issuance/replacement. Exact retry returns the same secret only for the same idempotency key.
- Browser Admin auth stays HTTP-only, Secure, SameSite=Strict cookie based; no bearer token or secret in local/session storage.
- The one-time dialog must prevent accidental browser navigation loss: before dismissal, show an explicit acknowledgement; it still must not re-fetch the secret after close.
- `mailto:` must use URL encoding and must not open automatically. It is user-initiated only. The generated body may contain the code but must never contain a bearer secret in a URL.
- Do not add a fake “sent” state. Provider delivery status requires a provider message identifier and webhook/audit evidence.

## 6. UI requirements

### Critical-path UI

- Use task language: **Professor access**, **Create professor access**, **Invitation code**, **Copy code**, **Open email draft**, **Replace invitation**.
- Never expose backend-only labels such as `resend`, opaque invitation IDs, masked-code metadata, change-ticket metadata, or raw lifecycle fields as primary actions.
- On creation/replacement, route into a dedicated handoff surface with separate copy buttons and a ready-to-send email draft.
- Provide keyboard accessible feedback when either value is copied and a no-clipboard fallback (selectable readonly input/text area).
- Add error recovery: clearly explain that a closed/lost secret cannot be recovered and offer a high-risk **Replace invitation** action.

### Admin information architecture

- **Overview:** operational counts plus the single next action: create professor access.
- **Professor access:** create, deliver, acknowledge, replace, revoke, search, and audit invitations.
- **Organizations:** create/edit/activate/inactivate organizations. It may not be a read-only metadata table if invitation issuance depends on it.
- **Users, sessions, operations, audit:** either offer a specifically authorized action or explicitly identify themselves as read-only observability. Do not present decorative controls or metadata without a user outcome.

## 7. iOS requirements

- Replace the legacy `PROF-XXXX-XXXX` placeholder and prose with **One-time invitation code** and paste-oriented guidance.
- Do not tell a professor they will “create an account first, then redeem” the code. The actual password route is atomic: invitation + account + organization membership are created in one request.
- Explain that the email must exactly match the email to which the Administrator sent the invitation.
- Preserve server authority; the iOS app must not treat entering a code as successful until the activation response succeeds.
- Add a deterministic activation error mapping for used, expired/revoked, and email-mismatch states without leaking other account details.

## 8. Ralph execution backlog

### P0 — blocks release

1. Replace the current generic secret modal with the dedicated delivery/handoff surface and separately test copy-code, copy-link, prepared-email, and acknowledgement behavior.
2. Rename/hide “resend”; implement **Replace invitation** with explicit invalidation semantics and a one-time replacement disclosure.
3. Fix iOS invitation copy, placeholder, and onboarding wording to match the atomic server contract.
4. Add an Admin organization creation path or a guided prerequisite branch from the professor-access flow.
5. Add backend/API, DOM, and iOS contract tests that execute the full Admin → handoff → activation journey.
6. Test all terminal invitation outcomes: redeemed, replayed, expired, revoked, replaced, lost-secret recovery, email mismatch, and rollback after account creation failure.

### P1 — required for operational quality

1. Persist and show a privacy-safe manual delivery acknowledgement/event.
2. Make every Admin view/action either operationally usable or explicitly read-only; remove dead metadata/actions.
3. Add an adapter interface for future provider email delivery, defaulted to disabled, with no misleading send UI.
4. Add accessibility and responsive-browser UI tests for the handoff surface.

### P2 — only after P0/P1

1. Configure an audited provider email implementation (for example SES) only with explicit product/security approval, domain validation, bounce handling, delivery webhooks, retention policy, and rollback.
2. Add universal/deep links only once iOS ownership and redirect security are designed and tested.

## 9. Definition of done / release gates

The feature is not done until all conditions below are demonstrated:

1. A fresh Administrator can create an organization if necessary, issue an invitation, copy its code, open a correctly addressed email draft, and see exact manual-send/browser-enrollment instructions without leaving the flow.
2. A professor can use the copied code in the iOS production onboarding UI and complete activation with the invited email.
3. Browser-code activation and iOS-code activation are each verified against the same backend invitation record.
4. Secret replay is blocked; replacement invalidates the prior secret; unacknowledged/acknowledged delivery metadata does not expose secrets.
5. Backend contracts, migration tests, iOS unit/UI tests, JS syntax checks, and an authenticated production smoke test pass.
6. All Admin metadata/actions have a documented user outcome, or are removed/labelled read-only.

## 10. Explicit non-goals for this release

- Claiming or simulating automatic email sending without a real configured delivery provider.
- Recovering a lost one-time secret from storage.
- Allowing client-side role promotion or client-derived organization scope.
- Replacing security controls merely to reduce steps in the UI.
