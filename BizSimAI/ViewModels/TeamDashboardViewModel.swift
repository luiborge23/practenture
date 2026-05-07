import SwiftUI

// MARK: - TeamDashboardViewModel
/// Student dashboard with investor scorecard, S/Q rating, and financial health.

@Observable
final class TeamDashboardViewModel {

    // MARK: - Properties

    private(set) var teamId: UUID
    private(set) var teamName: String

    var cash: Double = 0
    var inventory: Int = 0
    var reputation: Double = 0.5
    var rank: Int = 0
    var currentRound: Int = 1
    var totalRounds: Int = 10
    var hasSubmittedThisRound: Bool = false
    var sessionState: SessionState = .waitingForPlayers

    // Investor scorecard metrics
    var sqRating: Double = 5.0
    var imageRating: Double = 50.0
    var creditRating: CreditRating = .a
    var investorScore: Double = 0
    var eps: Double = 0
    var roe: Double = 0
    var stockPrice: Double = 25.0
    var equity: Double = 80_000
    var totalDebt: Double = 0
    var sharesOutstanding: Int = 10_000

    // MARK: - Init

    init(teamId: UUID, teamName: String) {
        self.teamId = teamId
        self.teamName = teamName
    }

    // MARK: - Computed

    var canSubmitDecisions: Bool {
        !hasSubmittedThisRound
            && sessionState == .inProgress
            && currentRound <= totalRounds
    }

    var isSessionActive: Bool {
        sessionState == .waitingForPlayers || sessionState == .inProgress
    }

    var isSessionComplete: Bool {
        sessionState == .completed
    }

    var roundProgressLabel: String {
        "Round \(currentRound) of \(totalRounds)"
    }

    var roundProgressFraction: Double {
        guard totalRounds > 0 else { return 0 }
        return Double(currentRound) / Double(totalRounds)
    }

    var formattedRank: String {
        guard rank > 0 else { return "--" }
        let suffix: String
        switch rank {
        case 1: suffix = "st"
        case 2: suffix = "nd"
        case 3: suffix = "rd"
        default: suffix = "th"
        }
        return "\(rank)\(suffix)"
    }

    var formattedCash: String {
        cash.formatted(.currency(code: "USD").precision(.fractionLength(0)))
    }

    var formattedReputation: String {
        (reputation * 100).formatted(.number.precision(.fractionLength(1))) + "%"
    }

    var inventoryLabel: String {
        "\(inventory) units"
    }

    var submissionStatusLabel: String {
        hasSubmittedThisRound ? "Decisions Submitted" : "Awaiting Your Decisions"
    }

    var submissionStatusColor: Color {
        hasSubmittedThisRound ? .green : .orange
    }

    var formattedSQRating: String {
        String(format: "%.1f", sqRating) + "★"
    }

    var formattedImageRating: String {
        String(format: "%.0f", imageRating) + "/100"
    }

    var formattedInvestorScore: String {
        String(format: "%.0f", investorScore) + "/100"
    }

    var formattedEPS: String {
        "$" + String(format: "%.2f", eps)
    }

    var formattedStockPrice: String {
        "$" + String(format: "%.2f", stockPrice)
    }

    // MARK: - Backend Sync

    func syncStatusFromBackend(sessionCode: String) async {
        do {
            let status = try await NetworkService.shared.getSessionStatus(code: sessionCode)
            currentRound = status.currentRound
            // Map backend string state to SessionState enum
            switch status.state {
            case "creating", "waiting": sessionState = .waitingForPlayers
            case "active", "in_progress": sessionState = .inProgress
            case "processing": sessionState = .inProgress
            case "completed": sessionState = .completed
            default: sessionState = .waitingForPlayers
            }
        } catch {
            // Backend unavailable — keep local state
        }
    }

    func refreshStatus(from session: SimulationSession) {
        currentRound = session.currentRound
        totalRounds = session.totalRounds
        sessionState = session.state

        hasSubmittedThisRound = session.hasDecision(for: teamId, round: currentRound)

        // Load most recent results
        let lastCompletedRound = max(1, currentRound - 1)
        if let result = session.roundResult(for: teamId, round: lastCompletedRound) {
            cash = result.cash
            inventory = result.inventory
            sqRating = result.sqRating
            eps = result.scorecard.eps
            roe = result.scorecard.roe
            stockPrice = result.scorecard.stockPrice
            imageRating = result.scorecard.imageRating
            investorScore = result.scorecard.totalScore
        } else {
            cash = session.startingCash
            inventory = 0
        }

        if let team = session.teams.first(where: { $0.id == teamId }) {
            reputation = team.reputation
            rank = team.rank
            creditRating = team.creditRating
            equity = team.equity
            totalDebt = team.totalDebt
            sharesOutstanding = team.sharesOutstanding
            imageRating = team.imageRating
            sqRating = team.sqRating
        }
    }
}
