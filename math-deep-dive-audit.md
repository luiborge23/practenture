# BizSimAI Math Deep Dive Audit

**Date:** 2026-07-15
**Scope:** All mathematical logic, calculations, and ratios in `SimulationEngine.swift` (iOS) vs `simulation_engine.py` (Python backend)
**Status:** CRITICAL — iOS and Python engines are NOT mathematically equivalent

---

## 1. S/Q Rating — DIFFERENT FORMULAS

### iOS Swift (lines 951-968)
```swift
var sq = 3.0 + materialsQuality.sqBonus          // 3.0 (standard) or 5.0 (superior)
sq += min(2.0, log(1 + stylingBudget / 3000) / log(5))   // LOGARITHMIC
sq += min(1.5, Double(modelsOffered) * 0.3)          // Linear: max 1.5
sq += min(1.5, log(1 + cumulativeTQM / 5000) / log(10)) // LOGARITHMIC
sq += min(0.5, bestPractices / 5000)                  // Linear: max 0.5
sq += min(0.5, trainingHours / 80.0)                  // Linear: max 0.5
let blended = 0.4 * previousSQ + 0.6 * sq             // RATCHETED
return min(10.0, max(1.0, blended))
```

### Python Backend (lines 72-78)
```python
base = materials_quality * 5.0                        # Linear: max 5.0
models_bonus = min(num_models / 10.0 * 2.0, 2.0)      # Linear: max 2.0
style_bonus = min(styling_budget / 500000.0 * 3.0, 3.0) # Linear: max 3.0
sq = base + models_bonus + style_bonus                # NO TQM, training, best practices
return clamp(sq, 0.0, 10.0)                           # NO ratchet, no previous SQ
```

### Discrepancies:
| Factor | iOS | Python | Impact |
|--------|-----|--------|--------|
| Base | 3.0 (standard) / 5.0 (superior) | `materials_quality * 5.0` (0-5) | Python uses raw quality score, not enum bonus |
| Styling | Logarithmic: `log(1+budget/3000)/log(5)` | Linear: `budget/500000*3` | iOS gives more value at low spend, Python needs $500K max |
| Models | `models * 0.3` (max 1.5) | `models/10*2` (max 2.0) | Python gives more value per model |
| TQM | **Included** (log, max 1.5) | **NOT INCLUDED** | Major omission in Python |
| Best Practices | **Included** (max 0.5) | **NOT INCLUDED** | Major omission in Python |
| Training | **Included** (max 0.5) | **NOT INCLUDED** | Major omission in Python |
| Previous SQ ratchet | **Yes** (40/60 blend) | **No** | iOS S/Q is sticky; Python resets each round |
| Min/Max | 1.0-10.0 | 0.0-10.0 | Different floor |

**Severity:** 🔴 CRITICAL — S/Q drives demand attractiveness in both engines. Different S/Q = different market outcomes.

---

## 2. Rejection Rate — DIFFERENT FORMULAS

### iOS Swift (lines 973-986)
```swift
var rate = 0.12
rate -= min(0.04, cumulativeTQM / 200000)           // TQM: max -4%
rate -= min(0.03, trainingHours / 100.0 * 0.03)     // Training: max -3%
rate -= min(0.02, incentivePay / 2.0 * 0.02)        // Incentive: max -2%
rate -= min(0.02, bestPractices / 5000 * 0.02)      // Best practices: max -2%
return max(0.01, rate)                                // Min 1%
```

### Python Backend (lines 63-69)
```python
tqm_reduction = min(tqm / 100000.0 * 0.011, 0.09)   # TQM: max -9%
training_reduction = min(training / 50000.0 * 0.009, 0.05) # Training: max -5%
return max(0.01, 0.12 - tqm_reduction - training_reduction)
```

### Discrepancies:
| Factor | iOS | Python | Impact |
|--------|-----|--------|--------|
| TQM reduction | `cumulativeTQM/200K` → max 4% | `tqm/100K*0.011` → max 9% | Python reduces MORE aggressively |
| Training | `trainingHours/100` → max 3% | `training/50K*0.009` → max 5% | Different units (hours vs $), different scale |
| Incentive Pay | **Included** (max 2%) | **NOT INCLUDED** | iOS has extra reduction |
| Best Practices | **Included** (max 2%) | **NOT INCLUDED** | iOS has extra reduction |
| Base rate | 12% | 12% | Same |

**Severity:** 🟡 HIGH — Different rejection rates = different net production, different costs.

---

## 3. Market Demand — DIFFERENT MODELS

### iOS Swift (lines 122-132)
```swift
let demandGrowth = min(2.0, 1.0 + 0.05 * Double(round))
let totalDemand = baseMarketDemand * marketType.demandMultiplier * demandGrowth * noise
// Channel splits (fixed percentages):
wholesaleDemand = totalDemand * 0.50   // 50%
internetDemand = totalDemand * 0.15    // 15%
privateLabelDemand = totalDemand * 0.15 // 15%
amazonDemand = totalDemand * 0.20      // 20%
```

### Python Backend (lines 108-207)
```python
# Each channel computed independently with its own base demand:
wholesale_demand = 10000.0 * attractiveness
internet_demand = 5000.0 * attractiveness
amazon_demand = 5000.0 * attractiveness
# NO private label channel
```

### Discrepancies:
| Aspect | iOS | Python | Impact |
|--------|-----|--------|--------|
| Growth model | `min(2.0, 1 + 0.05*round)` — linear capped at 2x | **No growth model** — fixed base per channel | iOS demand grows with rounds; Python doesn't |
| Channel splits | Fixed % of total (50/15/15/20) | Independent base demands (10K/5K/5K) | Different absolute volumes per channel |
| Private label | **Included** (15% of total) | **NOT INCLUDED** | Missing in Python entirely |
| Base demand | From config (`baseMarketDemand`) | Hardcoded 10,000 (wholesale) | Config-driven vs hardcoded |
| Attractiveness model | **Competitive share** (your attractiveness / total attractiveness) | **Independent demand** per channel | iOS = zero-sum within channel; Python = additive |

**Severity:** 🔴 CRITICAL — The demand model is fundamentally different. iOS uses competitive share allocation; Python uses independent channel demands. This means the same decisions produce completely different market outcomes.

---

## 4. Attractiveness / Demand Calculation — DIFFERENT FORMULAS

### iOS Swift (lines 172-213)
```swift
// Wholesale: multiplicative factors
wholesaleAttract = priceAttract * sqAttract * adAttract * outletFactor 
    * endorseFactor * reputationFactor * deliveryFactor * socialMediaBoost * noise

// Price: pow(avgPrice/effectivePrice, 1.5)
// SQ: pow(sq/avgSQ, 1.2)
// Ads: pow(adBudget/avgAd, 0.6)
// Social: tiktokFactor * instagramFactor * youtubeFactor * influencerFactor (multiplicative)
```

### Python Backend (lines 108-207)
```python
# Each channel: price_attr * sq_attr * (1 + marketing_influence + social_influence + outlet_influence)
# Price: pow(price/avgPrice, 1.5) — INVERTED vs iOS!
// SQ: pow(sq/avgSQ, 1.2) — same weight
// Marketing: linear (budget/divisor * multiplier)
// Social: linear (total_social/contribution / divisor * multiplier)
```

### Discrepancies:
| Factor | iOS | Python | Impact |
|--------|-----|--------|--------|
| Price attractiveness | `pow(avgPrice/effectivePrice, 1.5)` — LOWER price = HIGHER attractiveness | `pow(price/avgPrice, 1.5)` — HIGHER price = HIGHER attractiveness | 🔴 **INVERTED** — Python's formula rewards expensive products! |
| SQ attractiveness | `pow(sq/avgSQ, 1.2)` | `pow(sq/avgSQ, 1.2)` | Same |
| Marketing influence | `pow(adBudget/avgAd, 0.6)` — power function | `(budget/divisor)*multiplier` — linear | Different scaling behavior |
| Social media | Multiplicative platform factors (TikTok×Instagram×YouTube×Influencer) | Additive: `total_social * 0.3 / divisor * multiplier` | iOS amplifies multi-platform; Python treats as single pool |
| Reputation | **Included** (`0.7 + 0.6*reputation`) | **NOT INCLUDED** in demand | iOS rewards reputation; Python doesn't |
| Celebrity endorsement | **Included** (`demandBoost` from enum) | **NOT INCLUDED** in demand | iOS rewards endorsements; Python doesn't |
| Delivery time | **Included** (`demandBoost` from enum) | **NOT INCLUDED** in demand | iOS rewards fast delivery; Python doesn't |
| Retail outlets | `1 + outlets/100*0.3` — linear additive | `outlets * 0.3 / 10` — same math, different form | Equivalent |
| Free shipping (internet) | `1 + max(0, (100-threshold)/200)` | **NOT INCLUDED** | iOS rewards free shipping; Python doesn't |
| Amazon Buy Box | `buyBoxMultiplier` (FBA 1.25, FBM 0.85) | `channel_bonus` (FBA=1.0, FBM=1.0) — **NO DIFFERENCE** | 🔴 Python ignores fulfillment method for demand! |
| Amazon trust | `trustMultiplier` (FBA 1.15, FBM 1.0) | **NOT INCLUDED** | iOS rewards FBA trust; Python doesn't |
| Noise | 5% per channel | 5% per channel | Same amplitude, different RNG seed |

**Severity:** 🔴 CRITICAL — Price attractiveness is INVERTED in Python. Multiple iOS factors (reputation, endorsement, delivery, free shipping, Buy Box) are missing in Python.

---

## 5. Private Label Allocation — MISSING IN PYTHON

### iOS Swift (lines 219-228)
```swift
// Private label = 15% of total demand, allocated to LOWEST bidders first
let privateLabelBids = teams.sorted { $0.privateLabelBidPrice < $1.privateLabelBidPrice }
for (team, decision) in privateLabelBids {
    allocation = min(decision.privateLabelMaxUnits, remainingPL)
    remainingPL -= allocation
}
```

### Python Backend
**NOT IMPLEMENTED** — No private label channel exists.

**Severity:** 🟡 HIGH — Private label is a strategic decision variable in iOS with no backend equivalent.

---

## 6. Production Cost — DIFFERENT FORMULAS

### iOS Swift (lines 293-338)
```swift
// Production cost: materials + overtime + fixed costs + styling + TQM + best practices
materialsCost = baseCostPerUnit * materialsQuality.costMultiplier  // $30 or $42
regularUnits = min(grossProduction, baseCapacity)
overtimeUnits = max(0, grossProduction - baseCapacity)
regularProdCost = materialsCost * regularUnits
overtimeProdCost = materialsCost * 1.5 * overtimeUnits            // 1.5x premium
totalProdCost = regularProdCost + overtimeProdCost + fixedCostsPerRound 
    + stylingBudget + tqmInvestment + bestPracticesInvestment

// Workforce costs (SEPARATE from production):
workersNeeded = max(1, grossProduction / 10)  // ~10 units per worker
wageCost = baseWage * workersNeeded / 1000.0  // Scaled down
incentiveCost = incentivePay * grossProduction
trainingCost = trainingHours * 50.0 * workersNeeded / 1000.0
```

### Python Backend (lines 236-267)
```python
wage_factor = base_wage / 25000.0
labor_cost_per_unit = 8.0 * wage_factor       # $8 base labor per unit
material_cost_per_unit = 3.0 + materials_quality * 7.0  # $3-10 per unit
overtime_factor = 1.0 + (overtime/100) * 0.5
training_reduction = min(training/500K*0.15, 0.15)
unit_cost = (material + labor) * overtime_factor * (1 - training_reduction)
total_cost = unit_cost * quantity
```

### Discrepancies:
| Aspect | iOS | Python | Impact |
|--------|-----|--------|--------|
| Materials cost | `baseCostPerUnit * multiplier` ($30 standard, $42 superior) | `3.0 + quality*7.0` ($3-10) | 🔴 **Massive difference** — iOS is 3-14x more expensive per unit |
| Labor cost | SEPARATE line item: `wage * workers/1000` | Baked into unit cost: `$8 * wage_factor` | iOS workforce costs are separate; Python merges them |
| Overtime premium | 1.5x on materials only | 1.5x on total unit cost (materials + labor) | Different scope of premium |
| Fixed costs | `fixedCostsPerRound` ($5,000) added separately | **NOT INCLUDED** in unit cost | iOS has per-round fixed costs; Python doesn't |
| Styling/TQM/Best Practices | **Included** in production cost | **NOT INCLUDED** | iOS costs more for these investments |
| Training effect on cost | SEPARATE cost line item, no unit cost reduction | Reduces unit cost by up to 15% | Different mechanism |
| Workers needed | `max(1, production/10)` — floor of 1 worker | **NOT CALCULATED** | iOS has minimum workforce |

**Severity:** 🔴 CRITICAL — Materials cost differs by 3-14x. This alone makes profit calculations incomparable between iOS and Python.

---

## 7. Financial Metrics — PARTIAL OVERLAP

### EPS
| Aspect | iOS Swift | Python Backend |
|--------|-----------|----------------|
| Formula | `profit / newShares` | `profit / new_shares` | **SAME** |

### ROE
| Aspect | iOS Swift | Python Backend |
|--------|-----------|----------------|
| Formula | `profit / newEquity` | `profit / new_equity` | **SAME** |

### Stock Price
| Aspect | iOS Swift (lines 449-464) | Python Backend (lines 759-768) |
|--------|---------------------------|-------------------------------|
| Base target | $25.00 | $50.00 | **DIFFERENT** |
| EPS factor | `max(0.5, 1 + eps/targetEPS)` | Uses `eps_change` (delta from prev) | **DIFFERENT** |
| ROE factor | `max(0.5, 1 + roe)` | Uses `roe_change` (delta from prev) | **DIFFERENT** |
| Dividend yield | `dividends / previousStockPrice` | **NOT INCLUDED** | iOS has dividend effect; Python doesn't |
| Credit factor | `creditScore / 20.0` | **NOT INCLUDED** in stock price | iOS rewards good credit; Python doesn't |
| Dilution penalty | `max(0.85, 1 - issued/maxOutstanding*0.5)` | **NOT INCLUDED** | iOS penalizes share issuance; Python doesn't |
| Blending | 40% previous + 60% new (round > 1) | `prev_sp * (...) * 0.8 + 50*0.2` (80/20) | **DIFFERENT** blending weights |
| Noise | 3% amplitude | **NOT INCLUDED** | iOS has stock price volatility |

### Credit Rating
| Aspect | iOS Swift (lines 427-431, models lines 398-432) | Python Backend (lines 286-313) |
|--------|--------------------------------------------------|-------------------------------|
| Method | Tiered: A+ through C- based on D/E, interest coverage, cash ratio thresholds | Continuous 0-60 score: `de_score + ic_score + cash_score` | **DIFFERENT** |
| D/E scoring | 40/35/25/15/5 pts (threshold-based) | `max(0, 20 - de_ratio*10)` (linear) | **DIFFERENT** |
| Interest coverage | 35/30/20/10/0 pts (threshold-based) | `min(ic*5, 20)` (linear) | **DIFFERENT** |
| Cash ratio | 25/20/10/0 pts (threshold-based) | `min(cash/debt*10, 20)` (linear) | **DIFFERENT** |
| Max score | 100 pts (40+35+25) | 60 pts (20+20+20) | **DIFFERENT** ceiling |
| Interest rate multiplier | Tiered: 0.8x (A+) to 3.0x (C-) | **NOT USED** — flat 0.5% per round | 🔴 Python doesn't differentiate loan cost by credit! |

### Investor Scorecard
| Aspect | iOS Swift (lines 466-486) | Python Backend (lines 316-350+) |
|--------|---------------------------|-------------------------------|
| EPS target | `2.0 * 1.06^round` (ratcheting) | `25000 * 1.06^round * 0.001` (derived from wage) | **DIFFERENT** base |
| ROE target | `0.15 * 1.06^round` (ratcheting) | `prev_roe * 1.06` (relative to prev) | **DIFFERENT** approach |
| Stock target | `25.0 * 1.06^round` (ratcheting) | **NOT INCLUDED** — uses reputation instead | iOS has stock target; Python doesn't |
| Image target | `min(90, 50 * (1 + 0.03*round))` | Uses reputation directly as imageScore | **DIFFERENT** |
| Credit score | Direct: `creditRating.investorScore` (0-20) | Included in total scorecard | Similar concept, different scale |
| Scoring formula | `min(20, max(0, 20 * actual/target))` | Varies by metric (EPS ratio-based) | Similar concept, different implementation |

---

## 8. Customer Satisfaction — MISSING IN PYTHON

### iOS Swift (lines 412-418)
```swift
let priceFairness = min(1.0, avgWholesalePrice / max(decision.wholesalePrice, 1))
let supplyAdequacy = totalDemandForTeam > 0 ? min(1.0, Double(totalSold) / Double(totalDemandForTeam)) : 0.5
let satisfaction = min(1.0, max(0.0,
    0.35 * (sq / 10.0) + 0.3 * priceFairness + 0.2 * supplyAdequacy + 0.15 * team.reputation))
let newReputation = 0.7 * team.reputation + 0.3 * satisfaction
```

### Python Backend (lines 746-748)
```python
reputation = _compute_reputation(sq, tqm, csr, marketing)  // Independent formula
```

### Discrepancies:
| Aspect | iOS Swift | Python Backend | Impact |
|--------|-----------|----------------|--------|
| Satisfaction formula | Weighted: 35% SQ + 30% price fairness + 20% supply adequacy + 15% reputation | **NOT CALCULATED** | iOS has customer satisfaction metric; Python doesn't |
| Reputation update | Exponential moving average: `0.7*prev + 0.3*satisfaction` | Independent calculation from SQ/TQM/CSR/marketing | **DIFFERENT** reputation dynamics |
| Price fairness | `avgPrice / yourPrice` — lower price = higher fairness | **NOT INCLUDED** | iOS rewards competitive pricing |
| Supply adequacy | `sold / demanded` — measures stockouts | **NOT INCLUDED** | iOS penalizes stockouts |

**Severity:** 🟡 HIGH — Reputation dynamics are fundamentally different, which cascades into demand calculations in iOS.

---

## 9. Image Rating — MISSING IN PYTHON

### iOS Swift (lines 433-447)
```swift
sqImageContrib = sq * 5.0                    // Up to 50
adImageContrib = min(15, adBudget/2000*5)    // Up to 15
csrImageContrib = min(15, csr/2000*5)        // Up to 15
endorseImageContrib = celebrity.imageBoost   // 0/3/8/15
modelsImageContrib = min(10, models*2)       // Up to 10
workforceImageContrib = min(5, training/40*5) // Up to 5
instagramImageContrib = min(8, igBudget/10K*8) // Up to 8
tiktokImageContrib = min(4, ttBudget/10K*4)    // Up to 4
youtubeImageContrib = min(5, ytBudget/10K*5)   // Up to 5
influencerImageContrib = tier.imageBoost     // 0/1/3/6/10
imageRating = min(100, sum of all)
```

### Python Backend
**NOT IMPLEMENTED** — Uses `reputation` as a proxy but with different formula.

**Severity:** 🟡 MEDIUM — Image rating affects investor scorecard in iOS but has no Python equivalent.

---

## 10. Amazon Fees — DIFFERENT HANDLING

### iOS Swift (lines 361-365)
```swift
let amazonReferralFee = amazonRev * 0.15      // 15% of revenue
let amazonFulfillmentFee = feePerUnit * aSold // $4.50 (FBA) or $1.50 (FBM) per unit
let amazonAdCost = decision.amazonAdBudget    // Separate ad budget
let totalAmazonFees = referral + fulfillment + ads
```

### Python Backend (lines 680-684)
```python
if fulfillmentMethod == "fba":
    amazon_rev *= (1.0 - 0.15)   # Deducts 15% from revenue directly
else:
    amazon_rev *= (1.0 - 0.10)   # Deducts 10% from revenue directly
```

### Discrepancies:
| Aspect | iOS Swift | Python Backend | Impact |
|--------|-----------|----------------|--------|
| Fee structure | Separate: 15% referral + per-unit fulfillment + ad budget | Deducted from revenue directly (15% FBA, 10% FBM) | **DIFFERENT** — Python's FBM rate is lower (10% vs 15%) |
| Per-unit fee | $4.50 (FBA) / $1.50 (FBM) per unit sold | **NOT INCLUDED** | iOS has per-unit fulfillment cost; Python doesn't |
| Amazon ads | Separate `amazonAdBudget` line item | **NOT INCLUDED** | iOS tracks Amazon ad spend; Python doesn't |
| Fee reporting | `amazonFees` separate cost line in RoundResult | Baked into net revenue | Different accounting |

**Severity:** 🟡 HIGH — Amazon fee structure differs significantly, affecting profit calculations.

---

## 11. Interest Expense — DIFFERENT FORMULAS

### iOS Swift (lines 382-383)
```swift
let interestRate = baseInterestRate * creditRating.interestRateMultiplier
// e.g., 6% * 0.8 (A+) = 4.8% to 6% * 3.0 (C-) = 18%
let interestExpense = team.totalDebt * interestRate
```

### Python Backend (lines 707-711)
```python
loan_interest_rate = 0.005  // Flat 0.5% per round
interest_expense = debt * loan_interest_rate
```

### Discrepancies:
| Aspect | iOS Swift | Python Backend | Impact |
|--------|-----------|----------------|--------|
| Base rate | 6% annual (configurable) | 0.5% per round (= ~6% annual) | Similar base, different framing |
| Credit differentiation | **Yes** — 0.8x to 3.0x multiplier based on rating | **No** — flat rate for all teams | 🔴 Python ignores credit quality in loan cost! |
| Rate type | Annual rate applied per round | Per-round flat rate | Conceptually similar but iOS scales by credit |

**Severity:** 🟡 HIGH — Credit rating should affect borrowing cost. Python's flat rate means bad credit teams don't pay more for loans.

---

## 12. Share Buyback / Issuance — DIFFERENT FORMULAS

### iOS Swift (lines 386-392)
```swift
let safeBuyback = min(decision.sharesBuyback, team.sharesOutstanding - 1)
let newShares = max(1, team.sharesOutstanding - safeBuyback + decision.sharesIssued)
let dividendsPaid = decision.dividendsPerShare * Double(newShares)
let issuancePrice = max(5, team.cumulativeInvestorScore > 0 ? team.cumulativeInvestorScore / 2 : 15)
let issuanceProceeds = Double(decision.sharesIssued) * issuancePrice
```

### Python Backend (lines 698-705)
```python
dividend_cost = d.dividendsPerShare * max(prev_shares, 1)  // Uses OLD share count
buyback_cost = d.sharesBuyback * 50.0                       // Fixed $50/share
share_proceeds = d.sharesIssued * 50.0                      // Fixed $50/share
```

### Discrepancies:
| Aspect | iOS Swift | Python Backend | Impact |
|--------|-----------|----------------|--------|
| Buyback price | `max(5, previousStockPrice)` — market-based | Fixed $50/share | 🔴 **MASSIVE** — iOS can be much cheaper or more expensive |
| Issuance price | Dynamic: `cumulativeInvestorScore/2` or $15 minimum | Fixed $50/share | 🔴 **MASSIVE** — iOS issuance can be much cheaper |
| Dividend base | `newShares` (after buyback/issuance) | `prev_shares` (before changes) | Minor difference |
| Buyback cap | `sharesOutstanding - 1` (can't buy back all) | **NOT CAPPED** | Python could reduce shares to zero/negative |

**Severity:** 🔴 CRITICAL — Buyback and issuance prices differ by orders of magnitude. This makes cash flow and equity calculations incomparable.

---

## 12. Storage Costs — SAME

| Aspect | iOS Swift | Python Backend |
|--------|-----------|----------------|
| Formula | `1.50 * newInventory` | `ending_inventory * 1.50` | **SAME** |

---

## 13. Awareness Score — MISSING IN PYTHON

### iOS Swift (line 506)
```swift
awarenessScore = min(1, (advertisingBudget + socialMediaBudget) / 25000)
```

### Python Backend
**NOT IMPLEMENTED** — No awareness score in RoundResult.

---

## 14. Demand Growth Model — MISSING IN PYTHON

### iOS Swift (line 123)
```swift
let demandGrowth = min(2.0, 1.0 + 0.05 * Double(round))
// Round 1: 1.05x, Round 5: 1.25x, Round 10: 1.50x (capped at 2.0)
```

### Python Backend
**NOT IMPLEMENTED** — No growth model; each round uses same base demand.

---

## Summary of Discrepancies by Severity

### 🔴 CRITICAL (Must Fix — Causes Wrong Results)
1. **S/Q Rating** — Completely different formulas; iOS has 6 factors, Python has 3
2. **Market Demand Model** — iOS uses competitive share; Python uses independent demands
3. **Price Attractiveness** — INVERTED in Python (rewards high prices)
4. **Production Cost** — Materials cost differs by 3-14x
5. **Share Buyback/Issuance Prices** — iOS uses market-based; Python uses fixed $50
6. **Private Label Channel** — Missing in Python entirely

### 🟡 HIGH (Significant Impact)
7. **Rejection Rate** — Different factors and scales
8. **Demand Growth** — iOS grows with rounds; Python is static
9. **Customer Satisfaction / Reputation Dynamics** — Different update mechanisms
10. **Amazon Fees** — Different structure (per-unit vs revenue %); FBM rate differs
11. **Interest Expense** — Python ignores credit rating differentiation
12. **Image Rating** — Missing in Python; affects investor scorecard

### 🟢 MEDIUM (Minor Impact)
13. **Stock Price Model** — Different factors and blending weights
14. **Credit Rating Calculation** — Different scoring methods (tiered vs continuous)
15. **Investor Scorecard Targets** — Different base targets and ratcheting
16. **Awareness Score** — Missing in Python

---

## Recommendations

### Phase 1: Fix Critical Discrepancies (iOS → Python parity)
1. **Align S/Q Rating formula** in Python to match iOS (add TQM, best practices, training, previous SQ ratchet)
2. **Fix price attractiveness inversion** in Python (`competitor_avg / own_price` not `own / competitor`)
3. **Align production cost** — use iOS formula (materials * quality multiplier, separate workforce costs)
4. **Implement competitive share demand model** in Python (attractiveness / total attractiveness)
5. **Fix buyback/issuance pricing** — use market-based prices from iOS
6. **Add private label channel** to Python

### Phase 2: Fix High-Impact Discrepancies
7. Align rejection rate formula
8. Add demand growth model
9. Implement customer satisfaction and reputation dynamics
10. Align Amazon fee structure
11. Add credit-rated interest differentiation
12. Implement image rating

### Phase 3: Medium-Impact Alignment
13-16. Align stock price, credit rating, scorecard targets, awareness

---

## Key Insight

The iOS Swift engine is a **mature, comprehensive simulation** with 16+ decision factors affecting outcomes. The Python backend is a **simplified prototype** that captures the general concept but uses different formulas for most calculations. They are NOT interchangeable — running the same decisions through each produces completely different results.

The Python backend was likely written as an early prototype and never updated to match the iOS engine's evolved formulas. For the system to work correctly (iOS app sending decisions to backend for processing), the Python engine must be updated to match the iOS formulas exactly.
