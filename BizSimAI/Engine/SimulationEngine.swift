// SimulationEngine.swift
// BizSimAI
//
// Deterministic marketplace simulation engine.
// Computes S/Q ratings, multi-channel demand allocation, financial metrics,
// rejection/defect rate, workforce effects, inventory storage costs,
// and investor scorecard (EPS, ROE, Stock Price, Image Rating, Credit Rating)
// with ratcheting targets that increase each round.

import Foundation

// MARK: - Engine Protocol

protocol SimulationEngineProtocol {
    func processRound(
        session: SimulationSession,
        decisions: [UUID: PlayerDecision]
    ) -> (results: [RoundResult], explanations: [ResultExplanation])
}

// MARK: - Seeded Random Generator

struct SeededRandomGenerator: RandomNumberGenerator {
    private var state: UInt64

    init(seed: UInt64) {
        self.state = seed
    }

    mutating func next() -> UInt64 {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        return state
    }

    mutating func nextDouble() -> Double {
        return Double(next() >> 11) / Double(1 << 53)
    }

    mutating func noiseFactor(amplitude: Double) -> Double {
        return 1.0 + (nextDouble() * 2.0 - 1.0) * amplitude
    }
}

// MARK: - BizSim Simulation Engine

final class SimulationEngine: SimulationEngineProtocol {

    // MARK: - Constants

    private let priceElasticity: Double = 1.5
    private let sqWeight: Double = 1.2
    private let advertisingWeight: Double = 0.6
    private let outletsWeight: Double = 0.3
    private let noiseAmplitude: Double = 0.05

    // Channel splits (% of total market demand)
    private let wholesaleShare: Double = 0.50
    private let amazonShare: Double = 0.20
    private let internetShare: Double = 0.15
    private let privateLabelShare: Double = 0.15

    // Financial defaults
    private let baseInterestRate: Double = 0.06
    private let overtimeCostPremium: Double = 1.5
    private let storageCostPerUnit: Double = 1.50  // Per-unit inventory carrying cost

    // Investor expectation base targets
    private let baseEPSTarget: Double = 2.0
    private let baseROETarget: Double = 0.15
    private let baseStockTarget: Double = 25.0
    private let baseImageTarget: Double = 50.0

    // Ratcheting rate: targets increase by this % per round
    private let targetRatchetRate: Double = 0.06

    // Workforce baseline
    private let baseWageBaseline: Double = 25_000  // Industry standard wage

    // MARK: - Process Round

    func processRound(
        session: SimulationSession,
        decisions: [UUID: PlayerDecision]
    ) -> (results: [RoundResult], explanations: [ResultExplanation]) {
        let config = session.config
        let round = session.currentRound
        var rng = SeededRandomGenerator(seed: config.randomSeed &+ UInt64(round))

        // 1. Build team contexts and compute S/Q ratings
        var teamSQRatings: [UUID: Double] = [:]
        var teamRejectionRates: [UUID: Double] = [:]
        var teamContexts: [(team: TeamStatus, decision: PlayerDecision)] = []

        for team in session.teams {
            guard let decision = decisions[team.id] else { continue }

            let updatedCumulativeTQM = team.cumulativeTQM + decision.tqmInvestment

            let sqRating = computeSQRating(
                materialsQuality: decision.materialsQuality,
                stylingBudget: decision.stylingBudget,
                modelsOffered: decision.modelsOffered,
                cumulativeTQM: updatedCumulativeTQM,
                bestPractices: decision.bestPracticesInvestment,
                trainingHours: decision.trainingHours,
                previousSQ: team.sqRating
            )
            teamSQRatings[team.id] = sqRating

            // Compute rejection/defect rate
            let rejectionRate = computeRejectionRate(
                cumulativeTQM: updatedCumulativeTQM,
                trainingHours: decision.trainingHours,
                incentivePay: decision.incentivePay,
                bestPractices: decision.bestPracticesInvestment
            )
            teamRejectionRates[team.id] = rejectionRate

            teamContexts.append((team, decision))
        }

        // 2. Compute total market demand (grows ~5% per round with noise)
        let demandGrowth = min(2.0, 1.0 + 0.05 * Double(round))
        let totalDemand = Double(config.baseMarketDemand)
            * config.marketType.demandMultiplier
            * demandGrowth
            * rng.noiseFactor(amplitude: config.marketType.volatility)

        let wholesaleDemand = totalDemand * wholesaleShare
        let internetDemand = totalDemand * internetShare
        let privateLabelDemand = totalDemand * privateLabelShare
        let amazonDemand = totalDemand * amazonShare

        // 3. Compute competitive indices
        let avgWholesalePrice = teamContexts.map { $0.decision.wholesalePrice }.reduce(0, +) / Double(max(1, teamContexts.count))
        let avgInternetPrice = teamContexts.map { $0.decision.internetPrice }.reduce(0, +) / Double(max(1, teamContexts.count))
        let avgSQ = teamSQRatings.values.reduce(0, +) / Double(max(1, teamSQRatings.count))
        let avgAdvertising = teamContexts.map { $0.decision.advertisingBudget }.reduce(0, +) / Double(max(1, teamContexts.count))
        let avgRebate = teamContexts.map { $0.decision.mailInRebate }.reduce(0, +) / Double(max(1, teamContexts.count))

        var wholesaleAttractivities: [UUID: Double] = [:]
        var internetAttractivities: [UUID: Double] = [:]
        var amazonAttractivities: [UUID: Double] = [:]

        for (team, decision) in teamContexts {
            let sq = teamSQRatings[team.id] ?? 5.0

            // Social media demand boost factor
            // TikTok boosts awareness (viral reach), Instagram boosts brand image,
            // YouTube boosts credibility/trust (helps S/Q perception)
            let tiktokFactor = 1.0 + min(0.08, decision.tiktokBudget / 15_000 * 0.08)
            let instagramFactor = 1.0 + min(0.06, decision.instagramBudget / 15_000 * 0.06)
            let youtubeFactor = 1.0 + min(0.05, decision.youtubeBudget / 15_000 * 0.05)
            // Influencer count estimate for demand boost (mirrors cost calc below)
            let estInfluencerCount: Double
            if decision.socialMediaBudget <= 0 {
                estInfluencerCount = 0
            } else {
                switch decision.influencerTier {
                case .none: estInfluencerCount = 0
                case .nano: estInfluencerCount = Double(max(1, Int(decision.socialMediaBudget / 1000)))
                case .micro: estInfluencerCount = Double(max(1, Int(decision.socialMediaBudget / 5000)))
                case .macro: estInfluencerCount = Double(max(1, Int(decision.socialMediaBudget / 20000)))
                case .mega: estInfluencerCount = Double(max(1, Int(decision.socialMediaBudget / 60000)))
                }
            }
            // Diminishing returns: sqrt(count) so doubling spend doesn't double boost
            let influencerCountFactor = max(1, sqrt(estInfluencerCount))
            let influencerFactor = 1.0 + decision.influencerTier.engagementRate * decision.influencerTier.reachMultiplier * 0.1 * influencerCountFactor
            let socialMediaDemandBoost = tiktokFactor * instagramFactor * youtubeFactor * influencerFactor

            // Wholesale attractiveness (includes rebate and delivery time)
            let effectivePrice = decision.wholesalePrice - decision.mailInRebate * 0.6 // ~60% redemption rate
            let avgEffectivePrice = avgWholesalePrice - avgRebate * 0.6
            let priceAttract = pow(max(avgEffectivePrice, 1) / max(effectivePrice, 1), priceElasticity)
            let sqAttract = pow(sq / max(avgSQ, 1), sqWeight)
            let adAttract = pow(max(decision.advertisingBudget, 100) / max(avgAdvertising, 100), advertisingWeight)
            let outletFactor = 1.0 + Double(decision.retailOutlets) / 100.0 * outletsWeight
            let endorseFactor = decision.celebrityEndorsement.demandBoost
            let reputationFactor = 0.7 + 0.6 * team.reputation
            let deliveryFactor = decision.deliveryTime.demandBoost

            wholesaleAttractivities[team.id] = priceAttract * sqAttract * adAttract
                * outletFactor * endorseFactor * reputationFactor * deliveryFactor
                * socialMediaDemandBoost
                * rng.noiseFactor(amplitude: noiseAmplitude)

            // Internet attractiveness (includes free shipping threshold)
            let iPriceAttract = pow(max(avgInternetPrice, 1) / max(decision.internetPrice, 1), priceElasticity * 0.9)
            let iSQAttract = pow(sq / max(avgSQ, 1), sqWeight * 1.1)
            // Free shipping boost: lower threshold = more attractive (baseline $100)
            let freeShipBoost = 1.0 + max(0, (100 - decision.freeShippingThreshold) / 200.0)

            internetAttractivities[team.id] = iPriceAttract * iSQAttract * adAttract
                * endorseFactor * reputationFactor * freeShipBoost
                * socialMediaDemandBoost  // Social media especially boosts internet sales
                * rng.noiseFactor(amplitude: noiseAmplitude)

            // Amazon attractiveness (price competition + S/Q reviews proxy + ads + fulfillment method)
            let amazonReferralRate = 0.15  // 15% referral fee for footwear
            let amazonEffectivePrice = decision.amazonPrice * (1.0 - amazonReferralRate)
            let avgAmazonPrice = teamContexts.map { $0.decision.amazonPrice }.reduce(0, +) / Double(max(1, teamContexts.count))
            let avgAmazonEffective = avgAmazonPrice * (1.0 - amazonReferralRate)
            let aPriceAttract = pow(max(avgAmazonEffective, 1) / max(amazonEffectivePrice, 1), priceElasticity * 0.8)
            let aReviewProxy = pow(sq / max(avgSQ, 1), sqWeight * 1.2) // S/Q acts as review quality
            let aAdBoost = 1.0 + min(0.15, decision.amazonAdBudget / 10_000 * 0.15) // PPC ads boost
            let aBuyBox = decision.fulfillmentMethod.buyBoxMultiplier
            let aTrust = decision.fulfillmentMethod.trustMultiplier

            amazonAttractivities[team.id] = aPriceAttract * aReviewProxy * aAdBoost
                * aBuyBox * aTrust * socialMediaDemandBoost
                * rng.noiseFactor(amplitude: noiseAmplitude)
        }

        let totalWholesaleAttract = wholesaleAttractivities.values.reduce(0, +)
        let totalInternetAttract = internetAttractivities.values.reduce(0, +)
        let totalAmazonAttract = amazonAttractivities.values.reduce(0, +)

        // 4. Private-label allocation (lowest bid wins)
        let privateLabelBids = teamContexts.sorted { $0.decision.privateLabelBidPrice < $1.decision.privateLabelBidPrice }
        var privateLabelAllocations: [UUID: Int] = [:]
        var remainingPL = Int(privateLabelDemand)
        for (team, decision) in privateLabelBids {
            if remainingPL <= 0 { break }
            let allocation = min(decision.privateLabelMaxUnits, remainingPL)
            privateLabelAllocations[team.id] = allocation
            remainingPL -= allocation
        }

        // 5. Compute results for each team
        var results: [RoundResult] = []
        var explanations: [ResultExplanation] = []

        for (team, decision) in teamContexts {
            let sq = teamSQRatings[team.id] ?? 5.0
            let rejectionRate = teamRejectionRates[team.id] ?? 0.08

            // Demand allocation
            let wShare = (wholesaleAttractivities[team.id] ?? 0) / max(totalWholesaleAttract, 0.001)
            let iShare = (internetAttractivities[team.id] ?? 0) / max(totalInternetAttract, 0.001)
            let wholesaleAllocated = Int(wholesaleDemand * wShare)
            let internetAllocated = Int(internetDemand * iShare)
            let plAllocated = privateLabelAllocations[team.id] ?? 0

            // Amazon demand allocation
            let aShare = (amazonAttractivities[team.id] ?? 0) / max(totalAmazonAttract, 0.001)
            let amazonAllocated = Int(amazonDemand * aShare)

            // Production capacity
            let baseCapacity = config.plantCapacity
            let overtimeCapacity = Int(Double(baseCapacity) * decision.overtimePercent / 100.0)
            let totalCapacity = baseCapacity + overtimeCapacity

            // Apply rejection rate to production (rejected units are wasted)
            let grossProduction = min(decision.productionQuantity, totalCapacity)
            let rejectedUnits = Int(Double(grossProduction) * rejectionRate)
            let netProduction = grossProduction - rejectedUnits

            let totalAvailable = netProduction + team.inventory
            let totalDemandForTeam = wholesaleAllocated + internetAllocated + amazonAllocated + plAllocated

            // Allocate sales across channels proportionally
            let capForSale = min(totalDemandForTeam, totalAvailable)
            let wSold: Int
            let iSold: Int
            let aSold: Int
            let plSold: Int

            if totalDemandForTeam > 0 {
                let capDouble = Double(capForSale)
                let demandDouble = Double(totalDemandForTeam)
                wSold = min(wholesaleAllocated, Int(capDouble * Double(wholesaleAllocated) / demandDouble))
                let afterW = capForSale - wSold
                let remainDemand3 = Double(amazonAllocated + internetAllocated + plAllocated)
                aSold = min(amazonAllocated, remainDemand3 > 0 ? Int(Double(afterW) * Double(amazonAllocated) / remainDemand3) : 0)
                let afterWA = afterW - aSold
                let remainDemand2 = Double(internetAllocated + plAllocated)
                iSold = min(internetAllocated, remainDemand2 > 0 ? Int(Double(afterWA) * Double(internetAllocated) / remainDemand2) : 0)
                plSold = min(plAllocated, capForSale - wSold - aSold - iSold)
            } else {
                wSold = 0; iSold = 0; aSold = 0; plSold = 0
            }
            let totalSold = wSold + iSold + aSold + plSold

            // Revenue by channel
            let wholesaleRev = Double(wSold) * decision.wholesalePrice
            let internetRev = Double(iSold) * decision.internetPrice
            let privateLabelRev = Double(plSold) * decision.privateLabelBidPrice
            let amazonRev = Double(aSold) * decision.amazonPrice

            // --- COSTS ---

            // Production costs (materials + overtime)
            let materialsCost = config.baseCostPerUnit * decision.materialsQuality.costMultiplier
            let regularUnits = min(grossProduction, baseCapacity)
            let overtimeUnits = max(0, grossProduction - baseCapacity)
            let regularProdCost = materialsCost * Double(regularUnits)
            let overtimeProdCost = materialsCost * overtimeCostPremium * Double(overtimeUnits)
            // Note: rejection waste is already included in regularProdCost (gross production includes rejects)
            
            // Zero production still incurs fixed/decision costs and must flow through
            // the same safe financial ratios and scorecard formulas as every other
            // decision.  An early return here used to leave team state stale and made
            // the offline engine disagree with the backend-authoritative engine.
            let totalProdCost = regularProdCost + overtimeProdCost
                + config.fixedCostsPerRound + decision.stylingBudget
                + decision.tqmInvestment + decision.bestPracticesInvestment

            // Workforce costs
            let workersNeeded = max(1, grossProduction / 10) // ~10 units per worker
            let wageCost = decision.baseWage * Double(workersNeeded) / 1000.0 // Scaled down for game balance
            let incentiveCost = decision.incentivePay * Double(grossProduction)
            let trainingCost = decision.trainingHours * 50.0 * Double(workersNeeded) / 1000.0
            let workforceCosts = wageCost + incentiveCost + trainingCost

            // Marketing costs
            let marketingCost = decision.advertisingBudget + Double(decision.retailOutlets) * 50
            let csrCost = decision.csrInvestment
            let endorseCost = decision.celebrityEndorsement.annualCost

            // Social media & influencer costs
            let influencerCount: Int
            if decision.socialMediaBudget <= 0 {
                influencerCount = 0  // No social media spend = no influencer campaigns
            } else {
                switch decision.influencerTier {
                case .none: influencerCount = 0
                case .nano: influencerCount = max(1, Int(decision.socialMediaBudget / 1000))
                case .micro: influencerCount = max(1, Int(decision.socialMediaBudget / 5000))
                case .macro: influencerCount = max(1, Int(decision.socialMediaBudget / 20000))
                case .mega: influencerCount = max(1, Int(decision.socialMediaBudget / 60000))
                }
            }
            let influencerCost = Double(influencerCount) * decision.influencerTier.costPerInfluencer
            let socialMediaTotalCost = decision.socialMediaBudget + influencerCost

            // Amazon fees
            let amazonReferralFee = amazonRev * 0.15  // 15% referral fee
            let amazonFulfillmentFee = decision.fulfillmentMethod.feePerUnit * Double(aSold)
            let amazonAdCost = decision.amazonAdBudget
            let totalAmazonFees = amazonReferralFee + amazonFulfillmentFee + amazonAdCost

            // Rebate costs (only on wholesale units actually redeemed)
            let rebateRedemptionRate = 0.6
            let rebateCosts = decision.mailInRebate * rebateRedemptionRate * Double(wSold)

            // Delivery costs (wholesale + internet shipping)
            let deliveryCosts = decision.deliveryTime.costPerUnit * Double(wSold)
            // Internet shipping: lower threshold = more orders qualify for free shipping = higher cost
            let freeShipRate = max(0, min(1.0, (100 - decision.freeShippingThreshold) / 100.0))
            let internetShippingCost = Double(iSold) * 5.0 * freeShipRate // ~$5/unit for qualifying orders

            // Inventory storage costs
            let newInventory = max(0, totalAvailable - totalSold)
            let storageCosts = storageCostPerUnit * Double(newInventory)

            // Financial costs
            let interestRate = baseInterestRate * team.creditRating.interestRateMultiplier
            let interestExpense = team.totalDebt * interestRate

            // Share changes: buybacks reduce (capped at outstanding-1), issuances increase
            let safeBuyback = min(decision.sharesBuyback, team.sharesOutstanding - 1)
            let newShares = max(1, team.sharesOutstanding - safeBuyback + decision.sharesIssued)
            let dividendsPaid = decision.dividendsPerShare * Double(newShares)

            // Stock issuance proceeds (capital raised)
            let issuancePrice = max(5, team.cumulativeInvestorScore > 0 ? team.cumulativeInvestorScore / 2 : 15)
            let issuanceProceeds = Double(decision.sharesIssued) * issuancePrice

            let totalRevenue = wholesaleRev + internetRev + amazonRev + privateLabelRev
            let totalCosts = totalProdCost + workforceCosts + marketingCost + csrCost
                + endorseCost + rebateCosts + deliveryCosts + internetShippingCost + storageCosts
                + interestExpense + dividendsPaid + socialMediaTotalCost + totalAmazonFees

            let profit = totalRevenue - totalCosts

            // Update financial state
            let prevStockForBuyback = session.roundResult(for: team.id, round: round - 1)?.scorecard.stockPrice ?? 25.0
            let buybackCost = Double(safeBuyback) * max(5, prevStockForBuyback)
            let cashChange = profit - buybackCost + decision.newLoanAmount + issuanceProceeds
            let newCash = team.cash + cashChange  // Allow negative (bankruptcy tracking)
            let newDebt = max(0, team.totalDebt + decision.newLoanAmount)
            let newEquity = max(1, team.equity + profit)

            // Market share
            let marketShare = Double(totalSold) / max(totalDemand, 1)

            // Customer satisfaction
            let priceFairness = min(1.0, avgWholesalePrice / max(decision.wholesalePrice, 1))
            let supplyAdequacy = totalDemandForTeam > 0 ? min(1.0, Double(totalSold) / Double(totalDemandForTeam)) : 0.5
            let satisfaction = min(1.0, max(0.0,
                0.35 * (sq / 10.0) + 0.3 * priceFairness + 0.2 * supplyAdequacy + 0.15 * team.reputation))

            let newReputation = 0.7 * team.reputation + 0.3 * satisfaction

            // Investor Scorecard with ratcheting targets
            let eps = profit / Double(newShares)
            let roe = profit / newEquity
            let debtToEquity = newEquity > 0 ? newDebt / newEquity : 10
            let interestCoverage = interestExpense > 0 ? max(0, profit + interestExpense) / interestExpense : 20
            let cashRatio = newDebt > 0 ? newCash / newDebt : 5

            let creditRating = CreditRating.fromFinancials(
                debtToEquity: debtToEquity,
                interestCoverage: interestCoverage,
                cashRatio: cashRatio
            )

            // Image rating (includes workforce/CSR/social media factors)
            let sqImageContrib = sq * 5.0
            let adImageContrib = min(15, decision.advertisingBudget / 2000.0 * 5)
            let csrImageContrib = min(15, decision.csrInvestment / 2000.0 * 5)
            let endorseImageContrib = decision.celebrityEndorsement.imageBoost
            let modelsImageContrib = min(10, Double(decision.modelsOffered) * 2)
            let workforceImageContrib = min(5, decision.trainingHours / 40.0 * 5) // Training improves image
            // Social media image contributions
            let instagramImageContrib = min(8, decision.instagramBudget / 10_000 * 8) // Instagram best for image
            let tiktokImageContrib = min(4, decision.tiktokBudget / 10_000 * 4) // TikTok moderate for image
            let youtubeImageContrib = min(5, decision.youtubeBudget / 10_000 * 5) // YouTube builds credibility
            let influencerImageContrib = decision.influencerTier.imageBoost
            let imageRating = min(100, sqImageContrib + adImageContrib + csrImageContrib
                + endorseImageContrib + modelsImageContrib + workforceImageContrib
                + instagramImageContrib + tiktokImageContrib + youtubeImageContrib + influencerImageContrib)

            // Stock price
            let epsGrowthFactor = max(0.5, 1.0 + eps / max(abs(baseEPSTarget), 0.01))
            let roeFactor = max(0.5, 1.0 + roe)
            // Dividend yield based on previous stock price (not static target)
            let previousStockPrice = session.roundResult(for: team.id, round: round - 1)?.scorecard.stockPrice ?? baseStockTarget
            let dividendYield = decision.dividendsPerShare / max(1, previousStockPrice)
            let creditFactor = creditRating.investorScore / 20.0
            // Dilution penalty: issuing too many shares hurts stock price
            let dilutionPenalty = decision.sharesIssued > 0 ? max(0.85, 1.0 - Double(decision.sharesIssued) / Double(max(1, team.sharesOutstanding)) * 0.5) : 1.0
            let rawStockPrice = max(1, baseStockTarget * epsGrowthFactor * roeFactor
                * (1 + dividendYield) * creditFactor * dilutionPenalty
                * rng.noiseFactor(amplitude: 0.03))
            // Blend with previous price to dampen volatility (40% previous, 60% new)
            let stockPrice = round > 1
                ? 0.4 * previousStockPrice + 0.6 * rawStockPrice
                : rawStockPrice

            // Ratcheting targets: expectations increase each round
            let ratchetMultiplier = pow(1.0 + targetRatchetRate, Double(round))
            let epsTarget = baseEPSTarget * ratchetMultiplier
            let roeTarget = baseROETarget * ratchetMultiplier
            let stockTarget = baseStockTarget * ratchetMultiplier
            let imageTarget = min(90, baseImageTarget * (1.0 + 0.03 * Double(round))) // Image target grows slower

            // Scoring (each metric 0-20 pts)
            let epsScore = min(20, max(0, 20 * eps / max(epsTarget, 0.01)))
            let roeScore = min(20, max(0, 20 * roe / max(roeTarget, 0.001)))
            let stockPriceScore = min(20, max(0, 20 * stockPrice / max(stockTarget, 1)))
            let imageScore = min(20, max(0, 20 * imageRating / max(imageTarget, 1)))
            let creditScore = creditRating.investorScore

            let scorecard = InvestorScorecard(
                round: round,
                eps: eps, roe: roe, stockPrice: stockPrice,
                imageRating: imageRating, creditRating: creditRating,
                epsScore: epsScore, roeScore: roeScore, stockPriceScore: stockPriceScore,
                imageScore: imageScore, creditScore: creditScore
            )

            let result = RoundResult(
                teamId: team.id, round: round,
                wholesaleRevenue: wholesaleRev, internetRevenue: internetRev,
                amazonRevenue: amazonRev,
                privateLabelRevenue: privateLabelRev,
                productionCosts: totalProdCost, marketingCosts: marketingCost,
                csrCosts: csrCost, endorsementCosts: endorseCost,
                interestExpense: interestExpense, dividendsPaid: dividendsPaid,
                workforceCosts: workforceCosts, storageCosts: storageCosts,
                rebateCosts: rebateCosts, deliveryCosts: deliveryCosts + internetShippingCost,
                socialMediaCosts: socialMediaTotalCost,
                amazonFees: totalAmazonFees,
                wholesaleUnitsSold: wSold, internetUnitsSold: iSold,
                amazonUnitsSold: aSold,
                privateLabelUnitsSold: plSold,
                marketShare: marketShare, customerSatisfaction: satisfaction,
                inventory: newInventory, rejectionRate: rejectionRate,
                cash: newCash, sqRating: sq,
                awarenessScore: min(1, (decision.advertisingBudget + decision.socialMediaBudget) / 25000),
                scorecard: scorecard
            )

            session.recordResult(result)

            // Update team state (cash, inventory, sqRating, imageRating, creditRating
            // are updated by session.recordResult above — only set remaining fields here)
            if let index = session.teams.firstIndex(where: { $0.id == team.id }) {
                session.teams[index].reputation = newReputation
                session.teams[index].equity = newEquity
                session.teams[index].totalDebt = newDebt
                session.teams[index].sharesOutstanding = newShares
                session.teams[index].cumulativeRD += decision.stylingBudget
                session.teams[index].cumulativeMarketing += decision.advertisingBudget
                session.teams[index].cumulativeCSR += decision.csrInvestment
                session.teams[index].cumulativeTQM += decision.tqmInvestment
            }

            results.append(result)

            // Generate explanations for human player only
            if !team.isAI {
                explanations = generateExplanations(
                    decision: decision, result: result, sq: sq,
                    avgPrice: avgWholesalePrice, marketShare: marketShare,
                    rejectionRate: rejectionRate
                )
            }
        }

        session.updateRankings()
        return (results, explanations)
    }

    // MARK: - Pure Computation (background-thread safe)

    /// Process a round WITHOUT touching SimulationSession.
    /// Takes a snapshot + decisions, returns all results + team updates.
    /// Safe to call on a background thread.
    func processRoundPure(
        snapshot: SimulationSnapshot,
        decisions: [UUID: PlayerDecision]
    ) -> RoundOutput {
        let config = snapshot.config
        let round = snapshot.currentRound
        var rng = SeededRandomGenerator(seed: config.randomSeed &+ UInt64(round))

        // 1. Build team contexts and compute S/Q ratings
        var teamSQRatings: [UUID: Double] = [:]
        var teamRejectionRates: [UUID: Double] = [:]
        var teamContexts: [(team: TeamStatus, decision: PlayerDecision)] = []

        for team in snapshot.teams {
            guard let decision = decisions[team.id] else { continue }

            let updatedCumulativeTQM = team.cumulativeTQM + decision.tqmInvestment

            let sqRating = computeSQRating(
                materialsQuality: decision.materialsQuality,
                stylingBudget: decision.stylingBudget,
                modelsOffered: decision.modelsOffered,
                cumulativeTQM: updatedCumulativeTQM,
                bestPractices: decision.bestPracticesInvestment,
                trainingHours: decision.trainingHours,
                previousSQ: team.sqRating
            )
            teamSQRatings[team.id] = sqRating

            let rejectionRate = computeRejectionRate(
                cumulativeTQM: updatedCumulativeTQM,
                trainingHours: decision.trainingHours,
                incentivePay: decision.incentivePay,
                bestPractices: decision.bestPracticesInvestment
            )
            teamRejectionRates[team.id] = rejectionRate

            teamContexts.append((team, decision))
        }

        // 2. Compute total market demand
        let demandGrowth = min(2.0, 1.0 + 0.05 * Double(round))
        let totalDemand = Double(config.baseMarketDemand)
            * config.marketType.demandMultiplier
            * demandGrowth
            * rng.noiseFactor(amplitude: config.marketType.volatility)

        let wholesaleDemand = totalDemand * wholesaleShare
        let internetDemand = totalDemand * internetShare
        let privateLabelDemand = totalDemand * privateLabelShare
        let amazonDemand = totalDemand * amazonShare

        // 3. Compute competitive indices
        let avgWholesalePrice = teamContexts.map { $0.decision.wholesalePrice }.reduce(0, +) / Double(max(1, teamContexts.count))
        let avgInternetPrice = teamContexts.map { $0.decision.internetPrice }.reduce(0, +) / Double(max(1, teamContexts.count))
        let avgSQ = teamSQRatings.values.reduce(0, +) / Double(max(1, teamSQRatings.count))
        let avgAdvertising = teamContexts.map { $0.decision.advertisingBudget }.reduce(0, +) / Double(max(1, teamContexts.count))
        let avgRebate = teamContexts.map { $0.decision.mailInRebate }.reduce(0, +) / Double(max(1, teamContexts.count))

        var wholesaleAttractivities: [UUID: Double] = [:]
        var internetAttractivities: [UUID: Double] = [:]
        var amazonAttractivities: [UUID: Double] = [:]

        for (team, decision) in teamContexts {
            let sq = teamSQRatings[team.id] ?? 5.0

            let tiktokFactor = 1.0 + min(0.08, decision.tiktokBudget / 15_000 * 0.08)
            let instagramFactor = 1.0 + min(0.06, decision.instagramBudget / 15_000 * 0.06)
            let youtubeFactor = 1.0 + min(0.05, decision.youtubeBudget / 15_000 * 0.05)
            let estInfluencerCount: Double
            if decision.socialMediaBudget <= 0 {
                estInfluencerCount = 0
            } else {
                switch decision.influencerTier {
                case .none: estInfluencerCount = 0
                case .nano: estInfluencerCount = Double(max(1, Int(decision.socialMediaBudget / 1000)))
                case .micro: estInfluencerCount = Double(max(1, Int(decision.socialMediaBudget / 5000)))
                case .macro: estInfluencerCount = Double(max(1, Int(decision.socialMediaBudget / 20000)))
                case .mega: estInfluencerCount = Double(max(1, Int(decision.socialMediaBudget / 60000)))
                }
            }
            let influencerCountFactor = max(1, sqrt(estInfluencerCount))
            let influencerFactor = 1.0 + decision.influencerTier.engagementRate * decision.influencerTier.reachMultiplier * 0.1 * influencerCountFactor
            let socialMediaDemandBoost = tiktokFactor * instagramFactor * youtubeFactor * influencerFactor

            let effectivePrice = decision.wholesalePrice - decision.mailInRebate * 0.6
            let avgEffectivePrice = avgWholesalePrice - avgRebate * 0.6
            let priceAttract = pow(max(avgEffectivePrice, 1) / max(effectivePrice, 1), priceElasticity)
            let sqAttract = pow(sq / max(avgSQ, 1), sqWeight)
            let adAttract = pow(max(decision.advertisingBudget, 100) / max(avgAdvertising, 100), advertisingWeight)
            let outletFactor = 1.0 + Double(decision.retailOutlets) / 100.0 * outletsWeight
            let endorseFactor = decision.celebrityEndorsement.demandBoost
            let reputationFactor = 0.7 + 0.6 * team.reputation
            let deliveryFactor = decision.deliveryTime.demandBoost

            wholesaleAttractivities[team.id] = priceAttract * sqAttract * adAttract
                * outletFactor * endorseFactor * reputationFactor * deliveryFactor
                * socialMediaDemandBoost
                * rng.noiseFactor(amplitude: noiseAmplitude)

            let iPriceAttract = pow(max(avgInternetPrice, 1) / max(decision.internetPrice, 1), priceElasticity * 0.9)
            let iSQAttract = pow(sq / max(avgSQ, 1), sqWeight * 1.1)
            let freeShipBoost = 1.0 + max(0, (100 - decision.freeShippingThreshold) / 200.0)

            internetAttractivities[team.id] = iPriceAttract * iSQAttract * adAttract
                * endorseFactor * reputationFactor * freeShipBoost
                * socialMediaDemandBoost
                * rng.noiseFactor(amplitude: noiseAmplitude)

            let amazonReferralRate = 0.15
            let amazonEffectivePrice = decision.amazonPrice * (1.0 - amazonReferralRate)
            let avgAmazonPrice = teamContexts.map { $0.decision.amazonPrice }.reduce(0, +) / Double(max(1, teamContexts.count))
            let avgAmazonEffective = avgAmazonPrice * (1.0 - amazonReferralRate)
            let aPriceAttract = pow(max(avgAmazonEffective, 1) / max(amazonEffectivePrice, 1), priceElasticity * 0.8)
            let aReviewProxy = pow(sq / max(avgSQ, 1), sqWeight * 1.2)
            let aAdBoost = 1.0 + min(0.15, decision.amazonAdBudget / 10_000 * 0.15)
            let aBuyBox = decision.fulfillmentMethod.buyBoxMultiplier
            let aTrust = decision.fulfillmentMethod.trustMultiplier

            amazonAttractivities[team.id] = aPriceAttract * aReviewProxy * aAdBoost
                * aBuyBox * aTrust * socialMediaDemandBoost
                * rng.noiseFactor(amplitude: noiseAmplitude)
        }

        let totalWholesaleAttract = wholesaleAttractivities.values.reduce(0, +)
        let totalInternetAttract = internetAttractivities.values.reduce(0, +)
        let totalAmazonAttract = amazonAttractivities.values.reduce(0, +)

        // 4. Private-label allocation (lowest bid wins)
        let privateLabelBids = teamContexts.sorted { $0.decision.privateLabelBidPrice < $1.decision.privateLabelBidPrice }
        var privateLabelAllocations: [UUID: Int] = [:]
        var remainingPL = Int(privateLabelDemand)
        for (team, decision) in privateLabelBids {
            if remainingPL <= 0 { break }
            let allocation = min(decision.privateLabelMaxUnits, remainingPL)
            privateLabelAllocations[team.id] = allocation
            remainingPL -= allocation
        }

        // 5. Compute results for each team
        var results: [RoundResult] = []
        var explanations: [ResultExplanation] = []
        var teamUpdates: [TeamUpdate] = []
        var updatedRoundResults = snapshot.roundResults

        for (team, decision) in teamContexts {
            let sq = teamSQRatings[team.id] ?? 5.0
            let rejectionRate = teamRejectionRates[team.id] ?? 0.08

            let wShare = (wholesaleAttractivities[team.id] ?? 0) / max(totalWholesaleAttract, 0.001)
            let iShare = (internetAttractivities[team.id] ?? 0) / max(totalInternetAttract, 0.001)
            let wholesaleAllocated = Int(wholesaleDemand * wShare)
            let internetAllocated = Int(internetDemand * iShare)
            let plAllocated = privateLabelAllocations[team.id] ?? 0
            let aShare = (amazonAttractivities[team.id] ?? 0) / max(totalAmazonAttract, 0.001)
            let amazonAllocated = Int(amazonDemand * aShare)

            let baseCapacity = config.plantCapacity
            let overtimeCapacity = Int(Double(baseCapacity) * decision.overtimePercent / 100.0)
            let totalCapacity = baseCapacity + overtimeCapacity
            let grossProduction = min(decision.productionQuantity, totalCapacity)
            let rejectedUnits = Int(Double(grossProduction) * rejectionRate)
            let netProduction = grossProduction - rejectedUnits
            let totalAvailable = netProduction + team.inventory
            let totalDemandForTeam = wholesaleAllocated + internetAllocated + amazonAllocated + plAllocated
            let capForSale = min(totalDemandForTeam, totalAvailable)

            let wSold: Int, iSold: Int, aSold: Int, plSold: Int
            if totalDemandForTeam > 0 {
                let capDouble = Double(capForSale)
                let demandDouble = Double(totalDemandForTeam)
                wSold = min(wholesaleAllocated, Int(capDouble * Double(wholesaleAllocated) / demandDouble))
                let afterW = capForSale - wSold
                let remainDemand3 = Double(amazonAllocated + internetAllocated + plAllocated)
                aSold = min(amazonAllocated, remainDemand3 > 0 ? Int(Double(afterW) * Double(amazonAllocated) / remainDemand3) : 0)
                let afterWA = afterW - aSold
                let remainDemand2 = Double(internetAllocated + plAllocated)
                iSold = min(internetAllocated, remainDemand2 > 0 ? Int(Double(afterWA) * Double(internetAllocated) / remainDemand2) : 0)
                plSold = min(plAllocated, capForSale - wSold - aSold - iSold)
            } else {
                wSold = 0; iSold = 0; aSold = 0; plSold = 0
            }
            let totalSold = wSold + iSold + aSold + plSold

            let wholesaleRev = Double(wSold) * decision.wholesalePrice
            let internetRev = Double(iSold) * decision.internetPrice
            let privateLabelRev = Double(plSold) * decision.privateLabelBidPrice
            let amazonRev = Double(aSold) * decision.amazonPrice

            let materialsCost = config.baseCostPerUnit * decision.materialsQuality.costMultiplier
            let regularUnits = min(grossProduction, baseCapacity)
            let overtimeUnits = max(0, grossProduction - baseCapacity)
            let regularProdCost = materialsCost * Double(regularUnits)
            let overtimeProdCost = materialsCost * overtimeCostPremium * Double(overtimeUnits)

            // Keep zero-production decisions on the normal path: fixed and chosen
            // spending still apply, while denominator guards below make the resulting
            // financial ratios deterministic and finite.

            let totalProdCost = regularProdCost + overtimeProdCost
                + config.fixedCostsPerRound + decision.stylingBudget
                + decision.tqmInvestment + decision.bestPracticesInvestment

            let workersNeeded = max(1, grossProduction / 10)
            let wageCost = decision.baseWage * Double(workersNeeded) / 1000.0
            let incentiveCost = decision.incentivePay * Double(grossProduction)
            let trainingCost = decision.trainingHours * 50.0 * Double(workersNeeded) / 1000.0
            let workforceCosts = wageCost + incentiveCost + trainingCost

            let marketingCost = decision.advertisingBudget + Double(decision.retailOutlets) * 50
            let csrCost = decision.csrInvestment
            let endorseCost = decision.celebrityEndorsement.annualCost

            let influencerCount: Int
            if decision.socialMediaBudget <= 0 {
                influencerCount = 0
            } else {
                switch decision.influencerTier {
                case .none: influencerCount = 0
                case .nano: influencerCount = max(1, Int(decision.socialMediaBudget / 1000))
                case .micro: influencerCount = max(1, Int(decision.socialMediaBudget / 5000))
                case .macro: influencerCount = max(1, Int(decision.socialMediaBudget / 20000))
                case .mega: influencerCount = max(1, Int(decision.socialMediaBudget / 60000))
                }
            }
            let influencerCost = Double(influencerCount) * decision.influencerTier.costPerInfluencer
            let socialMediaTotalCost = decision.socialMediaBudget + influencerCost

            let amazonReferralFee = amazonRev * 0.15
            let amazonFulfillmentFee = decision.fulfillmentMethod.feePerUnit * Double(aSold)
            let amazonAdCost = decision.amazonAdBudget
            let totalAmazonFees = amazonReferralFee + amazonFulfillmentFee + amazonAdCost

            let rebateRedemptionRate = 0.6
            let rebateCosts = decision.mailInRebate * rebateRedemptionRate * Double(wSold)
            let deliveryCosts = decision.deliveryTime.costPerUnit * Double(wSold)
            let freeShipRate = max(0, min(1.0, (100 - decision.freeShippingThreshold) / 100.0))
            let internetShippingCost = Double(iSold) * 5.0 * freeShipRate
            let newInventory = max(0, totalAvailable - totalSold)
            let storageCosts = storageCostPerUnit * Double(newInventory)

            let interestRate = baseInterestRate * team.creditRating.interestRateMultiplier
            let interestExpense = team.totalDebt * interestRate
            let safeBuyback = min(decision.sharesBuyback, team.sharesOutstanding - 1)
            let newShares = max(1, team.sharesOutstanding - safeBuyback + decision.sharesIssued)
            let dividendsPaid = decision.dividendsPerShare * Double(newShares)
            let issuancePrice = max(5, team.cumulativeInvestorScore > 0 ? team.cumulativeInvestorScore / 2 : 15)
            let issuanceProceeds = Double(decision.sharesIssued) * issuancePrice

            let totalRevenue = wholesaleRev + internetRev + amazonRev + privateLabelRev
            let totalCosts = totalProdCost + workforceCosts + marketingCost + csrCost
                + endorseCost + rebateCosts + deliveryCosts + internetShippingCost + storageCosts
                + interestExpense + dividendsPaid + socialMediaTotalCost + totalAmazonFees
            let profit = totalRevenue - totalCosts

            let prevStockForBuyback = updatedRoundResults[team.id]?[round - 1]?.scorecard.stockPrice ?? 25.0
            let buybackCost = Double(safeBuyback) * max(5, prevStockForBuyback)
            let cashChange = profit - buybackCost + decision.newLoanAmount + issuanceProceeds
            let newCash = team.cash + cashChange
            let newDebt = max(0, team.totalDebt + decision.newLoanAmount)
            let newEquity = max(1, team.equity + profit)
            let marketShare = Double(totalSold) / max(totalDemand, 1)

            let priceFairness = min(1.0, avgWholesalePrice / max(decision.wholesalePrice, 1))
            let supplyAdequacy = totalDemandForTeam > 0 ? min(1.0, Double(totalSold) / Double(totalDemandForTeam)) : 0.5
            let satisfaction = min(1.0, max(0.0,
                0.35 * (sq / 10.0) + 0.3 * priceFairness + 0.2 * supplyAdequacy + 0.15 * team.reputation))
            let newReputation = 0.7 * team.reputation + 0.3 * satisfaction

            let eps = profit / Double(newShares)
            let roe = profit / newEquity
            let debtToEquity = newEquity > 0 ? newDebt / newEquity : 10
            let interestCoverage = interestExpense > 0 ? max(0, profit + interestExpense) / interestExpense : 20
            let cashRatio = newDebt > 0 ? newCash / newDebt : 5
            let creditRating = CreditRating.fromFinancials(
                debtToEquity: debtToEquity, interestCoverage: interestCoverage, cashRatio: cashRatio)

            let sqImageContrib = sq * 5.0
            let adImageContrib = min(15, decision.advertisingBudget / 2000.0 * 5)
            let csrImageContrib = min(15, decision.csrInvestment / 2000.0 * 5)
            let endorseImageContrib = decision.celebrityEndorsement.imageBoost
            let modelsImageContrib = min(10, Double(decision.modelsOffered) * 2)
            let workforceImageContrib = min(5, decision.trainingHours / 40.0 * 5)
            let instagramImageContrib = min(8, decision.instagramBudget / 10_000 * 8)
            let tiktokImageContrib = min(4, decision.tiktokBudget / 10_000 * 4)
            let youtubeImageContrib = min(5, decision.youtubeBudget / 10_000 * 5)
            let influencerImageContrib = decision.influencerTier.imageBoost
            let imageRating = min(100, sqImageContrib + adImageContrib + csrImageContrib
                + endorseImageContrib + modelsImageContrib + workforceImageContrib
                + instagramImageContrib + tiktokImageContrib + youtubeImageContrib + influencerImageContrib)

            let epsGrowthFactor = max(0.5, 1.0 + eps / max(abs(baseEPSTarget), 0.01))
            let roeFactor = max(0.5, 1.0 + roe)
            let previousStockPrice = updatedRoundResults[team.id]?[round - 1]?.scorecard.stockPrice ?? baseStockTarget
            let dividendYield = decision.dividendsPerShare / max(1, previousStockPrice)
            let creditFactor = creditRating.investorScore / 20.0
            let dilutionPenalty = decision.sharesIssued > 0 ? max(0.85, 1.0 - Double(decision.sharesIssued) / Double(max(1, team.sharesOutstanding)) * 0.5) : 1.0
            let rawStockPrice = max(1, baseStockTarget * epsGrowthFactor * roeFactor
                * (1 + dividendYield) * creditFactor * dilutionPenalty
                * rng.noiseFactor(amplitude: 0.03))
            let stockPrice = round > 1 ? 0.4 * previousStockPrice + 0.6 * rawStockPrice : rawStockPrice

            let ratchetMultiplier = pow(1.0 + targetRatchetRate, Double(round))
            let epsTarget = baseEPSTarget * ratchetMultiplier
            let roeTarget = baseROETarget * ratchetMultiplier
            let stockTarget = baseStockTarget * ratchetMultiplier
            let imageTarget = min(90, baseImageTarget * (1.0 + 0.03 * Double(round)))

            let epsScore = min(20, max(0, 20 * eps / max(epsTarget, 0.01)))
            let roeScore = min(20, max(0, 20 * roe / max(roeTarget, 0.001)))
            let stockPriceScore = min(20, max(0, 20 * stockPrice / max(stockTarget, 1)))
            let imageScore = min(20, max(0, 20 * imageRating / max(imageTarget, 1)))
            let creditScore = creditRating.investorScore

            let scorecard = InvestorScorecard(
                round: round, eps: eps, roe: roe, stockPrice: stockPrice,
                imageRating: imageRating, creditRating: creditRating,
                epsScore: epsScore, roeScore: roeScore, stockPriceScore: stockPriceScore,
                imageScore: imageScore, creditScore: creditScore)

            let result = RoundResult(
                teamId: team.id, round: round,
                wholesaleRevenue: wholesaleRev, internetRevenue: internetRev,
                amazonRevenue: amazonRev, privateLabelRevenue: privateLabelRev,
                productionCosts: totalProdCost, marketingCosts: marketingCost,
                csrCosts: csrCost, endorsementCosts: endorseCost,
                interestExpense: interestExpense, dividendsPaid: dividendsPaid,
                workforceCosts: workforceCosts, storageCosts: storageCosts,
                rebateCosts: rebateCosts, deliveryCosts: deliveryCosts + internetShippingCost,
                socialMediaCosts: socialMediaTotalCost, amazonFees: totalAmazonFees,
                wholesaleUnitsSold: wSold, internetUnitsSold: iSold,
                amazonUnitsSold: aSold, privateLabelUnitsSold: plSold,
                marketShare: marketShare, customerSatisfaction: satisfaction,
                inventory: newInventory, rejectionRate: rejectionRate,
                cash: newCash, sqRating: sq,
                awarenessScore: min(1, (decision.advertisingBudget + decision.socialMediaBudget) / 25000),
                scorecard: scorecard)

            results.append(result)
            if updatedRoundResults[team.id] == nil { updatedRoundResults[team.id] = [:] }
            updatedRoundResults[team.id]?[round] = result

            let prevTotal = team.cumulativeInvestorScore * Double(team.roundsScored)
            let newRoundsScored = team.roundsScored + 1
            let newCumInvestorScore = (prevTotal + scorecard.totalScore) / Double(newRoundsScored)

            teamUpdates.append(TeamUpdate(
                teamId: team.id, cash: newCash, inventory: newInventory,
                sqRating: sq, imageRating: imageRating, creditRating: creditRating,
                reputation: newReputation, equity: newEquity, totalDebt: newDebt,
                sharesOutstanding: newShares,
                cumulativeRD: team.cumulativeRD + decision.stylingBudget,
                cumulativeMarketing: team.cumulativeMarketing + decision.advertisingBudget,
                cumulativeCSR: team.cumulativeCSR + decision.csrInvestment,
                cumulativeTQM: team.cumulativeTQM + decision.tqmInvestment,
                cumulativeProfit: team.cumulativeProfit + profit,
                cumulativeInvestorScore: newCumInvestorScore,
                roundsScored: newRoundsScored,
                hasSubmittedDecisions: false, rank: team.rank))

            if !team.isAI {
                explanations = generateExplanations(
                    decision: decision, result: result, sq: sq,
                    avgPrice: avgWholesalePrice, marketShare: marketShare,
                    rejectionRate: rejectionRate)
            }
        }

        return RoundOutput(
            round: round, results: results, explanations: explanations,
            teamUpdates: teamUpdates, updatedRoundResults: updatedRoundResults)
    }

    // MARK: - S/Q Rating (Enhanced with workforce factors)

    private func computeSQRating(
        materialsQuality: MaterialsQuality,
        stylingBudget: Double,
        modelsOffered: Int,
        cumulativeTQM: Double,
        bestPractices: Double,
        trainingHours: Double,
        previousSQ: Double
    ) -> Double {
        var sq = 3.0 + materialsQuality.sqBonus
        sq += min(2.0, log(1 + stylingBudget / 3000) / log(5))
        sq += min(1.5, Double(modelsOffered) * 0.3)
        sq += min(1.5, log(1 + cumulativeTQM / 5000) / log(10))
        // Best practices and training boost S/Q
        sq += min(0.5, bestPractices / 5000)
        sq += min(0.5, trainingHours / 80.0)
        let blended = 0.4 * previousSQ + 0.6 * sq
        return min(10.0, max(1.0, blended))
    }

    // MARK: - Rejection Rate (defect rate)

    private func computeRejectionRate(
        cumulativeTQM: Double,
        trainingHours: Double,
        incentivePay: Double,
        bestPractices: Double
    ) -> Double {
        // Base rejection rate is 12%; reduced by TQM, training, incentive pay, best practices
        var rate = 0.12
        rate -= min(0.04, cumulativeTQM / 200000)    // TQM reduces up to 4% (needs ~$200K cumulative)
        rate -= min(0.03, trainingHours / 100.0 * 0.03)  // Training reduces up to 3%
        rate -= min(0.02, incentivePay / 2.0 * 0.02)     // Incentive pay reduces up to 2%
        rate -= min(0.02, bestPractices / 5000 * 0.02)    // Best practices reduces up to 2%
        return max(0.01, rate) // Minimum 1% rejection rate
    }

    // MARK: - Explanations (Enhanced)

    private func generateExplanations(
        decision: PlayerDecision, result: RoundResult, sq: Double,
        avgPrice: Double, marketShare: Double, rejectionRate: Double
    ) -> [ResultExplanation] {
        var explanations: [ResultExplanation] = []

        if sq >= 7.0 {
            explanations.append(ResultExplanation(
                metric: "S/Q Rating",
                explanation: "Your S/Q rating of \(String(format: "%.1f", sq))★ is strong, attracting quality-conscious buyers.",
                impact: .positive))
        } else if sq < 4.0 {
            explanations.append(ResultExplanation(
                metric: "S/Q Rating",
                explanation: "Your S/Q rating of \(String(format: "%.1f", sq))★ is low. Invest in materials, styling, TQM, and training.",
                impact: .negative))
        }

        if decision.wholesalePrice > avgPrice * 1.15 {
            explanations.append(ResultExplanation(
                metric: "Wholesale Pricing",
                explanation: "Your price ($\(String(format: "%.0f", decision.wholesalePrice))) is above market avg ($\(String(format: "%.0f", avgPrice))). Ensure S/Q justifies the premium.",
                impact: .negative))
        } else if decision.wholesalePrice < avgPrice * 0.85 {
            explanations.append(ResultExplanation(
                metric: "Wholesale Pricing",
                explanation: "Aggressive pricing at $\(String(format: "%.0f", decision.wholesalePrice)) vs $\(String(format: "%.0f", avgPrice)) avg. Watch margins.",
                impact: .neutral))
        }

        // Rejection rate feedback
        if rejectionRate > 0.08 {
            explanations.append(ResultExplanation(
                metric: "Rejection Rate",
                explanation: "Defect rate of \(String(format: "%.1f", rejectionRate * 100))% is costing you \(String(format: "%.0f", result.productionCosts * rejectionRate)) in wasted materials. Invest in TQM, training, and incentive pay.",
                impact: .negative))
        } else if rejectionRate <= 0.03 {
            explanations.append(ResultExplanation(
                metric: "Rejection Rate",
                explanation: "Excellent defect rate of \(String(format: "%.1f", rejectionRate * 100))% — your quality programs are paying off.",
                impact: .positive))
        }

        // Inventory feedback
        if result.inventory > 0 && result.storageCosts > 100 {
            explanations.append(ResultExplanation(
                metric: "Inventory",
                explanation: "\(result.inventory) unsold units costing $\(String(format: "%.0f", result.storageCosts)) in storage. Reduce production or boost demand.",
                impact: .negative))
        }

        let totalRev = result.revenue
        if totalRev > 0 {
            let internetPct = result.internetRevenue / totalRev * 100
            if internetPct > 40 {
                explanations.append(ResultExplanation(
                    metric: "Internet Sales",
                    explanation: "Internet channel at \(String(format: "%.0f", internetPct))% of revenue — higher margins driving profitability.",
                    impact: .positive))
            }
        }

        let score = result.scorecard.totalScore
        if score >= 80 {
            explanations.append(ResultExplanation(
                metric: "Investor Score",
                explanation: "Outstanding score of \(String(format: "%.0f", score))/100. Shareholders are delighted.",
                impact: .positive))
        } else if score < 40 {
            explanations.append(ResultExplanation(
                metric: "Investor Score",
                explanation: "Score of \(String(format: "%.0f", score))/100 is concerning. Targets ratchet up each round — act now.",
                impact: .negative))
        }

        if result.profit < 0 {
            explanations.append(ResultExplanation(
                metric: "Profitability",
                explanation: "Loss of $\(String(format: "%.0f", abs(result.profit))). Review costs and pricing.",
                impact: .negative))
        }

        // Mail-in rebate feedback
        if decision.mailInRebate > 0 && result.rebateCosts > 0 {
            explanations.append(ResultExplanation(
                metric: "Mail-in Rebate",
                explanation: "Rebate of $\(String(format: "%.0f", decision.mailInRebate))/pair cost $\(String(format: "%.0f", result.rebateCosts)) but boosted wholesale demand.",
                impact: .neutral))
        }

        // Social media feedback
        if decision.socialMediaBudget > 0 {
            let platforms: [String] = [
                decision.tiktokBudget > 0 ? "TikTok" : nil,
                decision.instagramBudget > 0 ? "Instagram" : nil,
                decision.youtubeBudget > 0 ? "YouTube" : nil
            ].compactMap { $0 }
            let platformList = platforms.joined(separator: ", ")
            let tierDesc = decision.influencerTier != .none ? " with \(decision.influencerTier.displayName) influencers" : ""
            explanations.append(ResultExplanation(
                metric: "Social Media",
                explanation: "Spending $\(String(format: "%.0f", decision.socialMediaBudget)) on \(platformList)\(tierDesc) — boosting awareness and internet demand.",
                impact: decision.socialMediaBudget > 5000 ? .positive : .neutral))
        }

        // Amazon channel feedback
        if result.amazonUnitsSold > 0 {
            let amazonPct = result.amazonRevenue / max(result.revenue, 1) * 100
            let netAmazonProfit = result.amazonRevenue - result.amazonFees
            explanations.append(ResultExplanation(
                metric: "Amazon Sales",
                explanation: "Amazon channel: \(result.amazonUnitsSold) units (\(String(format: "%.0f", amazonPct))% of revenue). Net after fees: $\(String(format: "%.0f", netAmazonProfit)).",
                impact: netAmazonProfit > 0 ? .positive : .negative))
        }

        return explanations
    }
}
