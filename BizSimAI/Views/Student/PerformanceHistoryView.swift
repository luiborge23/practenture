// PerformanceHistoryView.swift
// BizSimAI
//
// S-6: Multi-round performance charts using Swift Charts.
// Picker to switch between metrics. Uses PerformanceHistoryViewModel.

import SwiftUI
import Charts
import Combine

struct PerformanceHistoryView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel = PerformanceHistoryViewModel()

    var body: some View {
        VStack(spacing: 20) {
            metricPicker
            chartView
            summaryStats
        }
        .padding(24)
        .navigationTitle("Performance History")
        #if os(macOS)
        .frame(minWidth: 550, minHeight: 400)
        #endif
        .onAppear {
            if let session = appState.activeSession,
               let teamId = session.playerTeam?.id {
                viewModel.loadHistory(from: session, for: teamId)
            }
        }
        .onChange(of: appState.activeSession?.currentRound ?? 0) { _, newRound in
            // Reload history when round changes (professor advanced the round)
            if let session = appState.activeSession,
               let teamId = session.playerTeam?.id,
               newRound > 1 {
                viewModel.loadHistory(from: session, for: teamId)
            }
        }
        .onReceive(Timer.publish(every: 10, on: .main, in: .common).autoconnect()) { _ in
            // Reload history when new results arrive from backend polling
            if let session = appState.activeSession,
               let teamId = session.playerTeam?.id,
               !viewModel.hasData {
                viewModel.loadHistory(from: session, for: teamId)
            }
        }
    }

    // MARK: - Metric Picker

    private var metricPicker: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(PerformanceHistoryViewModel.ViewMetric.allCases) { metric in
                    Button {
                        viewModel.selectedMetric = metric
                    } label: {
                        Label(metric.displayName, systemImage: metric.systemImage)
                            .font(.caption)
                            .fontWeight(viewModel.selectedMetric == metric ? .bold : .regular)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 8)
                            .background(
                                Capsule().fill(viewModel.selectedMetric == metric ? Color.accentColor : Color.gray.opacity(0.15))
                            )
                            .foregroundStyle(viewModel.selectedMetric == metric ? .white : .primary)
                    }
                    .buttonStyle(.plain)
                }
            }
        }
    }

    // MARK: - Chart

    private var chartView: some View {
        GroupBox {
            if viewModel.hasData {
                Chart(viewModel.chartData) { point in
                    LineMark(
                        x: .value("Round", point.round),
                        y: .value(viewModel.selectedMetric.displayName, point.value)
                    )
                    .interpolationMethod(.catmullRom)
                    .foregroundStyle(metricColor.gradient)
                    .lineStyle(StrokeStyle(lineWidth: 3, lineCap: .round))

                    AreaMark(
                        x: .value("Round", point.round),
                        y: .value(viewModel.selectedMetric.displayName, point.value)
                    )
                    .interpolationMethod(.catmullRom)
                    .foregroundStyle(
                        .linearGradient(
                            colors: [metricColor.opacity(0.2), metricColor.opacity(0.02)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                    )

                    PointMark(
                        x: .value("Round", point.round),
                        y: .value(viewModel.selectedMetric.displayName, point.value)
                    )
                    .foregroundStyle(metricColor)
                    .symbolSize(40)
                    .annotation(position: .top, spacing: 6) {
                        Text(point.label)
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .foregroundStyle(metricColor)
                    }
                }
                .chartXAxis {
                    AxisMarks(values: .automatic) { value in
                        AxisGridLine()
                            .foregroundStyle(Color.secondary.opacity(0.15))
                        AxisValueLabel {
                            if let round = value.as(Int.self) {
                                Text("R\(round)")
                                    .font(.caption)
                            }
                        }
                    }
                }
                .chartYAxis {
                    AxisMarks(position: .leading) { value in
                        AxisGridLine()
                            .foregroundStyle(Color.secondary.opacity(0.1))
                        AxisValueLabel {
                            if let val = value.as(Double.self) {
                                Text(formattedAxisValue(val))
                                    .font(.caption2)
                            }
                        }
                    }
                }
                .chartYScale(domain: .automatic(includesZero: !isPercentageMetric))
                .frame(height: 260)
                .animation(.spring(duration: 0.4), value: viewModel.selectedMetric)
            } else {
                ContentUnavailableView(
                    "No Data Yet",
                    systemImage: "chart.xyaxis.line",
                    description: Text("Complete at least one round to see your performance history.")
                )
                .frame(height: 260)
            }
        } label: {
            HStack {
                Image(systemName: viewModel.selectedMetric.systemImage)
                    .foregroundStyle(metricColor)
                Text(viewModel.chartTitle)
                    .font(.headline)
                Spacer()

                if viewModel.hasData {
                    HStack(spacing: 4) {
                        Image(systemName: viewModel.trend.icon)
                            .font(.caption)
                            .fontWeight(.bold)
                        Text(viewModel.latestValue)
                            .font(.caption)
                            .fontWeight(.semibold)
                    }
                    .foregroundStyle(viewModel.trend.color)
                }
            }
        }
    }

    // MARK: - Summary Stats

    private var summaryStats: some View {
        HStack(spacing: 16) {
            let data = viewModel.chartData

            summaryItem(label: "Current", value: data.last?.value ?? 0)
            Divider().frame(height: 40)
            summaryItem(label: "Best", value: data.map(\.value).max() ?? 0)
            Divider().frame(height: 40)
            summaryItem(label: "Average", value: data.map(\.value).reduce(0, +) / Double(max(data.count, 1)))
            Divider().frame(height: 40)

            let change: Double = {
                guard data.count >= 2 else { return 0 }
                return data[data.count - 1].value - data[data.count - 2].value
            }()

            VStack(spacing: 4) {
                Text("Change")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                HStack(spacing: 2) {
                    Image(systemName: change >= 0 ? "arrow.up.right" : "arrow.down.right")
                        .font(.caption2)
                    Text(formattedValue(abs(change)))
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .monospacedDigit()
                }
                .foregroundStyle(change >= 0 ? .green : .red)
            }
            .frame(maxWidth: .infinity)
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    private func summaryItem(label: String, value: Double) -> some View {
        VStack(spacing: 4) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(formattedValue(value))
                .font(.subheadline)
                .fontWeight(.semibold)
                .monospacedDigit()
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Helpers

    private var metricColor: Color {
        switch viewModel.selectedMetric {
        case .revenue: return .blue
        case .profit: return .green
        case .cash: return .mint
        case .unitsSold: return .orange
        case .marketShare: return .purple
        case .sqRating: return .yellow
        case .investorScore: return .blue
        case .imageRating: return .pink
        case .rejectionRate: return .red
        }
    }

    private var isPercentageMetric: Bool {
        switch viewModel.selectedMetric {
        case .marketShare, .rejectionRate: return true
        default: return false
        }
    }

    private func formattedValue(_ value: Double) -> String {
        switch viewModel.selectedMetric {
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

    private func formattedAxisValue(_ value: Double) -> String {
        switch viewModel.selectedMetric {
        case .marketShare, .rejectionRate:
            return "\(String(format: "%.0f", value))%"
        case .unitsSold:
            return Int(value).formatted()
        case .sqRating:
            return String(format: "%.1f", value)
        case .investorScore, .imageRating:
            return String(format: "%.0f", value)
        default:
            if value >= 1000 {
                return "$\(String(format: "%.0f", value / 1000))K"
            } else {
                return "$\(String(format: "%.0f", value))"
            }
        }
    }

    // MARK: - Sample Data

    private func loadSampleData() {
        // In production, this would call:
        // viewModel.loadHistory(from: session, for: teamId)
        // For now, populate with sample round summaries.
        viewModel.rounds = [
            PerformanceHistoryViewModel.RoundSnapshot(
                round: 1, revenue: 32_000, profit: 8_500, cash: 85_000,
                unitsSold: 180, marketShare: 0.20, customerSatisfaction: 0.70,
                sqRating: 5.0, investorScore: 45, imageRating: 42, rejectionRate: 0.10
            ),
            PerformanceHistoryViewModel.RoundSnapshot(
                round: 2, revenue: 38_500, profit: 12_200, cash: 88_500,
                unitsSold: 210, marketShare: 0.22, customerSatisfaction: 0.74,
                sqRating: 5.8, investorScore: 52, imageRating: 48, rejectionRate: 0.08
            ),
            PerformanceHistoryViewModel.RoundSnapshot(
                round: 3, revenue: 45_200, profit: 15_800, cash: 93_200,
                unitsSold: 230, marketShare: 0.25, customerSatisfaction: 0.79,
                sqRating: 6.4, investorScore: 61, imageRating: 55, rejectionRate: 0.06
            ),
            PerformanceHistoryViewModel.RoundSnapshot(
                round: 4, revenue: 52_300, profit: 18_700, cash: 98_200,
                unitsSold: 245, marketShare: 0.28, customerSatisfaction: 0.76,
                sqRating: 6.8, investorScore: 72, imageRating: 62, rejectionRate: 0.04
            ),
        ]
    }
}
