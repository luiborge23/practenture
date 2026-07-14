// StudentLeaderboardView.swift
// BizSimAI
//
// S-7: Student-facing leaderboard showing team rankings.
// Current team is highlighted. Uses LeaderboardViewModel.

import SwiftUI

struct StudentLeaderboardView: View {
    @State private var viewModel = LeaderboardViewModel()
    @Environment(AppState.self) private var appState

    var body: some View {
        VStack(spacing: 20) {
            headerSection
            scoringPicker
            leaderboardList
        }
        .padding(24)
        .navigationTitle("Leaderboard")
        #if os(macOS)
        .frame(minWidth: 480, minHeight: 400)
        #endif
        .onAppear {
            if let session = appState.activeSession {
                Task {
                    await viewModel.loadLeaderboard(from: session, currentTeamId: session.playerTeam?.id)
                }
            } else {
                loadSampleData()
            }
        }
        .refreshable {
            // Pull-to-refresh for live leaderboard updates
            if let session = appState.activeSession {
                Task {
                    await viewModel.loadLeaderboard(from: session, currentTeamId: session.playerTeam?.id)
                }
            }
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Rankings")
                    .font(.title2)
                    .fontWeight(.bold)

                Text(viewModel.subtitle)
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            // Current position badge
            if let currentRank = viewModel.currentTeamRank {
                VStack(spacing: 2) {
                    Text("Your Rank")
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    HStack(spacing: 4) {
                        Text("#\(currentRank)")
                            .font(.title)
                            .fontWeight(.bold)
                            .foregroundStyle(.blue)

                        if let ranking = viewModel.currentTeamRanking {
                            Image(systemName: trendIcon(for: ranking.trend))
                                .font(.caption)
                                .fontWeight(.bold)
                                .foregroundStyle(trendColor(for: ranking.trend))
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(.blue.opacity(0.08))
                )
            }
        }
    }

    // MARK: - Scoring Metric Picker

    private var scoringPicker: some View {
        Picker("Scoring", selection: $viewModel.scoringMetric) {
            ForEach(ScoringMetric.allCases) { metric in
                Text(metric.displayName).tag(metric)
            }
        }
        .pickerStyle(.segmented)
    }

    // MARK: - Leaderboard List

    private var leaderboardList: some View {
        VStack(spacing: 4) {
            if viewModel.isLoading {
                ProgressView("Loading rankings...")
                    .padding(40)
            } else if !viewModel.hasRankings {
                ContentUnavailableView(
                    "No Rankings Yet",
                    systemImage: "trophy",
                    description: Text("Complete at least one round to see the leaderboard.")
                )
            } else {
                ForEach(viewModel.rankings) { entry in
                    LeaderboardRow(
                        rank: entry.rank,
                        teamName: entry.teamName,
                        score: entry.score,
                        trend: mapTrend(entry.trend),
                        isCurrentTeam: entry.isCurrentTeam,
                        scoringLabel: viewModel.scoringMetricLabel,
                        sqRating: entry.sqRating,
                        investorScore: entry.investorScore
                    )
                }
            }
        }
        .padding(8)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    // MARK: - Helpers

    private func mapTrend(_ trend: LeaderboardViewModel.TrendDirection) -> TrendDirection {
        switch trend {
        case .up: return .up
        case .down: return .down
        case .stable, .new: return .flat
        }
    }

    private func trendIcon(for trend: LeaderboardViewModel.TrendDirection) -> String {
        trend.icon
    }

    private func trendColor(for trend: LeaderboardViewModel.TrendDirection) -> Color {
        trend.color
    }

    // MARK: - Sample Data

    private func loadSampleData() {
        // In production, this would call:
        // viewModel.loadLeaderboard(from: session, currentTeamId: teamId)
        // For now, populate with sample rankings.
        viewModel.rankings = [
            LeaderboardViewModel.RankingEntry(
                rank: 1, teamName: "Alpha Corp", score: 82,
                trend: .up, isCurrentTeam: false,
                sqRating: 8.2, imageRating: 72, investorScore: 82
            ),
            LeaderboardViewModel.RankingEntry(
                rank: 2, teamName: "Team Rocket", score: 72,
                trend: .up, isCurrentTeam: true,
                sqRating: 6.8, imageRating: 62, investorScore: 72
            ),
            LeaderboardViewModel.RankingEntry(
                rank: 3, teamName: "Beta Inc", score: 58,
                trend: .down, isCurrentTeam: false,
                sqRating: 5.5, imageRating: 48, investorScore: 58
            ),
            LeaderboardViewModel.RankingEntry(
                rank: 4, teamName: "Gamma LLC", score: 45,
                trend: .stable, isCurrentTeam: false,
                sqRating: 4.2, imageRating: 38, investorScore: 45
            ),
            LeaderboardViewModel.RankingEntry(
                rank: 5, teamName: "Delta Co", score: 32,
                trend: .down, isCurrentTeam: false,
                sqRating: 3.8, imageRating: 30, investorScore: 32
            ),
            LeaderboardViewModel.RankingEntry(
                rank: 6, teamName: "Omega Group", score: 25,
                trend: .new, isCurrentTeam: false,
                sqRating: 5.0, imageRating: 50, investorScore: 25
            ),
        ]
    }
}
