# RCA Part 1: Data Model Mismatch Analysis

**Date:** 2026-07-16  
**Scope:** Field-by-field mapping of `RoundResult` data flow: iOS Swift model → Backend Pydantic model → `restoreResultsFromBackend` conversion → computed properties → UI display.  
**Files analyzed:**
- `Practenture/Models/SimulationModels.swift` (1577 lines)
- `Practenture/Services/NetworkService.swift` (1125 lines)
- `Practenture/Models/SimulationSession.swift` (904 lines)
- `backend/models.py` (756 lines)
- `backend/simulation_engine.py` (1260 lines)

---

## Executive Summary

The iOS `RoundResult` struct (28+ stored fields across revenue, costs, operations, and financials) is fundamentally incompatible with the backend `RoundResult` Pydantic model (25 flat fields). The backend produces a **subset** of the iOS model's data, and the `restoreResultsFromBackend` conversion function in `SimulationSession.swift` **fabricates** the missing fields using hardcoded heuristics, arbitrary ratios, and zero-fill defaults. This results in:

- **16 fields** that are lost, zeroed, or incorrectly recomputed during backend→iOS restoration
- **4 fields** where the mapping is semantically wrong (different meaning assigned to same field)
- **3 enum serialization mismatches** that cause silent decoding failures or wrong values
- A critical `creditRating` reconstruction bug that produces incorrect letter grades
- Revenue channel splitting based on arbitrary fixed ratios with no basis in actual channel performance
- Unit-cost figures fabricated from price division, not actual sales data

---

## 1. iOS `RoundResult` Struct — Complete Field Inventory

**Source:** `SimulationModels.swift` lines 936–1079

| # | Field | Type | Source Line | Category |
|---|-------|------|------------|----------|
| 1 | `id` | UUID | 937 | Identity |
| 2 | `teamId` | UUID | 938 | Identity |
| 3 | `round` | Int | 939 | Identity |
| 4 | `wholesaleRevenue` | Double | 942 | Revenue |
| 5 | `internetRevenue` | Double | 943 | Revenue |
| 6 | `amazonRevenue` | Double | 944 | Revenue |
| 7 | `privateLabelRevenue` | Double | 945 | Revenue |
| 8 | `productionCosts` | Double | 949 | Cost |
| 9 | `marketingCosts` | Double | 950 | Cost |
| 10 | `csrCosts` | Double | 951 | Cost |
| 11 | `endorsementCosts` | Double | 952 | Cost |
| 12 | `interestExpense` | Double | 953 | Cost |
| 13 | `dividendsPaid` | Double | 954 | Cost |
| 14 | `workforceCosts` | Double | 955 | Cost |
| 15 | `storageCosts` | Double | 956 | Cost |
| 16 | `rebateCosts` | Double | 957 | Cost |
| 17 | `deliveryCosts` | Double | 958 | Cost |
| 18 | `socialMediaCosts` | Double | 959 | Cost |
| 19 | `amazonFees` | Double | 960 | Cost |
| 20 | `overrideProfit` | Double? | 965 | Override |
| 21 | `wholesaleUnitsSold` | Int | 1010 | Operations |
| 22 | `internetUnitsSold` | Int | 1011 | Operations |
| 23 | `amazonUnitsSold` | Int | 1012 | Operations |
| 24 | `privateLabelUnitsSold` | Int | 1013 | Operations |
| 25 | `marketShare` | Double | 1015 | Operations |
| 26 | `customerSatisfaction` | Double | 1016 | Operations |
| 27 | `inventory` | Int | 1017 | Operations |
| 28 | `rejectionRate` | Double | 1018 | Operations |
| 29 | `cash` | Double | 1021 | Financial |
| 30 | `sqRating` | Double | 1024 | Brand |
| 31 | `awarenessScore` | Double | 1025 | Brand |
| 32 | `qualityScore` | Double | 1026 | Brand (computed) |
| 33 | `scorecard` | InvestorScorecard | 1029 | Scorecard |

**iOS Computed Properties (no backend equivalent):**
- `revenue` = `wholesaleRevenue + internetRevenue + amazonRevenue + privateLabelRevenue` (line 946)
- `costs` = sum of all 12 cost fields (lines 1002–1006)
- `profit` = `overrideProfit ?? (revenue - costs)` (line 1007)
- `unitsSold` = sum of 4 channel unit fields (line 1014)

### iOS `InvestorScorecard` Sub-Struct (lines 892–931)

| # | Field | Type |
|---|-------|------|
| 1 | `round` | Int |
| 2 | `eps` | Double |
| 3 | `roe` | Double |
| 4 | `stockPrice` | Double |
| 5 | `imageRating` | Double |
| 6 | `creditRating` | CreditRating (enum) |
| 7 | `epsScore` | Double |
| 8 | `roeScore` | Double |
| 9 | `stockPriceScore` | Double |
| 10 | `imageScore` | Double |
| 11 | `creditScore` | Double |
| — | `totalScore` | Double (computed: sum of 5 scores) |

---

## 2. Backend `RoundResult` Pydantic Model — Complete Field Inventory

**Source:** `backend/models.py` lines 391–421

| # | Field | Type | Default | Source Line |
|---|-------|------|---------|------------|
| 1 | `teamId` | str | (required) | 392 |
| 2 | `round` | int | (required) | 393 |
| 3 | `revenue` | float | 0.0 | 394 |
| 4 | `costs` | float | 0.0 | 395 |
| 5 | `profit` | float | 0.0 | 396 |
| 6 | `marketShare` | float | 0.0 | 397 |
| 7 | `sqRating` | float | 0.0 | 398 |
| 8 | `reputation` | float | 0.0 | 399 |
| 9 | `cumulativeProfit` | float | 0.0 | 400 |
| 10 | `cash` | float | 0.0 | 401 |
| 11 | `inventory` | float | 0.0 | 402 |
| 12 | `equity` | float | 0.0 | 403 |
| 13 | `debt` | float | 0.0 | 404 |
| 14 | `sharesOutstanding` | float | 0.0 | 405 |
| 15 | `eps` | float | 0.0 | 406 |
| 16 | `roe` | float | 0.0 | 407 |
| 17 | `stockPrice` | float | 0.0 | 408 |
| 18 | `epsScore` | float | 0.0 | 410 |
| 19 | `roeScore` | float | 0.0 | 411 |
| 20 | `stockPriceScore` | float | 0.0 | 412 |
| 21 | `imageScore` | float | 0.0 | 413 |
| 22 | `awarenessScore` | float | 0.0 | 414 |
| 23 | `creditScore` | float | 0.0 | 415 |
| 24 | `totalScore` | float | 0.0 | 416 |
| 25 | `productionCost` | float | 0.0 | 418 |
| 26 | `marketingCost` | float | 0.0 | 419 |
| 27 | `unitCost` | float | 0.0 | 420 |
| 28 | `demand` | Dict[str, float] | {} | 421 |

### Backend `process_round` Result Construction

**Source:** `simulation_engine.py` lines 1201–1236

The backend constructs `RoundResult` with these values:
```python
result = RoundResult(
    teamId=tid,
    round=round_num,
    revenue=round(total_revenue, 2),         # w_rev + i_rev + amazon_rev + pl_rev
    costs=round(total_costs, 2),              # all costs combined
    profit=round(profit, 2),
    marketShare=round(market_share, 4),
    sqRating=round(sq, 2),
    reputation=round(new_reputation, 2),
    cumulativeProfit=round(cumulative_profit, 2),
    cash=round(new_cash, 2),
    inventory=round(ending_inventory, 2),     # NOTE: float, not int
    equity=round(new_equity, 2),
    debt=round(new_debt, 2),
    sharesOutstanding=round(new_shares, 2),  # NOTE: float, not int
    eps=round(eps, 4),
    roe=round(roe, 4),
    stockPrice=round(stock_price, 2),
    epsScore=scorecard["epsScore"],
    roeScore=scorecard["roeScore"],
    stockPriceScore=scorecard["stockPriceScore"],
    imageScore=scorecard["imageScore"],
    awarenessScore=round(awareness_score, 4),
    creditScore=scorecard["creditScore"],
    totalScore=scorecard["totalScore"],
    productionCost=round(total_prod_cost, 2),
    marketingCost=round(marketing_cost, 2),
    unitCost=round(unit_cost, 2),
    demand={...},                             # per-channel units
)
```

**Fields computed by the engine but NOT in the Pydantic model:**
- `imageRating` (the actual 0-100 image rating) — the engine computes `image_rating` at line 1148 but **never sends it** in the RoundResult. Only `imageScore` (the 0-20 investor subscore) is sent.
- `creditRating` (the actual letter grade) — the engine computes `credit_rating` at line 1128 but **never sends it** in the RoundResult. Only `creditScore` (the 0-20 investor subscore) is sent.
- `customerSatisfaction` — computed at line 1135, never sent.
- `rejectionRate` — computed at line 934, never sent.
- Channel-level revenue breakdown (wholesale/internet/amazon/privateLabel) — computed individually but only the aggregate `revenue` is sent.
- Channel-level units sold — sent only in the `demand` dict, not as top-level fields.
- `endorsementCosts`, `workforceCosts`, `csrCosts`, `storageCosts`, `rebateCosts`, `deliveryCosts`, `socialMediaCosts`, `amazonFees`, `interestExpense`, `dividendsPaid` — all computed individually but **not sent**; only the aggregate `costs` and two sub-costs (`productionCost`, `marketingCost`) are in the model.

---

## 3. `RoundResultBackend` — iOS Wire DTO

**Source:** `NetworkService.swift` lines 774–801

This is the Codable struct the iOS app uses to decode the JSON response from the backend.

| # | Field | Type | Default | Line |
|---|-------|------|---------|------|
| 1 | `teamId` | String | "" | 775 |
| 2 | `round` | Int | 0 | 776 |
| 3 | `revenue` | Double | 0 | 777 |
| 4 | `costs` | Double | 0 | 778 |
| 5 | `profit` | Double | 0 | 779 |
| 6 | `marketShare` | Double | 0 | 780 |
| 7 | `sqRating` | Double | 0 | 781 |
| 8 | `reputation` | Double | 0 | 782 |
| 9 | `cumulativeProfit` | Double | 0 | 783 |
| 10 | `cash` | Double | 0 | 784 |
| 11 | `inventory` | Double | 0 | 785 |
| 12 | `equity` | Double | 0 | 786 |
| 13 | `debt` | Double | 0 | 787 |
| 14 | `sharesOutstanding` | Double | 0 | 788 |
| 15 | `eps` | Double | 0 | 789 |
| 16 | `roe` | Double | 0 | 790 |
| 17 | `stockPrice` | Double | 0 | 791 |
| 18 | `epsScore` | Double | 0 | 792 |
| 19 | `roeScore` | Double | 0 | 793 |
| 20 | `stockPriceScore` | Double | 0 | 794 |
| 21 | `imageScore` | Double | 0 | 795 |
| 22 | `creditScore` | Double | 0 | 796 |
| 23 | `totalScore` | Double | 0 | 797 |
| 24 | `productionCost` | Double | 0 | 798 |
| 25 | `marketingCost` | Double | 0 | 799 |
| 26 | `unitCost` | Double | 0 | 800 |

**⚠️ MISSING from `RoundResultBackend` but present in backend Pydantic model:**
- `awarenessScore` (backend model line 414) — the iOS wire DTO does not decode this field
- `demand` dict (backend model line 421) — the iOS wire DTO does not decode this field

**Impact:** Even though the backend sends `awarenessScore` and `demand` data, the iOS app silently drops them during JSON decoding because `RoundResultBackend` doesn't have matching fields. Swift's `Codable` ignores unknown keys by default.

---

## 4. `restoreResultsFromBackend` — Field-by-Field Mapping

**Source:** `SimulationSession.swift` lines 737–823

This function converts `[Int: [RoundResultBackend]]` → local `RoundResult` objects and records them via `recordResult()`.

### 4.1 Revenue Fields

| iOS `RoundResult` Field | Backend `RoundResultBackend` Source | `restoreResultsFromBackend` Mapping | Computed Property | Displayed Value | Mismatch? |
|---|---|---|---|---|---|
| `wholesaleRevenue` | `backendResult.revenue` | `revenue * 0.5` (line 774) | — | 50% of total revenue | 🔴 **FABRICATED** — Backend sends only aggregate `revenue`. The 50/30/15/5 split is hardcoded with no basis in actual channel performance. |
| `internetRevenue` | `backendResult.revenue` | `revenue * 0.3` (line 775) | — | 30% of total revenue | 🔴 **FABRICATED** — Same arbitrary ratio. |
| `amazonRevenue` | `backendResult.revenue` | `revenue * 0.15` (line 776) | — | 15% of total revenue | 🔴 **FABRICATED** — Same arbitrary ratio. |
| `privateLabelRevenue` | `backendResult.revenue` | `revenue * 0.05` (line 777) | — | 5% of total revenue | 🔴 **FABRICATED** — Same arbitrary ratio. |
| `revenue` (computed) | — | — | `wholesaleRevenue + internetRevenue + amazonRevenue + privateLabelRevenue` | Sum of fabricated splits = original total ✅ | The computed sum equals the backend value, but individual channels are wrong. |

### 4.2 Cost Fields

| iOS `RoundResult` Field | Backend `RoundResultBackend` Source | `restoreResultsFromBackend` Mapping | Computed Property | Displayed Value | Mismatch? |
|---|---|---|---|---|---|
| `productionCosts` | `backendResult.productionCost` | Direct map (line 778) | — | ✅ Correct | ✅ OK |
| `marketingCosts` | `backendResult.marketingCost` | Direct map (line 779) | — | ✅ Correct | ✅ OK |
| `csrCosts` | — | `0` (line 780) | — | Always zero | 🔴 **ZEROED** — Backend computes `csr_cost` (engine line 1016) but does not send it. iOS shows $0. |
| `endorsementCosts` | — | `0` (line 781) | — | Always zero | 🔴 **ZEROED** — Backend computes `endorse_cost` (engine line 1019) but does not send it. iOS shows $0. |
| `interestExpense` | `backendResult.equity` | `equity * 0.05` (line 782) | — | 5% of equity | 🔴 **FABRICATED** — Backend computes `interest_expense = debt * interest_rate` (engine line 1079) but doesn't send it. iOS uses `equity * 0.05` — wrong base (equity vs debt) and wrong rate. |
| `dividendsPaid` | — | `0` (line 783) | — | Always zero | 🔴 **ZEROED** — Backend computes `dividends_paid` (engine line 1087) but does not send it. iOS shows $0. |
| `workforceCosts` | — | `0` (line 784) | — | Always zero | 🔴 **ZEROED** — Backend computes `workforce_costs` (engine line 1010) but does not send it. iOS shows $0. |
| `storageCosts` | — | `0` (line 785) | — | Always zero | 🔴 **ZEROED** — Backend computes `storage_costs` (engine line 1060) but does not send it. iOS shows $0. |
| `rebateCosts` | — | `0` (line 786) | — | Always zero | 🔴 **ZEROED** — Backend computes `rebate_costs` (engine line 1050) but does not send it. iOS shows $0. |
| `deliveryCosts` | — | `0` (line 787) | — | Always zero | 🔴 **ZEROED** — Backend computes `delivery_costs` (engine line 1053) but does not send it. iOS shows $0. |
| `socialMediaCosts` | — | `0` (line 788) | — | Always zero | 🔴 **ZEROED** — Backend computes `social_media_total_cost` (engine line 1039) but does not send it. iOS shows $0. |
| `amazonFees` | — | `0` (line 789) | — | Always zero | 🔴 **ZEROED** — Backend computes `total_amazon_fees` (engine line 1046) but does not send it. iOS shows $0. |
| `costs` (computed) | `backendResult.costs` | — | Sum of all 12 cost fields | **WRONG** — sum of 2 correct + 10 zeroed/fabricated | 🔴 **INCORRECTLY RECOMPUTED** — The `costs` computed property sums all 12 cost fields. Since 10 of them are zeroed or fabricated, the computed `costs` ≠ backend `costs`. |
| `profit` (computed) | `backendResult.profit` | — | `overrideProfit ?? (revenue - costs)` | Uses override | ⚠️ **OVERRIDE SAVES IT** — `overrideProfit` is set to `backendResult.profit` (line 802), so `profit` returns the backend value. But if any code path uses `costs` directly, it gets the wrong number. |

### 4.3 Operations Fields

| iOS `RoundResult` Field | Backend `RoundResultBackend` Source | `restoreResultsFromBackend` Mapping | Computed Property | Displayed Value | Mismatch? |
|---|---|---|---|---|---|
| `wholesaleUnitsSold` | — | `max(0, Int(revenue / 50))` (line 790) | — | Revenue ÷ $50 | 🔴 **FABRICATED** — Backend sends `demand["wholesale"]` (actual units) but iOS doesn't decode it. Instead, it divides total revenue by $50 to guess units. |
| `internetUnitsSold` | — | `max(0, Int(revenue / 90 * 0.3))` (line 791) | — | (Revenue ÷ $90) × 30% | 🔴 **FABRICATED** — Divides total revenue by $90 (the default internet price), then applies 30%. No relation to actual sales. |
| `amazonUnitsSold` | — | `max(0, Int(revenue / 85 * 0.15))` (line 792) | — | (Revenue ÷ $85) × 15% | 🔴 **FABRICATED** — Divides total revenue by $85 (default amazon price), then applies 15%. |
| `privateLabelUnitsSold` | — | `0` (line 793) | — | Always zero | 🔴 **ZEROED** — Backend sends `demand["privateLabel"]` but iOS doesn't decode it. |
| `unitsSold` (computed) | — | — | Sum of 4 channel unit fields | Sum of fabricated values | 🔴 **INCORRECTLY RECOMPUTED** |
| `marketShare` | `backendResult.marketShare` | Direct map (line 794) | — | ✅ Correct | ✅ OK |
| `customerSatisfaction` | `backendResult.reputation` | Direct map (line 795) | — | Backend's `reputation` value | 🔴 **SEMANTIC MISMATCH** — Backend `reputation` is an EMA (0.7*prev + 0.3*satisfaction, engine line 1145). iOS maps it to `customerSatisfaction`, which is a different metric (computed from S/Q, price fairness, supply adequacy). The displayed "Customer Satisfaction" will show reputation, not satisfaction. |
| `inventory` | `backendResult.inventory` | `Int(backendResult.inventory)` (line 796) | — | Backend inventory truncated to Int | ⚠️ **TYPE COERCION** — Backend sends `Float`, iOS stores `Int`. Fractional units lost. Minor but technically lossy. |
| `rejectionRate` | — | `0` (line 797) | — | Always zero | 🔴 **ZEROED** — Backend computes `rejection_rate` (engine line 934) but does not send it. iOS shows 0%. |

### 4.4 Financial & Brand Fields

| iOS `RoundResult` Field | Backend `RoundResultBackend` Source | `restoreResultsFromBackend` Mapping | Computed Property | Displayed Value | Mismatch? |
|---|---|---|---|---|---|
| `cash` | `backendResult.cash` | Direct map (line 798) | — | ✅ Correct | ✅ OK |
| `sqRating` | `backendResult.sqRating` | Direct map (line 799) | — | ✅ Correct | ✅ OK |
| `awarenessScore` | — | `0` (line 800) | — | Always zero | 🔴 **ZEROED** — Backend computes `awareness_score` (engine line 1160) and includes it in the Pydantic model (line 414), but `RoundResultBackend` (the iOS wire DTO) doesn't have the field, so it's silently dropped. `restoreResultsFromBackend` hardcodes 0. |

### 4.5 InvestorScorecard Fields

| iOS Scorecard Field | Backend `RoundResultBackend` Source | `restoreResultsFromBackend` Mapping | Displayed Value | Mismatch? |
|---|---|---|---|---|
| `eps` | `backendResult.eps` | Direct map (line 759) | ✅ Correct | ✅ OK |
| `roe` | `backendResult.roe` | Direct map (line 760) | ✅ Correct | ✅ OK |
| `stockPrice` | `backendResult.stockPrice` | Direct map (line 761) | ✅ Correct | ✅ OK |
| `imageRating` | `backendResult.imageScore` | `imageScore` mapped to `imageRating` (line 762) | 🔴 **WRONG SCALE** — Backend `imageScore` is the 0–20 investor subscore. iOS maps it to `imageRating`, which should be the 0–100 absolute image rating. The scorecard displays a 0–20 value where 0–100 is expected. | 🔴 **SEMANTIC MISMATCH** — The backend computes `image_rating` (0–100, engine line 1148) but never sends it in RoundResult. Only `imageScore` (0–20, engine line 509) is sent. iOS incorrectly maps `imageScore` → `imageRating`. |
| `creditRating` | `backendResult.creditScore` | `CreditRating(rawValue: "\(Int(creditScore))") ?? .a` (line 763) | 🔴 **BROKEN** — See below | 🔴 **CRITICAL BUG** — See §4.5.1 |
| `epsScore` | `backendResult.epsScore` | Direct map (line 764) | ✅ Correct | ✅ OK |
| `roeScore` | `backendResult.roeScore` | Direct map (line 765) | ✅ Correct | ✅ OK |
| `stockPriceScore` | `backendResult.stockPriceScore` | Direct map (line 766) | ✅ Correct | ✅ OK |
| `imageScore` | `backendResult.imageScore` | Direct map (line 767) | ✅ Correct | ✅ OK |
| `creditScore` | `backendResult.creditScore` | Direct map (line 768) | ✅ Correct | ✅ OK |
| `totalScore` (computed) | `backendResult.totalScore` | — | Sum of 5 subscores | ✅ Correct (computed from correct subscores) |

#### 4.5.1 CreditRating Reconstruction Bug (CRITICAL)

**Code (line 763):**
```swift
CreditRating(rawValue: "\(Int(backendResult.creditScore))") ?? .a
```

**The Bug:** `creditScore` is a numeric score (0–20 scale, from `CreditRating.investor_score` property). The code converts this to an Int, stringifies it, and tries to match it against `CreditRating` rawValues which are letter grades like `"A+"`, `"A"`, `"B+"`, etc.

**Example:** If `creditScore = 18.0` (which means credit rating "A"), the code does:
1. `Int(18.0)` → `18`
2. `"\(18)"` → `"18"`
3. `CreditRating(rawValue: "18")` → `nil` (no case has rawValue "18")
4. Falls back to `?? .a` → **always returns "A"**

**Impact:** For ANY `creditScore` value, the reconstructed `creditRating` is **always "A"** because no numeric string can match a letter-grade rawValue. The fallback `?? .a` fires every time.

This means:
- The `TeamStatus.creditRating` field is always set to `.a` after backend restore (line 518 in `recordResult`)
- The UI always shows "A" credit rating regardless of actual financial health
- The `creditRating` displayed in the investor scorecard is wrong

---

## 5. `recordResult` — Team Status Update Mapping

**Source:** `SimulationSession.swift` lines 503–528

After `restoreResultsFromBackend` creates the `RoundResult`, `recordResult` updates the `TeamStatus`:

| TeamStatus Field | Source | Line | Mismatch? |
|---|---|---|---|
| `cash` | `result.cash` | 514 | ✅ OK (from backend) |
| `inventory` | `result.inventory` | 515 | ✅ OK (from backend, Int-truncated) |
| `sqRating` | `result.sqRating` | 516 | ✅ OK (from backend) |
| `imageRating` | `result.scorecard.imageRating` | 517 | 🔴 **WRONG** — `imageRating` in the scorecard is actually `imageScore` (0–20), not the real image rating (0–100). TeamStatus.imageRating shows 0–20 instead of 0–100. |
| `creditRating` | `result.scorecard.creditRating` | 518 | 🔴 **ALWAYS "A"** — Due to the CreditRating reconstruction bug (§4.5.1). |
| `cumulativeInvestorScore` | Recomputed: `(prevTotal + result.scorecard.totalScore) / roundsScored` | 521–523 | ✅ OK (totalScore comes from backend) |
| `cumulativeProfit` | `+= result.profit` | 526 | ⚠️ **DOUBLE COUNT RISK** — Backend already sends `cumulativeProfit` in the result, but `recordResult` ignores it and recomputes by adding `result.profit`. If the backend's `profit` per round is correct, the cumulative will be correct. But it ignores the backend's own `cumulativeProfit` field. |

### Fields NOT updated by `recordResult` (lost on restore):

| TeamStatus Field | iOS Local Engine Sets It | Backend Sends It | After Restore | Mismatch? |
|---|---|---|---|---|
| `equity` | ✅ (via `applyRoundOutput`) | ✅ `backendResult.equity` | ❌ **NOT RESTORED** — `recordResult` doesn't touch `equity`. `restoreResultsFromBackend` doesn't set it. Stays at initial value. | 🔴 **LOST** |
| `totalDebt` | ✅ (via `applyRoundOutput`) | ✅ `backendResult.debt` | ❌ **NOT RESTORED** | 🔴 **LOST** |
| `sharesOutstanding` | ✅ (via `applyRoundOutput`) | ✅ `backendResult.sharesOutstanding` | ❌ **NOT RESTORED** | 🔴 **LOST** |
| `cumulativeRD` | ✅ (via `applyRoundOutput`) | ❌ Not sent | ❌ **NOT RESTORED** | 🔴 **LOST** |
| `cumulativeMarketing` | ✅ (via `applyRoundOutput`) | ❌ Not sent | ❌ **NOT RESTORED** | 🔴 **LOST** |
| `cumulativeCSR` | ✅ (via `applyRoundOutput`) | ❌ Not sent | ❌ **NOT RESTORED** | 🔴 **LOST** |
| `cumulativeTQM` | ✅ (via `applyRoundOutput`) | ❌ Not sent | ❌ **NOT RESTORED** | 🔴 **LOST** |
| `reputation` | ✅ (via `applyRoundOutput`) | ✅ `backendResult.reputation` | ❌ **NOT RESTORED** — `recordResult` doesn't update `reputation`. | 🔴 **LOST** |
| `roundsScored` | ✅ (via `applyRoundOutput`) | ❌ Not sent | ⚠️ Partially restored — `recordResult` increments it (line 522) | ⚠️ Reconstructed from count of restored rounds, which is correct if all rounds are present. |

---

## 6. Enum Serialization Mismatches

### 6.1 ScoringMetric

| iOS Enum | iOS rawValue | Backend Enum | Backend value |
|---|---|---|---|
| `.investorScore` | `"investorScore"` | `ScoringMetric.investorScore` | `"investor_score"` |
| `.cumulativeProfit` | `"cumulativeProfit"` | `ScoringMetric.cumulativeProfit` | `"cumulative_profit"` |
| `.revenue` | `"revenue"` | `ScoringMetric.revenue` | `"revenue"` |
| `.composite` | `"composite"` | `ScoringMetric.composite` | `"composite"` |

🔴 **MISMATCH:** iOS uses camelCase rawValues; backend uses snake_case values. When the backend sends `"investor_score"`, the iOS `Codable` decoder cannot match it to `"investorScore"`, causing a **decoding failure** for the `scoringMetric` field in `SessionConfiguration`. This means the session config decoded from backend will fall back to the default (`.investorScore`), which happens to be correct by accident — but `.cumulativeProfit` sessions would silently revert to `.investorScore`.

### 6.2 CelebrityEndorsement

| iOS Enum | iOS rawValue | Backend Enum | Backend value |
|---|---|---|---|
| `.none` | `"none"` | `CelebrityEndorsement.none` | `"none"` |
| `.local` | `"local"` | `CelebrityEndorsement.local` | `"local"` |
| `.national` | `"national"` | `CelebrityEndorsement.national` | `"national"` |
| `.global` | `"global"` | `CelebrityEndorsement.global_` | `"global"` |

✅ **OK at the value level** — The backend enum member is named `global_` (to avoid the Python keyword `global`), but its **value** is `"global"` (line 71 of models.py: `global_ = "global"`). So when serialized to JSON, it sends `"global"`, which matches the iOS rawValue. The iOS `toBackendDecision()` sends `celebrityEndorsement.rawValue` (line 1049), which would be `"global"` — the backend can decode this.

**However**, the iOS `toBackendDecision()` also sends `celebrityType` (line 1048), which uses a different mapping:
- `.none` → `"none"`, `.local` → `"athlete"`, `.national` → `"musician"`, `.global` → `"actor"`

The backend's `translate_legacy_payload` validator (models.py lines 297–307) maps these back:
- `"athlete"` → `local`, `"musician"` → `national`, `"actor"` → `global_`

This double-sending (both `celebrityEndorsement` and `celebrityType`) works because the validator prefers `celebrityEndorsement` when present (line 297: `if "celebrityEndorsement" not in data and "celebrityType" in data`). ✅ Functionally correct but fragile.

### 6.3 InfluencerTier

| iOS Enum | iOS rawValue | Backend Enum | Backend value | iOS `backendValue` (NetworkService) |
|---|---|---|---|---|
| `.none` | `"none"` | `InfluencerTier.none` | `"none"` | `"none"` |
| `.nano` | `"nano"` | `InfluencerTier.nano` | `"nano"` | `"social_influencer"` 🔴 |
| `.micro` | `"micro"` | `InfluencerTier.micro` | `"micro"` | `"social_influencer"` 🔴 |
| `.macro` | `"macro"` | `InfluencerTier.macro` | `"macro"` | `"social_influencer"` 🔴 |
| `.mega` | `"mega"` | `InfluencerTier.mega` | `"mega"` | `"social_influencer"` 🔴 |

🔴 **MISMATCH:** The iOS `InfluencerTier.backendValue` extension (NetworkService.swift lines 1001–1010) maps ALL non-none tiers to `"social_influencer"`, but the backend expects `"nano"`, `"micro"`, `"macro"`, `"mega"`. The backend will fail to decode `"social_influencer"` as an `InfluencerTier` enum value, causing a **422 validation error** on decision submission.

**However**, `toBackendDecision()` (line 1062) actually sends `influencerTier.rawValue` (not `backendValue`), so the correct value IS sent. The `backendValue` extension appears to be **dead code** — it's never used in the actual conversion path. This is a latent bug that would activate if someone refactored to use `backendValue`.

### 6.4 DeliveryTime

| iOS Enum | iOS rawValue | Backend Enum | Backend value | iOS `backendValue` (NetworkService) |
|---|---|---|---|---|
| `.standard` | `"standard"` | `DeliveryTime.standard` | `"standard"` | `"fbm"` 🔴 |
| `.rush` | `"rush"` | `DeliveryTime.rush` | `"rush"` | `"fbm"` 🔴 |

🔴 **MISMATCH:** The iOS `DeliveryTime.backendValue` extension (NetworkService.swift lines 1013–1019) maps BOTH cases to `"fbm"` (a FulfillmentMethod value, not a DeliveryTime value). The backend expects `"standard"` or `"rush"`.

**However**, `toBackendDecision()` (line 1052) sends `deliveryTime.rawValue` (not `backendValue`), so the correct value IS sent. Same as InfluencerTier — the `backendValue` extension is dead code with wrong mappings.

---

## 7. `PlayerDecision` Conversion Mismatches

### 7.1 iOS → Backend (`toBackendDecision()`)

**Source:** NetworkService.swift lines 1031–1078

| iOS Field | Backend DTO Field | Mapping | Mismatch? |
|---|---|---|---|
| `pricing.wholesalePrice` | `wholesalePrice` | Direct | ✅ OK |
| `pricing.internetPrice` | `internetPrice` | Direct | ✅ OK |
| `pricing.amazonPrice` | `amazonPrice` | Direct | ✅ OK |
| `pricing.privateLabelBidPrice` | `privateLabelBidPrice` | Direct | ✅ OK |
| `pricing.privateLabelMaxUnits` | `privateLabelMaxUnits` | Direct | ✅ OK |
| `pricing.amazonAdBudget` | `amazonAdBudget` | Direct | ✅ OK |
| `materialsQuality` | `materialsQuality` | `backendValue` (0.5 or 1.0) | ⚠️ **TYPE MISMATCH** — iOS sends `Double` (0.5/1.0), backend expects `MaterialsQuality` enum. Backend's `translate_legacy_payload` validator handles this (lines 284–290), so it works, but the DTO field type is `Double` while the backend model field is `MaterialsQuality`. |
| `product.stylingBudget` | `stylingBudget` | Direct | ✅ OK |
| `product.modelsOffered` | `numModels` + `modelsOffered` | Both sent | ✅ OK (redundant but handled) |
| `product.tqmInvestment` | `tqmInvestment` | Direct | ✅ OK |
| `rdInvestment` (computed) | `rdInvestment` | `stylingBudget + tqmInvestment` | ⚠️ **Redundant** — backend doesn't use this field (models.py line 380: "not used in iOS engine") |
| `marketing.advertisingBudget` | `marketingInvestment` + `advertisingBudget` | Both sent, both = same value | ⚠️ **Redundant** — `marketingInvestment` is unused by the engine |
| `celebrityEndorsement` | `celebrityType` + `celebrityEndorsement` | Both sent (different encodings) | ✅ OK (validator prefers `celebrityEndorsement`) |
| `marketing.retailOutlets` | `retailOutlets` | Direct | ✅ OK |
| `marketing.mailInRebate` | `mailInRebate` | Direct | ✅ OK |
| `marketing.deliveryTime` | `deliveryTime` | `rawValue` | ✅ OK |
| `marketing.freeShippingThreshold` | `freeShippingThreshold` | Direct | ✅ OK |
| `tiktokBudget` | `socialMediaBudget.tiktok` + `tiktokBudget` | Both sent | ✅ OK |
| `instagramBudget` | `socialMediaBudget.instagram` + `instagramBudget` | Both sent | ✅ OK |
| `youtubeBudget` | `socialMediaBudget.youtube` + `youtubeBudget` | Both sent | ✅ OK |
| `influencerTier` | `influencerTier` | `rawValue` | ✅ OK |
| `workforce.baseWage` | `baseWage` | Direct | ✅ OK |
| `workforce.incentivePay` | `incentivePay` | Direct | ⚠️ **UNIT MISMATCH** — iOS default is `0.50` (dollars per unit). Backend default is `0.50` with comment "per-unit incentive" (models.py line 363). But the engine uses `d.incentivePay * gross_production` (line 1008), treating it as per-unit. iOS UI may present this differently. |
| `workforce.trainingHours` | `trainingBudget` + `trainingHours` | `trainingBudget = trainingHours * 50` | ✅ OK (validator converts back) |
| `workforce.bestPracticesInvestment` | `bestPracticesInvestment` | Direct | ✅ OK |
| `production.productionQuantity` | `productionQuantity` | Direct | ✅ OK |
| `production.overtimePercent` | `overtimePercent` | `Int(overtimePercent)` | ⚠️ **TYPE COERCION** — iOS `Double` → backend `Int`. Truncates fractional overtime. |
| `finance.csrInvestment` | `csrInvestment` | Direct | ✅ OK |
| `finance.dividendsPerShare` | `dividendsPerShare` | Direct | ✅ OK |
| `finance.newLoanAmount` | `newLoanAmount` | Direct | ✅ OK |
| `finance.sharesBuyback` | `sharesBuyback` | Direct | ✅ OK |
| `finance.sharesIssued` | `sharesIssued` | Direct | ✅ OK |
| `fulfillmentMethod` | `fulfillmentMethod` | `backendValue` | ✅ OK |
| — | `internetPromotion` | Hardcoded `0` | ✅ OK (unused) |

### 7.2 Backend → iOS (`toPlayerDecision()`)

**Source:** NetworkService.swift lines 1081–1125

| Backend DTO Field | iOS Field | Mapping | Mismatch? |
|---|---|---|---|
| `wholesalePrice` | `pricing.wholesalePrice` | Direct | ✅ OK |
| `internetPrice` | `pricing.internetPrice` | Direct | ✅ OK |
| — | `pricing.privateLabelBidPrice` | `wholesalePrice * 0.6` (line 1089) | 🔴 **FABRICATED** — Actual `privateLabelBidPrice` from backend is ignored; hardcoded as 60% of wholesale price. |
| — | `pricing.privateLabelMaxUnits` | `50` (line 1090) | 🔴 **HARDCODED** — Always 50 regardless of actual value. |
| — | `pricing.amazonAdBudget` | `0` (line 1092) | 🔴 **ZEROED** — Actual `amazonAdBudget` from backend is ignored. |
| `materialsQuality` (Double) | `product.materialsQuality` | `> 0.75 ? .superior : .standard` (line 1095) | ✅ OK (reverse of the forward mapping) |
| `stylingBudget` | `product.stylingBudget` | Direct | ✅ OK |
| `numModels` | `product.modelsOffered` | `max(1, numModels)` (line 1097) | ⚠️ **Prefers legacy field** — Uses `numModels` instead of `modelsOffered`. If only `modelsOffered` was sent (modern path), this defaults to 3. |
| `tqmInvestment` | `product.tqmInvestment` | Direct | ✅ OK |
| `advertisingBudget` | `marketing.advertisingBudget` | Direct | ✅ OK |
| `socialMediaBudget.tiktok` | `marketing.tiktokBudget` | Direct | ✅ OK |
| `socialMediaBudget.instagram` | `marketing.instagramBudget` | Direct | ✅ OK |
| `socialMediaBudget.youtube` | `marketing.youtubeBudget` | Direct | ✅ OK |
| — | `marketing.celebrityEndorsement` | Default `.none` | 🔴 **LOST** — Not decoded. Always defaults to `.none`. |
| — | `marketing.retailOutlets` | Default `20` | 🔴 **LOST** — Not decoded. Always defaults to 20. |
| — | `marketing.mailInRebate` | Default `0` | 🔴 **LOST** — Not decoded. Always defaults to 0. |
| — | `marketing.deliveryTime` | Default `.standard` | 🔴 **LOST** — Not decoded. Always defaults to `.standard`. |
| — | `marketing.freeShippingThreshold` | Default `100` | 🔴 **LOST** — Not decoded. Always defaults to 100. |
| — | `marketing.influencerTier` | Default `.none` | 🔴 **LOST** — Not decoded. Always defaults to `.none`. |
| `baseWage` | `workforce.baseWage` | Direct | ✅ OK |
| `incentivePay` | `workforce.incentivePay` | Direct | ✅ OK |
| `trainingBudget / 50` | `workforce.trainingHours` | Reverse of forward mapping (line 1109) | ⚠️ **LOSSY** — Division by 50 then truncation. If `trainingBudget` wasn't exactly `trainingHours * 50`, precision is lost. Also ignores the `trainingHours` field sent by backend. |
| — | `workforce.bestPracticesInvestment` | `0` (line 1110) | 🔴 **ZEROED** — Actual `bestPracticesInvestment` from backend is ignored. |
| `productionQuantity` | `production.productionQuantity` | Direct | ✅ OK |
| `overtimePercent` (Int) | `production.overtimePercent` | `Double(overtimePercent)` (line 1114) | ✅ OK (reverse of forward coercion) |
| `csrInvestment` | `finance.csrInvestment` | Direct | ✅ OK |
| `dividendsPerShare` | `finance.dividendsPerShare` | Direct | ✅ OK |
| `newLoanAmount` | `finance.newLoanAmount` | Direct | ✅ OK |
| `sharesBuyback` | `finance.sharesBuyback` | Direct | ✅ OK |
| `sharesIssued` | `finance.sharesIssued` | Direct | ✅ OK |
| — | `fulfillmentMethod` | Default `.fbm` | 🔴 **LOST** — Not decoded. Always defaults to `.fbm`. |

---

## 8. Summary of All Mismatches

### 🔴 Critical (Data loss, incorrect values, or broken logic)

| # | Field/Issue | Type | Impact |
|---|---|---|---|
| 1 | **CreditRating reconstruction** (§4.5.1) | Broken logic | Always returns "A" regardless of actual rating. UI displays wrong credit rating. |
| 2 | **imageRating ← imageScore** (§4.5) | Semantic mismatch | Scorecard displays 0–20 value where 0–100 expected. TeamStatus.imageRating also wrong. |
| 3 | **customerSatisfaction ← reputation** (§4.3) | Semantic mismatch | UI shows reputation (EMA) instead of satisfaction (composite metric). |
| 4 | **10 cost fields zeroed/fabricated** (§4.2) | Data lost | csrCosts, endorsementCosts, dividendsPaid, workforceCosts, storageCosts, rebateCosts, deliveryCosts, socialMediaCosts, amazonFees = always 0. interestExpense = equity*0.05 (wrong). Income statement view completely broken. |
| 5 | **4 revenue channel fields fabricated** (§4.1) | Data fabricated | 50/30/15/5 split has no basis in actual channel performance. Channel-level revenue breakdown is fictional. |
| 6 | **4 units-sold fields fabricated/zeroed** (§4.3) | Data lost/fabricated | Backend sends actual per-channel units in `demand` dict, but iOS doesn't decode it. Units are guessed from revenue/price. |
| 7 | **awarenessScore zeroed** (§4.4) | Data lost | Backend sends it but iOS wire DTO doesn't have the field. |
| 8 | **rejectionRate zeroed** (§4.3) | Data lost | Backend computes it but doesn't include it in RoundResult. |
| 9 | **5 TeamStatus fields not restored** (§5) | Data lost | equity, totalDebt, sharesOutstanding, cumulativeRD, cumulativeMarketing, cumulativeCSR, cumulativeTQM, reputation all lost on re-join. |
| 10 | **8 decision fields lost on reverse conversion** (§7.2) | Data lost | celebrityEndorsement, retailOutlets, mailInRebate, deliveryTime, freeShippingThreshold, influencerTier, bestPracticesInvestment, fulfillmentMethod all default on backend→iOS. |
| 11 | **ScoringMetric enum mismatch** (§6.1) | Decoding failure | camelCase vs snake_case causes decoding to fail; silently falls back to default. |

### ⚠️ Moderate (Lossy but not critical)

| # | Field/Issue | Type | Impact |
|---|---|---|---|
| 12 | **inventory type coercion** (§4.3) | Type mismatch | Float → Int truncation loses fractional units. |
| 13 | **sharesOutstanding type mismatch** (backend) | Type mismatch | Backend sends Float; iOS expects Int. |
| 14 | **overtimePercent type coercion** (§7.1) | Type mismatch | Double → Int truncation on forward path. |
| 15 | **cumulativeProfit recompute** (§5) | Logic | `recordResult` ignores backend's `cumulativeProfit` and recomputes from `profit`. Works if all rounds present, but fragile. |
| 16 | **numModels preferred over modelsOffered** (§7.2) | Legacy field | Reverse conversion prefers deprecated field. |
| 17 | **trainingHours lossy reverse** (§7.2) | Lossy | `trainingBudget / 50` loses precision; ignores `trainingHours` field. |

### ℹ️ Latent (Dead code, but would break if activated)

| # | Field/Issue | Type | Impact |
|---|---|---|---|
| 18 | **InfluencerTier.backendValue** (§6.3) | Dead code with wrong values | Maps all tiers to `"social_influencer"`. Would cause 422 errors if used. |
| 19 | **DeliveryTime.backendValue** (§6.4) | Dead code with wrong values | Maps both cases to `"fbm"`. Would cause wrong delivery time if used. |

---

## 9. Root Cause Analysis

### 9.1 Backend RoundResult is a Lossy Projection

The fundamental root cause is that the backend `RoundResult` Pydantic model was designed as a **summary** model with aggregate fields (`revenue`, `costs`, `profit`) and a few sub-costs, while the iOS `RoundResult` was designed as a **detailed** model with full channel and cost breakdowns. The backend simulation engine computes all the detailed fields internally but only serializes the aggregate summary to JSON.

**Evidence:** The engine computes `wholesale_rev`, `internet_rev`, `amazon_rev`, `private_label_rev` individually (lines 1095–1097) but the RoundResult only has `revenue = total_revenue` (line 1204). Similarly, 12 individual cost components are computed (lines 991–1060) but only `costs`, `productionCost`, and `marketingCost` are in the model.

### 9.2 `restoreResultsFromBackend` Uses Fabricated Heuristics

Instead of recognizing that the backend doesn't provide channel-level data, the conversion function fabricates values using hardcoded ratios:
- Revenue split: 50/30/15/5 (lines 774–777)
- Unit estimates: `revenue / price` (lines 790–792)
- Interest expense: `equity * 0.05` (line 782)

These have no basis in the actual simulation results and will always be wrong.

### 9.3 Wire DTO Missing Fields

`RoundResultBackend` (NetworkService.swift lines 774–801) is missing two fields that the backend Pydantic model actually sends:
- `awarenessScore` (backend models.py line 414)
- `demand` dict (backend models.py line 421)

The `demand` dict is particularly important because it contains the actual per-channel units sold — exactly the data that `restoreResultsFromBackend` is fabricating.

### 9.4 CreditRating Reconstruction is Fundamentally Broken

The backend does not send the `creditRating` letter grade in `RoundResult` — it only sends `creditScore` (a 0–20 numeric). The iOS code attempts to reverse-engineer the letter grade by converting the numeric score to a string and matching against enum rawValues, which are letter-grade strings. This can never work because `"18"` ≠ `"A"`.

### 9.5 `imageRating` vs `imageScore` Confusion

The backend has two distinct metrics:
- `image_rating`: 0–100 scale, used for display and team status
- `image_score`: 0–20 scale, investor scorecard subscore

The backend only sends `imageScore` in the RoundResult. The iOS conversion maps this to the scorecard's `imageRating` field, which should hold the 0–100 value. This conflates two different metrics.

---

## 10. Recommendations

### P0 — Immediate Fixes

1. **Fix CreditRating reconstruction:** Either add `creditRating` (letter grade string) to the backend `RoundResult` model, or build a reverse-mapping function from `creditScore` → `CreditRating` (e.g., `≥18 → A+, ≥16 → A, ≥13 → A-, ...`).

2. **Add `imageRating` to backend RoundResult:** The engine already computes `image_rating` (line 1148). Add it as a field in the Pydantic model and include it in the result construction.

3. **Add `awarenessScore` and `demand` to `RoundResultBackend`:** These fields are already sent by the backend but silently dropped by the iOS wire DTO. Adding them to `RoundResultBackend` and using them in `restoreResultsFromBackend` would eliminate the fabricated unit estimates and zeroed awareness score.

4. **Fix `restoreResultsFromBackend` to use `demand` dict:** Replace the fabricated `revenue / price` calculations with actual values from `backendResult.demand`.

### P1 — Should Fix

5. **Add missing cost fields to backend RoundResult:** Add `endorsementCosts`, `csrCosts`, `workforceCosts`, `storageCosts`, `rebateCosts`, `deliveryCosts`, `socialMediaCosts`, `amazonFees`, `interestExpense`, `dividendsPaid` as fields in the Pydantic model. The engine already computes all of them.

6. **Add per-channel revenue to backend RoundResult:** Add `wholesaleRevenue`, `internetRevenue`, `amazonRevenue`, `privateLabelRevenue` fields. The engine already computes them individually.

7. **Restore `equity`, `totalDebt`, `sharesOutstanding`, `reputation` in `restoreResultsFromBackend`:** These are sent by the backend but never applied to `TeamStatus`. Add them to `recordResult` or to the restore function.

8. **Fix ScoringMetric enum values:** Either change the backend enum values to match iOS camelCase, or add a `@model_validator` that translates snake_case → camelCase on the iOS side.

### P2 — Nice to Have

9. **Fix reverse decision conversion (`toPlayerDecision`):** Decode all fields that the backend sends, rather than defaulting 8 fields.

10. **Clean up dead `backendValue` extensions:** Remove or fix `InfluencerTier.backendValue` and `DeliveryTime.backendValue` since they contain wrong mappings and are unused.

11. **Unify `overtimePercent` type:** Decide on `Int` or `Double` and use consistently across both platforms.

12. **Unify `inventory` and `sharesOutstanding` types:** Backend uses `float`, iOS uses `Int`. Pick one.
