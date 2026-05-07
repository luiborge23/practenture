import SwiftUI

// MARK: - SessionMonitorViewModel
/// ViewModel for the professor's session monitoring screens.
/// Orchestrates AI decisions, engine processing, and round advancement.

@Observable
final class SessionMonitorViewModel {

    // MARK: - Types

    struct MonitoredTeamStatus: Identifiable {
        let id: UUID
        let teamName: String
        let isAI: Bool
        var hasSubmittedDecision: Bool
        var cash: Double
        var reputation: Double
        var rank: Int
        var sqRating: Double
        var imageRating: Double
        var investorScore: Double

        var formattedCash: String {
            cash.formatted(.currency(code: "USD").precision(.fractionLength(0)))
        }

        var statusLabel: String {
            hasSubmittedDecision ? "Submitted" : "Pending"
        }
    }

    // MARK: - Properties

    var session: SimulationSession
    var teams: [MonitoredTeamStatus] = []
    var isProcessingRound: Bool = false
    var roundProcessingError: String?
    var showEndSessionConfirmation: Bool = false
    var backendSubmittedCount: Int = 0
    var backendTeamCount: Int = 0
    var backendTeamStatus: String = ""

    private let engine = SimulationEngine()
    private var aiCompetitors: [AICompetitor] = []

    // MARK: - Init

    init(session: SimulationSession) {
        self.session = session
        self.aiCompetitors = AIStrategyFactory.createCompetitors(
            for: session,
            difficulty: session.config.aiDifficulty
        )
        refreshTeamStatuses()
    }

    // MARK: - Computed

    var currentRound: Int { session.currentRound }
    var totalRounds: Int { session.totalRounds }
    var roundProgress: String { "Round \(currentRound) of \(totalRounds)" }

    var roundProgressFraction: Double {
        guard totalRounds > 0 else { return 0 }
        return Double(currentRound) / Double(totalRounds)
    }

    var allDecisionsSubmitted: Bool {
        teams.allSatisfy { $0.hasSubmittedDecision }
    }

    var submittedCount: Int {
        teams.filter(\.hasSubmittedDecision).count
    }

    var pendingCount: Int {
        teams.filter { !$0.hasSubmittedDecision }.count
    }

    var submissionSummary: String {
        "\(submittedCount)/\(teams.count) teams submitted"
    }

    var canAdvanceRound: Bool {
        allDecisionsSubmitted && !isProcessingRound && !isSessionComplete
    }

    var isLastRound: Bool {
        currentRound >= totalRounds
    }

    var isSessionComplete: Bool {
        session.state == .completed
    }

    var sessionStatusLabel: String {
        session.state.displayName
    }

    // MARK: - Actions

    func advanceRound() {
        guard canAdvanceRound else { return }

        isProcessingRound = true
        roundProcessingError = nil

        // Generate AI decisions
        var rng = SeededRandomGenerator(seed: session.config.randomSeed &+ UInt64(session.currentRound))
        let playerPrevDecision: PlayerDecision? = session.previousRoundDecisions[session.playerTeam?.id ?? UUID()]

        // Compute average prices from already-submitted decisions
        let submittedDecisions = Array(session.currentRoundDecisions.values)
        let avgWholesale = submittedDecisions.isEmpty ? 80.0
            : submittedDecisions.map(\.wholesalePrice).reduce(0, +) / Double(submittedDecisions.count)
        let avgInternet = submittedDecisions.isEmpty ? 90.0
            : submittedDecisions.map(\.internetPrice).reduce(0, +) / Double(submittedDecisions.count)

        for aiComp in aiCompetitors {
            guard let team = session.teams.first(where: { $0.id == aiComp.teamId }) else { continue }
            let competitorProfits = session.teams.reduce(into: [:]) { dict, t in
                dict[t.id] = t.cumulativeProfit
            }
            let context = AIDecisionContext(
                config: session.config,
                team: team,
                playerPreviousDecision: playerPrevDecision,
                roundsRemaining: session.totalRounds - session.currentRound,
                competitorProfits: competitorProfits,
                averageWholesalePrice: avgWholesale,
                averageInternetPrice: avgInternet
            )
            let decision = aiComp.strategy.makeDecisions(
                teamId: aiComp.teamId,
                round: session.currentRound,
                context: context,
                rng: &rng
            )
            session.submitDecision(decision)
        }

        // Process through engine
        let (results, _) = engine.processRound(
            session: session,
            decisions: session.currentRoundDecisions
        )

        // Update AI competitor metrics
        for result in results {
            if let index = aiCompetitors.firstIndex(where: { $0.teamId == result.teamId }) {
                aiCompetitors[index].updateFromResult(result)
            }
        }

        session.advanceRound()
        refreshTeamStatuses()
        isProcessingRound = false
    }

    func endSession() {
        session.state = .completed
    }

    func refreshTeamStatuses() {
        teams = session.teams.map { team in
            MonitoredTeamStatus(
                id: team.id,
                teamName: team.name,
                isAI: team.isAI,
                hasSubmittedDecision: team.isAI || team.hasSubmittedDecisions,
                cash: team.cash,
                reputation: team.reputation,
                rank: team.rank,
                sqRating: team.sqRating,
                imageRating: team.imageRating,
                investorScore: team.cumulativeInvestorScore
            )
        }
    }

    func statusColor(for teamStatus: MonitoredTeamStatus) -> Color {
        teamStatus.hasSubmittedDecision ? .green : .orange
    }

    // MARK: - Backend Sync

    /// Poll the backend for the current team submission status.
    func pollBackendStatus() async {
        let sessionCode = session.sessionCode
        do {
            let status = try await NetworkService.shared.getSessionStatus(code: sessionCode)
            backendSubmittedCount = status.teamsSubmitted
            backendTeamCount = status.totalTeams
            backendTeamStatus = status.state
        } catch {
            // Backend unavailable — keep local state
            backendSubmittedCount = submittedCount
            backendTeamCount = teams.count
            backendTeamStatus = session.state.rawValue
        }
    }

    /// Process the round via backend and sync results back.
    func processRoundWithBackend() async {
        guard canAdvanceRound else { return }

        isProcessingRound = true
        roundProcessingError = nil

        let sessionCode = session.sessionCode

        // Generate AI decisions locally first
        var rng = SeededRandomGenerator(seed: session.config.randomSeed &+ UInt64(session.currentRound))
        let playerPrevDecision: PlayerDecision? = session.previousRoundDecisions[session.playerTeam?.id ?? UUID()]

        let submittedDecisions = Array(session.currentRoundDecisions.values)
        let avgWholesale = submittedDecisions.isEmpty ? 80.0
            : submittedDecisions.map(\.wholesalePrice).reduce(0, +) / Double(submittedDecisions.count)
        let avgInternet = submittedDecisions.isEmpty ? 90.0
            : submittedDecisions.map(\.internetPrice).reduce(0, +) / Double(submittedDecisions.count)

        for aiComp in aiCompetitors {
            guard let team = session.teams.first(where: { $0.id == aiComp.teamId }) else { continue }
            let competitorProfits = session.teams.reduce(into: [:]) { dict, t in
                dict[t.id] = t.cumulativeProfit
            }
            let context = AIDecisionContext(
                config: session.config,
                team: team,
                playerPreviousDecision: playerPrevDecision,
                roundsRemaining: session.totalRounds - session.currentRound,
                competitorProfits: competitorProfits,
                averageWholesalePrice: avgWholesale,
                averageInternetPrice: avgInternet
            )
            let decision = aiComp.strategy.makeDecisions(
                teamId: aiComp.teamId,
                round: session.currentRound,
                context: context,
                rng: &rng
            )
            session.submitDecision(decision)
        }

        // Send to backend for processing
        do {
            let results = try await NetworkService.shared.processRound(code: sessionCode)

            // Update local state from backend results
            for result in results {
                let teamUUID = UUID(uuidString: result.teamId) ?? UUID()
                if let index = teams.firstIndex(where: { $0.id == teamUUID }) {
                    teams[index].cash = result.cash
                    teams[index].reputation = result.reputation
                    teams[index].sqRating = result.sqRating
                    teams[index].investorScore = result.totalScore
                }
                if let aiIndex = aiCompetitors.firstIndex(where: { $0.teamId == teamUUID }) {
                    // Use lightweight update — no full RoundResult needed
                    aiCompetitors[aiIndex].updateFromBackendResult(
                        profit: result.profit,
                        revenue: result.revenue,
                        marketShare: result.marketShare
                    )
                }
            }

            session.advanceRound()
            refreshTeamStatuses()
        } catch {
            // Backend failed — fall back to local processing
            let (localResults, _) = engine.processRound(
                session: session,
                decisions: session.currentRoundDecisions
            )
            for result in localResults {
                if let index = aiCompetitors.firstIndex(where: { $0.teamId == result.teamId }) {
                    aiCompetitors[index].updateFromResult(result)
                }
            }
            session.advanceRound()
            refreshTeamStatuses()
            roundProcessingError = "Backend failed, used local processing: \(error.localizedDescription)"
        }

        isProcessingRound = false
    }

    func endSessionWithBackend() async {
        let sessionCode = session.sessionCode
        do {
            try await NetworkService.shared.endSession(code: sessionCode)
        } catch {
            // Silently ignore — session ends locally regardless
        }
        session.state = .completed
    }
}
