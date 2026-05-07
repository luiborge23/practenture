// MetricCard.swift
// BizSimAI
//
// Reusable metric display card with icon, value, trend indicator, and color accent.

import SwiftUI

enum TrendDirection: String, Codable {
    case up, down, flat

    var symbol: String {
        switch self {
        case .up: return "arrow.up.right"
        case .down: return "arrow.down.right"
        case .flat: return "arrow.right"
        }
    }

    var color: Color {
        switch self {
        case .up: return .green
        case .down: return .red
        case .flat: return .secondary
        }
    }
}

struct MetricCard: View {
    let title: String
    let value: String
    let icon: String
    var trend: TrendDirection = .flat
    var accentColor: Color = .blue

    var body: some View {
        GroupBox {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: icon)
                        .font(.title2)
                        .foregroundStyle(accentColor)
                        .frame(width: 32, height: 32)

                    Spacer()

                    HStack(spacing: 4) {
                        Image(systemName: trend.symbol)
                            .font(.caption)
                            .fontWeight(.bold)
                        Text(trend == .up ? "Up" : trend == .down ? "Down" : "Flat")
                            .font(.caption2)
                    }
                    .foregroundStyle(trend.color)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 4)
                    .background(trend.color.opacity(0.12), in: Capsule())
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(value)
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundStyle(.primary)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)

                    Text(title)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
            }
            .padding(4)
        }
        #if os(macOS)
        .backgroundStyle(Color(nsColor: .controlBackgroundColor))
        #else
        .backgroundStyle(Color(uiColor: .secondarySystemBackground))
        #endif
    }
}

// MARK: - Convenience Initializer for Currency

extension MetricCard {
    static func currency(
        title: String,
        amount: Double,
        icon: String = "dollarsign.circle.fill",
        trend: TrendDirection = .flat,
        color: Color = .green
    ) -> MetricCard {
        MetricCard(
            title: title,
            value: amount.formatted(.currency(code: "USD").precision(.fractionLength(0))),
            icon: icon,
            trend: trend,
            accentColor: color
        )
    }

    static func percentage(
        title: String,
        value: Double,
        icon: String = "chart.pie.fill",
        trend: TrendDirection = .flat,
        color: Color = .blue
    ) -> MetricCard {
        MetricCard(
            title: title,
            value: "\(String(format: "%.1f", value * 100))%",
            icon: icon,
            trend: trend,
            accentColor: color
        )
    }
}
