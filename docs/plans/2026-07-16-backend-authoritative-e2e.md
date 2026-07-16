# Backend-Authoritative Cross-Platform E2E Integration Plan

**Date:** 2026-07-16  
**Scope:** FastAPI contract, iOS online classroom flow, future Android client, automated 20-student × 8-round API E2E, EC2 verification, and physical-iPhone validation.

## 1. Non-negotiable authority contract

For every online classroom session:

1. A student sends `POST /api/sessions/{code}/submit_decision` with `{round, teamId, decision}`.
2. `teamId` is the backend identifier returned by join (currently the unique team-name string), not the local iOS `UUID`.
3. Students only submit and poll. They never process or advance a round.
4. An authenticated/authorized professor invokes `POST /api/sessions/{code}/process_round` once after all required decisions exist.
5. That response is decoded as `{round, results}` and applied to client presentation state.
6. Clients poll `GET /api/sessions/{code}/status`, and fetch `/results` and `/leaderboard` as needed.
7. `/process_round` computes results **and advances backend `currentRound`**. No client may call `/advance` afterward.
8. Failure of an online backend call leaves the local round unchanged. There is no online fallback to `SimulationEngine.processRoundPure`.
9. `GameController` and the Swift simulation engine are permitted only for an explicitly offline Quick Demo/local session.
10. Completion displays at `min(currentRound, totalRounds)` and accepts the backend terminal states `finished` and `completed` until the contract is normalized.

## 2. Current iOS implementation checkpoints

Required paths and ownership:

- `DecisionInputViewModel`: construct the decision, optimistically persist it, and submit using `SimulationSession.backendTeamId`.
- `DecisionInputView`: route online success to dismiss/wait; invoke `GameController.processRoundAfterPlayerSubmit()` only for an offline session.
- `NetworkService`: keep `/process_round` as the one processing primitive. Mark `advanceRound` legacy/deprecated and remove it from the online repository protocol after call-site migration.
- `BackendState`: poll status at five-second intervals and expose backend round/state/team/submission counts.
- `SyncService`: preserve `backendTeamId` in both immediate and queued submissions. Queue records must survive relaunch and must not silently substitute a UUID.
- `SessionMonitorViewModel` and `RoundControlView`: for online sessions, gate on backend counts, call `/process_round` once, apply returned results, then refresh status; never generate local AI decisions or fall back to the local engine.
- `TeamDashboardView`: poll backend status/results; students must never expose a process/advance action.
- `GameController`: offline Quick Demo/local simulation only.
- `SimulationSession`: restore backend result history by matching backend team-name IDs to local teams; do not fabricate unavailable metric precision in UI.

### iOS automated tests to add

Use `URLProtocol` stubs or an injected `NetworkClient` actor. Do not depend on production EC2 for unit tests.

1. **Online submission identity:** request JSON contains join-returned `backendTeamId`, never local UUID.
2. **Student routing:** online submission produces one submit request and zero calls to local processing, `/process_round`, or `/advance`.
3. **Professor routing:** one tap produces exactly one `/process_round`; a rapid second tap is disabled while in flight.
4. **No double advance:** after process succeeds, allowed requests are status/results/leaderboard; assert zero `/advance` requests.
5. **No split authority:** process failure leaves `currentRound` and results unchanged and does not invoke `SimulationEngine`.
6. **Status application:** active and terminal states, counts, and capped final round update the Swift model.
7. **History restoration:** logout/relaunch/rejoin restores all eight rounds using team-name mapping.
8. **Offline isolation:** explicit Quick Demo still invokes local `GameController`; an online session never can.
9. **Retry semantics:** a submit retry is safe and visible; a process retry must follow the server’s documented idempotency behavior rather than blindly retrying.

## 3. Live OpenAPI contract gate

Run against local, staging, and EC2 before client E2E:

```bash
export BASE_URL='https://<staging-or-production-host>'
curl --fail --silent --show-error "$BASE_URL/openapi.json" -o /tmp/bizsim-openapi.json
jq -e '.paths["/api/sessions/{code}/submit_decision"].post' /tmp/bizsim-openapi.json
jq -e '.paths["/api/sessions/{code}/process_round"].post' /tmp/bizsim-openapi.json
jq -e '.paths["/api/sessions/{code}/status"].get' /tmp/bizsim-openapi.json
jq -e '.paths["/api/sessions/{code}/results"].get' /tmp/bizsim-openapi.json
jq -e '.paths["/api/sessions/{code}/leaderboard"].get' /tmp/bizsim-openapi.json
jq -e '.components.schemas.SubmitDecisionRequest' /tmp/bizsim-openapi.json
jq -e '.components.schemas.ProcessRoundResponse' /tmp/bizsim-openapi.json
```

Add a repository script that validates required paths, methods, security declarations, request fields, response fields, numeric types, enum values, and nullability. Store the fetched OpenAPI SHA-256 in every E2E report. Fail CI when generated Swift/Kotlin DTO assumptions drift from live OpenAPI.

**Security blocker to resolve before release:** OpenAPI and route tests must prove that `/process_round`, `/start`, `/end`, and `/advance` reject student tokens (403) and unauthenticated calls (401). Professor ownership of the session must also be enforced. A hidden client button is not authorization.

## 4. Android contract (no Android repository currently exists)

Create this module when an Android repository is available:

```text
app/src/main/java/.../network/
  BizSimApi.kt
  SessionDtos.kt
  DecisionDtos.kt
  ResultDtos.kt
app/src/test/java/.../network/
  OpenApiContractTest.kt
  BackendAuthoritativeRoundTest.kt
app/src/androidTest/java/.../
  LiveBackendSmokeTest.kt
```

Retrofit contract:

```kotlin
interface BizSimApi {
  @PUT("api/sessions/{code}/join") suspend fun join(...): JoinSessionResponse
  @POST("api/sessions/{code}/submit_decision") suspend fun submit(...): Response<Unit>
  @POST("api/sessions/{code}/process_round") suspend fun processRound(...): ProcessRoundResponse
  @GET("api/sessions/{code}/status") suspend fun status(...): SessionStatus
  @GET("api/sessions/{code}/results") suspend fun results(...): List<RoundResult>
  @GET("api/sessions/{code}/leaderboard") suspend fun leaderboard(...): LeaderboardResponse
}
```

Android rules:

- Persist the join-returned team ID; do not synthesize a UUID.
- Student UI submits and polls only. Professor UI owns process action.
- Repository exposes a single `processRound` command and no process-then-advance composite.
- Do not port simulation formulas into the online client.
- Use `kotlinx.serialization` with explicit backend names and strict enum/required-field tests.
- Use MockWebServer to assert method, path, auth header, body, one process call, zero advance calls, and status/result application.
- Add a staging instrumentation smoke controlled by `BIZSIMAI_BASE_URL`, professor token, and student token environment variables.

Android completion gate: generated/manual DTOs pass schema fixtures from the same OpenAPI SHA used by iOS and API E2E. Until a repository exists, this section is the handoff contract, not a claim that Android is implemented.

## 5. Automated 20-student × 8-round API E2E

Create `backend/e2e/test_backend_authoritative_flow.py` and run it only against an isolated database or disposable test namespace. Parameterize:

```bash
export BIZSIMAI_BASE_URL='http://127.0.0.1:8000'
export BIZSIMAI_PROFESSOR_EMAIL='e2e-professor@example.invalid'
export BIZSIMAI_PROFESSOR_PASSWORD='<secret>'
export BIZSIMAI_STUDENT_TOKEN='<test-token-if-required>'
python -m pytest -q backend/e2e/test_backend_authoritative_flow.py \
  --students=20 --rounds=8 --report=/tmp/bizsim-e2e-report.json
```

### Test lifecycle

1. Health/OpenAPI check; record URL, UTC timestamp, API version/commit, and OpenAPI hash.
2. Authenticate one professor and enough student identities for the deployed authorization model.
3. Create an eight-round session with `maxHumanTeams >= 20`; capture code.
4. Join 20 unique team names concurrently; assert 20 unique returned backend IDs.
5. For each round 1 through 8:
   - Poll status and assert `currentRound == expectedRound` and state is active.
   - Generate deterministic but differentiated decisions from `(seed, teamIndex, round)`.
   - Submit all 20 concurrently; require 2xx and record latency/status.
   - Assert status reports exactly 20 human submissions (define whether AI teams count in `totalTeams`/`teamsSubmitted`; make the contract consistent).
   - Submit one duplicate and assert the documented response (prefer 409); ensure it does not change counts.
   - Send two concurrent professor process requests to validate idempotency/locking. Exactly one may mutate the round; the other must return the documented conflict/idempotent response.
   - Assert results exist exactly once for the processed round and every expected team.
   - Assert status increments by exactly one; never by two.
   - Assert the prior round rejects new submissions and the next round accepts them.
6. After round 8, assert terminal state and displayed/current round never exceeds 8.
7. Fetch all results and leaderboard. Assert eight unique rounds, complete team coverage, finite numeric values, stable rank ordering/tie rule, and at least two differentiated scores for differentiated inputs.
8. Re-authenticate/rejoin a sample student and assert all result history is recoverable.
9. Export grades/leaderboard if in release scope and validate row counts and session code.
10. Delete the disposable session or record cleanup failure without hiding test results.

### Required report fields

- OpenAPI hash and server commit/image digest
- session code (redacted in public artifacts)
- exact request counts by method/path/status
- 160 expected human submissions (20 × 8)
- processing attempts vs successful mutations
- per-round status transitions and result counts
- p50/p95/max latency
- final leaderboard digest
- failed assertions and cleanup status

The suite fails on any unexplained 4xx/5xx, duplicate round result, missing team result, NaN/infinity, round skip, or `/advance` request.

## 6. Local and CI execution order

```bash
# Backend (in a venv; commands are implementation targets, not evidence from this audit)
cd backend
python -m py_compile main.py models.py simulation_engine.py routers/sessions.py routers/decisions.py
python -m pytest -q
uvicorn main:app --host 127.0.0.1 --port 8000

# In another shell
curl --fail http://127.0.0.1:8000/api/health
python -m pytest -q e2e/test_backend_authoritative_flow.py --students=20 --rounds=8

# iOS
cd ..
xcodebuild -project BizSimAI.xcodeproj -scheme BizSimAI \
  -destination 'platform=iOS Simulator,name=iPhone 16 Pro' build test
```

CI stages: schema gate → backend unit/integration → isolated 20×8 E2E → iOS build/unit tests → Android contract tests (when repository exists). Preserve JUnit, JSON E2E report, OpenAPI file/hash, and xcode result bundle.

## 7. EC2 deployment verification (do not deploy from this plan run)

Before deployment:

1. Require a reviewed commit, green local/CI gates, rollback image/tag, and database backup.
2. Record `git rev-parse HEAD`, dirty diff status, source SHA-256 values, image digest, migration version, and OpenAPI hash.
3. Confirm secrets come from EC2/SSM/environment, never source control.

Operator verification after the normal deployment procedure:

```bash
ssh <ec2-host> 'docker ps --format "table {{.Names}}\t{{.Image}}\t{{.Status}}"'
ssh <ec2-host> 'docker inspect <container> --format "{{.Image}} {{json .Config.Labels}}"'
curl --fail --silent --show-error "$BASE_URL/api/health" | jq .
curl --fail --silent --show-error "$BASE_URL/openapi.json" -o /tmp/ec2-openapi.json
sha256sum /tmp/ec2-openapi.json
```

Then:

- Run a disposable one-team/one-round production smoke.
- If capacity/rate limits allow, run the full 20×8 suite with production-test accounts and a unique prefix.
- Verify application/nginx logs contain one process mutation per round, no `/advance` calls from mobile clients, and no unexplained 401/403/409/5xx loops.
- Compare container image/source labels and OpenAPI hash with the approved artifact.
- Check CPU, memory, database locks, latency, and error rate during the cohort test.
- Remove disposable sessions/accounts according to retention policy.

Rollback immediately on schema mismatch, migration failure, authorization regression, round skip/double-process, corrupt results, or sustained error-rate increase. Restore the prior image and database backup per the deployment runbook, then rerun health and read-only schema checks.

## 8. Real-device iOS test matrix

Prerequisites: physical unlocked iPhone, trusted Mac, valid signing/provisioning, EC2 HTTPS URL in `BIZSIMAI_BACKEND_URL`, professor and student test accounts, and access to server/nginx logs.

Build/install evidence commands:

```bash
xcrun xctrace list devices
xcodebuild -project BizSimAI.xcodeproj -scheme BizSimAI \
  -destination 'platform=iOS,id=<DEVICE_UDID>' \
  -configuration Debug -derivedDataPath /tmp/BizSimAIDerivedData build
xcrun devicectl device install app --device <DEVICE_UDID> \
  /tmp/BizSimAIDerivedData/Build/Products/Debug-iphoneos/BizSimAI.app
xcrun devicectl device process launch --device <DEVICE_UDID> <bundle-id>
```

Execute and capture screenshots/screen recording plus server request IDs:

1. Professor creates a fresh two-round online session.
2. Physical iPhone student joins; verify the returned team identity persists after force-quit/relaunch.
3. Student submits round 1; dashboard remains on round 1 while waiting. Confirm one submit request and no process/advance request from the student.
4. Professor processes once. Confirm button disables while in flight.
5. Within the five-second polling window, iPhone shows round 2 and backend result values. Compare visible score/profit/cash with `/results` and leaderboard.
6. Toggle airplane mode before a submit, restore connectivity, and verify explicit retry/queue behavior without local round processing.
7. Force-quit/relaunch and verify round/result history restoration.
8. Repeat final round; verify terminal UI says round 2 of 2, not 3 of 2.
9. Attempt rapid professor double tap and verify one mutation.
10. Run an explicit offline Quick Demo and verify it still works with zero backend round requests.

Device gate fails on client crash, UUID team ID submission, local online results, missing restored history, double advancement, student-triggered processing, hidden network error, or mismatch with backend values.

## 9. Release evidence and owners

The release PR must link:

- backend and iOS commit SHAs (and Android SHA when available)
- reviewed OpenAPI JSON plus SHA-256
- backend pytest/JUnit output
- 20×8 JSON report proving 160 submissions and eight single-step transitions
- iOS unit/UI test result bundle and build log
- Android MockWebServer/live-contract output or explicit “repository unavailable” blocker
- EC2 image digest, health/schema output, smoke session evidence, and rollback point
- physical-device model/OS/app build, screenshots, request IDs, and server logs

Sign-off owners: backend contract/security, iOS, Android, QA/E2E, and deployment operator. No owner may waive the authority, security, or no-double-advance gates without a documented design change.
