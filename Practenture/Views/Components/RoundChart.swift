// RoundChart.swift
// Practenture
//
// Reusable chart component for displaying round-by-round data.
// Supports bar and line chart types using Swift Charts.
// Enhanced with gradient fills, rounded corners, shadow depth, and smooth animations.

import SwiftUI
import Charts

// MARK: - Chart Data Point

struct RoundChartDataPoint: Identifiable {
    let id = UUID()
    let label: String
    let value: Double
}

// MARK: - Chart Type

enum RoundChartType: String, CaseIterable {
    case bar = "Bar"
    case line = "Line"

    var icon: String {
        switch self {
        case .bar: return "chart.bar.fill"
        case .line: return "chart.xyaxis.line"
        }
    }
}

// MARK: - Round Chart

struct RoundChart: View {
    let title: String
    let data: [RoundChartDataPoint]
    var chartType: RoundChartType = .bar
    var color: Color = .blue
    var showLegend: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 6) {
                Image(systemName: chartType.icon)
                    .font(.subheadline)
                    .foregroundStyle(color)
                Text(title)
                    .font(.headline)
            }

            if data.isEmpty {
                emptyState
            } else {
                chartContent
                    .frame(height: 200)
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [Color.gray.opacity(0.08), Color.gray.opacity(0.03)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(Color.gray.opacity(0.06), lineWidth: 0.5)
        )
        .shadow(color: Color.black.opacity(0.04), radius: 6, x: 0, y: 3)
    }

    // MARK: - Chart Content

    @ViewBuilder
    private var chartContent: some View {
        Chart(data) { point in
            switch chartType {
            case .bar:
                BarMark(
                    x: .value("Round", point.label),
                    y: .value("Value", point.value)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [color, color.opacity(0.6)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
                .cornerRadius(6)

            case .line:
                LineMark(
                    x: .value("Round", point.label),
                    y: .value("Value", point.value)
                )
                .foregroundStyle(color)
                .lineStyle(StrokeStyle(lineWidth: 3, lineCap: .round))
                .symbol {
                    Circle()
                        .fill(color)
                        .frame(width: 10, height: 10)
                        .shadow(color: color.opacity(0.3), radius: 3)
                }

                AreaMark(
                    x: .value("Round", point.label),
                    y: .value("Value", point.value)
                )
                .foregroundStyle(
                    LinearGradient(
                        colors: [color.opacity(0.2), color.opacity(0.02)],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
            }
        }
        .chartYAxis {
            AxisMarks(position: .leading) { value in
                AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [4]))
                    .foregroundStyle(.secondary.opacity(0.2))
                AxisValueLabel()
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .chartXAxis {
            AxisMarks { value in
                AxisValueLabel()
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .animation(.easeInOut(duration: 0.4), value: data.count)
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "chart.bar.xaxis")
                .font(.title)
                .foregroundStyle(.tertiary)
            Text("No data available")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 200)
    }
}
