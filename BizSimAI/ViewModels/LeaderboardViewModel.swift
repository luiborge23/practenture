import SwiftUI

// MARK: - LeaderboardViewModel
/// ViewModel for the leaderboard screen (S-7 for students, P-4 for professors).
/// Displays team rankings with scores and trend indicators.

@Observable
final class LeaderboardViewModel {

    // MARK: - Supporting Types

    enum TrendDirection: String {
        case up, down, stable, new

        var icon: String {
            switch self {
            case .up: return "arrow.up"
            case .down: return "arrow.down"
            case .stable: return "minus"
            case .new: return "sparkles"
            }
        }

        var color: Color {
            switch self {
            case .up: return .green
            case .down: return .red
            case .stable: return .secondary
            case .new: return .blue
            }
        }
    }

    struct RankingEntry: Identifiable {
        let id = UUID()
        let rank: Int
        let teamName: String
        let score: Double
        let trend: TrendDirection
        let isCurrentTeam: Bool
        let sqRating: Double
        let imageRating: Double
        let investorScore: Double

        var formattedScore: String {
            score.formatted(.number.precision(.fractionLength(0)))
        }

        var rankLabel: String {
            "#\(rank)"
        }

        var medalIcon: String? {
            switch rank {
            case 1: return "trophy.fill"
            case 2: return "medal.fill"
            case 3: return "medal"
            default: return nil
            }
        }

        var medalColor: Color {
            switch rank {
            case 1: return .yellow
            case 2: return .gray
            case 3: return .orange
            default: return .clear
            }
        }
    }

    // MARK: - Properties

    var rankings: [RankingEntry] = []
    var scoringMetric: ScoringMetric = .cumulativeProfit
    var isLoading: Bool = false
    var currentTeamId: UUID?

    // MARK: - Computed

    var hasRankings: Bool { !rankings.isEmpty }

    var leaderTeam: RankingEntry? { rankings.first }

    var currentTeamRanking: RankingEntry? {
        rankings.first { $0.isCurrentTeam }
    }

    var currentTeamRank: Int? {
        currentTeamRanking?.rank
    }

    var scoringMetricLabel: String {
        scoringMetric.displayName
    }

    var title: String {
        "Leaderboard"
    }

    var subtitle: String {
        "Ranked by \(scoringMetric.displayName)"
    }

    // MARK: - Actions

    /// Load the leaderboard from local session data.
    func loadLeaderboardLocally(from session: SimulationSession, currentTeamId: UUID? = nil) {
        isLoading = true
        self.currentTeamId = currentTeamId
        self.scoringMetric = session.scoringMetric

        // Compute scores for each team based on the scoring metric
        let completedRound = max(0, session.currentRound - 1)

        struct TeamScore {
            let team: TeamStatus
            var score: Double
            var previousRank: Int?
        }

        var teamScores: [TeamScore] = session.teams.map { team in
            var totalScore: Double = 0

            for round in 1...max(1, completedRound) {
                if let result = session.roundResult(for: team.id, round: round) {
                    switch session.scoringMetric {
                    case .investorScore:
                        totalScore = team.cumulativeInvestorScore // use running average
                    case .cumulativeProfit:
                        totalScore += result.profit
                    case .revenue:
                        totalScore += result.revenue
                    case .composite:
                        totalScore += result.profit * 0.4
                            + result.revenue * 0.3
                            + result.marketShare * 100 * 0.15
                            + result.customerSatisfaction * 100 * 0.15
                    }
                }
            }

            return TeamScore(team: team, score: totalScore)
        }

        // Sort by score descending
        teamScores.sort { $0.score > $1.score }

        // Build ranking entries
        rankings = teamScores.enumerated().map { index, teamScore in
            let rank = index + 1
            let isCurrentTeam = teamScore.team.id == currentTeamId

            // Determine trend (simplified: compare to previous round ranking)
            let trend: TrendDirection
            if completedRound <= 1 {
                trend = .new
            } else {
                // For MVP, use .stable; real implementation would track rank history
                trend = .stable
            }

            return RankingEntry(
                rank: rank,
                teamName: teamScore.team.name,
                score: teamScore.score,
                trend: trend,
                isCurrentTeam: isCurrentTeam,
                sqRating: teamScore.team.sqRating,
                imageRating: teamScore.team.imageRating,
                investorScore: teamScore.team.cumulativeInvestorScore
            )
        }

        isLoading = false
    }

    /// Load the leaderboard from backend (if available), falling back to local computation.
    func loadLeaderboard(from session: SimulationSession, currentTeamId: UUID? = nil, fromBackend: Bool = true) async {
        isLoading = true
        self.currentTeamId = currentTeamId
        self.scoringMetric = session.scoringMetric

        if fromBackend {
            let sessionCode = session.sessionCode
            do {
                let backendEntries = try await NetworkService.shared.getLeaderboard(code: sessionCode)
                rankings = backendEntries.map { entry -> RankingEntry in
                    let teamNameOrId = session.playerTeam?.name ?? ""
                    let isCurrentTeam = (entry.teamName == currentTeamId?.uuidString) ||
                                        (entry.studentName != nil && entry.studentName! == teamNameOrId)
                    return RankingEntry(
                        rank: entry.rank,
                        teamName: entry.teamName,
                        score: entry.totalScore,
                        trend: .stable,
                        isCurrentTeam: isCurrentTeam,
                        sqRating: 0,
                        imageRating: entry.imageRating,
                        investorScore: entry.totalScore
                    )
                }
                isLoading = false
                return
            } catch {
                // Backend unavailable — fall through to local
            }
        }

        // Local computation fallback
        loadLeaderboardLocally(from: session, currentTeamId: currentTeamId)
    }
}
