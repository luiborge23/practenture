// LeaderboardRow.swift
// BizSimAI
//
// Reusable leaderboard row with rank, team name, score, S/Q rating, and trend.
// Enhanced with gradient medal backgrounds, rank-based styling, and smooth animations.

import SwiftUI

struct LeaderboardRow: View {
    let rank: Int
    let teamName: String
    let score: Double
    var trend: TrendDirection = .flat
    var isCurrentTeam: Bool = false
    var isAI: Bool = false
    var scoringLabel: String = "Investor Score"
    var sqRating: Double = 5.0
    var investorScore: Double = 0

    private var medalEmoji: String? {
        switch rank {
        case 1: return "🥇"
        case 2: return "🥈"
        case 3: return "🥉"
        default: return nil
        }
    }

    // Gradient colors for top 3 ranks
    private var rankGradient: LinearGradient {
        switch rank {
        case 1:
            return LinearGradient(colors: [Color.yellow.opacity(0.15), Color.orange.opacity(0.05)], startPoint: .topLeading, endPoint: .bottomTrailing)
        case 2:
            return LinearGradient(colors: [Color.gray.opacity(0.12), Color.gray.opacity(0.04)], startPoint: .topLeading, endPoint: .bottomTrailing)
        case 3:
            return LinearGradient(colors: [Color.brown.opacity(0.10), Color.brown.opacity(0.03)], startPoint: .topLeading, endPoint: .bottomTrailing)
        default:
            return LinearGradient(colors: [Color.clear], startPoint: .topLeading, endPoint: .bottomTrailing)
        }
    }

    private var rankDisplay: some View {
        Group {
            if let medal = medalEmoji {
                Text(medal)
                    .font(.title2)
            } else {
                Text("#\(rank)")
                    .font(.headline)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(width: 44, height: 36)
        .background(
            RoundedRectangle(cornerRadius: 8)
                .fill(rank > 3 ? Color.gray.opacity(0.06) : Color.clear)
        )
    }

    /// Format score based on scoring label context
    private var formattedScore: String {
        if scoringLabel == "Investor Score" || scoringLabel == "Composite Score" {
            return String(format: "%.0f", score) + "/100"
        }
        return score.formatted(.currency(code: "USD").precision(.fractionLength(0)))
    }

    var body: some View {
        HStack(spacing: 12) {
            rankDisplay

            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(teamName)
                        .font(.headline)
                        .foregroundStyle(isCurrentTeam ? .blue : .primary)

                    if isCurrentTeam {
                        Text("YOU")
                            .font(.caption2)
                            .fontWeight(.bold)
                            .foregroundStyle(.white)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(
                                LinearGradient(colors: [Color.blue, Color.blue.opacity(0.8)], startPoint: .top, endPoint: .bottom),
                                in: Capsule()
                            )
                    }

                    if isAI {
                        HStack(spacing: 3) {
                            Image(systemName: "cpu")
                                .font(.caption2)
                            Text("AI")
                                .font(.caption2)
                                .fontWeight(.medium)
                        }
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Color.purple.opacity(0.08), in: Capsule())
                    }
                }

                HStack(spacing: 8) {
                    Text(scoringLabel)
                        .font(.caption)
                        .foregroundStyle(.tertiary)

                    Text("S/Q: \(String(format: "%.1f", sqRating))★")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 2) {
                HStack(spacing: 8) {
                    Text(formattedScore)
                        .font(.body)
                        .fontWeight(.semibold)
                        .monospacedDigit()

                    Image(systemName: trend.symbol)
                        .font(.caption)
                        .fontWeight(.bold)
                        .foregroundStyle(trend.color)
                }
            }
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 14)
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(
                    isCurrentTeam
                        ? AnyShapeStyle(LinearGradient(colors: [Color.blue.opacity(0.10), Color.blue.opacity(0.03)], startPoint: .topLeading, endPoint: .bottomTrailing))
                        : AnyShapeStyle(rankGradient)
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(
                    isCurrentTeam ? Color.blue.opacity(0.35) : Color.gray.opacity(0.08),
                    lineWidth: isCurrentTeam ? 1.5 : 0.5
                )
        )
        .shadow(color: Color.black.opacity(0.04), radius: 4, x: 0, y: 2)
    }
}
