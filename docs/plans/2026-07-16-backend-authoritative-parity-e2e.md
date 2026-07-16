# Backend-Authoritative Simulation Parity and E2E Plan

> **For Paul:** Execute with subagent-driven-development. Every implementation task requires spec review, code-quality review, and real test output before completion.

**Goal:** Make the Python FastAPI simulation engine mathematically equivalent to the iOS Swift engine, make it authoritative for online iOS and future Android clients, deploy it to EC2, and prove the complete flow through deterministic parity, API cohort, production, and real-device tests.

**Architecture:** FastAPI owns all online round computation. iOS and Android submit decisions and consume backend results; they never independently advance or recompute an online round. The existing Swift engine remains only for an explicitly labeled offline Quick Demo. Shared JSON fixtures define the decision/result contract and parity expectations.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest, Swift 6/SwiftUI, URLSession, Android Kotlin/Retrofit contract, Docker/nginx/EC2.

---

## Global Completion Gates

1. **Formula gate:** deterministic Swift and Python outputs differ by no more than 0.1% for every compared metric.
2. **Contract gate:** modern iOS payloads and legacy production payloads both validate; live OpenAPI contains the modern fields.
3. **Authority gate:** online iOS code performs submit → backend process_round → apply backend result/status, with no local processRoundPure call and no double advance.
4. **Cohort gate:** automated 20-student × 8-round API simulation completes 160 submissions with differentiated results and valid leaderboard/export.
5. **Production gate:** EC2 health, OpenAPI, container source hash, and production E2E all match the tested local artifact.
6. **Device gate:** connected iPhone completes an online round against EC2 with backend/nginx evidence and no crash.
7. **Android gate:** executable Kotlin contract tests pass against the live OpenAPI/API before an Android UI is considered integrated.

## Task 1: Correct Total Market Demand

**Files:**
- Modify: `backend/simulation_engine.py`
- Test: `backend/tests/test_engine_parity.py`
- Source: `BizSimAI/Engine/SimulationEngine.swift:122-132,586-596`

**Implementation:**
- Compute `demandGrowth = min(2.0, 1.0 + 0.05 * round_num)`.
- Compute `totalDemand = baseMarketDemand * marketType.demandMultiplier * demandGrowth * noiseFactor(marketType.volatility)`.
- Generate market noise exactly once before channel allocation.
- Preserve fixed channel splits: wholesale 0.50, internet 0.15, private label 0.15, Amazon 0.20.
- Do not derive market size from average attractiveness; attractiveness only allocates each channel among competitors.

**Verification:**
```bash
cd backend
.venv/bin/python -m pytest -q tests/test_engine_parity.py -k 'demand or channel'
```
Expected: demand-growth, multiplier, noise-sequence, and channel-sum tests pass.

## Task 2: Implement Awareness and Complete Result Contract

**Files:**
- Modify: `backend/models.py`
- Modify: `backend/simulation_engine.py`
- Test: `backend/tests/test_engine_parity.py`

**Implementation:**
- Add `awarenessScore` to `RoundResult`.
- Match Swift exactly: `min(1, (advertisingBudget + socialMediaBudget) / 25000)`.
- Ensure the social-media scalar uses the same semantic value as Swift; channel budgets remain separate demand/image inputs.
- Include awareness in serialization, result persistence, exports where applicable, and OpenAPI.

**Verification:** focused pytest plus OpenAPI schema assertion.

## Task 3: Backward-Compatible PlayerDecision Translation

**Files:**
- Modify: `backend/models.py`
- Test: `backend/tests/test_player_decision_contract.py`

**Implementation:**
- Use a Pydantic `model_validator(mode="before")` to translate legacy payloads without changing modern serialization.
- Map `numModels` to `modelsOffered` only when the modern field is absent.
- Map numeric legacy `materialsQuality` into the supported enum using documented thresholds.
- Map supported legacy `celebrityType` values into `CelebrityEndorsement`.
- Translate legacy `socialMediaBudget` object into the modern aggregate plus channel values without double counting.
- Preserve accepted legacy fields (`rdInvestment`, `marketingInvestment`, `trainingBudget`, `productionQuantity`, `overtimePercent`, `internetPromotion`) while documenting whether they are translated or ignored.
- Modern values always win when both modern and legacy keys are present.

**Verification:** modern iOS fixture, legacy `test_backend.py` fixture, malformed enum rejection, and serialization round-trip.

## Task 4: Golden Swift/Python Parity Harness

**Files:**
- Create: `shared/fixtures/parity/*.json`
- Create: `backend/tests/test_swift_python_parity.py`
- Create: `BizSimAIParityTests/SimulationParityTests.swift` or an executable Swift fixture runner that does not modify `project.pbxproj` unsafely.

**Fixtures:**
- One team baseline with noise disabled.
- Three teams with price competition.
- Superior quality/TQM/training ratchet across three rounds.
- Private-label bid ordering and capacity exhaustion.
- FBA versus FBM Amazon fees and attractiveness.
- Debt/credit/interest tiers.
- Buyback, issuance, dividends, and dilution.
- Inventory shortage and customer-satisfaction/reputation EMA.
- Market types and demand growth at rounds 1, 5, 10, and 20.

**Compared metrics:** channel demand/sales, S/Q, rejection rate, production cost, workforce cost, Amazon fees, revenue, costs, profit, cash, inventory, equity, debt, shares, EPS, ROE, stock price, satisfaction, reputation, image, awareness, credit, scorecard components, and total score.

**Tolerance:** `abs(py-swift) <= max(1e-9, abs(swift)*0.001)` for each metric. RNG-sensitive tests must use an identical documented sequence or disable noise.

## Task 5: Backend-Authoritative iOS Online Flow

**Files to trace/modify:**
- `BizSimAI/ViewModels/DecisionInputViewModel.swift`
- `BizSimAI/Services/NetworkService.swift`
- `BizSimAI/Services/BackendState.swift`
- `BizSimAI/Services/SyncService.swift`
- `BizSimAI/Engine/GameController.swift`
- `BizSimAI/Views/Professor/RoundControlView.swift`

**Online flow:**
1. Submit `{round, teamId, decision}`.
2. Professor/authorized coordinator calls `POST /api/sessions/{code}/process_round` once.
3. Decode `ProcessRoundResponseBackend` from that POST.
4. Fetch/apply backend status if necessary.
5. Apply backend results to local presentation state.
6. Never call local `processRoundPure()` for an online session.
7. Never call `/advance` after `/process_round`; the backend already advances.

**Offline flow:** Quick Demo may use `processRoundPure()` only behind an explicit offline/local mode check. Add tests that prove online mode cannot enter the local path.

**Verification:** Swift build, mocked URLProtocol integration tests, and real-device/nginx evidence.

## Task 6: Android API Contract

No Android source exists in this repository, so completion means producing an executable integration module or handing an exact contract to the Android repository.

**Create in Android repository when provided:**
- Kotlin DTOs matching live OpenAPI.
- Retrofit endpoints for login, join, submit decision, process round, status, results, and leaderboard.
- Enum serialization tests.
- MockWebServer test for a full submit/process/results cycle.
- Live staging smoke test controlled by environment variables.

**Rule:** Android contains no simulation formulas. It submits decisions and renders backend results only.

## Task 7: Automated Local API E2E

**Files:**
- Create/update: `backend/e2e/test_backend_authoritative_flow.py`
- Create: `backend/e2e/generate_decisions.py`
- Create: `backend/e2e/README.md`

**Scenarios:**
- Contract smoke: professor creates session, student joins, submits, round processes, results/status agree.
- 20 students, unique teams, 3 AI competitors, 8 rounds: exactly 160 human submissions.
- Duplicate submission returns 409.
- Missing decision excludes human team or follows documented policy; AI decisions auto-generate.
- Round progression is exactly 1→2→…→8→finished with no double advance.
- Leaderboard contains every human and AI team with differentiated scores.
- Grade export contains all expected teams/rounds.
- Re-running with same seed and decisions is deterministic.

**Verification:** save a timestamped JSON report containing request counts, pass/fail gates, round metrics, and final rankings.

## Task 8: Full Local Regression

Run:
```bash
cd backend
.venv/bin/python -m py_compile models.py simulation_engine.py main.py routers/decisions.py
.venv/bin/python -m pytest -q
```

Classify failures as current-contract defects or stale expectations. Update stale tests only when the new expected behavior is explicitly documented (automatic AI team count, 409 duplicates, authenticated status endpoint). Zero unexplained failures are allowed.

## Task 9: EC2 Deployment and Production Verification

1. Back up `/data/bizsim.db`.
2. Record local source hashes and Git diff.
3. Sync backend to `/home/ec2-user/bizsimai/backend/`.
4. Remove stale Docker image if needed; rebuild and restart.
5. Verify container source hashes equal local hashes.
6. Verify `/api/health`.
7. Verify live OpenAPI includes modern SessionConfiguration, PlayerDecision, RoundResult, and awareness fields.
8. Run a separate production smoke session.
9. Run production 20×8 E2E if test accounts and rate limits permit.
10. Verify nginx logs show live iOS/API requests and no repeated 4xx/5xx failures.

**Rollback:** restore previous image/source and DB backup if any production gate fails.

## Task 10: Real-Device iOS E2E

1. Confirm connected, unlocked iPhone.
2. Build for the real device with provisioning.
3. Uninstall old app if cached responses/keychain state could invalidate testing.
4. Install and launch.
5. Professor creates a fresh session.
6. Student joins with a unique team name.
7. Submit a decision and process one round.
8. Confirm the displayed result exactly matches backend `/results` and leaderboard.
9. Confirm nginx logs show submit/process/status/results.
10. Confirm there is one backend round increment and no local duplicate computation.
11. Complete remaining rounds or run a shorter dedicated E2E configuration.

## Task 11: Final Integration Review

Dispatch separate reviewers for:
- Formula/spec compliance.
- Python quality and test coverage.
- iOS authority/double-advance risks.
- API security and backward compatibility.
- Deployment reproducibility.

Final report must include exact commits/hashes, test commands and counts, parity maximum error by metric, production session code used for testing, Android integration status, known limitations, and rollback instructions.
