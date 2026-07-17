# RCA Part 2: Round Lifecycle State Machine + Polling/State Sync Analysis

## Overview

This report traces the complete round lifecycle from both student and professor perspectives across the BizSimAI iOS app, identifying every point where iOS local state diverges from backend state. The analysis covers `SimulationSession.swift`, `TeamDashboardView.swift`, `BackendState.swift`, `RoundControlView.swift`, `PerformanceHistoryView.swift`, and `PerformanceHistoryViewModel.swift`, with supporting context from `SessionMonitorViewModel.swift`, `DecisionInputViewModel.swift`, and `NetworkService.swift`.

---

## 1. State Tracking: Two Parallel State Machines

### 1.1 Local State Machine (`SimulationSession` / `SessionState`)

**`SessionState` enum** (SimulationModels.swift:1187):
```
waitingForPlayers → inProgress → roundProcessing → completed
```

**`SimulationSession` stored properties:**
- `currentRound: Int` — 1-based, starts at 0 ("not yet started")
- `stateRaw: String` — maps to `SessionState`
- `isPaused: Bool` — local pause flag
- `currentRoundDecisionsData` — decisions for current round, keyed by team UUID
- `previousRoundDecisionsData` — last round's decisions (for AI context)
- `roundResultsData` — all round results, keyed by team UUID → round → `RoundResult`
- `teamsData` — all teams with `hasSubmittedDecisions` per team
- `lastSyncedAt: Date?` — timestamp of last backend sync (set but **never read**)

### 1.2 Backend State Machine (`BackendState` + `SessionStatusBackend`)

**`SessionBackendState` enum** (BackendState.swift:9):
```
disconnected → creating → active → roundProcessing → completed
```

**`BackendState.shared` singleton tracks:**
- `sessionCode: String?`
- `isOnline: Bool`
- `currentRound: Int`
- `sessionState: SessionBackendState`
- `teamCount: Int`
- `submittedCount: Int`

**`SessionStatusBackend` (NetworkService.swift:762)** — the authoritative backend response:
- `state: String` — "creating", "active", "completed", "finished"
- `currentRound: Int`
- `teamsSubmitted: Int`
- `totalTeams: Int`
- `humanTeams: Int`

### 1.3 Critical Observation: Mismatched State Enums

| Local `SessionState` | Backend state string | `SessionBackendState` |
|---|---|---|
| `waitingForPlayers` | "creating" | `.creating` |
| `inProgress` | "active" | `.active` |
| `roundProcessing` | *(no equivalent)* | `.roundProcessing` |
| `completed` | "completed"/"finished" | `.completed` |
| *(no equivalent)* | *(no equivalent)* | `.disconnected` |

The local enum has `roundProcessing` which the backend never returns. The backend has no "paused" concept — `isPaused` is purely local.

---

## 2. Student Round Lifecycle

### 2.1 Student Submits Decisions

**Entry point:** `DecisionInputView.submitDecisions()` (line 100)
- Calls `viewModel.submitDecisions(to: session, teamId: teamId)`
- `DecisionInputViewModel.submitDecisions()` (line 438):

**Backend session path:**
1. Validates `backendTeamId` is non-empty (from `session.backendTeamId`)
2. Constructs `PlayerDecision` with `round: session.currentRound`
3. Calls `SyncService.shared.syncDecisionSubmission(...)` → `NetworkService.submitDecision(...)` → `POST /api/sessions/{code}/submit_decision`
4. **On success:** calls `session.submitDecision(decision)` locally (line 536) — this mirrors the decision into local state for UI feedback only
5. Sets `submittedViaBackend = true`, returns `true`
6. `DecisionInputView` does **NOT** call `gameController.processRoundAfterPlayerSubmit()` for backend sessions (line 112-114)

**Offline/demo path:**
1. Calls `session.submitDecision(decision)` directly
2. `DecisionInputView` calls `appState.gameController?.processRoundAfterPlayerSubmit()` (line 113)
3. Local engine runs the full simulation

### 2.2 `SimulationSession.submitDecision()` (line 491)

```swift
func submitDecision(_ decision: PlayerDecision) -> Bool {
    guard !isPaused else { return false }
    currentRoundDecisions[decision.teamId] = decision
    if let index = teams.firstIndex(where: { $0.id == decision.teamId }) {
        teams[index].hasSubmittedDecisions = true
    }
    return isRoundComplete()
}
```

**Divergence point:** This sets `hasSubmittedDecisions = true` locally. For backend sessions, the backend tracks submission status via its own `teamsSubmitted` counter. The local `hasSubmittedDecisions` flag and the backend `teamsSubmitted` count are independent — neither references the other.

### 2.3 Student Polling for Results

**`TeamDashboardView`** (line 97-121):

`.onAppear`:
- Sets `lastProcessedRound = session?.currentRound ?? 0`
- Syncs `BackendState.shared` values to local `@State` variables (`liveTeamCount`, `liveSubmittedCount`, `liveSessionState`)
- If backend session: calls `fetchBackendResults()`

`.onReceive(Timer.publish(every: 10, ...))`:
- If backend session: calls `fetchBackendResults()` every 10 seconds

**`fetchBackendResults()` (line 450):**
```swift
let backendResults = try await NetworkService.shared.getResults(code: session.sessionCode)
if !backendResults.isEmpty {
    let maxBackendRound = backendResults.keys.max() ?? 0
    if maxBackendRound >= session.currentRound {
        await MainActor.run {
            session.restoreResultsFromBackend(backendResults)
            if session.currentRound > lastProcessedRound {
                lastProcessedRound = session.currentRound
                showResults = true
            }
        }
    }
}
```

Key behaviors:
- Fetches ALL round results from backend (`GET /api/sessions/{code}/results`)
- Only restores if `maxBackendRound >= session.currentRound` (prevents stale overwrites)
- Calls `session.restoreResultsFromBackend(backendResults)` which:
  1. Maps backend team names → local team UUIDs
  2. Converts `RoundResultBackend` → `RoundResult` (with **fabricated revenue splits** — see §5.2)
  3. Calls `recordResult()` for each
  4. Calls `updateRankings()`
  5. **Sets `currentRound = maxRound + 1`** (line 816) — advances the local round counter
  6. **Resets `hasSubmittedDecisions = false`** for the player team (line 819)

**Divergence:** `restoreResultsFromBackend` always sets `currentRound = maxRound + 1`, even if the backend hasn't advanced yet. It infers "next round" from the presence of results rather than from the backend's actual `currentRound` field.

### 2.4 Student UI: Dual-Sourced Round Display

`TeamDashboardView` has **two different round values:**

1. `currentRound` (line 30): `max(session?.currentRound ?? 1, 1)` — from local `SimulationSession`
2. `backendCurrentRound` (line 52-54): `BackendState.shared.currentRound > 0 ? BackendState.shared.currentRound : currentRound` — from `BackendState` singleton, falls back to local

The round header (line 235) uses `backendCurrentRound`. The progress dots (line 245) also use `backendCurrentRound`. But the "Make Decisions" button text (line 396) uses local `currentRound`. And `canSubmitDecisions` (line 64-67) checks local `team.hasSubmittedDecisions`.

**Divergence:** If `BackendState.shared.currentRound` is updated by its own 5-second poll but `session.currentRound` hasn't been updated by `fetchBackendResults()` yet, the header shows one round number while the action button shows another.

### 2.5 Student UI: Dual-Sourced Submission Status

- `canSubmitDecisions` (line 64-67): checks `playerTeam.hasSubmittedDecisions` — local `SimulationSession` flag
- `backendSubmittedCount` (line 60-62): reads `BackendState.shared.submittedCount`
- `liveSubmittedCount` (line 23): `@State` copy made once in `onAppear`, never updated after

**Divergence:** `liveSubmittedCount` is a snapshot taken at `onAppear` and never synced again. `BackendState.shared.submittedCount` updates every 5s via `BackendState.pollStatus()`. The `liveSubmittedCount` local copy goes stale immediately.

---

## 3. Professor Round Lifecycle

### 3.1 Professor Polls for Status

**Two independent polling systems exist for the professor:**

**System A: `BackendState.shared` (BackendState.swift)**
- Singleton, shared across the entire app
- Polls every **5 seconds** via `pollTask`
- Calls `NetworkService.shared.getSessionStatus(code:)`
- Updates: `currentRound`, `teamCount`, `submittedCount`, `sessionState`
- Started by `connect(sessionCode:)`, stopped by `disconnect()`
- On error: sets `sessionState = .disconnected` (does NOT set `isOnline = false`)

**System B: `RoundControlView.loadFromBackend()` (line 104)**
- View-local `@State` variables
- Polls every **5 seconds** via `Timer.publish`
- Also calls `NetworkService.shared.getSessionStatus(code:)`
- Updates: `currentRound`, `backendSubmittedCount`, `backendTeamCount`, `backendHumanTeams`
- **Also writes directly to `session.currentRound`** (line 113) — mutates the shared `SimulationSession`
- On error: sets `processingError` string

**System C: `SessionMonitorViewModel.pollBackendStatus()` (line 232)**
- View-model-local
- Polls every **10 seconds** via `Timer`
- Also calls `NetworkService.shared.getSessionStatus(code:)`
- Updates: `backendSubmittedCount`, `backendTeamCount`, `backendTeamStatus`, `session.currentRound`, `session.state`
- **Also mutates `session.state` directly** (line 242-246)

**Divergence:** Three independent pollers hit the same backend endpoint on different intervals (5s, 5s, 10s), each writing to overlapping but different state. `BackendState.shared.currentRound`, `RoundControlView.currentRound` (`@State`), `SessionMonitorViewModel.session.currentRound`, and `SimulationSession.currentRound` can all disagree at any moment.

### 3.2 Professor Advances Round

**`RoundControlView.advanceRound()` (line 338):**

Backend path → calls `processBackendRound()`:

```swift
private func processBackendRound() async {
    guard let session = appState.activeSession, allSubmitted, !isProcessing else { return }
    isProcessing = true
    let processedRound = session.currentRound
    let results = try await NetworkService.shared.processRound(code: session.sessionCode)
    session.restoreResultsFromBackend([processedRound: results])
    await loadFromBackend()
    isProcessing = false
}
```

This:
1. Sends `POST /api/sessions/{code}/process_round` — backend computes results AND advances `currentRound`
2. Hydrates results via `restoreResultsFromBackend([processedRound: results])`
3. Reloads from backend via `loadFromBackend()` — fetches `getSessionStatus` and writes `session.currentRound`

**`SessionMonitorViewModel.processRoundWithBackend()` (line 260)** does the same:
1. Calls `NetworkService.shared.processRound(code:)`
2. Calls `session.restoreResultsFromBackend([processedRound: results])`
3. Calls `pollBackendStatus()` — fetches status, updates `session.currentRound` and `session.state`
4. Calls `refreshTeamStatuses()`

**Divergence:** Both professor advance paths call `restoreResultsFromBackend`, which sets `currentRound = maxRound + 1`. Then both call a status poll that sets `session.currentRound = min(status.currentRound, totalRounds)`. If the backend hasn't fully committed the round advance by the time the status poll returns, `session.currentRound` gets overwritten with a stale value.

### 3.3 Professor `allSubmitted` Gate

`RoundControlView.allSubmitted` (line 39-42):
```swift
if isBackendSession { return backendHumanTeams > 0 && backendSubmittedCount >= backendHumanTeams }
return teamSubmissions.allSatisfy(\.hasSubmitted)
```

Uses `backendSubmittedCount` and `backendHumanTeams` — both `@State` variables populated by `loadFromBackend()`. These are only as fresh as the last poll (up to 5 seconds old).

`SessionMonitorViewModel.allDecisionsSubmitted` (line 80-85):
```swift
if isBackendSession {
    return backendTeamCount > 0 && backendSubmittedCount >= backendTeamCount
}
return teams.allSatisfy { $0.hasSubmittedDecision }
```

**Divergence:** `RoundControlView` compares against `backendHumanTeams` (only human teams), while `SessionMonitorViewModel` compares against `backendTeamCount` (all teams including AI). If the backend counts AI teams in `teamsSubmitted`, `RoundControlView` will gate correctly but `SessionMonitorViewModel` won't, or vice versa.

### 3.4 Professor Pause/Resume — Local Only

`RoundControlView` pause toggle (line 308):
```swift
isPaused.toggle()
```

This only toggles the `@State private var isPaused` — it does **NOT** write to `session.isPaused`, does **NOT** call any backend endpoint, and does **NOT** sync with `BackendState`. The `Advance` button is disabled when `isPaused` is true, but this is purely cosmetic — the backend has no concept of paused state and the student's `TeamDashboardView` never sees it.

**Divergence:** Professor pauses locally → advance button disabled. But `BackendState.shared` keeps polling, students keep polling, and the backend remains "active." The pause is invisible to all other clients.

### 3.5 Professor End Session

`RoundControlView.endSession()` (line 388):
```swift
appState.clearActiveSession()
```

This only clears the local active session. It does **NOT** call `BackendState.shared.endSession()` or `NetworkService.endSession()`. The backend session remains active.

`SessionMonitorViewModel.endSessionWithBackend()` (line 283):
```swift
try await NetworkService.shared.endSession(code: sessionCode)
```

This calls the backend. But `endSession()` (line 178) just sets `session.state = .completed` locally without calling the backend variant.

**Divergence:** `RoundControlView.endSession()` doesn't notify the backend. `SessionMonitorViewModel` has both paths but `endSession()` (the local one) doesn't call `endSessionWithBackend()`.

---

## 4. PerformanceHistoryView & ViewModel

### 4.1 Data Loading

**`PerformanceHistoryView.onAppear` (line 25-30):**
```swift
if let session = appState.activeSession,
   let teamId = session.playerTeam?.id {
    viewModel.loadHistory(from: session, for: teamId)
}
```

**`PerformanceHistoryViewModel.loadHistory()` (line 180):**
```swift
let completedRounds = max(0, session.currentRound - 1)
for round in 1...max(1, completedRounds) {
    if let result = session.roundResult(for: teamId, round: round) {
        snapshots.append(RoundSnapshot(...))
    }
}
```

This reads from `session.roundResults` — the local SwiftData store. It computes `completedRounds` as `session.currentRound - 1` and iterates from 1 to that number.

### 4.2 Round Change Detection

**`PerformanceHistoryView.onChange(of: appState.activeSession?.currentRound)` (line 31-38):**
```swift
if let session = appState.activeSession,
   let teamId = session.playerTeam?.id,
   newRound > 1 {
    viewModel.loadHistory(from: session, for: teamId)
}
```

Triggers a reload whenever `session.currentRound` changes. But only if `newRound > 1` — **round 1 results are never loaded via onChange**.

**Divergence points:**
1. If `restoreResultsFromBackend` sets `currentRound = maxRound + 1`, the `onChange` fires. But `completedRounds = currentRound - 1 = maxRound`, so it tries to load rounds 1...maxRound. If the backend only returned results up to `maxRound` and `recordResult` was called for those, the data exists. But if `restoreResultsFromBackend` was called with a partial set (e.g., only the latest round from `processBackendRound`), `roundResult(for:round:)` returns `nil` for earlier rounds, and those rounds are silently skipped.

2. `loadHistory` is only called in `onAppear` and `onChange`. If the view is not currently visible (it's in a sheet that's been dismissed), round changes don't trigger a reload. The next `onAppear` will reload, but by then the `session.currentRound` may have advanced further.

3. The view reads `session.currentRound` to compute `completedRounds`, but `session.currentRound` may have been overwritten by `restoreResultsFromBackend` or a status poll. If `currentRound` was set to `maxRound + 1` before results were fully recorded, `completedRounds` includes a round that has no result yet — that round is simply skipped in the loop, so no crash, but the chart silently omits the latest round.

---

## 5. Complete Divergence Catalog

### D-01: `currentRound` — Four Independent Sources of Truth

| Source | Location | Updated By | Write Path |
|---|---|---|---|
| `SimulationSession.currentRound` | SwiftData `@Model` | `advanceRound()`, `restoreResultsFromBackend()`, `loadFromBackend()`, `pollBackendStatus()` | Multiple — no mutex |
| `BackendState.shared.currentRound` | `@Observable` singleton | `pollStatus()` every 5s | Single poller |
| `RoundControlView.currentRound` (`@State`) | View local | `loadFromSession()`, `loadFromBackend()` | Timer every 5s |
| `TeamDashboardView.backendCurrentRound` (computed) | View local | `BackendState.shared.currentRound` or `session.currentRound` | Read-only computed |

`SimulationSession.currentRound` is written by `restoreResultsFromBackend` (sets `maxRound + 1`), then potentially overwritten by `loadFromBackend`/`pollBackendStatus` (sets `min(status.currentRound, totalRounds)`). No locking; last writer wins.

### D-02: `hasSubmittedDecisions` — Local Flag vs Backend Counter

- Local: `SimulationSession.teams[i].hasSubmittedDecisions` — set to `true` in `submitDecision()`, reset to `false` in `advanceRound()` and `restoreResultsFromBackend()`
- Backend: `SessionStatusBackend.teamsSubmitted` — integer count from backend

**Problem:** Student submits decision → `submitDecision()` sets local flag `true`. Student closes app and reopens → `restoreResultsFromBackend()` unconditionally resets flag to `false` (line 819), even if the student already submitted for the current round. Backend still counts the submission. Student sees "Make Decisions" button again and can resubmit.

### D-03: `isPaused` — Local-Only, Backend-Unaware

`SimulationSession.isPaused` is a stored property never synced to the backend. `RoundControlView`'s pause button only toggles a `@State` copy (not even `session.isPaused`). The `submitDecision()` guard (`!isPaused`) uses `session.isPaused` but the view never writes to it. Net effect: pause does nothing functional.

### D-04: `session.state` — Overwritten by Multiple Pollers

- `SimulationSession.stateRaw` can be written by: `advanceRound()`, `restoreResultsFromBackend()` (doesn't set state), `loadFromBackend()` (sets `.completed` if backend says "finished"/"completed"), `pollBackendStatus()` (sets `.completed` or `.inProgress`)
- `restoreResultsFromBackend` does NOT set `session.state` — after restoring results the session could still be `.waitingForPlayers` if it was never updated by a poller
- `pollBackendStatus` sets `session.state = .inProgress` when backend says "active", even mid-round before processing

### D-05: Revenue Split Fabrication in `restoreResultsFromBackend`

```swift
wholesaleRevenue: backendResult.revenue * 0.5,   // hardcoded
internetRevenue: backendResult.revenue * 0.3,     // hardcoded
amazonRevenue: backendResult.revenue * 0.15,      // hardcoded
privateLabelRevenue: backendResult.revenue * 0.05 // hardcoded
```

The backend returns a single `revenue` field. The iOS app fabricates a split that may not match the actual backend computation. `RoundResult.revenue` is a computed property (`wholesaleRevenue + internetRevenue + ...`), so if the backend's actual split differs, the total revenue shown locally will differ from the backend's number.

Similarly fabricated:
- `wholesaleUnitsSold: max(0, Int(backendResult.revenue / 50))` — guessed
- `interestExpense: backendResult.equity * 0.05` — guessed
- `csrCosts`, `endorsementCosts`, `workforceCosts`, `storageCosts`, `rebateCosts`, `deliveryCosts`, `socialMediaCosts`, `amazonFees` — all hardcoded to 0
- `awarenessScore`, `rejectionRate` — hardcoded to 0

### D-06: `recordResult` Duplicate Guard — Silently Drops

```swift
guard roundResults[result.teamId]?[result.round] == nil else { return }
```

If `restoreResultsFromBackend` is called multiple times (e.g., student polls, professor advances, student polls again), the second call silently skips all results because they were already recorded. This means `currentRound = maxRound + 1` (line 816) still executes, but team financial state isn't updated again — it retains the first computation. If the backend recomputed with different values, the local state would be stale.

### D-07: Team Name Matching — Fragile

`restoreResultsFromBackend` matches backend results to local teams by **team name**:
```swift
guard let teamUUID = nameToUUID[backendResult.teamId] else {
    NSLog("... team '\(backendResult.teamId)' not found ...")
    continue
}
```

If the team name changed (e.g., local init generates "Team Alpha" but backend returns the professor-chosen name "Group 1"), the result is silently skipped. The student's local state will never receive results for their team.

### D-08: `BackendState.shared` — Singleton Lifecycle Mismatch

`BackendState.shared` is a singleton that persists across view transitions. If a student leaves a session (views dismissed) but `disconnect()` is never called, the singleton keeps polling the old session code. When the student joins a new session, `connect()` is called, but if the old poll task was still running there could be a race between `stopPolling()` and `startPolling()`.

### D-09: `lastSyncedAt` — Written, Never Read

`SimulationSession.lastSyncedAt` is defined as `Date?` but is set only in init (to `nil`) and never updated anywhere in the codebase. It's dead state that gives a false impression of sync tracking.

### D-10: `BackendState.shared.isOnline` Not Set on Poll Error

`pollStatus()` catch block sets `self.sessionState = .disconnected` but does **NOT** set `isOnline = false`. The `TeamDashboardView.isOnline` computed property checks both `BackendState.shared.isOnline && BackendState.shared.sessionState != .disconnected`. So after a poll error, `isOnline` remains `true` and the dashboard thinks it's online even though it's disconnected.

### D-11: `advanceRound()` vs `restoreResultsFromBackend()` — Mutually Exclusive Round Advancement

For offline sessions, `advanceRound()` is called:
- Increments `currentRound`, clears `currentRoundDecisions`, moves to `previousRoundDecisions`, resets all `hasSubmittedDecisions`, updates state to `.inProgress` or `.completed`

For online sessions, `restoreResultsFromBackend()` is called instead:
- Sets `currentRound = maxRound + 1`, calls `recordResult` for each team, resets only the player team's `hasSubmittedDecisions`
- Does NOT clear `currentRoundDecisions` (unlike `advanceRound`)
- Does NOT move `currentRoundDecisions` to `previousRoundDecisions`
- Does NOT reset AI team `hasSubmittedDecisions`

**Problem:** After `restoreResultsFromBackend`, the stale decisions from the previous round remain in `currentRoundDecisions`. The student can see ghost decisions from the previous round if any UI reads `currentRoundDecisions`.

### D-12: `RoundControlView` vs `SessionMonitorViewModel` — Two Professor Advance Paths

Both exist and both can be used:

| Aspect | `RoundControlView.processBackendRound()` | `SessionMonitorViewModel.processRoundWithBackend()` |
|---|---|---|
| Guard | `allSubmitted && !isProcessing` | `isBackendSession && canAdvanceRound` |
| `canAdvanceRound` | N/A | `allDecisionsSubmitted && !isProcessingRound && !isSessionComplete && backendTeamStatus == "active"` |
| After process | `loadFromBackend()` | `pollBackendStatus()` + `refreshTeamStatuses()` |
| Submission check | `backendHumanTeams` | `backendTeamCount` (all teams) |

If both views are active simultaneously, both could trigger `processRound` — double-processing. The guard `!isProcessing` / `!isProcessingRound` is view-local, not shared.

---

## 6. Round Lifecycle Sequence Diagrams

### 6.1 Student: Submit Decisions (Backend Session)

```
DecisionInputView
  └→ DecisionInputViewModel.submitDecisions()
       ├→ SyncService.syncDecisionSubmission()
       │    └→ NetworkService.submitDecision() → POST /submit_decision
       │         [Backend: records decision, increments teamsSubmitted]
       ├→ session.submitDecision(decision)  ← LOCAL MIRROR
       │    └→ currentRoundDecisions[teamId] = decision
       │    └→ teams[playerIdx].hasSubmittedDecisions = true
       └→ return true (no local processing for backend sessions)
```

### 6.2 Student: Receive Round Results (Polling)

```
TeamDashboardView Timer (every 10s)
  └→ fetchBackendResults()
       ├→ NetworkService.getResults() → GET /results
       │    [Returns {round: [RoundResultBackend]}]
       ├→ if maxBackendRound >= session.currentRound:
       │    └→ session.restoreResultsFromBackend(backendResults)
       │         ├→ Match team names → UUIDs
       │         ├→ Convert RoundResultBackend → RoundResult (FABRICATED splits)
       │         ├→ recordResult() for each [guard: skip if already exists]
       │         ├→ updateRankings()
       │         ├→ currentRound = maxRound + 1  ← INFERRED, not from backend status
       │         └→ teams[playerIdx].hasSubmittedDecisions = false  ← UNCONDITIONAL RESET
       └→ if session.currentRound > lastProcessedRound:
            └→ showResults = true
```

### 6.3 Professor: Advance Round (Backend Session)

```
RoundControlView.advanceRound()
  └→ processBackendRound()
       ├→ NetworkService.processRound() → POST /process_round
       │    [Backend: computes results, advances currentRound]
       ├→ session.restoreResultsFromBackend([processedRound: results])
       │    └→ currentRound = processedRound + 1
       │    └→ (partial: only this round's results)
       └→ loadFromBackend()
            ├→ NetworkService.getSessionStatus() → GET /status
            │    [Returns status.currentRound = processedRound + 1 (if committed)]
            ├→ currentRound = min(status.currentRound, totalRounds)
            │    ← MAY OVERWRITE restoreResultsFromBackend's value if backend not yet committed
            └→ session.currentRound = currentRound  ← WRITES TO SHARED MODEL
```

### 6.4 Offline/Demo: Advance Round

```
RoundControlView.advanceRound()
  └→ gameController.processRoundAfterPlayerSubmit()
       ├→ Generate AI decisions
       ├→ SimulationEngine.processRound()
       │    └→ Returns [RoundResult]
       ├→ session.applyRoundOutput()
       │    ├→ recordResult() for each
       │    ├→ Update team financial state
       │    └→ updateRankings()
       └→ session.advanceRound()
            ├→ currentRound += 1
            ├→ previousRoundDecisions = currentRoundDecisions
            ├→ currentRoundDecisions.removeAll()
            ├→ All teams: hasSubmittedDecisions = false
            └→ state = .inProgress (or .completed if > totalRounds)
```

---

## 7. Summary of State Sync Architecture Problems

| # | Problem | Severity | Impact |
|---|---|---|---|
| D-01 | `currentRound` has 4 independent sources with no locking | Critical | Race conditions, wrong round displayed |
| D-02 | `hasSubmittedDecisions` reset on restore allows re-submission | High | Duplicate submissions, backend confusion |
| D-03 | Pause is local-only and non-functional | Medium | Professor thinks they paused; nobody else sees it |
| D-04 | `session.state` written by multiple pollers | High | Incorrect state transitions, UI flicker |
| D-05 | Revenue/cost data fabricated during backend restore | High | Financial data shown to students is wrong |
| D-06 | `recordResult` duplicate guard silently drops updates | Medium | Stale data after re-restore |
| D-07 | Team name matching is fragile | High | Results silently dropped if names mismatch |
| D-08 | `BackendState` singleton lifecycle not tied to view lifecycle | Medium | Phantom polling, stale data |
| D-09 | `lastSyncedAt` is dead code | Low | Misleading, no functional impact |
| D-10 | `isOnline` not reset on poll error | Medium | False "online" indicator after disconnect |
| D-11 | `restoreResultsFromBackend` doesn't clear stale decisions | Medium | Ghost decisions from previous round visible |
| D-12 | Two independent professor advance paths can double-process | Critical | Double round processing, corrupted state |

---

## 8. Root Cause Analysis

The fundamental architectural flaw is that the app maintains **two authoritative state machines** — the local SwiftData `SimulationSession` and the backend API — with no clear ownership boundary. Every piece of round state (`currentRound`, `hasSubmittedDecisions`, `session.state`, team financials, results) exists in both systems and is reconciled through ad-hoc polling and `restoreResultsFromBackend` calls that:

1. **Infer** `currentRound` from result presence rather than reading the authoritative value
2. **Fabricate** financial breakdowns that may not match backend computation
3. **Unconditionally reset** submission flags without checking backend submission state
4. **Silently drop** results that don't match local team names
5. Are called by **multiple independent pollers** on different intervals with no coordination

The backend is declared "authoritative" in code comments (e.g., SessionMonitorViewModel: "the backend as the sole round authority for online classroom sessions") but the implementation doesn't enforce this — local state is mutated independently and the backend's authoritative values are treated as suggestions that get overwritten.
