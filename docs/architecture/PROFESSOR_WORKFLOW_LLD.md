# Practenture Professor Workflow — Low-Level Design

**Status:** Approved implementation target
**Last updated:** 2026-07-30
**Method:** RALPH full cycle (research → critique → architecture → contracts → vertical slices → executable gates)
**Systems:** FastAPI, SQLite/PostgreSQL-compatible persistence boundary, secure browser portal, SwiftUI iOS client, AWS SES

## 1. Purpose

Practenture provides one Professor identity and one server-authoritative classroom state across web and iOS. A Professor must be able to prepare, launch, facilitate, monitor, and close a simulation without learning two incompatible products or creating duplicate accounts.

The web experience is the primary planning and analysis workspace. The iOS experience is the mobile classroom companion. Core lifecycle commands are available in both clients and use the same backend contracts. Platform UI may differ; authorization, ownership, state transitions, and simulation rules never do.

## 2. Goals and measurable outcomes

1. A Professor activates one invited identity and uses the same username/password on web and iOS.
2. A Professor can create a backend session from web or iOS and see it on the other platform after refresh/synchronization.
3. Every session mutation derives the Professor and organization/class scope from authenticated server state—not browser fields.
4. A Professor can only read, mutate, grade, or export sessions they own or have explicit delegated access to.
5. Session creation ends with an unmistakable success state containing the join code, copy action, and classroom next steps.
6. Destructive or irreversible lifecycle commands use explicit confirmation and truthful server responses.
7. Repeated clicks, retries, expired authentication, and concurrent requests cannot silently duplicate or corrupt a lifecycle transition.
8. Web functionality meets WCAG-oriented form practices: labeled controls, keyboard operation, visible focus, error summary, status announcements, and one workflow state at a time.
9. Release gates prove backend contracts, browser behavior, iOS build/flow health, tenant isolation, production backup, deployment identity, and live end-to-end behavior.

## 3. Non-goals for the first production slice

- Reimplementing simulation formulas in JavaScript or SwiftUI views.
- Client-authoritative round advancement or inferred session state.
- Offline-to-online reconciliation for authoritative classroom sessions.
- Secret-bearing join or reset credentials in URLs.
- Silent auto-processing of a round when human submissions are missing.
- A pixel-identical web/iOS interface.

## 4. SOTA principles and source basis

- **OWASP CSRF guidance:** cookie-authenticated mutations require a CSRF defense beyond relying on SameSite alone. Practenture uses a random double-submit token, a custom request header, constant-time comparison, Strict cookies, and same-origin CSP.
- **W3C WAI form guidance:** controls have programmatic labels, instructions precede input, errors identify the affected field, and multi-step state is announced and keyboard operable.
- **NIST session principles:** authentication state has bounded lifetime; sensitive account recovery and lifecycle operations fail closed on expired sessions. Password reset revokes existing credentials.
- **HTTP resilience:** mutations return stable status/error envelopes, reject invalid transitions, disable controls in-flight, and treat retries explicitly rather than assuming a network failure means the mutation did not occur.

References:
- OWASP Cross-Site Request Forgery Prevention Cheat Sheet
- W3C Web Accessibility Initiative Forms Tutorial
- NIST SP 800-63B session management guidance
- RFC 9457 Problem Details (future normalization target; existing Practenture `detail` envelopes remain compatible during this slice)

## 5. Review of the initial three-phase rollout

### 5.1 What was correct

The initial proposal correctly established:

- one shared identity;
- iOS-to-web session visibility as the first proof;
- web creation as the next capability;
- lifecycle parity as the final direction;
- backend authority and ownership isolation.

### 5.2 What was incomplete

The proposal was feature-ordered rather than risk-ordered. It omitted:

- browser cookie-authentication adaptation for bearer-authenticated session APIs;
- CSRF protection for browser mutations;
- explicit lifecycle/state-machine contracts;
- idempotency/concurrency behavior;
- creation success and error recovery UX;
- scenario and class ownership validation;
- destructive confirmation and rollback gates;
- accessibility requirements;
- production deployment identity and cross-client contract verification.

### 5.3 Revised rollout: vertical slices

Each slice is independently usable and releasable, and each includes backend, web, iOS contract, security, tests, and telemetry.

#### Slice A — Shared identity and cross-client proof

1. Sign into iOS and web with the same Professor identity.
2. Verify JWT/cookie sessions both resolve to the same backend `sub`, Professor role, and organization membership.
3. Create one disposable iOS session.
4. Verify web visibility, configuration fidelity, and ownership isolation.
5. Delete the disposable session through an authorized lifecycle command.

#### Slice B — Safe web creation

1. Fetch production-backed scenario choices from the server.
2. Fetch only classes owned by the Professor.
3. Complete a focused creation form with safe defaults.
4. Review the complete server-bound configuration.
5. Submit once with CSRF and in-flight duplicate prevention.
6. Display the returned join code, copy action, next steps, and session row.
7. Verify the session appears in iOS from the same backend.

#### Slice C — Classroom lifecycle controls

1. Start only a `creating` session.
2. Monitor teams and current-round submissions.
3. Process a round only when all human teams have submitted; identify missing teams otherwise.
4. End an active/creating session with explicit confirmation.
5. Delete only through a typed/destructive confirmation after showing impact.
6. Send announcements to the owned session.
7. Refresh server state after every successful command; never increment locally.

#### Slice D — Organization and roster workflows

1. Create/list classes.
2. Display class join code separately from simulation join code.
3. Show class roster and enrollment state.
4. Bind a session to an owned class.
5. Add delegated co-Professor access as an explicit authorization model before allowing non-owner mutation.

#### Slice E — Analysis and operational hardening

1. Detailed leaderboard, grading, and exports.
2. WebSocket/SSE updates with polling fallback.
3. Session templates and cloning through a server-side command.
4. Provider delivery/bounce monitoring and domain email authentication.
5. PostgreSQL migration/readiness before multi-worker classroom scale.

## 6. Capability matrix

| Capability | Web | iOS | Authority |
|---|---:|---:|---|
| Shared Professor login | Yes | Yes | Auth backend |
| Invitation activation | Yes | Yes | Enrollment backend |
| Password recovery | Yes | Yes | Auth backend + SES |
| List owned sessions | Yes | Yes | Backend scoped query |
| Create/configure session | Yes | Yes | Session API |
| Display/copy join code | Yes | Yes | Server response |
| Start/end session | Yes | Yes | Session state machine |
| Process round | Yes | Yes | Simulation backend |
| Monitor submissions | Yes | Yes | Backend status/progress |
| Announcements | Yes | Yes | Backend session channel |
| Classes/roster | Primary | Companion | Class APIs |
| Grades/leaderboard/export | Primary | Summary/share | Backend/export APIs |
| Simulation formulas | Never | Never for online mode | Backend engine |

## 7. Professor journey

### 7.1 Account access

1. Administrator invites an exact email.
2. Professor activates and creates one username/password identity.
3. Web stores a Secure, HttpOnly, SameSite=Strict session cookie.
4. iOS stores access/refresh credentials in Keychain.
5. Both sessions resolve to the same `user_id`/JWT `sub`.
6. Forgotten passwords use an emailed one-time code; invitations are not reused for recovery.

### 7.2 Workspace landing

The workspace presents:

- `Create session` as the primary action;
- total, active, and student-team metrics;
- owned-session table;
- status, round, teams, submissions, and available actions;
- truthful empty state that offers creation on web or iOS.

It must not imply that an empty list is an authentication failure.

### 7.3 Create-session workflow

The production slice uses a focused, single-page staged form rather than exposing every engine constant.

**Step 1 — Scenario**
- Select from server-returned production scenarios only.
- Research/uncalibrated scenarios are disabled server-side and absent from selectable results.

**Step 2 — Classroom details**
- Session name (required, normalized length limit).
- Optional owned class.
- Optional course code and semester metadata.

**Step 3 — Gameplay**
- Total rounds: 1–50; recommended templates describe classroom duration.
- Human-team capacity: bounded by server contract.
- AI competitors: 0–20.
- Market type, AI difficulty, and scoring metric.
- Advanced economic constants remain collapsed/defaulted unless the product intentionally exposes them.

**Step 4 — Review**
- Read-only summary of every value sent to the backend.
- Warning that authoritative online sessions require network connectivity.
- One primary `Create session` command.

**Success**
- Dedicated success panel with join code.
- `Copy code`, `Open session`, and `Create another` actions.
- The created row is loaded from the server response/refresh—not synthesized optimistically.

**Failure**
- Form values remain intact.
- Error summary receives focus and identifies invalid fields.
- Authentication failure returns to sign-in without claiming creation.
- Retry is safe; duplicate in-flight submission is blocked client-side, while server-side idempotency remains the target for distributed retries.

### 7.4 Operate-session workflow

State machine:

```text
creating --start--> active --process round--> active
                         |                    |
                         +------end---------->finished
                                              ^
                         final round processing+
```

Allowed commands:

| Current state | Command | Result |
|---|---|---|
| creating | start | active, currentRound=1 |
| creating | end | finished |
| active | process round | next round or finished |
| active | end | finished |
| finished/completed | export | immutable read/export |
| any owned state | delete | removed after explicit confirmation |

Invalid transitions return `400/409` and do not mutate state. A foreign Professor always receives `403`, including when guessing a valid code.

Round processing:

1. Lock/serialize by session in the application boundary and use transactional persistence where available.
2. Re-read the authoritative state after acquiring the transition boundary.
3. Require all human-team decisions for the current round.
4. Generate AI decisions deterministically.
5. Store results and team state before advancing.
6. Advance exactly once; clients never call a second `/advance` operation.
7. Return the processed round and authoritative next state.

### 7.5 End and delete

- **End:** explicit confirmation explaining that no further decisions can be submitted. Export remains available.
- **Delete:** destructive confirmation includes session code and warns that results/submissions are removed. A future hardened deletion slice requires typed confirmation, recent authentication, verified backup, audit record, transaction, and rollback injection. Until that complete control plane exists, web deletion must remain deliberately constrained and tested.

## 8. Backend contracts

### 8.1 Browser adapter

Browser JavaScript never receives or stores a bearer token. `/api/professor-portal/*` adapts the Secure HttpOnly Professor cookie to the existing server-side service functions.

Every browser mutation requires:

- valid Professor session cookie;
- `X-CSRF-Token` custom header;
- matching random `practenture_professor_csrf` cookie;
- constant-time token comparison;
- SameSite=Strict cookies and same-origin CSP;
- ownership check using authenticated `sub`.

### 8.2 Creation request

```json
{
  "config": {
    "name": "MBA 510 — Fall 2026",
    "courseCode": "MBA 510",
    "semester": "Fall 2026",
    "totalRounds": 8,
    "numberOfAICompetitors": 3,
    "marketType": "moderate",
    "aiDifficulty": "medium",
    "scoringMetric": "investorScore"
  },
  "teams": [],
  "maxHumanTeams": 10,
  "classId": null,
  "scenarioId": "athletic-footwear",
  "scenarioVersion": "1.0.0"
}
```

Server ignores/rejects client-selected owner identity. `professor_user_id` is always `auth.sub`.

### 8.3 Responses and errors

- `201`: creation response contains `sessionId` and `code`.
- `200`: lifecycle command succeeded and returns authoritative state/summary.
- `204`: deletion succeeded.
- `400`: invalid state or validation.
- `401`: missing/expired session.
- `403`: role/ownership/class-scope denial or CSRF denial.
- `404`: resource absent after authorization policy is applied.
- `409`: missing submissions, replay/in-flight transition, or conflict.
- `422`: structured field validation.

No response or audit record includes passwords, invitation codes, reset codes, cookies, or bearer tokens.

## 9. Security and tenancy invariants

1. Client input never selects the Professor owner, organization, or authorization scope.
2. Class binding is accepted only when the class belongs to `auth.sub` (or an explicit server-authorized delegate).
3. Every read/export/mutation checks durable session ownership.
4. Session codes are identifiers, not authorization credentials.
5. Browser mutations fail without a valid CSRF token even when the session cookie is present.
6. Cookie and bearer authentication paths call the same domain operations and produce identical ownership behavior.
7. Online session mutations never fall back to a local engine.
8. Refresh after mutation adopts backend state; clients do not predict advancement.
9. Repeated round processing cannot advance twice for one authoritative round.
10. Logs and UI diagnostics never expose JWTs, cookies, passwords, invitation/reset codes, or AWS credentials.

## 10. Accessibility and responsive UX

- Exactly one authentication/recovery mode is visible at a time.
- `hidden` is enforced globally and cannot be overridden by layout classes.
- Every input has a `<label>` and concise help text.
- Validation errors are connected with `aria-describedby` and announced through `role=alert`/`aria-live`.
- Successful mutations use an explicit `role=status` panel and move focus to the new state.
- Dialogs trap focus, support Escape where safe, and restore focus to their invoking control.
- Color is never the only state indicator.
- All session actions are keyboard reachable.
- Tables provide useful small-screen card behavior or horizontal affordance without hiding critical actions.
- Destructive actions are visually separated from routine controls.

## 11. Observability and audit

Record non-secret events:

- session created (actor, session ID/code, class ID, scenario/version);
- session started/ended;
- round processed (session, processed round, resulting state);
- announcement created;
- export requested;
- deletion attempted/completed/denied;
- ownership/CSRF denials aggregated without credentials.

Metrics:

- creation success/failure rate;
- time from creation to first team join;
- missing-submission conflicts;
- lifecycle command latency and 5xx rate;
- cross-client synchronization delay;
- active sessions and concurrent teams.

## 12. RALPH implementation stories

### US-001 — Shared browser mutation security
- Issue/clear a CSRF token with Professor browser authentication.
- Validate custom header + cookie on every portal mutation.
- Preserve Secure/HttpOnly/Strict session-cookie behavior.
- Add success/failure/constant-time-boundary contracts.

### US-002 — Session metadata contract
- Add bounded name/course/semester fields to `SessionConfiguration`.
- Preserve backward compatibility/defaults and persisted JSON loading.
- Verify iOS payload compatibility and OpenAPI contracts.

### US-003 — Professor portal creation APIs
- List production scenarios and owned classes.
- Create sessions through the same domain operation as iOS.
- Derive owner from authenticated Professor session.
- Test class/tenant isolation and invalid scenarios.

### US-004 — Web creation UX
- Add accessible staged form and review summary.
- Add in-flight prevention, field/error preservation, and dedicated success state.
- Copy join code without putting it in a URL.
- Reload the created session from server state.

### US-005 — Lifecycle commands
- Add cookie-adapted start, process-round, end, and constrained delete operations.
- Serialize/re-read round transitions.
- Add explicit confirmations and authoritative refresh.
- Test invalid state, replay, and foreign ownership.

### US-006 — Classes and announcements
- List/create owned classes and display class join codes distinctly.
- Send announcements only to an owned session.
- Add roster/read contracts where the UI exposes them.

### US-007 — iOS shared-account parity
- Build and test Professor login against the shared login contract.
- Verify creation request fields and server-authoritative synchronization.
- Remove secret/token preview diagnostics from production UI.
- Ensure online mutations never use local fallback.

### US-008 — Release gate
- Run focused and complete backend tests.
- Run JavaScript syntax/contract/browser checks.
- Run iOS unit/UI build checks on the available iPhone 17 Pro simulator.
- Back up production, verify artifact checksum, deploy, and compare live source/static identity.
- Run disposable authenticated production E2E and clean it up.

## 13. Executable acceptance matrix

| Requirement | Evidence |
|---|---|
| Same credentials | iOS login response and web cookie session resolve to same `sub`/role |
| Web creation | Browser/API creates session; row and success join code shown |
| Cross-client visibility | Created session appears in iOS dashboard fetch |
| Ownership | Second Professor gets 403 for read/mutate/export |
| CSRF | Missing/mismatched token rejects every cookie-authenticated mutation |
| Scenario/class validation | Unavailable scenario and foreign/missing class rejected |
| Start | creating→active/currentRound=1 exactly once |
| Process | missing human submissions=409; valid round advances exactly once |
| End | state becomes finished and rejects future submissions/processing |
| Delete | explicit confirmation and owned-only deletion |
| Accessibility | browser snapshot contains one active workflow and labeled controls |
| Recovery regression | invitation/login/reset/success UI contracts remain green |
| Deployment | backup, checksum, healthy container, live asset/source hashes, no fatal logs |

## 14. Test strategy

### Backend

- Professor portal authentication/cookie/CSRF contracts.
- Creation validation and exact persisted configuration.
- Own/foreign class and session matrix.
- Lifecycle state table tests.
- Concurrent/repeated round-processing winner test.
- Rollback/failure-injection tests around multi-write operations where supported.
- Existing gameplay, tenant, auth, enrollment, password reset, exports, migrations, OpenAPI, formula parity, and 20-student E2E suites.

### Browser

- Unauthenticated shell and one-visible-mode contract.
- Professor sign-in and workspace load.
- Create form field validation and review.
- Success join-code state.
- Start/end/process confirmation and error handling.
- Keyboard/label/ARIA snapshot.
- Responsive layout checks.
- No console errors and no bearer tokens in Web Storage.

### iOS

- `AuthManager.loginProfessor` shared contract.
- `NetworkService.createSession` payload contract.
- Session refresh adopts backend code/state.
- No duplicate local round advancement.
- Simulator clean build, unit tests, and maintained UI tests.
- Physical-device install/launch and opt-in production integration where available.

### Production E2E

Use a uniquely named disposable QA session. Never use the same session/team planned for manual classroom testing.

1. Authenticate through a secure non-logging method.
2. Create via web adapter.
3. Verify owner and configuration in server state.
4. Verify session appears through the iOS-used dashboard API.
5. Exercise safe lifecycle transitions with disposable teams/data.
6. Verify a different Professor is denied.
7. Export results when available.
8. Delete the disposable session and verify absence.
9. Recheck health, restart count, and fatal logs.

## 15. Deployment and rollback

1. Record branch/status and exclude secrets, `.ec2-state.json`, databases, caches, and generated test artifacts.
2. Run all release gates before network/deployment actions.
3. Build deterministic release artifact and SHA-256 checksum.
4. Create and independently verify a production database backup.
5. Preserve stable JWT, Professor/Admin credentials, SES settings, Compose project, and volume identity.
6. Deploy through the backup-gated script.
7. Verify container health and intended source/static versions—not health alone.
8. Run live authenticated smoke/E2E.
9. Roll back the image and database only from the verified pre-release pair if a schema/state incompatibility occurs.

## 16. Decisions

- Web is no longer designed as monitoring-only; it is the primary Professor command center.
- iOS remains a fully supported classroom companion using the same account and backend commands.
- Backend is authoritative across both clients.
- The first production implementation prioritizes safe creation and lifecycle controls over exposing every advanced engine constant.
- Co-Professor delegation requires an explicit durable authorization model and is not inferred from organization membership.
- Server-side idempotency keys and transactional lifecycle operations are required before horizontally scaled/multi-worker deployment.
