import SwiftUI

// MARK: - RoundResultsViewModel
/// Round results with investor scorecard, revenue by channel,
/// cost breakdown, and competitive intelligence.

@Observable
final class RoundResultsViewModel {

    // MARK: - Supporting Types

    struct CompetitorSummary: Identifiable {
        let id = UUID()
        let teamName: String
        let revenue: Double
        let unitsSold: Int
        let marketShare: Double
        let sqRating: Double
        let imageRating: Double

        var formattedRevenue: String {
            revenue.formatted(.currency(code: "USD").precision(.fractionLength(0)))
        }

        var formattedMarketShare: String {
            (marketShare * 100).formatted(.number.precision(.fractionLength(1))) + "%"
        }
    }

    struct RoundExplanation: Identifiable {
        let id = UUID()
        let category: String
        let explanation: String
        let impact: Impact

        var color: Color {
            switch impact {
            case .positive: return .green
            case .negative: return .red
            case .neutral: return .secondary
            }
        }

        var icon: String {
            switch impact {
            case .positive: return "arrow.up.circle.fill"
            case .negative: return "arrow.down.circle.fill"
            case .neutral: return "minus.circle.fill"
            }
        }
    }

    // MARK: - Properties

    var roundNumber: Int = 0
    var revenue: Double = 0
    var costs: Double = 0
    var profit: Double = 0
    var unitsSold: Int = 0
    var marketShare: Double = 0
    var customerSatisfaction: Double = 0
    var cashAfter: Double = 0

    // Revenue by channel
    var wholesaleRevenue: Double = 0
    var internetRevenue: Double = 0
    var amazonRevenue: Double = 0
    var privateLabelRevenue: Double = 0

    // Units by channel
    var wholesaleUnitsSold: Int = 0
    var internetUnitsSold: Int = 0
    var amazonUnitsSold: Int = 0
    var privateLabelUnitsSold: Int = 0

    // Investor Scorecard
    var sqRating: Double = 5.0
    var eps: Double = 0
    var roe: Double = 0
    var stockPrice: Double = 25.0
    var imageRating: Double = 50.0
    var creditRating: CreditRating = .a
    var investorScore: Double = 0
    var epsScore: Double = 0
    var roeScore: Double = 0
    var stockPriceScore: Double = 0
    var imageScore: Double = 0
    var creditScore: Double = 0

    // Enhanced metrics
    var rejectionRate: Double = 0
    var inventoryUnits: Int = 0
    var productionCosts: Double = 0
    var workforceCosts: Double = 0
    var marketingCosts: Double = 0
    var csrCosts: Double = 0
    var endorsementCosts: Double = 0
    var storageCosts: Double = 0
    var rebateCosts: Double = 0
    var deliveryCosts: Double = 0
    var socialMediaCosts: Double = 0
    var amazonFees: Double = 0
    var interestExpense: Double = 0
    var dividendsPaid: Double = 0

    var competitorSummary: [CompetitorSummary] = []
    var explanations: [RoundExplanation] = []
    var coachingTips: [String] = []

    var isLoading: Bool = false
    var isRequestingCoaching: Bool = false

    // MARK: - Formatted Display

    func formatted(_ value: Double) -> String {
        value.formatted(.currency(code: "USD").precision(.fractionLength(0)))
    }

    var formattedRevenue: String { formatted(revenue) }
    var formattedCosts: String { formatted(costs) }
    var formattedProfit: String { formatted(profit) }
    var formattedCashAfter: String { formatted(cashAfter) }

    var formattedMarketShare: String {
        (marketShare * 100).formatted(.number.precision(.fractionLength(1))) + "%"
    }

    var formattedSatisfaction: String {
        (customerSatisfaction * 100).formatted(.number.precision(.fractionLength(1))) + "%"
    }

    var profitColor: Color {
        if profit > 0 { return .green }
        if profit < 0 { return .red }
        return .secondary
    }

    var roundLabel: String { "Round \(roundNumber) Results" }
    var isProfitable: Bool { profit > 0 }

    // MARK: - Actions

    func loadResults(from session: SimulationSession, for teamId: UUID, round: Int) {
        isLoading = true
        roundNumber = round

        // Try to fetch from backend first, fall back to local session data
        Task {
            do {
                // Extract session code from session
                let sessionCode = session.sessionCode
                
                // Attempt to fetch results from backend
                let backendResults = try await NetworkService.shared.getResultsForTeam(
                    code: sessionCode,
                    teamId: teamId,
                    round: round
                )
                
                if let result = backendResults.first {
                    await MainActor.run {
                        self.updateFromBackendResult(result)
                        self.isLoading = false
                    }
                    return
                }
            } catch {
                // Backend failed or no results - fall back to local session data
                print("Backend fetch failed, falling back to local: \(error)")
            }
            
            // Fallback to local session data
            if let result = session.roundResult(for: teamId, round: round) {
                await MainActor.run {
                    self.updateFromLocalResult(result)
                    self.isLoading = false
                }
            } else {
                await MainActor.run {
                    self.isLoading = false
                }
            }
        }
    }

    /// Update view model from backend RoundResultBackend
    @MainActor
    private func updateFromBackendResult(_ result: RoundResultBackend) {
        revenue = result.revenue
        costs = result.costs
        profit = result.profit
        unitsSold = 0  // Not in backend model, would need to be added
        marketShare = result.marketShare
        customerSatisfaction = result.reputation  // Using reputation as satisfaction proxy
        cashAfter = result.cash
        sqRating = result.sqRating

        // Channel breakdown - not in backend model, would need enhancement
        wholesaleRevenue = 0
        internetRevenue = 0
        amazonRevenue = 0
        privateLabelRevenue = 0
        wholesaleUnitsSold = 0
        internetUnitsSold = 0
        amazonUnitsSold = 0
        privateLabelUnitsSold = 0

        // Investor Scorecard
        eps = result.eps
        roe = result.roe
        stockPrice = result.stockPrice
        imageRating = result.imageScore  // Note: backend has imageScore, iOS has imageRating
        creditRating = CreditRating(rawValue: "\(result.creditScore)") ?? .a
        investorScore = result.totalScore
        epsScore = result.epsScore
        roeScore = result.roeScore
        stockPriceScore = result.stockPriceScore
        imageScore = result.imageScore
        creditScore = result.creditScore

        // Enhanced metrics - not in backend model
        rejectionRate = 0
        inventoryUnits = 0
        productionCosts = 0
        workforceCosts = 0
        marketingCosts = 0
        csrCosts = 0
        endorsementCosts = 0
        storageCosts = 0
        rebateCosts = 0
        deliveryCosts = 0
        socialMediaCosts = 0
        amazonFees = 0
        interestExpense = 0
        dividendsPaid = 0

        // Competitive intelligence - would need to fetch all teams
        competitorSummary = []
        explanations = buildExplanations(from: convertToLocalRoundResult(result))
        coachingTips = generateBasicTips()
    }

    /// Update view model from local RoundResult (fallback)
    @MainActor
    private func updateFromLocalResult(_ result: RoundResult) {
        revenue = result.revenue
        costs = result.costs
        profit = result.profit
        unitsSold = result.unitsSold
        marketShare = result.marketShare
        customerSatisfaction = result.customerSatisfaction
        cashAfter = result.cash
        sqRating = result.sqRating

        // Channel breakdown
        wholesaleRevenue = result.wholesaleRevenue
        internetRevenue = result.internetRevenue
        amazonRevenue = result.amazonRevenue
        privateLabelRevenue = result.privateLabelRevenue
        wholesaleUnitsSold = result.wholesaleUnitsSold
        internetUnitsSold = result.internetUnitsSold
        amazonUnitsSold = result.amazonUnitsSold
        privateLabelUnitsSold = result.privateLabelUnitsSold

        // Investor Scorecard
        eps = result.scorecard.eps
        roe = result.scorecard.roe
        stockPrice = result.scorecard.stockPrice
        imageRating = result.scorecard.imageRating
        creditRating = result.scorecard.creditRating
        investorScore = result.scorecard.totalScore
        epsScore = result.scorecard.epsScore
        roeScore = result.scorecard.roeScore
        stockPriceScore = result.scorecard.stockPriceScore
        imageScore = result.scorecard.imageScore
        creditScore = result.scorecard.creditScore

        // Enhanced metrics
        rejectionRate = result.rejectionRate
        inventoryUnits = result.inventory
        productionCosts = result.productionCosts
        workforceCosts = result.workforceCosts
        marketingCosts = result.marketingCosts
        csrCosts = result.csrCosts
        endorsementCosts = result.endorsementCosts
        storageCosts = result.storageCosts
        rebateCosts = result.rebateCosts
        deliveryCosts = result.deliveryCosts
        socialMediaCosts = result.socialMediaCosts
        amazonFees = result.amazonFees
        interestExpense = result.interestExpense
        dividendsPaid = result.dividendsPaid

        explanations = buildExplanations(from: result)
        coachingTips = generateBasicTips()

        // Competitive intelligence
        // Note: This would need the full session to compare against other teams
        // For now, we'll leave it empty and rely on the explanations
        competitorSummary = []
    }

    /// Convert backend RoundResultBackend to local RoundResult for explanation building
    private func convertToLocalRoundResult(_ backend: RoundResultBackend) -> RoundResult {
        let scorecard = InvestorScorecard(
            round: backend.round,
            eps: backend.eps,
            roe: backend.roe,
            stockPrice: backend.stockPrice,
            imageRating: backend.imageScore,
            creditRating: CreditRating(rawValue: "\(Int(backend.creditScore))") ?? .a,
            epsScore: backend.epsScore,
            roeScore: backend.roeScore,
            stockPriceScore: backend.stockPriceScore,
            imageScore: backend.imageScore,
            creditScore: backend.creditScore
        )
        let result = RoundResult(
            teamId: UUID(uuidString: backend.teamId) ?? UUID(),
            round: backend.round,
            wholesaleRevenue: backend.revenue * 0.5,  // Split revenue proportionally (approximation)
            internetRevenue: backend.revenue * 0.3,
            amazonRevenue: backend.revenue * 0.15,
            privateLabelRevenue: backend.revenue * 0.05,
            productionCosts: backend.productionCost,
            marketingCosts: backend.marketingCost,
            csrCosts: 0,
            endorsementCosts: 0,
            interestExpense: backend.equity * 0.05,  // Approximation
            dividendsPaid: 0,
            workforceCosts: 0,
            storageCosts: 0,
            rebateCosts: 0,
            deliveryCosts: 0,
            socialMediaCosts: 0,
            amazonFees: 0,
            wholesaleUnitsSold: 0,
            internetUnitsSold: 0,
            amazonUnitsSold: 0,
            privateLabelUnitsSold: 0,
            marketShare: backend.marketShare,
            customerSatisfaction: backend.reputation,
            inventory: Int(backend.inventory),
            rejectionRate: 0,
            cash: backend.cash,
            sqRating: backend.sqRating,
            awarenessScore: 0,
            scorecard: scorecard
        )
        return result
    }

    func requestCoaching() {
        isRequestingCoaching = true
        coachingTips = generateBasicTips()
        isRequestingCoaching = false
    }

    // MARK: - Private Helpers

    private func buildExplanations(from result: RoundResult) -> [RoundExplanation] {
        var items: [RoundExplanation] = []

        // S/Q Rating
        if result.sqRating >= 7 {
            items.append(RoundExplanation(
                category: "S/Q Rating", explanation: "Excellent quality at \(String(format: "%.1f", result.sqRating))★ — drives premium demand.", impact: .positive))
        } else if result.sqRating < 4 {
            items.append(RoundExplanation(
                category: "S/Q Rating", explanation: "Quality at \(String(format: "%.1f", result.sqRating))★ is below average. Invest in materials and TQM.", impact: .negative))
        }

        // Revenue channels
        if result.revenue > 0 {
            let internetPct = result.internetRevenue / result.revenue * 100
            if internetPct > 35 {
                items.append(RoundExplanation(
                    category: "Internet Channel", explanation: "Internet sales at \(String(format: "%.0f", internetPct))% of revenue — higher margin channel.", impact: .positive))
            }
            if result.privateLabelRevenue > 0 {
                items.append(RoundExplanation(
                    category: "Private Label", explanation: "Private-label contracts filling capacity and reducing per-unit costs.", impact: .neutral))
            }
        }

        // Profitability
        if result.profit < 0 {
            items.append(RoundExplanation(
                category: "Profitability", explanation: "Operating at a loss. Review cost structure and pricing strategy.", impact: .negative))
        } else if result.profit > result.revenue * 0.15 {
            items.append(RoundExplanation(
                category: "Profitability", explanation: "Strong margins at \(String(format: "%.0f", result.profit / result.revenue * 100))%. Good cost management.", impact: .positive))
        }

        // Investor score
        if result.scorecard.totalScore >= 80 {
            items.append(RoundExplanation(
                category: "Investor Score", explanation: "Outstanding score of \(String(format: "%.0f", result.scorecard.totalScore))/100.", impact: .positive))
        } else if result.scorecard.totalScore < 40 {
            items.append(RoundExplanation(
                category: "Investor Score", explanation: "Score of \(String(format: "%.0f", result.scorecard.totalScore))/100 — targets ratchet up each round.", impact: .negative))
        }

        // Rejection rate
        if result.rejectionRate > 0.08 {
            items.append(RoundExplanation(
                category: "Rejection Rate", explanation: "Defect rate of \(String(format: "%.1f", result.rejectionRate * 100))% — invest in TQM, training, and incentive pay.", impact: .negative))
        } else if result.rejectionRate <= 0.03 {
            items.append(RoundExplanation(
                category: "Rejection Rate", explanation: "Excellent defect rate of \(String(format: "%.1f", result.rejectionRate * 100))% — quality programs paying off.", impact: .positive))
        }

        // Inventory
        if result.inventory > 20 {
            items.append(RoundExplanation(
                category: "Inventory", explanation: "\(result.inventory) unsold units carrying $\(String(format: "%.0f", result.storageCosts)) in storage costs.", impact: .negative))
        }

        return items
    }

    private func generateBasicTips() -> [String] {
        var tips: [String] = []

        if profit < 0 {
            tips.append("Operating at a loss. Consider raising prices, switching to superior materials to justify premiums, or cutting costs.")
        }

        if marketShare < 0.1 && unitsSold > 0 {
            tips.append("Low market share. Increase advertising, add celebrity endorsements, or lower wholesale price to gain volume.")
        }

        if sqRating < 5.0 {
            tips.append("Your S/Q rating is below average. Switch to superior materials and invest in styling and TQM programs.")
        }

        if imageRating < 40 {
            tips.append("Image rating is low. Boost CSR spending, add celebrity endorsements, and improve S/Q to strengthen your brand.")
        }

        if creditRating < .bPlus {
            tips.append("Credit rating is weakening. Reduce debt and maintain positive cash flow to avoid higher borrowing costs.")
        }

        if tips.isEmpty {
            tips.append("Solid performance! Monitor competitor moves and keep building on your S/Q and image advantages.")
        }

        return tips
    }
}
