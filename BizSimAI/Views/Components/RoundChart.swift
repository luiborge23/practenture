// RoundChart.swift
// BizSimAI
//
// Reusable chart component for displaying round-by-round data.
// Supports bar and line chart types using Swift Charts.

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
            Text(title)
                .font(.headline)

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
                .fill(Color.gray.opacity(0.1))
        )
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
                .foregroundStyle(color.gradient)
                .cornerRadius(4)

            case .line:
                LineMark(
                    x: .value("Round", point.label),
                    y: .value("Value", point.value)
                )
                .foregroundStyle(color)
                .lineStyle(StrokeStyle(lineWidth: 2.5))
                .symbol {
                    Circle()
                        .fill(color)
                        .frame(width: 8, height: 8)
                }

                AreaMark(
                    x: .value("Round", point.label),
                    y: .value("Value", point.value)
                )
                .foregroundStyle(color.opacity(0.1).gradient)
            }
        }
        .chartYAxis {
            AxisMarks(position: .leading) { value in
                AxisGridLine(stroke: StrokeStyle(lineWidth: 0.5, dash: [4]))
                    .foregroundStyle(.secondary.opacity(0.3))
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
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 8) {
            Image(systemName: "chart.bar.xaxis")
                .font(.title)
                .foregroundStyle(.secondary)
            Text("No data available")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity)
        .frame(height: 200)
    }
}
