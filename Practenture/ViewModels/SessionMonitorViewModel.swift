import SwiftUI
import os
import Combine
import os

// MARK: - SessionMonitorViewModel
/// ViewModel for the professor's session monitoring screens.
/// Uses the backend as the sole round authority for online classroom sessions.
/// The local engine remains available only for explicit offline/demo sessions.
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
    var lastPollTime: Date = .now
    var isPollingActive: Bool = false

    private let engine = SimulationEngine()
    private var aiCompetitors: [AICompetitor] = []
    private var pollingTimer: Timer?
    private let pollingInterval: TimeInterval = 10 // Poll every 10 seconds

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

    var isBackendSession: Bool {
        !session.sessionCode.isEmpty && session.sessionCode != session.id.uuidString
    }

    var allDecisionsSubmitted: Bool {
        if isBackendSession {
            return backendTeamCount > 0 && backendSubmittedCount >= backendTeamCount
        }
        return teams.allSatisfy { $0.hasSubmittedDecision }
    }

    var submittedCount: Int {
        if isBackendSession { return backendSubmittedCount }
        return teams.filter(\.hasSubmittedDecision).count
    }

    var pendingCount: Int {
        if isBackendSession { return max(backendTeamCount - backendSubmittedCount, 0) }
        return teams.filter { !$0.hasSubmittedDecision }.count
    }

    var submissionSummary: String {
        "\(submittedCount)/\(isBackendSession ? backendTeamCount : teams.count) teams submitted"
    }

    var canAdvanceRound: Bool {
        allDecisionsSubmitted && !isProcessingRound && !isSessionComplete
            && (!isBackendSession || backendTeamStatus == "active")
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

    // MARK: - Backend Sync & Polling

    /// Start polling the backend for session status updates.
    func startPolling() {
        guard !isPollingActive else { return }
        isPollingActive = true
        lastPollTime = .now
        
        // Initial poll
        Task {
            await pollBackendStatus()
        }
        
        // Set up periodic polling
        pollingTimer = Timer.scheduledTimer(withTimeInterval: pollingInterval, repeats: true) { [weak self] _ in
            Task { @MainActor in
                await self?.pollBackendStatus()
            }
        }
    }

    /// Stop polling the backend.
    func stopPolling() {
        isPollingActive = false
        pollingTimer?.invalidate()
        pollingTimer = nil
    }

    /// Poll the backend for the current team submission status.
    func pollBackendStatus() async {
        guard !session.sessionCode.isEmpty else { return }

        let sessionCode = session.sessionCode
        do {
            let status = try await NetworkService.shared.getSessionStatus(code: sessionCode)
            backendSubmittedCount = status.teamsSubmitted
            backendTeamCount = status.totalTeams
            backendTeamStatus = status.state
            session.currentRound = min(status.currentRound, session.totalRounds)
            if status.state == "finished" || status.state == "completed" {
                session.state = .completed
            } else if status.state == "active" {
                session.state = .inProgress
            }
            
            // Update last poll time
            await MainActor.run {
                self.lastPollTime = .now
            }
        } catch {
            // Backend unavailable — keep local state
            Logger.sync.error("PollBackendStatus error: \(UserFriendlyError.message(for: error))")
        }
    }

    /// Process an online round exactly once via the backend and apply its response.
    /// Never invokes the local engine and never calls the legacy /advance endpoint.
    func processRoundWithBackend() async {
        guard isBackendSession, canAdvanceRound else { return }

        isProcessingRound = true
        roundProcessingError = nil

        do {
            let processedRound = session.currentRound
            let results = try await NetworkService.shared.processRound(code: session.sessionCode)

            // process_round both computes this round and advances backend currentRound.
            // Hydrate returned results, then poll the authoritative status exactly once.
            session.restoreResultsFromBackend([processedRound: results])
            await pollBackendStatus()
            refreshTeamStatuses()
        } catch {
            // Never split authority by falling back to SimulationEngine online.
            roundProcessingError = UserFriendlyError.message(for: error)
        }

        isProcessingRound = false
    }

    func endSessionWithBackend() async -> Bool {
        let sessionCode = session.sessionCode
        do {
            try await NetworkService.shared.endSession(code: sessionCode)
        } catch {
            roundProcessingError = UserFriendlyError.message(for: error)
            return false
        }
        session.state = .completed
        return true
    }

    // MARK: - Cleanup

    deinit {
        stopPolling()
    }
}
