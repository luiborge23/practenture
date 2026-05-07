// GameController.swift
// BizSimAI
//
// Manages the game loop: generates AI decisions, processes rounds via the
// SimulationEngine, and advances the session. Also provides a "Quick Demo"
// auto-play mode that runs the full simulation with diverse team strategies.

import Foundation
import Observation

@Observable
final class GameController {

    // MARK: - Properties

    let session: SimulationSession
    private let engine: SimulationEngine
    private var aiCompetitors: [AICompetitor]

    var latestExplanations: [ResultExplanation] = []
    var isProcessing: Bool = false
    var lastRoundResults: [RoundResult] = []

    // MARK: - Init

    init(session: SimulationSession) {
        self.session = session
        self.engine = SimulationEngine()
        self.aiCompetitors = AIStrategyFactory.createCompetitors(
            for: session, difficulty: session.config.aiDifficulty
        )
        // Start the game
        if session.currentRound == 0 {
            session.advanceRound()
        }
    }

    // MARK: - Submit Player Decisions & Process Round

    /// Called after the player submits decisions. Generates AI decisions,
    /// processes the round, and advances to the next round.
    func processRoundAfterPlayerSubmit() {
        guard !isProcessing else { return }
        isProcessing = true

        let round = session.currentRound

        // Generate AI decisions using PREVIOUS round's player decision (not current)
        guard let playerTeamId = session.teams.first(where: { !$0.isAI })?.id else {
            // No human team found, skip AI decision generation
            isProcessing = false
            return
        }
        let playerPrevDecision: PlayerDecision? = session.previousRoundDecisions[playerTeamId]

        // Use submitted player decisions for average prices (current round)
        let submittedDecisions = Array(session.currentRoundDecisions.values)
        let avgWholesale = submittedDecisions.isEmpty ? 80.0
            : submittedDecisions.map(\.wholesalePrice).reduce(0, +) / Double(submittedDecisions.count)
        let avgInternet = submittedDecisions.isEmpty ? 90.0
            : submittedDecisions.map(\.internetPrice).reduce(0, +) / Double(submittedDecisions.count)

        for competitor in aiCompetitors {
            guard let aiTeam = session.teams.first(where: { $0.id == competitor.teamId }) else { continue }
            let competitorProfits = session.teams.reduce(into: [:]) { dict, t in
                dict[t.id] = t.cumulativeProfit
            }
            let context = AIDecisionContext(
                config: session.config,
                team: aiTeam,
                playerPreviousDecision: playerPrevDecision,
                roundsRemaining: session.config.totalRounds - round,
                competitorProfits: competitorProfits,
                averageWholesalePrice: avgWholesale,
                averageInternetPrice: avgInternet
            )

            var rng = SeededRandomGenerator(seed: session.config.randomSeed &+ UInt64(round) &+ UInt64(bitPattern: Int64(competitor.teamId.hashValue)))
            let aiDecision = competitor.strategy.makeDecisions(
                teamId: competitor.teamId, round: round, context: context, rng: &rng
            )
            session.submitDecision(aiDecision)
        }

        // Process the round
        let (results, explanations) = engine.processRound(
            session: session, decisions: session.currentRoundDecisions
        )

        lastRoundResults = results
        latestExplanations = explanations

        // Update AI competitor tracking
        for result in results {
            if let idx = aiCompetitors.firstIndex(where: { $0.teamId == result.teamId }) {
                aiCompetitors[idx].updateFromResult(result)
            }
        }

        // Add player round summary
        if let playerTeam = session.playerTeam,
           let playerResult = results.first(where: { $0.teamId == playerTeam.id }),
           let playerDec = session.currentRoundDecisions[playerTeam.id] {
            let summary = RoundSummary(from: playerResult, price: playerDec.wholesalePrice)
            session.playerRoundSummaries.append(summary)
        }

        // Advance to next round
        session.advanceRound()
        isProcessing = false
    }

    // MARK: - Quick Demo (Auto-Play Full Simulation)

    /// Runs the entire simulation automatically with preset player decisions.
    /// Returns after all rounds are complete. Uses a "Best-Cost" strategy for the player.
    func runQuickDemo() {
        guard !isProcessing else { return }
        isProcessing = true

        let totalRounds = session.config.totalRounds

        var previousPlayerDecision: PlayerDecision? = nil

        while session.currentRound <= totalRounds && session.state != .completed {
            let round = session.currentRound

            // Generate player decision (Best-Cost style for demo)
            guard let playerTeam = session.playerTeam else { break }
            let playerDecision = generateDemoPlayerDecision(
                teamId: playerTeam.id, round: round
            )
            session.submitDecision(playerDecision)

            // Generate AI decisions using PREVIOUS round's player decision
            let avgWholesale = playerDecision.wholesalePrice
            let avgInternet = playerDecision.internetPrice

            for competitor in aiCompetitors {
                guard let aiTeam = session.teams.first(where: { $0.id == competitor.teamId }) else { continue }
                let competitorProfits = session.teams.reduce(into: [:]) { dict, t in
                    dict[t.id] = t.cumulativeTQM
                }
                let context = AIDecisionContext(
                    config: session.config,
                    team: aiTeam,
                    playerPreviousDecision: previousPlayerDecision,
                    roundsRemaining: totalRounds - round,
                    competitorProfits: competitorProfits,
                    averageWholesalePrice: avgWholesale,
                    averageInternetPrice: avgInternet
                )
                var rng = SeededRandomGenerator(seed: session.config.randomSeed &+ UInt64(round) &+ UInt64(bitPattern: Int64(competitor.teamId.hashValue)))
                let aiDecision = competitor.strategy.makeDecisions(
                    teamId: competitor.teamId, round: round, context: context, rng: &rng
                )
                session.submitDecision(aiDecision)
            }

            // Process the round
            let (results, explanations) = engine.processRound(
                session: session, decisions: session.currentRoundDecisions
            )
            lastRoundResults = results
            latestExplanations = explanations

            // Update AI tracking
            for result in results {
                if let idx = aiCompetitors.firstIndex(where: { $0.teamId == result.teamId }) {
                    aiCompetitors[idx].updateFromResult(result)
                }
            }

            // Add player round summary
            if let pResult = results.first(where: { $0.teamId == playerTeam.id }) {
                let summary = RoundSummary(from: pResult, price: playerDecision.wholesalePrice)
                session.playerRoundSummaries.append(summary)
            }

            // Advance
            previousPlayerDecision = playerDecision
            session.advanceRound()
        }

        isProcessing = false
    }

    // MARK: - Demo Player Decision Generator

    /// Generates reasonable "Best-Cost Provider" decisions for the demo player.
    /// Decisions evolve over rounds to simulate a real player learning.
    private func generateDemoPlayerDecision(teamId: UUID, round: Int) -> PlayerDecision {
        let baseCost = session.config.baseCostPerUnit

        // Gradually improve strategy over rounds
        let materialsQuality: MaterialsQuality = round >= 3 ? .superior : .standard
        let celebrity: CelebrityEndorsement = round >= 4 ? .local : .none

        let _wholesalePrice = baseCost * 2.2 + Double(round) * 1.5
        let _internetPrice = baseCost * 2.5 + Double(round) * 2.0
        let _privateLabelBidPrice = baseCost * 1.3
        let _stylingBudget = 3_000 + Double(round) * 300
        let _tqmInvestment = 2_000 + Double(round) * 200
        let _advertisingBudget = 8_000 + Double(round) * 500
        let _amazonPrice = baseCost * 2.1 + Double(round) * 1.0
        let _amazonAdBudget = round >= 2 ? 1000 + Double(round) * 300 : 0
        let _tiktokBudget = round >= 2 ? 1500 + Double(round) * 300 : 0
        let _instagramBudget = round >= 2 ? 2000 + Double(round) * 400 : 0
        let _youtubeBudget = round >= 3 ? 1500 + Double(round) * 300 : 0
        let _bestPracticesInvestment = 1_500 + Double(round) * 200
        let _csrInvestment = 2_000 + Double(round) * 300

        return PlayerDecision(
            teamId: teamId,
            round: round,
            pricing: PricingDecision(
                wholesalePrice: _wholesalePrice,
                internetPrice: _internetPrice,
                privateLabelBidPrice: _privateLabelBidPrice,
                privateLabelMaxUnits: 60,
                amazonPrice: _amazonPrice,
                amazonAdBudget: _amazonAdBudget
            ),
            product: ProductDecision(
                materialsQuality: materialsQuality,
                stylingBudget: _stylingBudget,
                modelsOffered: min(5, 3 + round / 3),
                tqmInvestment: _tqmInvestment
            ),
            marketing: MarketingDecision(
                advertisingBudget: _advertisingBudget,
                celebrityEndorsement: celebrity,
                retailOutlets: min(45, 20 + round * 3),
                mailInRebate: round >= 3 ? 3.0 : 0,
                deliveryTime: round >= 6 ? .rush : .standard,
                freeShippingThreshold: round >= 4 ? 50 : 100,
                tiktokBudget: _tiktokBudget,
                instagramBudget: _instagramBudget,
                youtubeBudget: _youtubeBudget,
                influencerTier: round >= 4 ? .micro : (round >= 2 ? .nano : .none)
            ),
            workforce: WorkforceDecision(
                baseWage: 26_000,
                incentivePay: 0.60 + Double(round) * 0.05,
                trainingHours: 20 + Double(round) * 3,
                bestPracticesInvestment: _bestPracticesInvestment
            ),
            production: ProductionDecision(
                productionQuantity: min(session.config.plantCapacity + 50, 250 + round * 20),
                overtimePercent: round >= 5 ? 10 : 0
            ),
            finance: FinanceDecision(
                csrInvestment: _csrInvestment,
                dividendsPerShare: 0.50 + Double(round) * 0.05,
                newLoanAmount: 0,
                sharesBuyback: round >= 7 ? 100 : 0,
                sharesIssued: 0
            ),
            fulfillmentMethod: round >= 4 ? .fba : .fbm
        )
    }
}
