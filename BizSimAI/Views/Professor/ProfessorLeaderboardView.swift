// ProfessorLeaderboardView.swift
// BizSimAI
//
// P-4: Full leaderboard for professors showing detailed team metrics.
// Table-like layout with sortable columns: Rank, Team, Revenue, Profit, Market Share, Satisfaction.

import SwiftUI
import os

// MARK: - Sort Column

enum LeaderboardSortColumn: String, CaseIterable {
    case rank = "Rank"
    case team = "Team"
    case revenue = "Revenue"
    case profit = "Profit"
    case marketShare = "Market Share"
    case satisfaction = "Satisfaction"

    var icon: String {
        switch self {
        case .rank: return "number"
        case .team: return "person.3"
        case .revenue: return "dollarsign.arrow.circlepath"
        case .profit: return "chart.line.uptrend.xyaxis"
        case .marketShare: return "chart.pie"
        case .satisfaction: return "face.smiling"
        }
    }
}

// MARK: - Team Metric Data

struct TeamMetricData: Identifiable {
    let id: UUID
    let rank: Int
    let name: String
    let isAI: Bool
    let revenue: Double
    let profit: Double
    let marketShare: Double
    let satisfaction: Double

    static let samples: [TeamMetricData] = [
        TeamMetricData(id: UUID(), rank: 1, name: "Alpha Corp", isAI: true, revenue: 285_000, profit: 142_500, marketShare: 0.28, satisfaction: 0.85),
        TeamMetricData(id: UUID(), rank: 2, name: "Team Rocket", isAI: false, revenue: 242_500, profit: 121_250, marketShare: 0.24, satisfaction: 0.82),
        TeamMetricData(id: UUID(), rank: 3, name: "Beta Inc", isAI: true, revenue: 198_000, profit: 99_000, marketShare: 0.20, satisfaction: 0.78),
        TeamMetricData(id: UUID(), rank: 4, name: "Gamma LLC", isAI: true, revenue: 156_300, profit: 78_150, marketShare: 0.16, satisfaction: 0.72),
        TeamMetricData(id: UUID(), rank: 5, name: "Delta Co", isAI: false, revenue: 89_200, profit: 44_600, marketShare: 0.08, satisfaction: 0.65),
        TeamMetricData(id: UUID(), rank: 6, name: "Omega Group", isAI: false, revenue: 54_800, profit: 21_920, marketShare: 0.04, satisfaction: 0.58),
    ]
}

// MARK: - Professor Leaderboard View

struct ProfessorLeaderboardView: View {
    @Environment(AppState.self) private var appState

    @State private var teams: [TeamMetricData] = TeamMetricData.samples
    @State private var sortColumn: LeaderboardSortColumn = .rank
    @State private var sortAscending: Bool = true

    private var sortedTeams: [TeamMetricData] {
        teams.sorted { a, b in
            let result: Bool
            switch sortColumn {
            case .rank:
                result = a.rank < b.rank
            case .team:
                result = a.name.localizedCompare(b.name) == .orderedAscending
            case .revenue:
                result = a.revenue > b.revenue
            case .profit:
                result = a.profit > b.profit
            case .marketShare:
                result = a.marketShare > b.marketShare
            case .satisfaction:
                result = a.satisfaction > b.satisfaction
            }
            return sortAscending ? result : !result
        }
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 16) {
                headerSection
                sortControls
                leaderboardTable
            }
            .padding(24)
        }
        .navigationTitle("Leaderboard")
        #if os(macOS)
        .frame(minWidth: 700)
        #endif
        .onAppear {
            loadFromSession()
        }
    }

    private func loadFromSession() {
        guard let session = appState.activeSession else { return }
        
        // First try backend leaderboard API
        Task.detached { [session, self] in
            do {
                let leaderboardData = try await NetworkService.shared.getLeaderboard(code: session.sessionCode)
                
                if !leaderboardData.isEmpty {
                    // Backend has data — use it
                    var loaded: [TeamMetricData] = []
                    for (_, entry) in leaderboardData.enumerated() {
                        let teamResult = await self.sessionResultsForTeam(session, teamId: entry.teamName)
                        loaded.append(teamResult)
                    }

                    // Sort by backend ranking
                    loaded.sort { a, b in a.rank < b.rank }

                    await MainActor.run { [loaded] in
                        if !loaded.isEmpty {
                            self.teams = loaded
                        }
                    }
                } else {
                    // Backend has no data yet — fall back to local session teams
                    await MainActor.run { [self, session] in
                        loadFromLocalSession(session)
                    }
                }
            } catch {
                Logger.network.error("Backend leaderboard fetch failed: \(UserFriendlyError.message(for: error))")
                // Fall back to local data on error
                await MainActor.run { [self, session] in
                    loadFromLocalSession(session)
                }
            }
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Team Rankings")
                    .font(.title2)
                    .fontWeight(.bold)

                Text("\(teams.count) teams competing")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            Spacer()

            StatusBadge(text: "Live", color: .green, icon: "circle.fill", size: .regular)
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    // MARK: - Sort Controls

    private var sortControls: some View {
        HStack(spacing: 8) {
            Text("Sort by:")
                .font(.subheadline)
                .foregroundStyle(.secondary)

            Picker("Sort", selection: $sortColumn) {
                ForEach(LeaderboardSortColumn.allCases, id: \.self) { column in
                    Label(column.rawValue, systemImage: column.icon)
                        .tag(column)
                }
            }
            .pickerStyle(.segmented)
            .labelsHidden()

            Button {
                sortAscending.toggle()
            } label: {
                Image(systemName: sortAscending ? "arrow.up" : "arrow.down")
                    .font(.subheadline)
                    .fontWeight(.semibold)
            }
            .buttonStyle(.bordered)
            .help(sortAscending ? "Sort Descending" : "Sort Ascending")
        }
    }

    // MARK: - Leaderboard Table

    private var leaderboardTable: some View {
        VStack(spacing: 0) {
            // Column headers
            tableHeader

            Divider()

            // Team rows
            ForEach(Array(sortedTeams.enumerated()), id: \.element.id) { index, team in
                teamRow(team)

                if index < sortedTeams.count - 1 {
                    Divider()
                        .padding(.horizontal, 16)
                }
            }
        }
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    private var tableHeader: some View {
        HStack(spacing: 0) {
            columnHeader("Rank", width: 60)
            columnHeader("Team", width: nil, alignment: .leading)
            columnHeader("Revenue", width: 110)
            columnHeader("Profit", width: 110)
            columnHeader("Mkt Share", width: 90)
            columnHeader("Satisfaction", width: 90)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 10)
        .background(Color.secondary.opacity(0.06))
    }

    private func columnHeader(_ title: String, width: CGFloat?, alignment: HorizontalAlignment = .center) -> some View {
        Text(title)
            .font(.caption)
            .fontWeight(.semibold)
            .foregroundStyle(.secondary)
            .frame(maxWidth: width ?? .infinity, alignment: alignment == .leading ? .leading : .center)
    }

    private func teamRow(_ team: TeamMetricData) -> some View {
        HStack(spacing: 0) {
            // Rank
            rankBadge(team.rank)
                .frame(width: 60)

            // Team name
            HStack(spacing: 6) {
                Text(team.name)
                    .font(.subheadline)
                    .fontWeight(.medium)
                    .lineLimit(1)

                if team.isAI {
                    Image(systemName: "cpu")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                Spacer()
            }

            // Revenue
            Text(team.revenue.formatted(.currency(code: "USD").precision(.fractionLength(0))))
                .font(.subheadline)
                .monospacedDigit()
                .frame(width: 110)

            // Profit
            Text(team.profit.formatted(.currency(code: "USD").precision(.fractionLength(0))))
                .font(.subheadline)
                .monospacedDigit()
                .foregroundStyle(team.profit >= 0 ? Color.primary : Color.red)
                .frame(width: 110)

            // Market Share
            Text("\(String(format: "%.1f", team.marketShare * 100))%")
                .font(.subheadline)
                .monospacedDigit()
                .frame(width: 90)

            // Satisfaction
            satisfactionIndicator(team.satisfaction)
                .frame(width: 90)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    // MARK: - Helpers

    private func loadFromLocalSession(_ session: SimulationSession) {
        let sessionTeams = session.teams.sorted { $0.rank < $1.rank }
        var loaded: [TeamMetricData] = []
        for (idx, team) in sessionTeams.enumerated() {
            let results = session.resultsForTeam(team.id)
            let totalRevenue = results.reduce(0) { $0 + $1.revenue }
            let totalProfit = results.reduce(0) { $0 + $1.profit }
            let avgMarketShare = results.isEmpty ? 0 : results.reduce(0) { $0 + $1.marketShare } / Double(results.count)
            let avgSatisfaction = results.isEmpty ? 0 : results.reduce(0) { $0 + $1.customerSatisfaction } / Double(results.count)
            loaded.append(TeamMetricData(
                id: team.id, rank: idx + 1, name: team.name, isAI: team.isAI,
                revenue: totalRevenue, profit: totalProfit,
                marketShare: avgMarketShare, satisfaction: avgSatisfaction
            ))
        }
        if !loaded.isEmpty {
            teams = loaded
        }
    }

    private func sessionResultsForTeam(_ session: SimulationSession, teamId: String) -> TeamMetricData {
        let idx = session.teams.firstIndex(where: { $0.name == teamId }) ?? -1
        let rank = (idx >= 0) ? idx + 1 : 0
        let team = session.teams.filter({ $0.name == teamId }).first
        let results = session.resultsForTeam(team?.id ?? UUID())
        let totalRevenue = results.reduce(0) { $0 + $1.revenue }
        let totalProfit = results.reduce(0) { $0 + $1.profit }
        let avgMarketShare = results.isEmpty ? 0 : results.reduce(0) { $0 + $1.marketShare } / Double(results.count)
        let avgSatisfaction = results.isEmpty ? 0 : results.reduce(0) { $0 + $1.customerSatisfaction } / Double(results.count)
        return TeamMetricData(
            id: team?.id ?? UUID(), rank: max(rank, 1), name: teamId, isAI: team?.isAI ?? false,
            revenue: totalRevenue, profit: totalProfit,
            marketShare: avgMarketShare, satisfaction: avgSatisfaction
        )
    }

    @ViewBuilder
    private func rankBadge(_ rank: Int) -> some View {
        switch rank {
        case 1:
            Text("🥇")
                .font(.title3)
        case 2:
            Text("🥈")
                .font(.title3)
        case 3:
            Text("🥉")
                .font(.title3)
        default:
            Text("#\(rank)")
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)
        }
    }

    private func satisfactionIndicator(_ value: Double) -> some View {
        HStack(spacing: 4) {
            Circle()
                .fill(satisfactionColor(value))
                .frame(width: 8, height: 8)

            Text("\(String(format: "%.0f", value * 100))%")
                .font(.subheadline)
                .monospacedDigit()
        }
    }

    private func satisfactionColor(_ value: Double) -> Color {
        switch value {
        case 0.8...: return .green
        case 0.6..<0.8: return .yellow
        default: return .red
        }
    }
}
