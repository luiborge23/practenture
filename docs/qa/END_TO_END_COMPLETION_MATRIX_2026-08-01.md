# Practenture End-to-End Completion Matrix — 2026-08-01

This matrix records fresh evidence for the current uncommitted candidate. It is not release authorization. Production remains on the previously qualified revision until a committed exact SHA passes CI and post-deployment gates.

## Status vocabulary

- **Verified locally** — exercised successfully against the current working tree.
- **Implemented, production proof pending** — code and local contracts pass, but the production-only gate was intentionally not run.
- **External/manual blocker** — requires credentials, a physical device, signing, provider acceptance, or store review unavailable to this qualification run.
- **Open** — locally controllable acceptance evidence is incomplete.

## Administrator and authentication

| Requirement | Implementation | Fresh evidence | Status / blocker |
|---|---|---|---|
| Administrator MFA enrollment, confirmation, recovery codes, replay rejection, and disable lifecycle | `backend/admin_v2.py`, `backend/database.py`, migration `007` | Full backend wrapper: `515 passed`; Administrator MFA contract suites included | **Verified locally** |
| MFA throttling and reservation ownership | Administrator auth/database throttle paths | Full backend wrapper and focused MFA contracts | **Verified locally** |
| Suspended/deleted/password-revoked identities lose HTTP and WebSocket access | `backend/auth.py`, `backend/ws_manager.py`, `backend/routers/websocket.py` | Gameplay WebSocket contract suspends a connected user and observes close code `4001`; full wrapper passes | **Verified locally** |
| Browser Professor session cookies, same-origin checks, CSRF, and secure MFA controls | `backend/professor_portal.py`, portal JS/templates | Professor portal and invitation-enrollment contracts in full wrapper | **Verified locally** |
| Physical Apple, Google, password, MFA, and recovery acceptance on the final iOS build | Provider UI/device interaction | Current source builds and signs for the connected iPhone; provider interactions were not performed | **External/manual blocker** |
| Physical Google Credential Manager acceptance on Android | Android Credential Manager plus backend Google contract | No physical Android device is attached; emulator build has no production server client ID | **External/manual blocker** |

## Backend, tenant isolation, and simulation authority

| Requirement | Implementation | Fresh evidence | Status / blocker |
|---|---|---|---|
| Backend-authoritative session lifecycle and decision processing | `backend/routers/sessions.py`, `decisions.py`, simulation engine | Full warning-fail-closed backend wrapper: `515 passed in 137.38s` | **Verified locally** |
| One Professor, 20 Students/teams, eight rounds, exports, announcements, leaderboard, and tenant denial | `backend/tests/contracts/test_gameplay_contract.py` | Included in the 515-test aggregate; focused lifecycle/gameplay gate also passed | **Verified locally** |
| Session reads, announcements, and WebSockets enforce participant/owner/tenant access | `backend/session_access.py`, session/announcement/WebSocket routers | Focused gameplay/lifecycle contracts and aggregate wrapper pass | **Verified locally** |
| Connected sockets cannot outlive token/account/session authorization boundaries | `backend/ws_manager.py`, `backend/routers/websocket.py` | Inbound requests revalidate credentials; broadcasts revalidate token, account status, and session access; suspension contract passes | **Verified locally** |
| Lifecycle events reach clients, including terminal state | Session router broadcasts `session_started`, `round_complete`, and `session_ended`; announcement router broadcasts messages | Backend contracts plus iOS reducer tests | **Verified locally** |
| Exact OpenAPI/client DTO compatibility | Backend contract manifests, Swift DTOs, Kotlin DTOs | Backend contracts, 32 iOS unit tests (one skipped), and 17 Android JVM contracts pass | **Verified locally** |

## Professor workflows

| Requirement | Implementation | Fresh evidence | Status / blocker |
|---|---|---|---|
| Login/enrollment, class/session creation, start, announcement, process, end, export, delete | `backend/professor_portal.py`, portal templates/JS | Professor workflow, dashboard export, classes, invitation, and gameplay contracts in aggregate wrapper | **Verified locally** |
| Foreign Professor cannot read, mutate, announce, export, or stream another session | Shared session authorization and Professor portal ownership checks | Contract matrix included in aggregate wrapper | **Verified locally** |
| Dashboard monitoring: lifecycle state, current round, team count, current/total submissions | `/api/professor-portal/progress`, portal session table | Professor workflow contract checks exact progress response | **Verified locally** |
| Browser-level per-team submission drill-down, result charting, and submission audit | `/api/professor-portal/progress/{code}/monitor`, portal monitor dialog | Ownership contract verifies foreign denial and authoritative team/round/result payload; focused portal/release gate: `20 passed`; aggregate backend wrapper: `515 passed`; static rendered-data visual QA verified visible Close/Refresh actions, table, and charts | **Verified locally**; live authenticated multi-browser exercise remains pending |
| Raw decision-value audit | No raw decision values are exposed by the monitor endpoint | The portal shows which teams submitted each round without disclosing each decision field | **Open only if raw decision-value inspection is a product requirement** |
| Fresh live multi-browser Professor/Student exercise against the final candidate | Browser runtime | Production was intentionally unchanged and backend was not run locally | **Open** under current no-local-backend/no-deploy constraint |

## Student workflows

| Requirement | Implementation | Fresh evidence | Status / blocker |
|---|---|---|---|
| Authenticate, join, submit complete modern decisions, observe state/results/leaderboard/announcements | Backend routes, iOS Student views, Android Compose/repository | 20-student backend E2E, iOS QA harness Student test, Android serialization/lifecycle contracts | **Verified locally** at contract/harness level |
| Student identity and team authority are server-derived | Shared session authorization and decision routes | Wrong-principal, unjoined, and foreign-tenant contracts pass | **Verified locally** |
| Rejected or duplicate mutations leave authoritative state unchanged | Backend lifecycle/decision contracts | Included in aggregate backend wrapper | **Verified locally** |
| Fresh real-provider Student login and live production gameplay on final candidate | Physical device/provider/production runtime | Not exercised because production remains on qualified baseline | **External/manual blocker** |

## iOS

| Requirement | Fresh evidence | Status / blocker |
|---|---|---|
| Simulator compile and XCTest | `xcodebuild ... test`: 32 tests executed, one skipped, zero failures; `/tmp/practenture-ios-final-p1.log` has zero `warning:`/`error:` matches | **Verified locally** |
| Real-time events update production state | `BackendState` reducer tests cover start, round completion, announcement, and terminal state | **Verified locally** |
| Logout closes authenticated WebSocket | `AuthManager.logout()` calls `BackendState.shared.disconnect()`; unit build/tests pass | **Verified locally** |
| Professor/Student/error/offline UI harness | QAUITests: four tests, zero failures | **Functionally verified**, but the simulator runtime emits duplicate accessibility-class and debugger-version diagnostics; strict clean-log release gate remains **Open** |
| Connected-iPhone compilation and development signing | `xcodebuild` for device `00008150-000839012132401C`: `BUILD SUCCEEDED`; zero `warning:`/`error:` matches | **Verified locally** |
| Physical provider execution | Not run | **External/manual blocker** |
| Distribution archive and TestFlight acceptance | Not run | **External/manual blocker** |

## Android

| Requirement | Fresh evidence | Status / blocker |
|---|---|---|
| Keystore-encrypted access/refresh tokens, refresh rotation, one retry | `TokenStore`, `ApiFactory`; JVM contracts include transient refresh preservation | **Verified locally** |
| MFA/password-change/Google challenge handling | Compose authentication UI and backend DTO contracts | JVM contracts pass; first-time Google Professor challenge is surfaced instead of accepting a blank token | **Verified locally** at contract level |
| Professor/Student backend-authoritative lifecycle and decisions | Compose/repository/API implementations | 17 JVM contracts pass | **Verified locally** |
| Compile, APK, lint | `testDebugUnitTest assembleDebug lintDebug`: `BUILD SUCCESSFUL`; lint says `No issues found.` | **Functionally verified** |
| Warning-free Android aggregate log | `/tmp/practenture-android-final-p1.log` | **Open** — Android SDK metadata parser emits one SDK XML v4 compatibility warning |
| Emulator installation, cold launch, and visual QA | APK installed and launched on `emulator-5554`; final login visual QA passed | **Verified locally** |
| Physical Google authentication and release-signed AAB/Play acceptance | No physical Android; no production server client ID/signing/store interaction | **External/manual blocker** |

## Deployment, TLS, monitoring, and recovery

| Requirement | Implementation | Fresh evidence | Status / blocker |
|---|---|---|---|
| Immutable release manifest and exact revision/digest binding | `ec2-deploy.sh`, `scripts/verify_release_manifest.py` | `Tests/test_release_contracts.py`: 14 passed; shell syntax passes | **Verified locally** |
| Transactional activation and retained-image/database/TLS rollback | `ec2-deploy.sh`, `scripts/restore_tls_renewal.sh` | `14` release contracts pass; durable commit markers, protected root-owned TLS snapshots, interrupted-promotion recovery, and fail-closed restoration received final independent P0/P1 `PASS` | **Verified locally** |
| Failed first activation is retryable | First deployment now creates a pre-migration SQLite snapshot and clears candidate markers after restoration | Release contract assertions and shell syntax pass | **Verified locally** |
| ACME webroot renewal without stopping Nginx | Nginx challenge route and `scripts/install_tls_renewal.sh` | Release contracts verify webroot-only behavior | **Implemented, production proof pending** |
| Failed renewal installation restores prior timer/units/hook | Installer atomic snapshot and EXIT trap; dry run precedes unit replacement; exact prior enabled/active state restored | Release contracts and final independent P0/P1 `PASS` | **Verified locally**; production failure injection not performed |
| Expiry watchdog healthy/threshold/scheduled behavior | `scripts/check_tls_expiry.py` | Local healthy, alert, and scheduled-mode executions previously passed | **Verified locally** |
| Production Certbot dry run, timer enabled/active/next run, deploy-hook reload without outage | Requires production installation | Intentionally not run because production cannot change before release qualification | **Production gate pending** |
| Backup/restore, integrity, migration head, rollback artifact on final deployed SHA | Deployment verification path | Previously proven for the qualified baseline only | **Pending for candidate** |

## Release decision

**NOT AUTHORIZED FOR COMMIT, PUSH, DEPLOYMENT, OR STORE DISTRIBUTION.**

The current candidate has strong local functional evidence, but release authorization still requires:

1. Resolve or explicitly waive the Android SDK XML warning and iOS simulator platform diagnostics under the strict zero-warning policy.
2. Complete live browser visual acceptance of the new Professor monitor and decide whether raw decision-value inspection is required.
3. Preserve the completed backend/deployment, Android, and iOS/WebSocket independent P0/P1 `PASS` verdicts by making no further implementation edits before candidate qualification.
4. Commit only with explicit authorization, then require a clean six-job exact-SHA CI run with zero unresolved warnings or annotations.
5. Deploy only through `./ec2-deploy.sh deploy`, then verify production TLS dry run/timer/reload, migrations, integrity, backups/restores, rollback evidence, revisions, and restart-free health.
6. Separately complete physical provider authentication, release signing, TestFlight, Play internal-track acceptance, and store distribution.
