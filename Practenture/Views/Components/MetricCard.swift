// MetricCard.swift
// Practenture
//
// Reusable metric display card with icon, value, trend indicator, and color accent.
// Enhanced with gradient backgrounds, shadow depth, and smooth animations.

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
                    // Icon with gradient circle background
                    ZStack {
                        Circle()
                            .fill(
                                LinearGradient(
                                    colors: [accentColor.opacity(0.8), accentColor.opacity(0.4)],
                                    startPoint: .topLeading,
                                    endPoint: .bottomTrailing
                                )
                            )
                        Image(systemName: icon)
                            .font(.title3)
                            .fontWeight(.semibold)
                            .foregroundStyle(.white)
                    }
                    .frame(width: 36, height: 36)
                    .shadow(color: accentColor.opacity(0.3), radius: 4, x: 0, y: 2)

                    Spacer()

                    // Trend badge
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
        .shadow(color: Color.black.opacity(0.06), radius: 8, x: 0, y: 4)
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
