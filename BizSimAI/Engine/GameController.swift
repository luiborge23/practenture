// GameController.swift
// BizSimAI
//
// Manages the game loop: generates AI decisions, processes rounds via the
// SimulationEngine, and advances the session. Also provides a "Quick Demo"
// auto-play mode that runs the full simulation with diverse team strategies.

import Foundation
import Observation
import os

@Observable
final class GameController: @unchecked Sendable {

    // MARK: - Properties

    static let logger = Logger(subsystem: "com.bizsimai", category: "GameController")

    /// Debug log that uses NSLog for reliable console capture
    private static func dlog(_ msg: String) {
        NSLog("[BizSimAI] \(msg)")
    }

    let session: SimulationSession
    private let engine: SimulationEngine
    private var aiCompetitors: [AICompetitor]

    var latestExplanations: [ResultExplanation] = []
    var isProcessing: Bool = false
    var lastRoundResults: [RoundResult] = []

    // MARK: - Init

    init(session: SimulationSession) {
        Self.dlog("GameController init starting")
        self.session = session
        self.engine = SimulationEngine()
        Self.dlog("Creating AI competitors")
        self.aiCompetitors = AIStrategyFactory.createCompetitors(
            for: session, difficulty: session.config.aiDifficulty
        )
        Self.dlog("AI competitors created: \(self.aiCompetitors.count)")
        // Start the game
        if session.currentRound == 0 {
            session.advanceRound()
        }
    }

    // MARK: - Submit Player Decisions & Process Round

    /// Called after the player submits decisions. Generates AI decisions,
    /// processes the round, and advances to the next round.
    /// Uses snapshot→background→apply pattern so UI never freezes.
    func processRoundAfterPlayerSubmit() {
        guard !isProcessing else { return }
        isProcessing = true

        let round = session.currentRound

        // Generate AI decisions (main thread, touches @Observable)
        guard let playerTeamId = session.teams.first(where: { !$0.isAI })?.id else {
            isProcessing = false
            return
        }
        let playerPrevDecision: PlayerDecision? = session.previousRoundDecisions[playerTeamId]

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
            var rng = SeededRandomGenerator(
                seed: session.config.randomSeed
                &+ UInt64(round)
                &+ UInt64(bitPattern: Int64(competitor.teamId.hashValue)))
            let aiDecision = competitor.strategy.makeDecisions(
                teamId: competitor.teamId, round: round, context: context, rng: &rng)
            session.submitDecision(aiDecision)
        }

        // Snapshot → Background Compute → Main-Thread Apply
        let snapshot = session.takeSnapshot()
        let decisions = session.currentRoundDecisions

        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }

            let output = self.engine.processRoundPure(
                snapshot: snapshot, decisions: decisions)

            // Apply results on main thread
            DispatchQueue.main.async {
                self.session.applyRoundOutput(output)
                self.lastRoundResults = output.results
                self.latestExplanations = output.explanations

                // Update AI tracking
                for result in output.results {
                    if let idx = self.aiCompetitors.firstIndex(where: { $0.teamId == result.teamId }) {
                        self.aiCompetitors[idx].updateFromResult(result)
                    }
                }

                // Add player round summary
                if let playerTeam = self.session.playerTeam,
                   let playerResult = output.results.first(where: { $0.teamId == playerTeam.id }),
                   let playerDec = decisions[playerTeam.id] {
                    let summary = RoundSummary(from: playerResult, price: playerDec.wholesalePrice)
                    self.session.playerRoundSummaries.append(summary)
                }

                self.session.advanceRound()
                self.isProcessing = false
            }
        }
    }

    // MARK: - Quick Demo (Auto-Play Full Simulation)

    /// Runs the entire simulation automatically with preset player decisions.
    /// Runs synchronously on main thread using pure computation (no @Model access during compute).
    /// The snapshot pattern reduces JSON cycles from 240+ to ~16, making this fast enough
    /// to run on the main thread without freezing.
    func runQuickDemo() {
        guard !isProcessing else { return }
        isProcessing = true
        Self.dlog("runQuickDemo STARTED (synchronous)")

        let totalRounds = session.config.totalRounds
        let baseCostPerUnit = session.config.baseCostPerUnit
        let plantCapacity = session.config.plantCapacity

        let aiStrategyMap: [(teamId: UUID, strategy: AIStrategyProtocol)] = aiCompetitors.map {
            (teamId: $0.teamId, strategy: $0.strategy)
        }

        Self.dlog("Taking snapshot...")
        var workingSnapshot = session.takeSnapshot()
        Self.dlog("Snapshot taken. Teams: \(workingSnapshot.teams.count)")

        var allOutputs: [RoundOutput] = []
        var allPlayerSummaries: [RoundSummary] = []
        var finalRoundResults = workingSnapshot.roundResults

        for round in 1...totalRounds {
            Self.dlog("Round \(round) start")
            guard let playerTeamId = workingSnapshot.teams.first(where: { !$0.isAI })?.id else { break }

            let playerDecision = generateDemoPlayerDecision(
                teamId: playerTeamId, round: round,
                baseCostPerUnit: baseCostPerUnit, plantCapacity: plantCapacity
            )

            var roundDecisions: [UUID: PlayerDecision] = [:]
            roundDecisions[playerTeamId] = playerDecision

            for team in workingSnapshot.teams where team.isAI {
                guard let aiEntry = aiStrategyMap.first(where: { $0.teamId == team.id }) else { continue }
                let competitorProfits = workingSnapshot.teams.reduce(into: [UUID: Double]()) { dict, t in
                    dict[t.id] = t.cumulativeTQM
                }
                let context = AIDecisionContext(
                    config: workingSnapshot.config,
                    team: team,
                    playerPreviousDecision: nil,
                    roundsRemaining: totalRounds - round,
                    competitorProfits: competitorProfits,
                    averageWholesalePrice: playerDecision.wholesalePrice,
                    averageInternetPrice: playerDecision.internetPrice
                )
                var rng = SeededRandomGenerator(
                    seed: workingSnapshot.config.randomSeed
                    &+ UInt64(round)
                    &+ UInt64(bitPattern: Int64(team.id.hashValue)))
                let aiDecision = aiEntry.strategy.makeDecisions(
                    teamId: team.id, round: round, context: context, rng: &rng)
                roundDecisions[team.id] = aiDecision
            }

            workingSnapshot = SimulationSnapshot(
                config: workingSnapshot.config,
                currentRound: round,
                teams: workingSnapshot.teams,
                decisions: roundDecisions,
                previousRoundDecisions: workingSnapshot.previousRoundDecisions,
                roundResults: finalRoundResults
            )

            Self.dlog("Round \(round) computing...")
            let output = engine.processRoundPure(
                snapshot: workingSnapshot, decisions: roundDecisions)
            Self.dlog("Round \(round) done. Results: \(output.results.count)")

            finalRoundResults = output.updatedRoundResults
            allOutputs.append(output)

            if let pResult = output.results.first(where: { $0.teamId == playerTeamId }) {
                allPlayerSummaries.append(
                    RoundSummary(from: pResult, price: playerDecision.wholesalePrice))
            }

            // Update teams for next round
            var updatedTeams = workingSnapshot.teams
            for update in output.teamUpdates {
                if let idx = updatedTeams.firstIndex(where: { $0.id == update.teamId }) {
                    updatedTeams[idx].cash = update.cash
                    updatedTeams[idx].inventory = update.inventory
                    updatedTeams[idx].sqRating = update.sqRating
                    updatedTeams[idx].imageRating = update.imageRating
                    updatedTeams[idx].creditRating = update.creditRating
                    updatedTeams[idx].reputation = update.reputation
                    updatedTeams[idx].equity = update.equity
                    updatedTeams[idx].totalDebt = update.totalDebt
                    updatedTeams[idx].sharesOutstanding = update.sharesOutstanding
                    updatedTeams[idx].cumulativeRD = update.cumulativeRD
                    updatedTeams[idx].cumulativeMarketing = update.cumulativeMarketing
                    updatedTeams[idx].cumulativeCSR = update.cumulativeCSR
                    updatedTeams[idx].cumulativeTQM = update.cumulativeTQM
                    updatedTeams[idx].cumulativeProfit = update.cumulativeProfit
                    updatedTeams[idx].cumulativeInvestorScore = update.cumulativeInvestorScore
                    updatedTeams[idx].roundsScored = update.roundsScored
                }
            }

            workingSnapshot = SimulationSnapshot(
                config: workingSnapshot.config,
                currentRound: round + 1,
                teams: updatedTeams,
                decisions: [:],
                previousRoundDecisions: roundDecisions,
                roundResults: finalRoundResults
            )
        }

        Self.dlog("All rounds done. Applying \(allOutputs.count) outputs...")
        // Apply all outputs to session
        for output in allOutputs {
            session.applyRoundOutput(output)
        }
        session.playerRoundSummaries.append(contentsOf: allPlayerSummaries)

        if let lastOutput = allOutputs.last {
            lastRoundResults = lastOutput.results
            latestExplanations = lastOutput.explanations
            for result in lastOutput.results {
                if let idx = aiCompetitors.firstIndex(where: { $0.teamId == result.teamId }) {
                    aiCompetitors[idx].updateFromResult(result)
                }
            }
        }

        // CRITICAL: Set session to completed state
        // applyRoundOutput doesn't update currentRound — set it directly
        session.currentRound = totalRounds
        session.state = .completed
        Self.dlog("Session state: \(session.state.rawValue), currentRound: \(session.currentRound)")

        isProcessing = false
        Self.dlog("runQuickDemo COMPLETE")
    }

    // MARK: - Demo Player Decision Generator

    /// Generates reasonable "Best-Cost Provider" decisions for the demo player.
    /// Decisions evolve over rounds to simulate a real player learning.
    /// NOTE: Takes baseCostPerUnit and plantCapacity as params to avoid
    /// accessing session.config from background thread.
    private func generateDemoPlayerDecision(
        teamId: UUID, round: Int,
        baseCostPerUnit: Double, plantCapacity: Int
    ) -> PlayerDecision {
        let baseCost = baseCostPerUnit

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
                productionQuantity: min(plantCapacity + 50, 250 + round * 20),
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
