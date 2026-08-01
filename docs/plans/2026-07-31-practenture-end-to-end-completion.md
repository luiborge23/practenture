# Practenture End-to-End Completion Plan

> **For Hermes:** Use subagent-driven-development to implement this plan task-by-task. Use fresh bounded specialists, then specification and quality review. The controller reruns every load-bearing gate after agents stop modifying the tree.

**Goal:** Reach the strongest verifiable Practenture release state between 2026-07-31 22:35 CDT and 2026-08-01 23:59 CDT across production operations, backend, Administrator, Professor, Student, iOS, and Android, while explicitly separating external store/provider/device approvals from code completion.

**Architecture:** The FastAPI backend is authoritative for identity, tenant ownership, simulation state, rounds, decisions, results, exports, and announcements. Web, iOS, and Android must consume the same reviewed API contracts and never advance local state without server confirmation. Release qualification is fail-closed: clean quiescent worktree, complete local gates, independent review, exact-SHA CI, transactional deployment, and post-deploy verification.

**Tech Stack:** Python 3.11, FastAPI, SQLite/Alembic, pytest, Docker Compose, Nginx, Certbot/systemd, SwiftUI/XCTest/XCUITest, Kotlin/Jetpack Compose/Retrofit/Credential Manager/Gradle, GitHub Actions.

---

## Time Box and Definition of “Complete”

### Tonight — July 31, 22:35–23:59 CDT

1. Freeze requirements from `PRD.md` and current OpenAPI/tests.
2. Finish TLS/deployment hardening and final review findings.
3. Run focused infrastructure and complete backend regression gates.
4. Build a requirements-to-evidence matrix for all six product surfaces.
5. Start independent backend, iOS, and Android audits in parallel.

### Tomorrow morning — August 1, 00:00–08:00 CDT

1. Fix backend/Professor/Student contract gaps using focused tests first.
2. Run a fresh disposable-database 20-student × 8-round E2E.
3. Verify Professor create/start/process/end/export/announcement ownership flows.
4. Verify Student login/join/submit/results/leaderboard/announcement flows.
5. Reconcile OpenAPI, web, Swift, and Kotlin DTOs.

### Tomorrow daytime — August 1, 08:00–17:00 CDT

1. Build and test iOS on the available iPhone 17 Pro simulator.
2. Run deterministic XCTest/UI harness flows and warning scans.
3. Build and test Android with warnings-as-errors.
4. Launch Android on an available emulator and capture process/logcat evidence.
5. If the connected physical iPhone is available and unlocked, install/launch and run opt-in production-network XCTest without exposing credentials.
6. Record physical Android Google sign-in as externally blocked unless a correctly signed device build and production OAuth client are available.

### Tomorrow evening — August 1, 17:00–23:59 CDT

1. Quiescence barrier: all agents stopped; inspect all diffs and imports.
2. Run aggregate backend, release, iOS, Android, parity, container, and warning gates.
3. Obtain independent specification, security, and integration reviews.
4. If commit/push/deploy authorization is granted: create a new SHA, require clean exact-SHA CI with zero annotations, deploy only through `./ec2-deploy.sh deploy`, and run post-deploy verification.
5. Publish final completion matrix and explicit external blockers.

“Complete” means every locally controllable requirement is either backed by fresh executable evidence or identified as a precise defect and fixed. App Store/TestFlight, Play Console, production identity-provider approval, physical-device Google behavior, and institutional acceptance cannot be truthfully declared complete without their external credentials/devices/review outcomes.

---

## Task 1: Finish TLS Renewal and Transactional Deployment Hardening

**Objective:** Make certificate renewal and interrupted deployment recovery fail-closed and testable.

**Files:**
- Modify: `ec2-deploy.sh`
- Modify: `docker-compose.yml`
- Modify: `nginx-practenture.conf`
- Modify: `Tests/test_release_contracts.py`
- Create: `scripts/install_tls_renewal.sh`
- Create: `scripts/check_tls_expiry.py`
- Create: `scripts/verify_release_manifest.py`
- Modify: `docs/architecture/SYSTEM_ARCHITECTURE.md`

**Steps:**
1. Verify the uploaded artifact cryptographically binds the immutable release manifest.
2. Reject manifest/file mutation, unexpected files, and symlinks in reused releases.
3. Clear activation markers after promotion and preserve rollback evidence until the durable marker exists.
4. Ensure any failed candidate completion restores the retained image and SQLite backup before retry.
5. Serve HTTP-01 only under `/.well-known/acme-challenge/`; redirect all other HTTP traffic.
6. Install Certbot webroot service/timer, validate systemd units, execute a real dry run, validate Nginx, reload only after success, then enable the timer.
7. Keep the expiry monitor silent while healthy and actionable on threshold/validation failure.
8. Run:
   - `PYTHONPATH='' backend/.venv/bin/python -m pytest Tests/test_release_contracts.py -q`
   - `bash -n ec2-deploy.sh scripts/install_tls_renewal.sh`
   - `docker-compose config --quiet`
   - `git diff --check`
   - isolated Docker Nginx/ACME challenge gate
   - `./scripts/test_backend.sh`

**Acceptance:** No unresolved P0/P1 independent-review finding; every focused and aggregate gate exits zero; no deployment occurs from an uncommitted or unqualified tree.

## Task 2: Build the Requirements-to-Evidence Matrix

**Objective:** Replace stale “complete” claims with current executable evidence.

**Files:**
- Create: `docs/qa/END_TO_END_COMPLETION_MATRIX_2026-08-01.md`
- Review: `PRD.md`
- Review: `backend/main.py`, `backend/routers/`, `backend/tests/contracts/`
- Review: `backend/templates/`
- Review: `Practenture/`, `PractentureTests/`, `PractentureUITests/`
- Review: `android/app/src/main/`, `android/app/src/test/`

**Steps:**
1. Enumerate Administrator, Professor, Student, simulation, real-time, export, iOS, Android, deployment, backup, TLS, and monitoring requirements.
2. For each requirement record implementation path, automated test, runtime evidence, status, and blocker.
3. Mark stale May E2E reports as historical, not current release authorization.
4. Require exact evidence for every “verified” status.

**Acceptance:** No requirement is labeled complete solely because code exists or an old report says PASS.

## Task 3: Backend and API Contract Closure

**Objective:** Prove the backend is authoritative, tenant-safe, and correct across complete gameplay.

**Files:**
- Review/modify as findings require: `backend/routers/*.py`, `backend/database.py`, `backend/models.py`, `backend/simulation_engine.py`, `backend/ws_manager.py`
- Test: `backend/tests/contracts/`
- Test: `backend/tests/test_simulation_golden_parity.py`
- Create or extend a disposable cohort E2E under `backend/tests/contracts/`

**Steps:**
1. Compare live app OpenAPI inventory with `backend/tests/contracts/openapi_route_manifest.json`.
2. Prove unauthenticated, malformed-token, wrong-role, foreign-tenant, owning-tenant, and owner cases.
3. Prove rejected lifecycle mutations leave state unchanged.
4. Prove overlapping process-round requests advance exactly once and return stable `409` for overlap.
5. Prove processing is denied until every human team submits, with sorted missing-team evidence and unchanged state.
6. Run 20 students × 8 rounds against a new temporary SQLite database: 20 joins, 160 accepted complete decisions, exactly 8 authoritative process calls, 8 persisted result sets, final finished state, contiguous ranks, grade and leaderboard exports.
7. Verify WebSocket authentication and event contract without putting durable tokens in logs.
8. Run full isolated backend wrapper with warnings as errors.

**Acceptance:** Complete cohort assertions pass on a disposable DB; production-like database files and lockfiles remain unchanged.

## Task 4: Professor Web Workflow Closure

**Objective:** Verify the browser dashboard can execute the full Professor journey securely.

**Files:**
- Review/modify: `backend/templates/`
- Review/modify: Professor/dashboard routers under `backend/routers/`
- Test: `backend/tests/contracts/test_professor_workflow_contract.py`
- Test: `backend/tests/contracts/test_dashboard_exports_contract.py`
- Test: `backend/tests/contracts/test_classes_professor_contract.py`

**Steps:**
1. Verify login/enrollment/provider controls match supported backend methods.
2. Verify create-session DTO round-trips every configuration field.
3. Verify owning Professor can start, monitor, announce, process, end, export, and delete.
4. Verify foreign Professor denial for every mutation/read/export and unchanged state.
5. Verify friendly browser errors, CSRF/idempotency behavior where applicable, and no raw role/status leakage.
6. Verify web-created sessions converge in iOS/Android contract tests.

**Acceptance:** Full browser/API workflow has fresh automated contract evidence and representative rendered-state evidence.

## Task 5: Student Workflow Closure

**Objective:** Verify a Student can authenticate, join, decide, and observe results without local-authority shortcuts.

**Files:**
- Review/modify: student/session/decision/result routes and tests
- Review/modify: `Practenture/Views/Student/`, `Practenture/ViewModels/`
- Review/modify: Android Student Compose screens/repository/API DTOs

**Steps:**
1. Verify supported login methods, wrong-credential UX, rate-limit UX, logout, and restoration contracts.
2. Verify join identity is derived from the authenticated principal where required and session capacity/duplicate names fail atomically.
3. Verify complete modern decision serialization and rejection of stale aliases.
4. Verify results/leaderboard appear only from backend-confirmed state.
5. Verify announcements and final-state behavior.

**Acceptance:** The same backend session can be observed consistently by web, iOS contract tests, and Android contract tests.

## Task 6: iOS Qualification

**Objective:** Qualify iOS Professor and Student workflows on the current toolchain and available devices.

**Files:**
- Review/modify: `Practenture/Services/NetworkService.swift`
- Review/modify: `Practenture/Services/AuthManager.swift`
- Review/modify: `Practenture/ViewModels/`
- Review/modify: `Practenture/Views/Professor/`, `Practenture/Views/Student/`
- Test: `PractentureTests/`
- Test: `PractentureUITests/PractentureUITests.swift`

**Steps:**
1. Verify base URL and HTTPS configuration from built product, not assumptions.
2. Run clean simulator build and complete XCTest suite on available iPhone 17 Pro.
3. Scan both build and test logs for warning signals.
4. Run UI harness states for Professor and Student entry, loading, error, and main workflows.
5. Verify NetworkService request paths, auth injection, camelCase DTOs, retry policy, cache policy, and backend-confirmed state changes.
6. If device available: resolve destination structurally, uninstall stale app if needed, install, launch, verify process survival, and run opt-in production integration XCTest with disposable non-secret session data.

**Acceptance:** Build/test exit zero, warning scan zero, UI process survives, and backend contract paths are exercised. Apple/Google production provider acceptance is separately recorded if external interaction is required.

## Task 7: Android Qualification

**Objective:** Bring Android to backend-authoritative parity and verify it on an emulator.

**Files:**
- Review/modify: `android/app/src/main/java/com/practenture/android/MainActivity.kt`
- Review/modify: `android/app/src/main/java/com/practenture/android/network/`
- Review/modify: `android/app/src/main/java/com/practenture/android/data/PractentureRepository.kt`
- Test: `android/app/src/test/java/com/practenture/android/BackendAuthoritativeContractTest.kt`
- Review: `android/app/build.gradle.kts`, `android/README.md`

**Steps:**
1. Inventory Professor/Student screens and API operations against the matrix.
2. Add missing DTOs/repository methods/UI flows only where required by PRD.
3. Ensure every mutation waits for server confirmation and reconciles server state.
4. Run `testDebugUnitTest`, `assembleDebug`, warning scan, and packaging checks with the configured Android SDK.
5. Discover/start an available emulator, install APK, cold-launch, verify PID survival, and inspect bounded logcat for crashes/exceptions.
6. Produce release bundle only when signing configuration can be used without exposing secrets.
7. Record physical Google Credential Manager acceptance as external until package name, signing fingerprint, server client ID, and device interaction are verified together.

**Acceptance:** Automated contract/build gates and emulator startup/rendering pass. Compilation alone does not count as Google sign-in acceptance.

## Task 8: Aggregate Release Qualification

**Objective:** Produce one reproducible release decision after all implementation lanes stop.

**Steps:**
1. Quiescence barrier: agents complete; inspect `git status`, staged/unstaged/untracked diffs, imports, generated artifacts, and protected files.
2. Run focused suites, then aggregate backend, release contracts, simulation parity, iOS, Android, container, Compose, shell, and diff gates.
3. Run independent specification review, security/correctness review, and integration review. Reconcile every P0/P1.
4. If authorized, commit a new SHA and push it.
5. Require all exact-SHA GitHub Actions jobs to succeed with zero warnings/annotations; cancelled/superseded runs do not count.
6. If authorized, deploy only with `./ec2-deploy.sh deploy`.
7. Verify source/image/manifest SHA, public HTTPS, redirects/HSTS/CORS/cache, containers/restarts/logs, Alembic head, integrity/FKs, backup/restore evidence, rollback artifact, TLS dry run, timer enabled/active/next-run, and expiry monitor.

**Acceptance:** Release status is PASS only with all local gates, completed reviews, clean exact-SHA CI, and verified deployment evidence. Otherwise report BLOCKED with the exact missing gate.

## Task 9: Final Completion Report

**Objective:** Give Luis an honest end-to-end completion decision.

**File:**
- Create: `docs/qa/PRACTENTURE_RELEASE_DECISION_2026-08-01.md`

**Report sections:**
1. Exact SHA and environment.
2. Requirement-to-evidence matrix.
3. Commands and exact pass/fail/warning counts.
4. Production health and rollback evidence, if deployment was authorized.
5. External blockers: Apple/Google provider acceptance, physical Android, signing, TestFlight/App Store, Play Console, institutional acceptance.
6. Explicit statement of what is not claimed.

---

## Abort Gates

Stop release promotion—not local investigation—if any of these occurs:

- Unknown or secret-bearing worktree changes.
- Test contamination of persistent database or lockfiles.
- Any P0/P1 review finding.
- Backend, parity, iOS, Android, container, TLS, backup, or rollback gate fails.
- Exact-SHA CI is absent, cancelled, superseded, warning-bearing, or annotated.
- Source/image/manifest revisions disagree.
- Deployment health is indeterminate.
- Identity-provider configuration or signing provenance cannot be verified.
