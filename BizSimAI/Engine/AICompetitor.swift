import Foundation

// MARK: - AI Strategy Protocol

protocol AIStrategyProtocol {
    func makeDecisions(teamId: UUID, round: Int, context: AIDecisionContext, rng: inout SeededRandomGenerator) -> PlayerDecision
}

// MARK: - AI Decision Context

struct AIDecisionContext {
    let config: SessionConfiguration
    let team: TeamStatus
    let playerPreviousDecision: PlayerDecision?
    let roundsRemaining: Int
    let competitorProfits: [UUID: Double]
    let averageWholesalePrice: Double
    let averageInternetPrice: Double
}

// MARK: - Low-Cost Leader Strategy (aggressive pricing, standard quality, lean workforce)

struct LowCostLeaderStrategy: AIStrategyProtocol {
    func makeDecisions(teamId: UUID, round: Int, context: AIDecisionContext, rng: inout SeededRandomGenerator) -> PlayerDecision {
        let baseCost = context.config.baseCostPerUnit
        let cash = context.team.cash
        // Emergency loan if cash is negative
        let emergencyLoan = cash < 0 ? min(50_000, abs(cash) + 10_000) : 0.0

        let _wholesalePrice = baseCost * 1.6 * rng.noiseFactor(amplitude: 0.08)
        let _internetPrice = baseCost * 1.8 * rng.noiseFactor(amplitude: 0.08)
        let _privateLabelBidPrice = baseCost * 1.2 * rng.noiseFactor(amplitude: 0.05)
        let _stylingBudget = 1500 * rng.noiseFactor(amplitude: 0.1)
        let _tqmInvestment = 1000 * rng.noiseFactor(amplitude: 0.1)
        let _advertisingBudget = max(0, cash * 0.15 * rng.noiseFactor(amplitude: 0.1))
        let _amazonPrice = baseCost * 1.7 * rng.noiseFactor(amplitude: 0.08)
        let _amazonAdBudget = round >= 2 ? 800 * rng.noiseFactor(amplitude: 0.1) : 0
        let _productionQuantity = Int(Double(context.config.plantCapacity) * 1.1 * rng.noiseFactor(amplitude: 0.1))

        return PlayerDecision(
            teamId: teamId,
            round: round,
            pricing: PricingDecision(
                wholesalePrice: _wholesalePrice,
                internetPrice: _internetPrice,
                privateLabelBidPrice: _privateLabelBidPrice,
                privateLabelMaxUnits: Int(Double(context.config.plantCapacity) * 0.3),
                amazonPrice: _amazonPrice,
                amazonAdBudget: _amazonAdBudget
            ),
            product: ProductDecision(
                materialsQuality: .standard,
                stylingBudget: _stylingBudget,
                modelsOffered: 2,
                tqmInvestment: _tqmInvestment
            ),
            marketing: MarketingDecision(
                advertisingBudget: _advertisingBudget,
                celebrityEndorsement: .none,
                retailOutlets: 30,
                mailInRebate: 2.0,
                deliveryTime: .standard,
                freeShippingThreshold: 150,
                tiktokBudget: round >= 2 ? 1000 : 0,
                instagramBudget: 0,
                youtubeBudget: 0,
                influencerTier: round >= 4 ? .nano : .none
            ),
            workforce: WorkforceDecision(
                baseWage: 22_000,
                incentivePay: 0.30,
                trainingHours: 10,
                bestPracticesInvestment: 500
            ),
            production: ProductionDecision(
                productionQuantity: _productionQuantity,
                overtimePercent: 10
            ),
            finance: FinanceDecision(
                csrInvestment: 500,
                dividendsPerShare: 0.30,
                newLoanAmount: emergencyLoan,
                sharesBuyback: 0,
                sharesIssued: 0
            ),
            fulfillmentMethod: .fbm
        )
    }
}

// MARK: - Differentiator Strategy (premium quality, high marketing, strong workforce)

struct DifferentiatorStrategy: AIStrategyProtocol {
    func makeDecisions(teamId: UUID, round: Int, context: AIDecisionContext, rng: inout SeededRandomGenerator) -> PlayerDecision {
        let baseCost = context.config.baseCostPerUnit
        let cash = context.team.cash
        let emergencyLoan = cash < 0 ? min(50_000, abs(cash) + 10_000) : 0.0

        let _wholesalePrice = baseCost * 2.5 * rng.noiseFactor(amplitude: 0.08)
        let _internetPrice = baseCost * 2.8 * rng.noiseFactor(amplitude: 0.08)
        let _privateLabelBidPrice = baseCost * 1.5 * rng.noiseFactor(amplitude: 0.05)
        let _stylingBudget = 6000 * rng.noiseFactor(amplitude: 0.1)
        let _tqmInvestment = 4000 * rng.noiseFactor(amplitude: 0.1)
        let _advertisingBudget = max(0, cash * 0.12 * rng.noiseFactor(amplitude: 0.1))
        let _amazonPrice = baseCost * 2.6 * rng.noiseFactor(amplitude: 0.08)
        let _amazonAdBudget = round >= 2 ? 3000 * rng.noiseFactor(amplitude: 0.1) : 0
        let _tiktokBudget = round >= 2 ? 3000 * rng.noiseFactor(amplitude: 0.1) : 0
        let _instagramBudget = round >= 2 ? 5000 * rng.noiseFactor(amplitude: 0.1) : 0
        let _youtubeBudget = round >= 3 ? 4000 * rng.noiseFactor(amplitude: 0.1) : 0
        let _bestPracticesInvestment = 3000 * rng.noiseFactor(amplitude: 0.1)
        let _productionQuantity = Int(Double(context.config.plantCapacity) * 0.8 * rng.noiseFactor(amplitude: 0.1))
        let _csrInvestment = 3000 * rng.noiseFactor(amplitude: 0.1)

        return PlayerDecision(
            teamId: teamId,
            round: round,
            pricing: PricingDecision(
                wholesalePrice: _wholesalePrice,
                internetPrice: _internetPrice,
                privateLabelBidPrice: _privateLabelBidPrice,
                privateLabelMaxUnits: Int(Double(context.config.plantCapacity) * 0.1),
                amazonPrice: _amazonPrice,
                amazonAdBudget: _amazonAdBudget
            ),
            product: ProductDecision(
                materialsQuality: .superior,
                stylingBudget: _stylingBudget,
                modelsOffered: 5,
                tqmInvestment: _tqmInvestment
            ),
            marketing: MarketingDecision(
                advertisingBudget: _advertisingBudget,
                celebrityEndorsement: round >= 3 ? .national : .local,
                retailOutlets: 40,
                mailInRebate: 0,
                deliveryTime: .rush,
                freeShippingThreshold: 0,
                tiktokBudget: _tiktokBudget,
                instagramBudget: _instagramBudget,
                youtubeBudget: _youtubeBudget,
                influencerTier: round >= 3 ? .macro : (round >= 2 ? .micro : .none)
            ),
            workforce: WorkforceDecision(
                baseWage: 30_000,
                incentivePay: 1.00,
                trainingHours: 40,
                bestPracticesInvestment: _bestPracticesInvestment
            ),
            production: ProductionDecision(
                productionQuantity: _productionQuantity,
                overtimePercent: 0
            ),
            finance: FinanceDecision(
                csrInvestment: _csrInvestment,
                dividendsPerShare: 0.80,
                newLoanAmount: emergencyLoan,
                sharesBuyback: round >= 5 ? 200 : 0,
                sharesIssued: 0
            ),
            fulfillmentMethod: .fba
        )
    }
}

// MARK: - Best-Cost Provider Strategy (balanced quality and pricing)

struct BestCostStrategy: AIStrategyProtocol {
    func makeDecisions(teamId: UUID, round: Int, context: AIDecisionContext, rng: inout SeededRandomGenerator) -> PlayerDecision {
        let baseCost = context.config.baseCostPerUnit
        let cash = context.team.cash
        let emergencyLoan = cash < 0 ? min(50_000, abs(cash) + 10_000) : 0.0

        // Late-game: slightly more aggressive if behind
        let lateGamePriceAdj = context.roundsRemaining <= 3 ? 0.95 : 1.0

        let _wholesalePrice = baseCost * 2.0 * lateGamePriceAdj * rng.noiseFactor(amplitude: 0.08)
        let _internetPrice = baseCost * 2.3 * lateGamePriceAdj * rng.noiseFactor(amplitude: 0.08)
        let _privateLabelBidPrice = baseCost * 1.3 * rng.noiseFactor(amplitude: 0.05)
        let _stylingBudget = 3500 * rng.noiseFactor(amplitude: 0.1)
        let _tqmInvestment = 2500 * rng.noiseFactor(amplitude: 0.1)
        let _advertisingBudget = max(0, cash * 0.10 * rng.noiseFactor(amplitude: 0.1))
        let _amazonPrice = baseCost * 2.1 * lateGamePriceAdj * rng.noiseFactor(amplitude: 0.08)
        let _amazonAdBudget = round >= 2 ? 1500 * rng.noiseFactor(amplitude: 0.1) : 0
        let _tiktokBudget = round >= 2 ? 2000 * rng.noiseFactor(amplitude: 0.1) : 0
        let _instagramBudget = round >= 3 ? 2500 * rng.noiseFactor(amplitude: 0.1) : 0
        let _youtubeBudget = round >= 4 ? 2000 * rng.noiseFactor(amplitude: 0.1) : 0
        let _bestPracticesInvestment = 1500 * rng.noiseFactor(amplitude: 0.1)
        let _productionQuantity = Int(Double(context.config.plantCapacity) * 0.95 * rng.noiseFactor(amplitude: 0.1))
        let _csrInvestment = 2000 * rng.noiseFactor(amplitude: 0.1)

        return PlayerDecision(
            teamId: teamId,
            round: round,
            pricing: PricingDecision(
                wholesalePrice: _wholesalePrice,
                internetPrice: _internetPrice,
                privateLabelBidPrice: _privateLabelBidPrice,
                privateLabelMaxUnits: Int(Double(context.config.plantCapacity) * 0.2),
                amazonPrice: _amazonPrice,
                amazonAdBudget: _amazonAdBudget
            ),
            product: ProductDecision(
                materialsQuality: round >= 4 ? .superior : .standard,
                stylingBudget: _stylingBudget,
                modelsOffered: 4,
                tqmInvestment: _tqmInvestment
            ),
            marketing: MarketingDecision(
                advertisingBudget: _advertisingBudget,
                celebrityEndorsement: round >= 4 ? .local : .none,
                retailOutlets: 35,
                mailInRebate: round >= 3 ? 3.0 : 0,
                deliveryTime: round >= 5 ? .rush : .standard,
                freeShippingThreshold: 75,
                tiktokBudget: _tiktokBudget,
                instagramBudget: _instagramBudget,
                youtubeBudget: _youtubeBudget,
                influencerTier: round >= 3 ? .micro : (round >= 2 ? .nano : .none)
            ),
            workforce: WorkforceDecision(
                baseWage: 25_000,
                incentivePay: 0.60,
                trainingHours: 25,
                bestPracticesInvestment: _bestPracticesInvestment
            ),
            production: ProductionDecision(
                productionQuantity: _productionQuantity,
                overtimePercent: 5
            ),
            finance: FinanceDecision(
                csrInvestment: _csrInvestment,
                dividendsPerShare: min(1.50, 0.50 + Double(round) * 0.05),
                newLoanAmount: emergencyLoan,
                sharesBuyback: round >= 6 ? 100 : 0,
                sharesIssued: 0
            ),
            fulfillmentMethod: round >= 4 ? .fba : .fbm
        )
    }
}

// MARK: - Adaptive Strategy (counter-plays the human)

struct AdaptiveStrategy: AIStrategyProtocol {
    func makeDecisions(teamId: UUID, round: Int, context: AIDecisionContext, rng: inout SeededRandomGenerator) -> PlayerDecision {
        let baseCost = context.config.baseCostPerUnit
        let cash = context.team.cash
        let emergencyLoan = cash < 0 ? min(50_000, abs(cash) + 10_000) : 0.0

        // Analyze player's last move to counter
        let playerPrice = context.playerPreviousDecision?.wholesalePrice ?? (baseCost * 2.0)
        let playerInternetPrice = context.playerPreviousDecision?.internetPrice ?? (baseCost * 2.3)
        let playerMaterials = context.playerPreviousDecision?.materialsQuality ?? .standard
        let playerRebate = context.playerPreviousDecision?.mailInRebate ?? 0

        // Counter-strategy: undercut if player prices high, go premium if player prices low
        let priceRatio = playerPrice / (baseCost * 2.0)
        let wholesalePrice: Double
        let materialsQuality: MaterialsQuality
        let stylingBudget: Double
        let mailInRebate: Double

        if priceRatio > 1.2 {
            // Player is pricing high — undercut with decent quality
            wholesalePrice = playerPrice * 0.88 * rng.noiseFactor(amplitude: 0.05)
            materialsQuality = .standard
            stylingBudget = 3000
            mailInRebate = min(10.0, max(0, playerRebate + 1.0)) // Beat their rebate, capped
        } else if priceRatio < 0.85 {
            // Player is pricing low — go premium to differentiate
            wholesalePrice = baseCost * 2.3 * rng.noiseFactor(amplitude: 0.05)
            materialsQuality = .superior
            stylingBudget = 5000
            mailInRebate = 0
        } else {
            // Player is moderate — match and compete on other factors
            wholesalePrice = playerPrice * 0.97 * rng.noiseFactor(amplitude: 0.05)
            materialsQuality = playerMaterials
            stylingBudget = 3500
            mailInRebate = 2.0
        }

        // Minimum price must cover material cost with margin
        let materialsCost = materialsQuality == .superior ? baseCost * 1.4 : baseCost
        let minPrice = materialsCost * 1.3

        // End-game boost
        let endGameBoost = context.roundsRemaining <= 2 ? 1.2 : 1.0

        let _internetPrice = max(minPrice * 1.15, min(playerInternetPrice * 0.95, baseCost * 2.5) * rng.noiseFactor(amplitude: 0.05))
        let _privateLabelBidPrice = baseCost * 1.25 * rng.noiseFactor(amplitude: 0.05)
        let _stylingBudget = stylingBudget * rng.noiseFactor(amplitude: 0.1)
        let _tqmInvestment = 2000 * rng.noiseFactor(amplitude: 0.1)
        let _advertisingBudget = max(0, cash * 0.12 * endGameBoost * rng.noiseFactor(amplitude: 0.1))
        let _amazonPrice = max(minPrice * 1.2, min(playerPrice * 0.92, baseCost * 2.3) * rng.noiseFactor(amplitude: 0.05))
        let _amazonAdBudget = round >= 2 ? 2000 * endGameBoost * rng.noiseFactor(amplitude: 0.15) : 0
        let _tiktokBudget = round >= 2 ? 2500 * endGameBoost * rng.noiseFactor(amplitude: 0.15) : 0
        let _instagramBudget = round >= 2 ? 3000 * endGameBoost * rng.noiseFactor(amplitude: 0.15) : 0
        let _youtubeBudget = round >= 3 ? 2000 * endGameBoost * rng.noiseFactor(amplitude: 0.15) : 0
        let _bestPracticesInvestment = 2000 * rng.noiseFactor(amplitude: 0.1)
        let _productionQuantity = Int(Double(context.config.plantCapacity) * 1.0 * rng.noiseFactor(amplitude: 0.1))
        let _csrInvestment = 1500 * rng.noiseFactor(amplitude: 0.1)

        return PlayerDecision(
            teamId: teamId,
            round: round,
            pricing: PricingDecision(
                wholesalePrice: max(minPrice, wholesalePrice),
                internetPrice: _internetPrice,
                privateLabelBidPrice: _privateLabelBidPrice,
                privateLabelMaxUnits: Int(Double(context.config.plantCapacity) * 0.25),
                amazonPrice: _amazonPrice,
                amazonAdBudget: _amazonAdBudget
            ),
            product: ProductDecision(
                materialsQuality: materialsQuality,
                stylingBudget: _stylingBudget,
                modelsOffered: 4,
                tqmInvestment: _tqmInvestment
            ),
            marketing: MarketingDecision(
                advertisingBudget: _advertisingBudget,
                celebrityEndorsement: round >= 3 ? .local : .none,
                retailOutlets: 35,
                mailInRebate: mailInRebate,
                deliveryTime: context.roundsRemaining <= 3 ? .rush : .standard,
                freeShippingThreshold: 50,
                tiktokBudget: _tiktokBudget,
                instagramBudget: _instagramBudget,
                youtubeBudget: _youtubeBudget,
                influencerTier: round >= 4 ? .micro : (round >= 2 ? .nano : .none)
            ),
            workforce: WorkforceDecision(
                baseWage: 26_000,
                incentivePay: 0.70,
                trainingHours: 30,
                bestPracticesInvestment: _bestPracticesInvestment
            ),
            production: ProductionDecision(
                productionQuantity: _productionQuantity,
                overtimePercent: context.roundsRemaining <= 2 ? 15 : 5
            ),
            finance: FinanceDecision(
                csrInvestment: _csrInvestment,
                dividendsPerShare: 0.50,
                newLoanAmount: emergencyLoan,
                sharesBuyback: context.roundsRemaining <= 3 ? 150 : 0,
                sharesIssued: 0
            ),
            fulfillmentMethod: round >= 3 ? .fba : .fbm
        )
    }
}

// MARK: - AI Competitor

struct AICompetitor {
    let teamId: UUID
    let name: String
    let strategy: AIStrategyProtocol

    var cumulativeProfit: Double = 0
    var cumulativeRevenue: Double = 0
    var latestMarketShare: Double = 0

    mutating func updateFromResult(_ result: RoundResult) {
        cumulativeProfit += result.profit
        cumulativeRevenue += result.revenue
        latestMarketShare = result.marketShare
    }

    /// Lightweight update from backend round result data (no full RoundResult needed).
    mutating func updateFromBackendResult(profit: Double, revenue: Double, marketShare: Double) {
        cumulativeProfit += profit
        cumulativeRevenue += revenue
        latestMarketShare = marketShare
    }
}

// MARK: - Strategy Factory

enum AIStrategyFactory {
    static func createCompetitors(
        for session: SimulationSession,
        difficulty: AIDifficulty
    ) -> [AICompetitor] {
        let aiTeams = session.teams.filter { $0.isAI }
        var competitors: [AICompetitor] = []

        for (index, team) in aiTeams.enumerated() {
            let strategy: AIStrategyProtocol
            switch difficulty {
            case .easy:
                strategy = index % 2 == 0 ? BestCostStrategy() : LowCostLeaderStrategy()
            case .medium:
                switch index % 4 {
                case 0: strategy = LowCostLeaderStrategy()
                case 1: strategy = DifferentiatorStrategy()
                case 2: strategy = BestCostStrategy()
                default: strategy = AdaptiveStrategy()
                }
            case .hard:
                switch index % 3 {
                case 0: strategy = AdaptiveStrategy()
                case 1: strategy = DifferentiatorStrategy()
                default: strategy = BestCostStrategy()
                }
            }

            competitors.append(AICompetitor(
                teamId: team.id,
                name: team.name,
                strategy: strategy
            ))
        }
        return competitors
    }
}
