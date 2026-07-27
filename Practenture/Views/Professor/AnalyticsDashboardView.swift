// MARK: - Analytics Dashboard View (Phase 7)

import SwiftUI
import Charts

// MARK: - Analytics ViewModel

@Observable
final class AnalyticsDashboardViewModel {
    var classMetrics = ClassMetrics(
        totalTeams: 0,
        averageEquity: 0,
        averageProfit: 0,
        averageMarketShare: 0,
        averageSQRating: 0,
        averageCreditRating: 0
    )
    var roundTrends: [RoundTrend] = []
    var teamAnalytics: [TeamAnalytics] = []
    var strategyDistribution: [StrategyDistribution] = []
    var isLoading = false
    var errorMessage: String?
    
    func loadAnalytics(for code: String) async {
        isLoading = true
        errorMessage = nil
        
        do {
            let status: SessionStatusBackend = try await NetworkService.shared.getSessionStatus(code: code)
            
            classMetrics = ClassMetrics(
                totalTeams: status.teamsSubmitted,
                averageEquity: 500_000,
                averageProfit: 50_000,
                averageMarketShare: 25.0,
                averageSQRating: 5.0,
                averageCreditRating: 3.5
            )
            
            // Generate sample trend data based on rounds
            let totalRounds = status.totalRounds > 0 ? status.totalRounds : 5
            for round in 1...totalRounds {
                roundTrends.append(RoundTrend(
                    round: round,
                    averageEquity: 500_000 + Double(round) * 15_000,
                    averageProfit: Double(round) * 8_000,
                    averageMarketShare: 25.0 + Double.random(in: -3...3),
                    totalInvestments: Double(round) * 5_000
                ))
            }
            
            // Sample team analytics
            for teamIndex in 0..<max(status.teamsSubmitted, 4) {
                teamAnalytics.append(TeamAnalytics(
                    teamName: ["Team Alpha", "Team Beta", "Team Gamma", "Team Delta"][teamIndex % 4],
                    currentEquity: 500_000 + Double(teamIndex) * 50_000,
                    totalProfit: Double(teamIndex) * 40_000,
                    marketShare: 25.0 + Double(teamIndex) * 3,
                    sqRating: 5.0 + Double(teamIndex) * 0.3,
                    creditRating: Double(teamIndex) + 2.0,
                    investorScore: 60.0 + Double(teamIndex) * 5
                ))
            }
            
            // Strategy distribution
            strategyDistribution = [
                StrategyDistribution(strategy: "Low-Cost Leader", percentage: 25.0),
                StrategyDistribution(strategy: "Differentiator", percentage: 25.0),
                StrategyDistribution(strategy: "Best-Cost", percentage: 25.0),
                StrategyDistribution(strategy: "Adaptive", percentage: 25.0)
            ]
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
        }
        
        isLoading = false
    }
}

// MARK: - Data Models

struct ClassMetrics {
    let totalTeams: Int
    let averageEquity: Double
    let averageProfit: Double
    let averageMarketShare: Double
    let averageSQRating: Double
    let averageCreditRating: Double
}

struct RoundTrend: Identifiable {
    let id = UUID()
    let round: Int
    let averageEquity: Double
    let averageProfit: Double
    let averageMarketShare: Double
    let totalInvestments: Double
}

struct TeamAnalytics: Identifiable {
    let id = UUID()
    let teamName: String
    let currentEquity: Double
    let totalProfit: Double
    let marketShare: Double
    let sqRating: Double
    let creditRating: Double
    let investorScore: Double
}

struct StrategyDistribution: Identifiable {
    let id = UUID()
    let strategy: String
    let percentage: Double
}

// MARK: - Analytics Dashboard View

struct AnalyticsDashboardView: View {
    @Environment(\.dismiss) private var dismiss
    let sessionCode: String
    
    @State private var viewModel = AnalyticsDashboardViewModel()
    @State private var selectedTab = 0
    
    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 20) {
                    if viewModel.isLoading {
                        ProgressView("Loading analytics...")
                            .padding()
                    } else if let error = viewModel.errorMessage {
                        VStack(spacing: 12) {
                            Image(systemName: "exclamationmark.triangle")
                                .font(.system(size: 48))
                                .foregroundStyle(.orange)
                            Text("Error Loading Data")
                                .font(.headline)
                            Text(error)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                                .multilineTextAlignment(.center)
                        }
                        .padding()
                    } else {
                        // Class Overview Cards
                        ClassOverviewCards(metrics: viewModel.classMetrics)
                        
                        // Tab Navigation
                        Picker("Analytics View", selection: $selectedTab) {
                            Text("Trends").tag(0)
                            Text("Teams").tag(1)
                            Text("Strategies").tag(2)
                        }
                        .pickerStyle(.segmented)
                        
                        // Tab Content
                        switch selectedTab {
                        case 0:
                            RoundTrendsView(trends: viewModel.roundTrends)
                        case 1:
                            TeamComparisonView(teams: viewModel.teamAnalytics)
                        case 2:
                            StrategyDistributionView(distribution: viewModel.strategyDistribution)
                        default:
                            EmptyStateView()
                        }
                    }
                }
                .padding()
            }
            .navigationTitle("Analytics Dashboard")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "chevron.left")
                            .foregroundStyle(.secondary)
                    }
                }
            }
            .task {
                await viewModel.loadAnalytics(for: sessionCode)
            }
        }
    }
}

// MARK: - Class Overview Cards

struct ClassOverviewCards: View {
    let metrics: ClassMetrics
    
    var body: some View {
        LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: 12) {
            MetricCardView(
                title: "Total Teams",
                value: "\(metrics.totalTeams)",
                icon: "people.fill",
                color: .blue
            )
            MetricCardView(
                title: "Avg Equity",
                value: formatCurrency(metrics.averageEquity),
                icon: "chart.line.uptrend.xyaxis",
                color: .green
            )
            MetricCardView(
                title: "Avg Profit",
                value: formatCurrency(metrics.averageProfit),
                icon: "dollarsign.circle.fill",
                color: .purple
            )
            MetricCardView(
                title: "Avg Mkt Share",
                value: String(format: "%.1f%%", metrics.averageMarketShare),
                icon: "chart.pie.fill",
                color: .orange
            )
            MetricCardView(
                title: "Avg S/Q Rating",
                value: String(format: "%.1f", metrics.averageSQRating),
                icon: "star.fill",
                color: .yellow
            )
            MetricCardView(
                title: "Avg Credit Rating",
                value: String(format: "%.1f", metrics.averageCreditRating),
                icon: "creditcard.fill",
                color: .cyan
            )
        }
    }
}

// MARK: - Round Trends View

struct RoundTrendsView: View {
    let trends: [RoundTrend]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Class Performance Trends")
                .font(.headline)
            
            if trends.isEmpty {
                EmptyStateView()
            } else {
                Chart {
                    ForEach(trends) { trend in
                        LineMark(
                            x: .value("Round", trend.round),
                            y: .value("Equity", trend.averageEquity)
                        )
                        .foregroundStyle(.blue)
                        .lineStyle(StrokeStyle(lineWidth: 2))
                        
                        AreaMark(
                            x: .value("Round", trend.round),
                            yStart: .value("Min", trend.averageEquity * 0.8),
                            yEnd: .value("Max", trend.averageEquity * 1.2)
                        )
                        .foregroundStyle(.blue.opacity(0.2))
                    }
                    
                    ForEach(trends) { trend in
                        PointMark(
                            x: .value("Round", trend.round),
                            y: .value("Profit", trend.averageProfit)
                        )
                        .foregroundStyle(.green)
                        .symbolSize(60)
                    }
                }
                .frame(height: 200)
                .chartXAxisLabel("Round")
                .chartYAxisLabel("Value ($)")
            }
        }
    }
}

// MARK: - Team Comparison View

struct TeamComparisonView: View {
    let teams: [TeamAnalytics]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Team Comparison")
                .font(.headline)
            
            if teams.isEmpty {
                EmptyStateView()
            } else {
                ForEach(teams) { team in
                    TeamComparisonRow(team: team)
                }
            }
        }
    }
}

struct TeamComparisonRow: View {
    let team: TeamAnalytics
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(team.teamName)
                    .font(.headline)
                Spacer()
                Text(formatCurrency(team.currentEquity))
                    .font(.subheadline)
                    .foregroundStyle(.green)
            }
            
            HStack(spacing: 16) {
                MetricPill(label: "Profit", value: formatCurrency(team.totalProfit))
                MetricPill(label: "Mkt Share", value: String(format: "%.1f%%", team.marketShare))
                MetricPill(label: "S/Q", value: String(format: "%.1f", team.sqRating))
                MetricPill(label: "Credit", value: String(format: "%.1f", team.creditRating))
            }
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

struct MetricPill: View {
    let label: String
    let value: String
    
    var body: some View {
        VStack(alignment: .center, spacing: 2) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.caption)
                .fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
    }
}

// MARK: - Strategy Distribution View

struct StrategyDistributionView: View {
    let distribution: [StrategyDistribution]
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            Text("Strategy Distribution")
                .font(.headline)
            
            if distribution.isEmpty {
                EmptyStateView()
            } else {
                Chart {
                    ForEach(distribution) { item in
                        BarMark(
                            x: .value("Strategy", item.strategy),
                            y: .value("Percentage", item.percentage)
                        )
                        .foregroundStyle(by: .value("Strategy", item.strategy))
                        .cornerRadius(4)
                    }
                }
                .frame(height: 200)
            }
        }
    }
}

// MARK: - Empty State

struct EmptyStateView: View {
    var body: some View {
        VStack(spacing: 12) {
            Image(systemName: "chart.line.uptrend.xyaxis")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)
            Text("No Analytics Data")
                .font(.headline)
            Text("Analytics will populate as the simulation progresses.")
                .font(.subheadline)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .padding()
    }
}

// MARK: - Metric Card View

struct MetricCardView: View {
    let title: String
    let value: String
    let icon: String
    let color: Color
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .foregroundStyle(color)
                Spacer()
            }
            .font(.title2)
            
            Text(value)
                .font(.title3)
                .fontWeight(.bold)
            
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding()
        .background(Color(.systemGray6))
        .cornerRadius(12)
    }
}

// MARK: - Helper Functions

private func formatCurrency(_ value: Double) -> String {
    if value >= 1_000_000 {
        return String(format: "$%.1fM", value / 1_000_000)
    } else if value >= 1_000 {
        return String(format: "$%.1fK", value / 1_000)
    }
    return String(format: "$%.0f", value)
}

// MARK: - Preview

#if DEBUG
#Preview {
    AnalyticsDashboardView(sessionCode: "BIZ-TEST01")
}
#endif
