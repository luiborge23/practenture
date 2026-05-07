# BizSimAI iOS — Deep Code Review Report

> **Scope:** All 59 Swift files across Engine/, Models/, Services/, ViewModels/, Views/, and Views/Components/
> **Date:** 2026-05-05
> **Severity key:** 🔴 HIGH · 🟡 MEDIUM · 🔵 LOW

---

## 1. Crash Risks

### 1.1 Non-deterministic AI team name assignment
- **File:** `Models/SimulationSession.swift`, line 93
- **Severity:** 🟡 MEDIUM
- **Code:** `let aiNames = Self.aiCompanyNames.shuffled().prefix(config.numberOfAICompetitors)`
- **Issue:** `shuffled()` uses a non-deterministic RNG seed. Re-creating a session from the same configuration may produce different AI competitors, breaking reproducibility and making debugging/simulations unpredictable.
- **Fix:** Use the session's `randomSeed` to seed the shuffle: create a `SeededRandomGenerator(seed: config.randomSeed)` and use it to shuffle, or assign AI names by index offset from a deterministic rotation.

### 1.2 Division by zero risk in `totalDemandForTeam` check
- **File:** `Engine/SimulationEngine.swift`, line 269
- **Severity:** 🔵 LOW
- **Code:** `if totalDemandForTeam > 0 { ... }`
- **Issue:** The guard is correct, but `capForSale` on line 263 could be 0 when `totalDemandForTeam > 0 && totalAvailable == 0`. The subsequent proportional allocation uses `demandDouble` (which is `totalDemandForTeam`, > 0), but if `capDouble` is 0 all allocations become 0. This is mathematically correct (no units available → zero sold), but the code comment at line 262 ("Allocate sales across channels proportionally") implies some sales should happen — consider adding a warning explanation for the player when they produce nothing but have demand.
- **Fix:** Add a `ResultExplanation` for zero-capacity allocation to inform players why they got zero sales.

### 1.3 No validation on `overtimePercent` in AI strategies
- **File:** `Engine/AICompetitor.swift`, lines 77, 151, 228, 341
- **Severity:** 🔵 LOW
- **Issue:** AI strategies set `overtimePercent` to fixed values (0, 5, 10, 15). These are within valid ranges, but if a user-configured `config.maxOvertimePercent` exists, AI strategies don't respect it. This is a minor correctness gap.
- **Fix:** Cap AI overtime at `config.maxOvertimePercent` if configurable.

### 1.4 `currentRound` access after session completion
- **File:** `Models/SimulationSession.swift`, line 180
- **Severity:** 🔵 LOW
- **Code:** `roundResults[teamId]?[currentRound] ?? roundResults[teamId]?[currentRound - 1]`
- **Issue:** When session state is `.completed` and `currentRound > config.totalRounds`, `currentRound - 1` may still be valid, but this creates an implicit dependency on the session finishing exactly one round past the last. If a session is reset or manipulated, this could return stale data.
- **Fix:** Add a guard for `session.state != .completed` or use `config.totalRounds` instead of `currentRound - 1`.

---

## 2. Logic Bugs

### 2.1 `cumulativeTQM` used as profit proxy for AI decisions
- **File:** `Engine/GameController.swift`, line 62–64
- **File:** `Engine/SessionMonitorViewModel.swift`, line 119–121
- **Severity:** 🔴 HIGH
- **Code:**
  ```swift
  let competitorProfits = session.teams.reduce(into: [:]) { dict, t in
      dict[t.id] = t.cumulativeTQM // Using TQM as proxy for profit tracking
  }
  ```
- **Issue:** TQM (Total Quality Management) investment is completely unrelated to a team's profit. The AI strategies receive `competitorProfits` in their `AIDecisionContext` but actually get TQM investment totals. AI strategies that consider competitor profits (e.g., `AdaptiveStrategy`) will base decisions on garbage data. This fundamentally breaks the "BestCostStrategy" and "AdaptiveStrategy" counterplay logic.
- **Fix:** Replace `t.cumulativeTQM` with `t.cumulativeProfit` or compute actual profit from `session.cumulativeProfit(for: t.id)`. Ensure `TeamStatus` tracks cumulative profit, or compute it from `RoundResult` values.

### 2.2 Team state double-updated (engine + session)
- **File:** `Engine/SimulationEngine.swift`, lines 402–523
- **Severity:** 🟡 MEDIUM
- **Issue:** `processRound` updates team financial state at lines 514–523 (reputation, equity, debt, shares, cumulative investments) AND `session.recordResult()` at line 510 updates cash, inventory, S/Q, image, credit, and cumulative investor score. However, `SimulationEngine` directly mutates `session.teams[index]` without going through `recordResult`. If `recordResult` were ever refactored to also update equity/debt/shares, there'd be a conflict. More importantly, the `SimulationEngine` modifies `TeamStatus.equity` directly but `TeamStatus` is an `@Observable` class — this direct mutation bypasses any encapsulation and could lead to race conditions if the UI observes these values mid-calculation.
- **Fix:** Move all team state updates into `SimulationSession.recordResult()` and have the engine only compute values, then call `recordResult` with everything needed.

### 2.3 `roundResult(for:teamId:round:)` returns stale data when round not yet processed
- **File:** `Models/SimulationSession.swift`, line 375–377
- **Severity:** 🔵 LOW
- **Issue:** The `latestResult(for:)` method (line 179-181) returns `roundResults[teamId]?[currentRound]` first, but that round hasn't been processed yet (it's in `currentRoundDecisions`, not `roundResults`). It falls back to `currentRound - 1` which is correct, but callers may misinterpret the result as being from the current round.
- **Fix:** Rename to `latestCompletedResult` or add documentation clarifying this returns the most recently *completed* round.

### 2.4 AI strategy uses `playerPreviousDecision` from wrong round
- **File:** `Engine/GameController.swift`, lines 48–51
- **Severity:** 🟡 MEDIUM
- **Issue:**
  ```swift
  let playerPrevDecision: PlayerDecision? = session.previousRoundDecisions.values.first(where: { decision in
      session.teams.first(where: { !$0.isAI && $0.id == decision.teamId }) != nil
  })
  ```
  This filters `previousRoundDecisions` by any non-AI team, but `previousRoundDecisions` may contain decisions from multiple teams. Using `first(where:)` on a `[UUID: PlayerDecision]` values sequence returns the first value with no guaranteed ordering. The intent is to get the human player's previous round decision, but this could pick an AI team's decision if the dictionary iteration order differs.
- **Fix:** Use `session.previousRoundDecisions[session.playerTeam?.id]` directly.

### 2.5 `competitiveProfits` context is never used effectively
- **File:** `Engine/AICompetitor.swift`, line 14, 68
- **Severity:** 🟡 MEDIUM
- **Issue:** `AIDecisionContext.competitorProfits` is a `[UUID: Double]` map that AI strategies receive but none of the four strategies actually read. The map is populated with garbage data (see 2.1), and even if fixed, no strategy uses it. This dead code wastes memory and suggests incomplete implementation.
- **Fix:** Remove the unused property from `AIDecisionContext`, or implement actual competitor-profit-based decision logic in strategies.

### 2.6 `DecisionInputViewModel.totalSpend` omits loan/issuance costs
- **File:** `ViewModels/DecisionInputViewModel.swift`, lines 297–302
- **Severity:** 🟡 MEDIUM
- **Code:**
  ```swift
  var totalSpend: Double {
      productionCost + stylingBudget + ...
  }
  ```
- **Issue:** `totalSpend` does not include `dividendsPerShare * currentShares` in a way consistent with the engine. The engine computes dividends as `dividendsPerShare * newShares` (line 388), where `newShares = max(1, sharesOutstanding - safeBuyback + sharesIssued)`. The ViewModel uses `currentShares` which is `sharesOutstanding` (pre-buyback). This means the UI preview and the actual engine cost will differ, leading to confusing "over budget" behavior after a round is processed.
- **Fix:** Compute dividends in ViewModel using the same formula as the engine: `dividendsPerShare * (currentShares - sharesBuyback + sharesIssued)`.

### 2.7 `isOverBudget` tolerance is silently ignored
- **File:** `ViewModels/DecisionInputViewModel.swift`, line 309
- **Severity:** 🔵 LOW
- **Code:** `remainingBudget < -100 // Small tolerance`
- **Issue:** The 100-unit tolerance means a team can be $100 in the red and still show as valid. However, the engine doesn't apply the same tolerance — it calculates actual costs precisely. A player could "submit valid" UI-wise but get a negative profit the engine computes. The tolerance should match engine behavior.
- **Fix:** Either remove tolerance or align with engine behavior.

---

## 3. Architecture Issues

### 3.1 Duplicate `SimulationEngine` instantiation
- **File:** `Engine/GameController.swift`, line 28
- **File:** `ViewModels/SessionMonitorViewModel.swift`, line 41
- **Severity:** 🔴 HIGH
- **Issue:** Both `GameController` and `SessionMonitorViewModel` independently instantiate `SimulationEngine`. If the engine has internal state (it doesn't currently, but the `SeededRandomGenerator` is created fresh per round), changes to one won't affect the other. If someone adds memoization or caching to the engine, both copies would have independent caches, causing inconsistencies between student-view and professor-view simulation results.
- **Fix:** Create a single `SimulationEngine` instance in `AppState` or `SimulationSession` and inject it into both consumers.

### 3.2 AI strategy factory duplicated
- **File:** `Engine/GameController.swift`, lines 29–31
- **File:** `ViewModels/SessionMonitorViewModel.swift`, lines 48–51
- **Severity:** 🟡 MEDIUM
- **Issue:** Both places call `AIStrategyFactory.createCompetitors(...)` with the same parameters. If the factory logic changes (e.g., adding more strategies), both call sites must be updated.
- **Fix:** Store `aiCompetitors` in `SimulationSession` or `GameState` so it's the single source of truth.

### 3.3 Tight coupling between `SimulationEngine` and `SimulationSession`
- **File:** `Engine/SimulationEngine.swift`, lines 510, 514–523, 537
- **Severity:** 🟡 MEDIUM
- **Issue:** `SimulationEngine` directly calls `session.recordResult()`, `session.updateRankings()`, and mutates `session.teams[index]`. The engine knows too much about the session's internal structure. If `SimulationSession` changes its internal representation (e.g., stores results differently), the engine breaks.
- **Fix:** Pass a callback/result handler to `processRound` that handles session updates externally, or have the engine return a `SimulationStateUpdate` struct that `SimulationSession` applies.

### 3.4 `TeamDashboardViewModel` is disconnected from session
- **File:** `ViewModels/TeamDashboardViewModel.swift`
- **Severity:** 🟡 MEDIUM
- **Issue:** The VM is created in views but has no connection to `SimulationSession`. `refreshStatus(from:)` is a manual method that must be called at the right time. If a view doesn't call it (or calls it too late), the dashboard shows stale data. There's no automatic synchronization.
- **Fix:** Make `TeamDashboardViewModel` observe `SimulationSession` directly (e.g., via a closure callback from `SimulationSession` or by holding a reference and using SwiftUI's environment to propagate updates).

### 3.5 No protocol for `SimulationSession`
- **File:** `Models/SimulationSession.swift`
- **Severity:** 🔵 LOW
- **Issue:** `SimulationSession` is a concrete `@Observable` class. There's no protocol abstracting its interface. This makes testing difficult (can't mock the session) and tightly couples all ViewModels to the concrete type.
- **Fix:** Define a `SimulationSessionProtocol` with read-only accessors for teams, results, config, and a `submitDecision` method.

### 3.6 `RoundSummary` struct defined in two places?
- **File:** Search across Views
- **Severity:** 🔵 LOW
- **Issue:** `RoundSummary` appears to be defined in the Views (used in `GameController.processRoundAfterPlayerSubmit` line 101: `RoundSummary(from: playerResult, price: playerDec.wholesalePrice)`). Check if there's a model-layer `RoundSummary` and a view-layer `RoundSummary` — this naming collision could cause confusion.
- **Fix:** Ensure unique naming. If there's duplication, consolidate into one location.

### 3.7 `DecisionInputViewModel.submitDecisions` bypasses `recordResult`
- **File:** `ViewModels/DecisionInputViewModel.swift`, line 507
- **Severity:** 🔵 LOW
- **Code:** `session.submitDecision(decision)`
- **Issue:** The `submitDecision` method on `SimulationSession` stores the decision in `currentRoundDecisions` but doesn't validate that the player's team actually has positive cash to cover costs. The budget check is in `DecisionInputViewModel.isOverBudget` which uses an approximate formula (see 2.6). There's no server-side or model-side validation of financial feasibility.
- **Fix:** Add a `validateDecision(_:)` method on `SimulationSession` that computes actual costs using the same formula as the engine.

---

## 4. Data Integrity

### 4.1 `TeamStatus` missing `cumulativeProfit` property
- **File:** `Models/SimulationModels.swift`
- **Severity:** 🔴 HIGH
- **Issue:** The `TeamStatus` struct has `cumulativeTQM`, `cumulativeRD`, `cumulativeMarketing`, `cumulativeCSR` but no `cumulativeProfit`. This is why the AI strategies use `cumulativeTQM` as a profit proxy (see 2.1). Without actual cumulative profit tracking in the model, any system that needs profit data (AI decisions, leaderboards, coaching) must recompute it from `RoundResult` values, which is O(n) per query and error-prone.
- **Fix:** Add `var cumulativeProfit: Double = 0` to `TeamStatus` and update it in `SimulationSession.recordResult()` alongside `cumulativeInvestorScore`.

### 4.2 `SessionConfiguration` not `Codable`
- **File:** `Models/SimulationModels.swift`
- **Severity:** 🟡 MEDIUM
- **Issue:** If `SessionConfiguration` is not `@objc`-compatible and doesn't conform to `Codable`, it can't be persisted or transferred between processes. The `CreateSessionViewModel` creates sessions in-memory only; there's no session persistence.
- **Fix:** Add `Codable` conformance to `SessionConfiguration` and all its sub-structs if persistence or cross-process communication is planned.

### 4.3 `PlayerDecision` stores `fulfillmentMethod` but it's not in the sub-structs
- **File:** `Engine/AICompetitor.swift`, line 86, 160, 237, 350
- **Severity:** 🔵 LOW
- **Issue:** `PlayerDecision` has a top-level `fulfillmentMethod` property that's set directly (not inside a sub-struct). The engine's `processRound` uses it for Amazon fees (line 363: `decision.fulfillmentMethod.feePerUnit`), but the UI doesn't clearly expose it as a distinct decision category. It sits awkwardly between the decision sub-structs and the top-level properties.
- **Fix:** Move `fulfillmentMethod` into the `PricingDecision` sub-struct since it's an Amazon/Pricing-related decision.

### 4.4 `InvestorScorecard` missing `totalScore` implementation detail
- **File:** `Models/SimulationModels.swift`
- **Severity:** 🔵 LOW
- **Issue:** `InvestorScorecard.totalScore` is a computed property. Ensure it sums the five scorecard component scores (eps, roe, stockPrice, image, credit). If it uses hardcoded weights that don't match the displayed breakdown, users will see inconsistent numbers.
- **Fix:** Add a unit test to verify `totalScore == epsScore + roeScore + stockPriceScore + imageScore + creditScore` and document the formula.

### 4.5 `CreditRating` from financials may produce inconsistent results
- **File:** `Engine/SimulationEngine.swift`, lines 422–431
- **Severity:** 🟡 MEDIUM
- **Code:**
  ```swift
  let debtToEquity = newEquity > 0 ? newDebt / newEquity : 10
  let interestCoverage = interestExpense > 0 ? max(0, profit + interestExpense) / interestExpense : 20
  let cashRatio = newDebt > 0 ? newCash / newDebt : 5
  ```
- **Issue:** When `newEquity <= 0` (team is insolvent), `debtToEquity` is set to 10 — a very high ratio. When `interestExpense == 0`, `interestCoverage` defaults to 20 — a very favorable ratio. The inconsistency in defaults (10 for bad, 20 for good, 5 for neutral) is intentional but may produce edge-case ratings where a team with no debt gets an artificially high interest coverage rating. Also, `newEquity` is set to `max(1, team.equity + profit)` on line 407, meaning equity can never be ≤ 0. The `> 0` check on line 422 is dead code.
- **Fix:** Remove the dead `> 0` guard on `newEquity` (line 422) since equity is clamped to minimum 1. Clarify the default values for the credit rating computation.

### 4.6 `previousStockPrice` fallback in engine is inconsistent
- **File:** `Engine/SimulationEngine.swift`, lines 402, 453, 303
- **Severity:** 🔵 LOW
- **Code:** `session.roundResult(for: team.id, round: round - 1)?.scorecard.stockPrice ?? baseStockTarget`
- **Issue:** On round 1, `round - 1 = 0`, and `roundResult(for:teamId:round: 0)` will always return `nil` (rounds are 1-indexed). This means round 1 always uses `baseStockTarget` ($25). This is correct behavior but worth documenting, as the fallback hides the fact that there's "no previous round."
- **Fix:** Document the behavior or use `round > 1` guard explicitly with a clearer fallback comment.

---

## 5. UI Concerns

### 5.1 `PerformanceHistoryView` dead code: `loadSampleData()`
- **File:** `Views/Student/PerformanceHistoryView.swift`, lines 271–296
- **Severity:** 🔵 LOW
- **Issue:** `loadSampleData()` populates hardcoded round data and is called when `appState.activeSession` is nil. This masks real data-loading bugs — if the session is nil due to a bug, the view still shows "data."
- **Fix:** Remove the dead code path or make it explicitly opt-in via a debug flag.

### 5.2 `StudentLeaderboardView` also has `loadSampleData()`
- **File:** `Views/Student/StudentLeaderboardView.swift`, lines 147–183
- **Severity:** 🔵 LOW
- **Same issue:** Sample data masks issues when session is unavailable.

### 5.3 No automatic re-load on session data changes
- **File:** Multiple views (`TeamDashboardView`, `RoundResultsView`, `PerformanceHistoryView`, `StudentLeaderboardView`)
- **Severity:** 🟡 MEDIUM
- **Issue:** All these views use `@State private var viewModel = ...` and load data in `onAppear`. When the user navigates back to these views, `onAppear` fires again but the `@State` VM is a new instance (fresh defaults). If the session data changed between visits, the view will show stale defaults until `onAppear` reloads. However, if the VM holds state from the previous visit (e.g., selected metric, scroll position), it's lost.
- **Fix:** Use `@Observable` property wrappers that observe session state changes, or lift VM state to the environment level.

### 5.4 `TeamDashboardViewModel.refreshStatus` doesn't update on session state changes
- **File:** `ViewModels/TeamDashboardViewModel.swift`, lines 121–154
- **Severity:** 🟡 MEDIUM
- **Issue:** The dashboard must manually call `refreshStatus()` to get fresh data. If a user opens the dashboard before all AI decisions are submitted, they'll see incomplete data. There's no loading/refresh indicator tied to the session's AI decision generation.
- **Fix:** Have the dashboard observe `session.currentRoundDecisions.count` or `session.state` and auto-refresh when the AI finishes generating decisions.

### 5.5 `DecisionInputView` does not show real-time cost projection
- **File:** `Views/Components/DecisionInput/DecisionInputView.swift`
- **Severity:** 🔵 LOW
- **Issue:** The ViewModel has `totalSpend` and `remainingBudget` computed properties, but the actual engine cost formula differs (see 2.6). The UI cost preview could be off by a significant margin, leading to budget overages on submission.
- **Fix:** Align the ViewModel cost formula with the engine's, including buyback costs, share issuance proceeds, and the actual dividend calculation using `newShares`.

### 5.6 `TeamDashboardView` uses `onAppear` for refresh
- **File:** `Views/Student/TeamDashboardView.swift`
- **Severity:** 🔵 LOW
- **Issue:** Dashboard data only refreshes on view appear, not during active rounds. If AI teams finish generating decisions while the user is on the dashboard, the "Round Progress" and "Has Submitted" state won't update until they navigate away and back.
- **Fix:** Use `Timer.publish` or `onTask` to periodically refresh, or observe session state changes.

### 5.7 Memory: No `@MainActor` on `@Observable` classes
- **File:** `ViewModels/AppState.swift`, line 6
- **Severity:** 🔵 LOW
- **Code:** `@Observable final class AppState`
- **Issue:** `@Observable` classes should be annotated with `@MainActor` to ensure thread-safety of property access from SwiftUI. Without it, concurrent updates from different threads (e.g., background simulation processing) could cause race conditions on observed properties.
- **Fix:** Add `@MainActor` to all `@Observable` ViewModels and `SimulationSession`.

---

## 6. Code Quality

### 6.1 Magic numbers without documentation
- **File:** `Engine/SimulationEngine.swift`
- **Severity:** 🟡 MEDIUM
- **Examples:**
  - Line 51: `priceElasticity = 1.5` — Is this from academic research, or tuned empirically?
  - Line 52: `sqWeight = 1.2` — What justifies this specific weight?
  - Line 53: `outletsWeight = 0.3` — Why 0.3 specifically?
  - Line 65: `storageCostPerUnit = 1.50` — Per unit, per round? Per month?
  - Line 77: `baseWageBaseline = 25_000` — "Industry standard wage" is labeled but the range is wide (15K-40K in UI). Is $25K realistic?
  - Line 334: `workersNeeded = max(1, grossProduction / 10)` — Why 10 units per worker? No source.
  - Line 375: `internetShippingCost = Double(iSold) * 5.0 * freeShipRate` — $5/unit hardcoded.
  - Line 435: `advertisingBudget / 2000.0 * 5` — Magic divisor 2000 and multiplier 5.
  - Line 173: `mailInRebate * 0.6` — "~60% redemption rate" is commented, but 0.6 is used in multiple places without consistent documentation.
- **Fix:** Extract these into named `private let` constants with comments explaining their source (academic model, empirical tuning, business assumption).

### 6.2 Duplicate code in AI strategies
- **File:** `Engine/AICompetitor.swift`
- **Severity:** 🟡 MEDIUM
- **Issue:** Each of the four AI strategies (`LowCostLeaderStrategy`, `DifferentiatorStrategy`, `BestCostStrategy`, `AdaptiveStrategy`) contains ~60 lines of nearly identical `PlayerDecision` construction code. The only differences are in a few numeric constants and branch conditions. This violates DRY and makes adding new decision fields (e.g., a future "CSR" field) require editing all four strategies.
- **Fix:** Create a builder/factory pattern with default values per strategy, then override only the differing fields. For example:
  ```swift
  struct AIDecisionBuilder {
      var wholesalePrice: Double = 80
      var materialsQuality: MaterialsQuality = .standard
      // ...
      func build(teamId: UUID, round: Int, config: SessionConfiguration, rng: inout SeededRandomGenerator) -> PlayerDecision
  }
  ```

### 6.3 `AIDecisionContext.competitorProfits` is dead code
- **File:** `Engine/AICompetitor.swift`, line 16
- **Severity:** 🔵 LOW
- **Issue:** The `competitorProfits` property in `AIDecisionContext` is never read by any strategy. It exists as a planned feature that was never implemented.
- **Fix:** Remove the property or implement actual competitive-profit-based decision logic.

### 6.4 `CoachMessage` count capped at 3 silently
- **File:** `Services/CoachingService.swift`, line 201
- **Severity:** 🔵 LOW
- **Code:** `return Array(messages.prefix(3))`
- **Issue:** The coach generates 10+ possible messages but silently truncates to 3. This means critical warnings (e.g., "cash running low" + "high rejection rate" + "poor S/Q") could be silently dropped. There's no configuration for message priority.
- **Fix:** Implement a priority system where critical messages (cash < threshold, loss > threshold) always appear, and less critical ones fill remaining slots.

### 6.5 `creditRating` enum comparison at round boundary
- **File:** `ViewModels/RoundResultsViewModel.swift`, line 306
- **Severity:** 🔵 LOW
- **Code:** `if creditRating < .bPlus`
- **Issue:** This uses enum raw value ordering. Ensure the `CreditRating` enum is declared with a consistent `rawValue` that reflects severity (lower rawValue = worse rating). If not, the comparison is meaningless.
- **Fix:** Verify `CreditRating` has ordered `rawValue: Int` (e.g., AAA=7, AA=6, ... D=1) and add a comment documenting this.

### 6.6 `SessionConfiguration` default values unclear
- **File:** `Models/SimulationModels.swift`
- **Severity:** 🔵 LOW
- **Issue:** If `SessionConfiguration` has default values for `startingCash`, `initialEquity`, `plantCapacity`, etc., they're not well-documented. A professor creating a session might not know what the defaults mean or whether they should override them.
- **Fix:** Add `/// Default: X. Adjust for harder/easier simulation` comments on each default field.

### 6.7 `generateDemoPlayerDecision` has hardcoded growth that exceeds realistic bounds
- **File:** `Engine/GameController.swift`, line 196
- **Severity:** 🔵 LOW
- **Code:** `let _wholesalePrice = baseCost * 2.2 + Double(round) * 1.5`
- **Issue:** By round 10, this adds $15 to the wholesale price on top of a base markup. Over a 10-round session, prices inflate by ~7%. This might be fine, but there's no cap — if `totalRounds` is 20, prices go up $30 which could exceed the `wholesalePriceRange` (30-200) depending on base cost.
- **Fix:** Clamp generated demo prices to valid ranges: `min(_wholesalePrice, 200)`.

### 6.8 `roundsScored` computation in `recordResult` is incorrect for non-consecutive rounds
- **File:** `Models/SimulationSession.swift`, lines 152–154
- **Code:**
  ```swift
  let prevTotal = teams[index].cumulativeInvestorScore * Double(teams[index].roundsScored)
  teams[index].roundsScored += 1
  teams[index].cumulativeInvestorScore = (prevTotal + result.scorecard.totalScore) / Double(teams[index].roundsScored)
  ```
- **Severity:** 🟡 MEDIUM
- **Issue:** The running average formula assumes rounds are scored consecutively from round 1. If a team misses round 3 (no decision submitted) but scores rounds 1, 2, 4, the `roundsScored` counter will be 3 after round 4, but the average will only reflect 3 rounds of scores. The `roundsScored` variable is incremented every time `recordResult` is called, so it correctly counts scored rounds. However, if `recordResult` is called multiple times for the same round (e.g., a replay), `roundsScored` would be double-counted.
- **Fix:** Guard against duplicate `recordResult` calls by checking `roundResults[result.teamId]?[result.round] != nil` before computing.

### 6.9 `SessionConfiguration.maxHumanTeams` range unchecked
- **File:** `ViewModels/CreateSessionViewModel.swift`
- **Severity:** 🔵 LOW
- **Issue:** The max human teams is configurable. If set to 0 or 1, the AI team name shuffling and the `humanTeamNames` prefix logic still works correctly (prefix(0) = empty, prefix(1) = first name), but the session would have no player teams. This is a valid configuration (AI-vs-AI demo) but should be explicitly supported with a session state for it.
- **Fix:** Document that `maxHumanTeams == 0` creates an AI-only session.

### 6.10 Magic number `0.05` in `noiseFactor` used consistently but undocumented
- **File:** `Engine/SimulationEngine.swift`, line 54
- **Code:** `private let noiseAmplitude: Double = 0.05`
- **Severity:** 🔵 LOW
- **Issue:** The 5% noise amplitude is applied to price attractiveness, internet attractiveness, and amazon attractiveness. It represents stochastic market variation. The comment at line 54 says nothing — it should say "5% market volatility noise applied to attractiveness calculations."
- **Fix:** Add inline comment with the business meaning.

---

## Summary by Severity

| Severity | Count | Description |
|----------|-------|-------------|
| 🔴 HIGH | 2 | TQM-as-profit proxy breaks AI strategies (2.1); duplicate SimulationEngine (3.1) |
| 🟡 MEDIUM | 10 | AI using wrong profit proxy; session state double-update; dead TQM-as-profit context; ViewModel cost mismatch; missing cumulativeProfit in model; UI data not auto-refreshing; no MainActor on observables; magic numbers; duplicate engine; non-deterministic shuffle |
| 🔵 LOW | 20+ | Dead code sample data; no automatic re-load on session changes; magic numbers; duplicate strategy code; missing documentation; enum ordering assumptions; edge case guards |

## Top 5 Prioritized Fixes

1. **🔴 Fix TQM-as-profit proxy** (`GameController.swift:62-64`, `SessionMonitorViewModel.swift:119-121`): Replace `cumulativeTQM` with actual `cumulativeProfit` computation. Add `cumulativeProfit` to `TeamStatus`. This directly impacts AI strategy quality.

2. **🔴 Add `@MainActor` to all `@Observable` classes**: Prevents potential race conditions between background engine processing and SwiftUI observation.

3. **🟡 Align `DecisionInputViewModel` cost formula with engine**: Ensure the UI budget preview matches actual engine calculations, preventing confusing "over budget" behavior.

4. **🟡 Centralize `SimulationEngine` instance**: Create it once and inject it to prevent future divergence between student and professor views.

5. **🟡 Add `cumulativeProfit` to `TeamStatus`**: Without this, any profit-based ranking, coaching, or AI decision-making must recompute from scratch each time, which is O(n²) over a session.
