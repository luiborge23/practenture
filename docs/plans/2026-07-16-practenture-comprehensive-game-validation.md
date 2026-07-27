# Practenture Comprehensive Game Validation Implementation Plan

> **For Paul:** Execute with `subagent-driven-development`. Each implementation task requires a failing test where applicable, implementation, focused verification, full regression, and independent spec/code-quality review.

**Goal:** Prove that every supported iOS decision, FastAPI contract, simulation formula, gameplay flow, persistence path, and production deployment behaves correctly before release.

**Architecture:** FastAPI is authoritative for online simulation and persistence. Swift may calculate rounds only in explicitly offline Quick Demo mode. Validation is layered: static contract inventory → executable request/response contracts → deterministic Swift/Python golden parity → mathematical invariants → local and production cohorts → simulator/device UX → deployment and rollback gates.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy/SQLite, pytest/httpx, Swift 6/XCTest/XCUITest, URLSession, Docker/nginx/AWS EC2.

---

## 1. Verified Baseline and Evidence Rules

### Current verified baseline (2026-07-16)

- Backend full regression: `146 passed, 3 skipped`.
- Focused formula/decision gate: `19 passed`.
- Formula invariants include 100 seeded full-field rounds, accounting identities, capacity/inventory conservation, bounds, channel sensitivity, AI strategies, and rebate-over-price safety.
- Local authoritative cohort test exists: `backend/test_backend.py::test_authoritative_20_students_complete_8_rounds`.
- iOS serialization tests exist for join and every game decision input.
- A production live-device test exists but must be run—not merely counted—as release evidence.
- Python now matches Swift's `$1` minimum before fractional price elasticity calculations.

### Evidence policy

A gate is complete only when its command output is captured. Source presence, test discovery, prior chat claims, and skipped tests do not count as execution evidence. Reports must contain timestamp, environment, command, exit status, pass/fail/skip counts, and artifact hashes where relevant. No unexplained skip, warning, flaky retry, or stale expectation is release-safe.

### Global release gates

1. **Contract:** every first-party HTTP route has auth, success, validation, not-found/conflict, and response-schema coverage; iOS DTOs match live OpenAPI.
2. **Formula:** deterministic Swift/Python values differ by at most `max(1e-9, abs(swift) * 0.001)` for every shared metric.
3. **Invariant:** accounting, market allocation, capacity, inventory, shares, debt/equity, bounds, and determinism hold across boundary and seeded randomized rounds.
4. **Authority:** online iOS never computes or double-advances a backend round.
5. **Cohort:** 20 students × 8 rounds yields exactly 160 accepted human submissions, differentiated outcomes, complete leaderboard, and valid exports.
6. **Persistence/concurrency:** restart, simultaneous submission, duplicate processing, and idempotency behavior are proven.
7. **Device:** professor and student flows pass on simulator and connected iPhone against the intended backend.
8. **Production identity:** deployed source/OpenAPI hashes match the tested artifact; health, logs, backup, monitoring, and rollback are verified.

---

## 2. Audit Summary and Gap Matrix

| Area | Existing evidence | Remaining release gap |
|---|---|---|
| Auth | Broad password/OAuth/MFA/refresh tests | Real Apple/Google provider validation, rate-limit persistence, skipped enterprise tests classification |
| Sessions | Core create/join/start/end/status tests | Complete OpenAPI matrix, malformed payloads, ownership/tenant isolation, delete/restart behavior |
| Decisions/results | Submit/process/results and 20×8 local test | Concurrent duplicate process, missing-team policy, exact result schema for every field |
| Classes | Routes exist | Route-level contract/security/error tests absent from discovered suite |
| Dashboard | Route exists | Wrapped `{"sessions": [...]}` schema and empty/stale-data cases need executable contract tests |
| Grades/exports | Routes exist | CSV/JSON schema, escaping, ordering, authorization, all-round completeness unproven |
| Professor admin | Routes exist | Codes, pre-create, redeem, password change, and audit endpoint matrix incomplete |
| AI endpoints | Fallback/mocked tests exist | Output schema and production-disabled behavior must remain non-blocking |
| Formula parity | Six Python formula tests and Swift runner infrastructure | Execute true golden Swift-vs-Python fixtures across all metrics and rounds |
| Invariants | Ten broad tests, 100 seeded rounds | Multi-team market conservation, multi-round cash/debt/share roll-forward, adversarial extrema |
| iOS contracts | Join/full decision serialization tests | Decode every backend response and compare DTO required/optional fields to OpenAPI |
| iOS resilience | Network/token/sync tests | Professor/student online round, reconnect, stale cache, 401/409/5xx UX and no-double-advance tests |
| UI | Launch/demo/navigation tests | Real authenticated professor/student online flows and result equality |
| Production | Prior EC2/device evidence | Fresh source identity, persistence, monitoring, backup/rollback drill, production cohort report |

---

## 3. Ordered Execution Tasks

### Task 1: Freeze the live API and iOS contract inventories

**Objective:** Generate machine-readable inventories so no endpoint or DTO can silently escape testing.

**Files:**
- Create: `backend/tests/contracts/test_openapi_inventory.py`
- Create: `backend/tests/contracts/openapi_route_manifest.json`
- Create: `shared/contracts/ios_backend_contract_manifest.json`
- Read: `backend/main.py`, `backend/routers/*.py`, `Practenture/Services/NetworkService.swift`

**Steps:**
1. Write a test that loads `app.openapi()` and normalizes method, path, security, request schema, success schema, and documented errors.
2. Write a failing assertion for any OpenAPI operation absent from `openapi_route_manifest.json`.
3. Inventory every `NetworkService` request and response DTO, including coding keys and optionality.
4. Add a failing assertion when an iOS-used operation is absent from OpenAPI or has a method/path mismatch.
5. Review intentional exclusions such as WebSocket operations in a separate manifest section.

**Verification:**
```bash
cd backend
.venv/bin/python -m pytest -q tests/contracts/test_openapi_inventory.py
```
Expected: every first-party HTTP operation is accounted for with zero undocumented exclusions.

### Task 2: Build exhaustive FastAPI request/response contract tests

**Objective:** Cover every HTTP route and response field, not only representative flows.

**Files:**
- Create: `backend/tests/contracts/conftest.py`
- Create: `backend/tests/contracts/test_auth_contracts.py`
- Create: `backend/tests/contracts/test_session_contracts.py`
- Create: `backend/tests/contracts/test_decision_result_contracts.py`
- Create: `backend/tests/contracts/test_class_dashboard_contracts.py`
- Create: `backend/tests/contracts/test_professor_grade_ai_contracts.py`

**Steps per operation:**
1. Assert unauthenticated behavior and each unauthorized role.
2. Assert minimum valid request and all documented response fields/types.
3. Assert full valid request and enum serialization.
4. Parameterize missing required fields, nulls, wrong types, invalid enum values, negatives, boundaries, and unknown fields according to policy.
5. Assert not-found, duplicate/conflict, wrong-round, wrong-owner, and cross-tenant behavior.
6. Validate actual JSON against the exact OpenAPI response schema.
7. Assert dashboard returns `{"sessions": [...]}` and never a bare array.
8. Assert process-round result includes every `RoundResult` field and all demand subfields.

**Verification:**
```bash
cd backend
.venv/bin/python -m pytest -q tests/contracts
```
Expected: zero first-party operations without at least one success and one failure-path contract test.

### Task 3: Enforce iOS ↔ OpenAPI DTO parity

**Objective:** Prove Swift encoding/decoding matches FastAPI aliases, required fields, enums, and nesting.

**Files:**
- Modify: `PractentureTests/DecisionContractSerializationTests.swift`
- Create: `PractentureTests/BackendResponseContractTests.swift`
- Create: `shared/contracts/fixtures/*.json`
- Test: `backend/tests/contracts/test_ios_fixture_acceptance.py`

**Steps:**
1. Export canonical FastAPI fixtures for login, register, session, join, status, teams, submit, process, result, leaderboard, announcement, dashboard, and grade/export metadata.
2. Decode every response fixture in XCTest and assert all semantically important values.
3. Encode every iOS request and validate it through the corresponding Pydantic model/API.
4. Test every enum raw value and unknown-value behavior.
5. Test missing optional fields and reject missing required fields.
6. Ensure decision fields use camelCase and top-level submit shape is `{round, teamId, decision}`.

**Verification:** run backend fixture tests and the `PractentureTests` scheme; expected zero encode/decode mismatch.

### Task 4: Complete deterministic Swift/Python golden parity

**Objective:** Compare the real Swift and Python engines, not duplicated Python expectations.

**Files:**
- Existing: `backend/parity/SwiftGoldenRunner.swift`
- Existing/modify: `backend/test_simulation_formula_parity.py`
- Create: `backend/parity/fixtures/*.json`
- Create: `backend/parity/run_parity.py`
- Create: `backend/parity/reports/latest.json`

**Fixture matrix:**
- One-team baseline and zero production.
- Three-team low/baseline/high price competition.
- Standard/superior materials; styling/model/TQM/training/best-practice caps.
- Private-label ties, bid order, max-units limits, and capacity exhaustion.
- FBA/FBM Amazon attractiveness and fees.
- Rebates below/equal/above wholesale price; free-shipping boundaries.
- Inventory shortage/surplus and rejection-rate floor.
- Loans, interest tiers, dividends, issuance, buybacks, dilution, and share floor.
- Market types and rounds 1, 5, 10, 20; multi-round ratcheting/state.
- Every AI strategy with stable seed handling.

**Compared values:** all channel demand/sales, S/Q, rejection, production/workforce/storage/marketing/Amazon costs, revenue, total costs, profit, cash, inventory, equity, debt, shares, EPS, ROE, stock, satisfaction, reputation, image, awareness, credit, component scores, and total score.

**Verification:**
```bash
cd backend
.venv/bin/python parity/run_parity.py --report parity/reports/latest.json
.venv/bin/python -m pytest -q test_simulation_formula_parity.py
```
Expected: every metric within 0.1%; report records maximum absolute/relative error by metric.

### Task 5: Extend multi-team and multi-round invariants

**Objective:** Close conservation gaps not covered by single-team randomized rounds.

**Files:**
- Modify: `backend/test_simulation_invariants.py`

**Steps:**
1. Add 2, 5, 20, and 50-team seeded rounds.
2. Assert each channel's allocated demand equals its fixed market pool within rounding and sales never exceed available inventory.
3. Assert total market share sums to one when sales are nonzero.
4. Roll state through 20 rounds and independently reconcile cash, equity, debt, shares, cumulative profit/TQM, and inventory.
5. Test zero/near-zero prices, extreme valid budgets, no production, maximum overtime, ties, all-zero attractiveness inputs, and insolvency.
6. Verify same seed/input/state produces byte-equivalent normalized results.

**Verification:** focused invariants plus full backend regression.

### Task 6: Harden authoritative process-round concurrency and persistence

**Objective:** Ensure a round is processed exactly once and survives restart safely.

**Files:**
- Create: `backend/tests/test_round_concurrency.py`
- Create: `backend/tests/test_persistence_restart.py`
- Modify if needed: `backend/routers/decisions.py`, database models/migrations

**Steps:**
1. Fire concurrent duplicate submissions for the same team/round; assert one accepted record and deterministic 409/idempotent response policy.
2. Fire concurrent `process_round`; assert one result set and one round increment.
3. Restart the application/database connection between submit/process/read steps.
4. Verify results, leaderboard, session state, and exports survive restart.
5. Inject transaction failure and verify no partially advanced round.
6. Verify SQLite deployment configuration serializes writes safely under expected classroom load.

**Verification:** repeat concurrency tests at least 20 times with zero flakes.

### Task 7: Run local cohort and gameplay differentiation matrix

**Objective:** Prove realistic classroom gameplay, not merely API availability.

**Files:**
- Modify: `backend/test_backend.py`
- Create: `backend/e2e/test_cohort_matrix.py`
- Create: `backend/e2e/reports/`

**Scenarios:**
- 20 humans × 8 rounds × 3 AI teams = exactly 160 accepted human submissions.
- Balanced, low-cost, premium, quality, and aggressive strategies.
- Late/missing submissions according to configured policy.
- Duplicate submissions and wrong-round attempts.
- Same-seed determinism and different-seed variation.
- Final leaderboard includes all teams with differentiated scores.
- Grade and leaderboard exports include every required row/round and correctly escaped names.

**Verification:** save timestamped JSON with request counts, status histogram, per-round metrics, rankings, and all gate assertions.

### Task 8: Prove iOS online authority and resilience on simulator

**Objective:** Ensure online mode submits and renders backend results without local computation or stale state.

**Files:**
- Modify/create tests under `PractentureTests/`
- Modify/create UI tests under `PractentureUITests/`
- Trace: `DecisionInputViewModel.swift`, `NetworkService.swift`, `BackendState.swift`, `SyncService.swift`, `GameController.swift`, `RoundControlView.swift`

**Steps:**
1. Add a URLProtocol-backed professor create/start/process flow.
2. Add student join/submit/status/results/leaderboard flow.
3. Assert online paths never call `processRoundPure()` and never call a second advance.
4. Test reconnect queue ordering and duplicate prevention.
5. Test 401 refresh, 403, 404, 409, 422, 500, timeout, malformed JSON, and offline recovery UX.
6. Disable URL cache and verify stale empty session/results responses cannot recur.
7. Run all first-party unit/UI tests on a clean simulator installation.

**Verification:** `xcodebuild test` result bundle with zero unexpected skips/failures and screenshots for critical UI states.

### Task 9: Deploy a source-identical backend and verify production

**Objective:** Prove EC2 runs the exact artifact validated locally.

**Files/artifacts:**
- Local source-hash manifest
- EC2 backup manifest
- Docker image digest
- Live OpenAPI snapshot
- nginx/application log excerpts

**Steps:**
1. Record Git status/diff and SHA-256 hashes of backend source, requirements, Dockerfile, and migrations.
2. Back up `/data/practenture.db` and verify backup readability.
3. Build/restart the deployment; confirm one worker/four threads policy for SQLite.
4. Read source hashes from inside the running container and compare to local.
5. Verify health and compare normalized live OpenAPI to local OpenAPI.
6. Run isolated production smoke and then 20×8 cohort with unique test identities.
7. Restart container and verify persistence.
8. Inspect nginx/application logs for 4xx/5xx spikes, tracebacks, duplicate processing, and latency.
9. Exercise rollback to the prior image/config or conduct a documented dry run with exact commands.

**Verification:** no source/OpenAPI mismatch, no unexplained 5xx, successful persistence, valid backup, and executable rollback.

### Task 10: Run clean-install real-iPhone E2E

**Objective:** Validate actual device networking, provisioning, authentication, caching, and authoritative round behavior.

**Steps:**
1. Confirm device connection/unlock and paid-team provisioning.
2. Uninstall the old app before install to clear cache/keychain contamination.
3. Build/install/launch with EC2 base URL verified in `Debug.xcconfig`, `Info.plist`, and `NetworkService.swift` fallback.
4. Run professor login/create/start/process and student login/join/submit/results/leaderboard flows.
5. Verify displayed metrics exactly equal backend result JSON.
6. Disable/re-enable network during submission and verify reconnect without duplicate decisions.
7. Verify nginx logs show one submit, one process, expected reads, and one round increment.
8. Test expired-token refresh and a user-facing server error.

**Verification:** device test output, session code, backend JSON, matching screenshots, and correlated server log timestamps.

### Task 11: Validate operations, security, exports, and rollback readiness

**Objective:** Close non-gameplay release risks.

**Checks:**
- Tenant/role isolation for every mutating/read endpoint.
- Secrets absent from source/logs and production uses non-default credentials.
- JWT expiry/refresh/revocation behavior and OAuth audience validation.
- Database backup schedule, restore test, disk capacity, and corruption response.
- Health/readiness, structured logs, error alerting, latency/error-rate thresholds.
- Export authorization, escaping/formula-injection prevention, stable ordering, and completeness.
- CORS/nginx/body-size/timeouts/TLS behavior.
- Documented deploy and rollback commands with responsible operator and expected duration.

### Task 12: Independent final reviews and release decision

**Objective:** Prevent implementation authors from self-certifying release readiness.

**Dispatch separate reviews for:**
1. Contract/OpenAPI completeness.
2. Swift/Python formula parity and gameplay quality.
3. Accounting/conservation/property-test strength.
4. iOS authority, state, cache, reconnect, and error UX.
5. Auth/tenant/security and export safety.
6. Deployment identity, persistence, observability, and rollback.

**Final report must contain:**
- Git commit and clean/dirty status.
- Exact commands and pass/fail/skip counts.
- OpenAPI operation coverage percentage.
- Maximum parity error by metric.
- Invariant seed/team/round coverage.
- Local and production cohort reports.
- Simulator/device model, OS, test results, and session code.
- Deployed image digest and source hash comparison.
- Known limitations with owner/severity.
- Explicit `GO`, `NO-GO`, or `GO WITH ACCEPTED RISKS` decision.

---

## 4. Mandatory Regression Commands

```bash
cd backend
.venv/bin/python -m py_compile models.py simulation_engine.py main.py routers/*.py
.venv/bin/python -m pytest -q --disable-warnings
```

```bash
xcodebuild -project Practenture.xcodeproj \
  -scheme Practenture \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' \
  test
```

Release expectation: all first-party tests pass; every skip is listed with a reason and owner. Third-party package tests are not part of the first-party count.

## 5. Stop Conditions

Stop release and classify as `NO-GO` for any of the following:

- Swift/Python metric variance exceeds 0.1% without an approved semantic exception.
- Any valid decision can produce NaN, infinity, complex values, negative inventory, or duplicate round advancement.
- Production OpenAPI/source differs from the tested artifact.
- Cohort loses/duplicates submissions or omits teams/rounds from results/exports.
- Online iOS computes a local round or displays values different from backend results.
- Cross-tenant data access, auth bypass, persistent 5xx, unverified backup, or non-executable rollback.
