// RoundResultsView.swift
// BizSimAI
//
// Round results with investor scorecard, revenue by channel,
// cost breakdown, competitive intelligence, and coaching tips.

import SwiftUI

struct RoundResultsView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AppState.self) private var appState

    @State private var viewModel = RoundResultsViewModel()
    @State private var animateMetrics = false
    @State private var showCoach = false
    @State private var roundNumber: Int
    @State private var totalRounds: Int

    init(roundNumber: Int? = nil, totalRounds: Int? = nil) {
        // Resolve from session in onAppear if not provided
        self._roundNumber = State(initialValue: roundNumber ?? 0)
        self._totalRounds = State(initialValue: totalRounds ?? 10)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                roundHeader
                investorScorecardSection
                channelBreakdown
                incomeStatementSection
                metricsSection
                competitorsSection
                explanationsSection
                coachingSection
                navigationButtons
            }
            .padding(24)
        }
        .navigationTitle("Round Results")
        #if os(macOS)
        .frame(minWidth: 550)
        #endif
        .onAppear {
            if let session = appState.activeSession,
               let teamId = session.playerTeam?.id {
                // Resolve round number from session if not explicitly provided
                if roundNumber == 0 {
                    // When session is completed, show the final round
                    // Otherwise show the most recent completed round (currentRound - 1)
                    if session.state == .completed {
                        roundNumber = session.totalRounds
                    } else {
                        roundNumber = max(1, session.currentRound - 1)
                    }
                }
                totalRounds = session.totalRounds
                viewModel.loadResults(from: session, for: teamId, round: roundNumber)
            } else {
                loadSampleData()
            }
            withAnimation(.spring(duration: 0.6)) {
                animateMetrics = true
            }
        }
        .sheet(isPresented: $showCoach) {
            NavigationStack {
                AICoachView()
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Done") { showCoach = false }
                        }
                    }
            }
            #if os(macOS)
            .frame(minWidth: 520, minHeight: 500)
            #endif
        }
    }

    // MARK: - Round Header

    private var roundHeader: some View {
        VStack(spacing: 8) {
            Text(viewModel.roundLabel.isEmpty ? "Round \(roundNumber) Results" : viewModel.roundLabel)
                .font(.largeTitle)
                .fontWeight(.bold)

            if roundNumber >= totalRounds {
                Text("Simulation Complete")
                    .font(.subheadline)
                    .foregroundStyle(.green)
            } else {
                Text("\(totalRounds - roundNumber) rounds remaining")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
    }

    // MARK: - Investor Scorecard

    private var investorScorecardSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Investor Scorecard", systemImage: "chart.bar.doc.horizontal")
                    .font(.headline)
                Spacer()
                Text("Score: \(String(format: "%.0f", viewModel.investorScore))/100")
                    .font(.title3)
                    .fontWeight(.bold)
                    .foregroundStyle(viewModel.investorScore >= 70 ? .green : viewModel.investorScore < 40 ? .red : .orange)
            }

            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 5), spacing: 8) {
                scorecardItem("EPS", value: String(format: "$%.2f", viewModel.eps),
                              score: viewModel.epsScore, maxScore: 20)
                scorecardItem("ROE", value: String(format: "%.1f%%", viewModel.roe * 100),
                              score: viewModel.roeScore, maxScore: 20)
                scorecardItem("Stock", value: String(format: "$%.2f", viewModel.stockPrice),
                              score: viewModel.stockPriceScore, maxScore: 20)
                scorecardItem("Image", value: String(format: "%.0f", viewModel.imageRating),
                              score: viewModel.imageScore, maxScore: 20)
                scorecardItem("Credit", value: viewModel.creditRating.displayName,
                              score: viewModel.creditScore, maxScore: 20)
            }
        }
        .padding(16)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Color.blue.opacity(0.05)))
    }

    private func scorecardItem(_ label: String, value: String, score: Double, maxScore: Double) -> some View {
        VStack(spacing: 6) {
            Text(value)
                .font(.subheadline)
                .fontWeight(.bold)
                .foregroundStyle(score >= maxScore * 0.7 ? .green : score < maxScore * 0.3 ? .red : .primary)
            Text("\(String(format: "%.0f", score))/\(String(format: "%.0f", maxScore))")
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.08)))
    }

    // MARK: - Channel Revenue Breakdown

    private var channelBreakdown: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Revenue by Channel")
                .font(.headline)

            HStack(spacing: 12) {
                channelCard(title: "Wholesale", revenue: viewModel.wholesaleRevenue,
                            units: viewModel.wholesaleUnitsSold, color: .blue)
                channelCard(title: "Internet", revenue: viewModel.internetRevenue,
                            units: viewModel.internetUnitsSold, color: .purple)
                channelCard(title: "Private Label", revenue: viewModel.privateLabelRevenue,
                            units: viewModel.privateLabelUnitsSold, color: .orange)
            }
        }
    }

    private func channelCard(title: String, revenue: Double, units: Int, color: Color) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
            Text(viewModel.formatted(revenue))
                .font(.headline)
                .fontWeight(.bold)
                .monospacedDigit()
            Text("\(units) units")
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(color.opacity(0.08))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(color.opacity(0.2), lineWidth: 1)
        )
    }

    // MARK: - Income Statement

    private var incomeStatementSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Income Statement", systemImage: "doc.text")
                    .font(.headline)
                Spacer()
                Text("Round \(roundNumber)")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }

            VStack(spacing: 0) {
                // Revenue
                incomeRow("Wholesale Revenue", value: viewModel.wholesaleRevenue, isHeader: false)
                incomeRow("Internet Revenue", value: viewModel.internetRevenue, isHeader: false)
                incomeRow("Amazon Revenue", value: viewModel.amazonRevenue, isHeader: false)
                incomeRow("Private-Label Revenue", value: viewModel.privateLabelRevenue, isHeader: false)
                incomeDivider
                incomeRow("Gross Revenue", value: viewModel.revenue, isHeader: true, color: .green)

                Divider().padding(.vertical, 4)

                // Costs (using actual values from engine)
                incomeRow("Production Costs", value: -viewModel.productionCosts, isHeader: false)
                incomeRow("Workforce Costs", value: -viewModel.workforceCosts, isHeader: false)
                incomeRow("Marketing & Ads", value: -viewModel.marketingCosts, isHeader: false)
                if viewModel.csrCosts > 0 {
                    incomeRow("CSR Investment", value: -viewModel.csrCosts, isHeader: false)
                }
                if viewModel.endorsementCosts > 0 {
                    incomeRow("Celebrity Endorsement", value: -viewModel.endorsementCosts, isHeader: false)
                }
                if viewModel.socialMediaCosts > 0 {
                    incomeRow("Social Media & Influencers", value: -viewModel.socialMediaCosts, isHeader: false)
                }
                if viewModel.amazonFees > 0 {
                    incomeRow("Amazon Fees", value: -viewModel.amazonFees, isHeader: false)
                }
                if viewModel.rebateCosts > 0 {
                    incomeRow("Mail-in Rebates", value: -viewModel.rebateCosts, isHeader: false)
                }
                if viewModel.deliveryCosts > 0 {
                    incomeRow("Rush Delivery Costs", value: -viewModel.deliveryCosts, isHeader: false)
                }
                if viewModel.storageCosts > 0 {
                    incomeRow("Inventory Storage", value: -viewModel.storageCosts, isHeader: false)
                }
                incomeDivider
                let operatingIncome = viewModel.revenue - viewModel.costs
                    + viewModel.interestExpense + viewModel.dividendsPaid
                incomeRow("Operating Income", value: operatingIncome, isHeader: true)

                Divider().padding(.vertical, 4)

                // Below the line
                incomeRow("Interest Expense", value: -viewModel.interestExpense, isHeader: false)
                incomeRow("Dividends Paid", value: -viewModel.dividendsPaid, isHeader: false)
                incomeDivider

                // Net
                let netIncome = viewModel.profit
                incomeRow("Net Income", value: netIncome, isHeader: true,
                          color: netIncome >= 0 ? .green : .red)

                // Rejection rate
                HStack {
                    Label("Rejection Rate", systemImage: "xmark.circle")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Spacer()
                    Text(String(format: "%.1f%%", viewModel.rejectionRate * 100))
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(viewModel.rejectionRate > 0.08 ? .red : viewModel.rejectionRate > 0.05 ? .orange : .green)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 6)

                // Inventory
                if viewModel.inventoryUnits > 0 {
                    HStack {
                        Label("Unsold Inventory", systemImage: "shippingbox")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Spacer()
                        Text("\(viewModel.inventoryUnits) units")
                            .font(.caption)
                            .fontWeight(.medium)
                    }
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                }
            }
            .padding(12)
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.gray.opacity(0.06))
            )
            .overlay(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(Color.gray.opacity(0.15), lineWidth: 1)
            )
        }
    }

    private func incomeRow(_ label: String, value: Double, isHeader: Bool, color: Color? = nil) -> some View {
        HStack {
            Text(label)
                .font(isHeader ? .subheadline : .caption)
                .fontWeight(isHeader ? .bold : .regular)
                .foregroundStyle(isHeader ? .primary : .secondary)
            Spacer()
            Text(viewModel.formatted(abs(value)))
                .font(isHeader ? .subheadline : .caption)
                .fontWeight(isHeader ? .bold : .medium)
                .monospacedDigit()
                .foregroundStyle(color ?? (value < 0 ? Color.red : .primary))
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 3)
    }

    private var incomeDivider: some View {
        Rectangle()
            .fill(Color.gray.opacity(0.3))
            .frame(height: 1)
            .padding(.horizontal, 12)
            .padding(.vertical, 2)
    }

    // MARK: - Key Metrics

    private var metricsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Key Metrics")
                .font(.headline)

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12)
            ], spacing: 12) {
                resultCard(title: "Total Revenue", value: viewModel.formattedRevenue,
                           icon: "arrow.up.right.circle.fill", color: .green,
                           trend: viewModel.revenue > 0 ? .up : .flat)
                resultCard(title: "Profit", value: viewModel.formattedProfit,
                           icon: "dollarsign.circle.fill", color: viewModel.profitColor,
                           trend: viewModel.isProfitable ? .up : .down)
                resultCard(title: "S/Q Rating", value: String(format: "%.1f", viewModel.sqRating) + "★",
                           icon: "star.fill", color: viewModel.sqRating >= 7 ? .green : .yellow,
                           trend: viewModel.sqRating >= 5 ? .up : .down)
            }

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12)
            ], spacing: 12) {
                resultCard(title: "Market Share", value: viewModel.formattedMarketShare,
                           icon: "chart.pie.fill", color: .purple,
                           trend: viewModel.marketShare > 0.2 ? .up : .flat)
                resultCard(title: "Cash Balance", value: viewModel.formattedCashAfter,
                           icon: "banknote.fill", color: .mint,
                           trend: .flat)
            }
        }
    }

    private func resultCard(title: String, value: String, icon: String, color: Color, trend: TrendDirection) -> some View {
        VStack(spacing: 8) {
            HStack {
                Image(systemName: icon)
                    .font(.title3)
                    .foregroundStyle(color)
                Spacer()
                HStack(spacing: 3) {
                    Image(systemName: trend.symbol)
                        .font(.caption2)
                        .fontWeight(.bold)
                }
                .foregroundStyle(trend.color)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(value)
                    .font(.title3)
                    .fontWeight(.bold)
                    .monospacedDigit()
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
        .scaleEffect(animateMetrics ? 1 : 0.9)
        .opacity(animateMetrics ? 1 : 0)
    }

    // MARK: - Competitors

    private var competitorsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "person.3.fill")
                    .foregroundStyle(.blue)
                Text("Competitive Intelligence")
                    .font(.headline)
            }

            if viewModel.competitorSummary.isEmpty {
                Text("No competitor data available.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(12)
            } else {
                ForEach(viewModel.competitorSummary) { comp in
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(comp.teamName)
                                .font(.subheadline)
                                .fontWeight(.semibold)
                            Text("S/Q: \(String(format: "%.1f", comp.sqRating))★ · Image: \(String(format: "%.0f", comp.imageRating))")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                        Spacer()
                        VStack(alignment: .trailing, spacing: 2) {
                            Text(comp.formattedRevenue)
                                .font(.subheadline)
                                .fontWeight(.medium)
                                .monospacedDigit()
                            Text(comp.formattedMarketShare + " share")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(10)
                    .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.06)))
                }
            }
        }
    }

    // MARK: - Explanations ("Why?")

    private var explanationsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "questionmark.circle.fill")
                    .foregroundStyle(.blue)
                Text("Why Did This Happen?")
                    .font(.headline)
            }

            if viewModel.explanations.isEmpty {
                Text("No detailed explanations available for this round.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(12)
            } else {
                VStack(spacing: 8) {
                    ForEach(viewModel.explanations) { explanation in
                        HStack(alignment: .top, spacing: 12) {
                            ZStack {
                                Circle()
                                    .fill(explanation.color.opacity(0.12))
                                    .frame(width: 32, height: 32)

                                Image(systemName: explanation.icon)
                                    .font(.caption)
                                    .fontWeight(.bold)
                                    .foregroundStyle(explanation.color)
                            }

                            VStack(alignment: .leading, spacing: 4) {
                                Text(explanation.category)
                                    .font(.subheadline)
                                    .fontWeight(.semibold)

                                Text(explanation.explanation)
                                    .font(.subheadline)
                                    .foregroundStyle(.secondary)
                            }

                            Spacer()
                        }
                        .padding(12)
                        .background(
                            RoundedRectangle(cornerRadius: 10, style: .continuous)
                                .fill(explanation.impact == .positive
                                      ? Color.green.opacity(0.04)
                                      : explanation.impact == .negative
                                      ? Color.red.opacity(0.04)
                                      : Color.secondary.opacity(0.04))
                        )
                    }
                }
            }
        }
    }

    // MARK: - Coaching Tips

    private var coachingSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Image(systemName: "brain.head.profile")
                    .foregroundStyle(.blue)
                Text("Coaching Tips")
                    .font(.headline)
            }

            if viewModel.coachingTips.isEmpty {
                Text("Submit decisions and complete a round to receive coaching tips.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .padding(16)
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(viewModel.coachingTips, id: \.self) { tip in
                        HStack(alignment: .top, spacing: 10) {
                            Image(systemName: "lightbulb.fill")
                                .font(.caption)
                                .foregroundStyle(.yellow)
                                .padding(.top, 2)

                            Text(tip)
                                .font(.subheadline)
                                .foregroundStyle(.secondary)
                        }
                    }
                }
                .padding(16)
                .background(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(.blue.opacity(0.04))
                )
            }
        }
    }

    // MARK: - Navigation Buttons

    private var navigationButtons: some View {
        HStack(spacing: 12) {
            Button {
                showCoach = true
            } label: {
                Label("Ask AI Coach", systemImage: "brain.head.profile")
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 4)
            }
            .buttonStyle(.bordered)
            .controlSize(.large)

            Button {
                dismiss()
            } label: {
                Text(roundNumber >= totalRounds ? "View Final Results" : "Next Round")
                    .fontWeight(.semibold)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
        }
    }

    // MARK: - Data Loading

    private func loadSampleData() {
        // In production, this would call:
        // viewModel.loadResults(from: session, for: teamId, round: roundNumber)
        viewModel.roundNumber = roundNumber
        viewModel.revenue = 52_300
        viewModel.wholesaleRevenue = 31_200
        viewModel.internetRevenue = 16_800
        viewModel.privateLabelRevenue = 4_300
        viewModel.wholesaleUnitsSold = 156
        viewModel.internetUnitsSold = 64
        viewModel.privateLabelUnitsSold = 25
        viewModel.sqRating = 6.8
        viewModel.cashAfter = 98_200
        viewModel.marketShare = 0.28
        viewModel.customerSatisfaction = 0.76
        viewModel.eps = 1.87
        viewModel.roe = 0.234
        viewModel.stockPrice = 38.50
        viewModel.imageRating = 62.0
        viewModel.creditRating = .a
        viewModel.investorScore = 72.0
        viewModel.epsScore = 15.0
        viewModel.roeScore = 16.0
        viewModel.stockPriceScore = 14.0
        viewModel.imageScore = 13.0
        viewModel.creditScore = 18.0

        viewModel.rejectionRate = 0.065
        viewModel.inventoryUnits = 12
        viewModel.workforceCosts = 3_200
        viewModel.storageCosts = 18
        viewModel.rebateCosts = 280
        viewModel.deliveryCosts = 0

        viewModel.explanations = [
            RoundResultsViewModel.RoundExplanation(
                category: "S/Q Rating",
                explanation: "Quality at 6.8★ is above average — driving solid wholesale and internet demand.",
                impact: .positive
            ),
            RoundResultsViewModel.RoundExplanation(
                category: "Internet Channel",
                explanation: "Internet sales at 32% of revenue — higher margin channel performing well.",
                impact: .positive
            ),
            RoundResultsViewModel.RoundExplanation(
                category: "Investor Score",
                explanation: "Score of 72/100 — good performance. EPS and ROE are strong contributors.",
                impact: .positive
            ),
        ]

        viewModel.coachingTips = [
            "Your S/Q rating at 6.8★ is good. Consider switching to superior materials to push past 8★ and justify premium pricing.",
            "Internet channel is performing well at 32% of revenue. You could grow it further with competitive internet pricing.",
            "Credit rating at A is solid. You have room to take on moderate debt for growth investments.",
        ]
    }
}
