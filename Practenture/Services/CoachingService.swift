// CoachingService.swift
// Practenture
//
// Rule-based AI coaching for the marketplace simulation.
// Analyzes the player's decisions and results across all simulation dimensions.

import Foundation

// MARK: - Protocol

protocol CoachingServiceProtocol {
    func generateCoaching(
        session: SimulationSession,
        latestDecision: PlayerDecision,
        latestResult: RoundResult,
        competitorResults: [RoundResult]
    ) -> [CoachMessage]
}

// MARK: - Rule-Based Coaching Service

final class RuleBasedCoachingService: CoachingServiceProtocol {

    func generateCoaching(
        session: SimulationSession,
        latestDecision: PlayerDecision,
        latestResult: RoundResult,
        competitorResults: [RoundResult]
    ) -> [CoachMessage] {

        var messages: [CoachMessage] = []
        let config = session.config
        let playerHistory = session.resultsForTeam(latestResult.teamId)

        // Gather competitor context
        let avgWholesalePrice = calculateAverage(session: session) { $0.wholesalePrice }
        let avgAdvertising = calculateAverage(session: session) { $0.advertisingBudget }

        // -----------------------------------------------------------------
        // Rule 1: S/Q Rating too low
        // -----------------------------------------------------------------
        if latestResult.sqRating < 4.0 {
            messages.append(CoachMessage(
                content: "Your S/Q rating is \(String(format: "%.1f", latestResult.sqRating))★ — below average. Switch to superior materials (+2.0★), increase styling budget, and invest in TQM programs. Quality drives demand across all channels.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 2: Wholesale price significantly above market
        // -----------------------------------------------------------------
        if latestDecision.wholesalePrice > avgWholesalePrice * 1.2 && avgWholesalePrice > 0 {
            let premiumPct = Int((latestDecision.wholesalePrice / avgWholesalePrice - 1) * 100)
            if latestResult.sqRating < 7.0 {
                messages.append(CoachMessage(
                    content: "Your wholesale price is \(premiumPct)% above market average ($\(formatted(avgWholesalePrice))). With your S/Q at \(String(format: "%.1f", latestResult.sqRating))★, you may not justify the premium. Either lower price or improve quality.",
                    isFromAI: true
                ))
            }
        }

        // -----------------------------------------------------------------
        // Rule 3: Low advertising vs competitors
        // -----------------------------------------------------------------
        if latestDecision.advertisingBudget < avgAdvertising * 0.5 && avgAdvertising > 0 {
            messages.append(CoachMessage(
                content: "Your advertising spend ($\(formatted(latestDecision.advertisingBudget))) is well below average ($\(formatted(avgAdvertising))). Low visibility means potential customers don't know about your products, regardless of quality.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 4: No CSR investment
        // -----------------------------------------------------------------
        if latestDecision.csrInvestment < 1_000 {
            messages.append(CoachMessage(
                content: "You're barely investing in CSR ($\(formatted(latestDecision.csrInvestment))). CSR directly affects your Image Rating, which is worth 20 points on the investor scorecard. Even $3,000-5,000 per round makes a significant impact.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 5: Investor score declining
        // -----------------------------------------------------------------
        if playerHistory.count >= 2 {
            let current = latestResult.scorecard.totalScore
            let previous = playerHistory[playerHistory.count - 2].scorecard.totalScore
            if current < previous - 5 {
                messages.append(CoachMessage(
                    content: "Investor score dropped from \(String(format: "%.0f", previous)) to \(String(format: "%.0f", current)). Review which scorecard components declined and address them. Targets ratchet up each round — you need consistent improvement.",
                    isFromAI: true
                ))
            }
        }

        // -----------------------------------------------------------------
        // Rule 6: Cash running low
        // -----------------------------------------------------------------
        if latestResult.cash < config.startingCash * 0.3 {
            let cashPct = Int(latestResult.cash / config.startingCash * 100)
            messages.append(CoachMessage(
                content: "Cash is at \(cashPct)% of starting capital ($\(formatted(latestResult.cash)) remaining). Consider taking a loan to fund operations, but watch your debt-to-equity ratio for credit rating impact.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 7: Standard materials with high pricing
        // -----------------------------------------------------------------
        if latestDecision.materialsQuality == .standard && latestDecision.wholesalePrice > 90 {
            messages.append(CoachMessage(
                content: "You're charging premium prices ($\(formatted(latestDecision.wholesalePrice))) with standard materials. Customers expect higher S/Q for premium prices. Consider switching to superior materials to justify your pricing.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 8: Internet price lower than wholesale
        // -----------------------------------------------------------------
        if latestDecision.internetPrice < latestDecision.wholesalePrice {
            messages.append(CoachMessage(
                content: "Your internet price ($\(formatted(latestDecision.internetPrice))) is below your wholesale price ($\(formatted(latestDecision.wholesalePrice))). The internet channel should generally be priced higher since it's direct-to-consumer with better margins.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 9: High rejection rate
        // -----------------------------------------------------------------
        if latestResult.rejectionRate > 0.08 {
            messages.append(CoachMessage(
                content: "Your rejection rate is \(String(format: "%.1f", latestResult.rejectionRate * 100))% — you're wasting production. Invest in TQM, increase training hours, and add incentive pay to reduce defects. Target under 5% for efficient operations.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 10: Low workforce investment with quality issues
        // -----------------------------------------------------------------
        if latestDecision.trainingHours < 10 && latestDecision.incentivePay < 0.30 && latestResult.sqRating < 6.0 {
            messages.append(CoachMessage(
                content: "Low training (\(String(format: "%.0f", latestDecision.trainingHours))hrs) and minimal incentive pay ($\(String(format: "%.2f", latestDecision.incentivePay))/pair). Your workforce affects quality, rejection rate, and S/Q. Invest in your people to improve product quality.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 11: Unsold inventory piling up
        // -----------------------------------------------------------------
        if latestResult.inventory > 30 {
            messages.append(CoachMessage(
                content: "You have \(latestResult.inventory) units in inventory, costing $\(String(format: "%.0f", latestResult.storageCosts)) in storage. Either reduce production next round or boost demand with better pricing, advertising, or mail-in rebates.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 12: First-round tips
        // -----------------------------------------------------------------
        if latestResult.round == 1 {
            messages.append(CoachMessage(
                content: "Round 1 complete! Key insight: The investor scorecard (EPS, ROE, Stock Price, Image, Credit) determines your final rank. Targets ratchet up each round! Start building your image early with CSR and endorsements, maintain credit by keeping debt low, and invest in workforce training to reduce defects.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 13: Strong performance
        // -----------------------------------------------------------------
        if latestResult.scorecard.totalScore >= 70
            && latestResult.profit > 0
            && messages.isEmpty {
            messages.append(CoachMessage(
                content: "Strong round! Investor score of \(String(format: "%.0f", latestResult.scorecard.totalScore))/100. Keep investing in quality and brand to stay ahead. Watch for competitors adjusting their strategies to challenge your position.",
                isFromAI: true
            ))
        }

        // -----------------------------------------------------------------
        // Rule 14: End-game strategy
        // -----------------------------------------------------------------
        let roundsRemaining = config.totalRounds - latestResult.round
        if roundsRemaining == 2 {
            let scoringHint: String
            switch config.scoringMetric {
            case .investorScore:
                scoringHint = "Maximize your investor scorecard — boost EPS with buybacks, maintain dividends for stock price."
            case .cumulativeProfit:
                scoringHint = "Focus on margins. Cut any spending that doesn't directly drive profitable sales."
            case .revenue:
                scoringHint = "Push volume across all channels. Competitive pricing and high marketing are key."
            case .composite:
                scoringHint = "Balance profit, revenue, and market position. Don't sacrifice one metric for another."
            }
            messages.append(CoachMessage(
                content: "Two rounds left! \(scoringHint) Now is the time to commit to your final push.",
                isFromAI: true
            ))
        }

        return Array(messages.prefix(3))
    }

    // MARK: - Helpers

    private func calculateAverage(session: SimulationSession, extractor: (PlayerDecision) -> Double) -> Double {
        let decisions = session.currentRoundDecisions.values
        guard !decisions.isEmpty else { return 0 }
        let total = decisions.reduce(0.0) { $0 + extractor($1) }
        return total / Double(decisions.count)
    }

    private func formatted(_ value: Double) -> String {
        let formatter = NumberFormatter()
        formatter.numberStyle = .decimal
        formatter.maximumFractionDigits = 0
        return formatter.string(from: NSNumber(value: value)) ?? "\(Int(value))"
    }
}
