import SwiftUI

// MARK: - PerformanceHistoryViewModel
/// ViewModel for the student's performance charts (S-6).
/// Transforms round history into chart-ready data for the selected metric.

@Observable
final class PerformanceHistoryViewModel {

    // MARK: - Supporting Types

    /// View-specific metric enum with additional display properties.
    /// Distinct from the model-layer `PerformanceMetric` to include extra
    /// cases (unitsSold, reputation) and view-specific formatting.
    enum ViewMetric: String, CaseIterable, Identifiable {
        case revenue = "Revenue"
        case profit = "Profit"
        case cash = "Cash"
        case unitsSold = "Units Sold"
        case marketShare = "Market Share"
        case sqRating = "S/Q Rating"
        case investorScore = "Investor Score"
        case imageRating = "Image Rating"
        case rejectionRate = "Rejection Rate"

        var id: String { rawValue }

        var displayName: String { rawValue }

        var unit: String {
            switch self {
            case .revenue, .profit, .cash: return "$"
            case .unitsSold: return "units"
            case .marketShare, .rejectionRate: return "%"
            case .sqRating: return "★"
            case .investorScore, .imageRating: return "pts"
            }
        }

        var systemImage: String {
            switch self {
            case .revenue: return "dollarsign.circle"
            case .profit: return "chart.line.uptrend.xyaxis"
            case .cash: return "banknote"
            case .unitsSold: return "shippingbox"
            case .marketShare: return "chart.pie"
            case .sqRating: return "star.fill"
            case .investorScore: return "chart.bar.doc.horizontal"
            case .imageRating: return "sparkles"
            case .rejectionRate: return "xmark.circle"
            }
        }
    }

    /// View-specific round data snapshot for charting.
    /// Named distinctly from the model-layer `RoundSummary`.
    struct RoundSnapshot: Identifiable {
        let id = UUID()
        let round: Int
        let revenue: Double
        let profit: Double
        let cash: Double
        let unitsSold: Int
        let marketShare: Double
        let customerSatisfaction: Double
        let sqRating: Double
        let investorScore: Double
        let imageRating: Double
        let rejectionRate: Double
    }

    /// View-specific chart data point.
    /// Named distinctly from the model-layer `ChartDataPoint`.
    struct ViewChartDataPoint: Identifiable {
        let id = UUID()
        let round: Int
        let value: Double
        let label: String

        var roundLabel: String { "R\(round)" }
    }

    // MARK: - Properties

    var rounds: [RoundSnapshot] = []
    var selectedMetric: ViewMetric = .profit
    var isLoading: Bool = false

    // MARK: - Computed

    /// Chart data points for the currently selected metric.
    var chartData: [ViewChartDataPoint] {
        rounds.map { summary in
            let value: Double
            switch selectedMetric {
            case .revenue:
                value = summary.revenue
            case .profit:
                value = summary.profit
            case .cash:
                value = summary.cash
            case .unitsSold:
                value = Double(summary.unitsSold)
            case .marketShare:
                value = summary.marketShare * 100
            case .sqRating:
                value = summary.sqRating
            case .investorScore:
                value = summary.investorScore
            case .imageRating:
                value = summary.imageRating
            case .rejectionRate:
                value = summary.rejectionRate * 100
            }

            return ViewChartDataPoint(
                round: summary.round,
                value: value,
                label: formattedValue(value, for: selectedMetric)
            )
        }
    }

    var hasData: Bool { !rounds.isEmpty }

    var latestValue: String {
        guard let last = chartData.last else { return "—" }
        return last.label
    }

    var trend: Trend {
        guard chartData.count >= 2 else { return .stable }
        let last = chartData[chartData.count - 1].value
        let previous = chartData[chartData.count - 2].value
        if last > previous { return .up }
        if last < previous { return .down }
        return .stable
    }

    enum Trend {
        case up, down, stable

        var icon: String {
            switch self {
            case .up: return "arrow.up.right"
            case .down: return "arrow.down.right"
            case .stable: return "arrow.right"
            }
        }

        var color: Color {
            switch self {
            case .up: return .green
            case .down: return .red
            case .stable: return .secondary
            }
        }
    }

    var chartTitle: String {
        "\(selectedMetric.displayName) Over Time"
    }

    var yAxisLabel: String {
        selectedMetric.unit
    }

    /// Min/max values for chart axis scaling.
    var minValue: Double {
        chartData.map(\.value).min() ?? 0
    }

    var maxValue: Double {
        chartData.map(\.value).max() ?? 100
    }

    // MARK: - Actions

    /// Load performance history for a team across all completed rounds.
    func loadHistory(from session: SimulationSession, for teamId: UUID) {
        isLoading = true

        var snapshots: [RoundSnapshot] = []
        let completedRounds = max(0, session.currentRound - 1)

        for round in 1...max(1, completedRounds) {
            if let result = session.roundResult(for: teamId, round: round) {
                snapshots.append(RoundSnapshot(
                    round: round,
                    revenue: result.revenue,
                    profit: result.profit,
                    cash: result.cash,
                    unitsSold: result.unitsSold,
                    marketShare: result.marketShare,
                    customerSatisfaction: result.customerSatisfaction,
                    sqRating: result.sqRating,
                    investorScore: result.scorecard.totalScore,
                    imageRating: result.scorecard.imageRating,
                    rejectionRate: result.rejectionRate
                ))
            }
        }

        rounds = snapshots
        isLoading = false
    }

    // MARK: - Formatting

    private func formattedValue(_ value: Double, for metric: ViewMetric) -> String {
        switch metric {
        case .revenue, .profit, .cash:
            return value.formatted(.currency(code: "USD").precision(.fractionLength(0)))
        case .unitsSold:
            return Int(value).formatted()
        case .marketShare, .rejectionRate:
            return value.formatted(.number.precision(.fractionLength(1))) + "%"
        case .sqRating:
            return String(format: "%.1f", value) + "★"
        case .investorScore, .imageRating:
            return String(format: "%.0f", value)
        }
    }
}
