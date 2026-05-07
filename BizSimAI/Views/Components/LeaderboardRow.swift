// LeaderboardRow.swift
// BizSimAI
//
// Reusable leaderboard row with rank, team name, score, S/Q rating, and trend.

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
        .frame(width: 40)
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
                            .background(.blue, in: Capsule())
                    }

                    if isAI {
                        Image(systemName: "cpu")
                            .font(.caption)
                            .foregroundStyle(.secondary)
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
        .padding(.vertical, 8)
        .padding(.horizontal, 12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(isCurrentTeam ? Color.blue.opacity(0.08) : Color.clear)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 10)
                .strokeBorder(isCurrentTeam ? Color.blue.opacity(0.3) : Color.clear, lineWidth: 1.5)
        )
    }
}
