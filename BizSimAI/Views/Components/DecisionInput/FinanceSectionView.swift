// FinanceSectionView.swift
// BizSimAI
//
// Finance decision inputs: dividends, loans, share buybacks,
// and share issuance with financial summary.

import SwiftUI

struct FinanceSectionView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        DecisionInputSectionView(
            title: "Finance",
            icon: "banknote",
            description: "Manage dividends, debt, equity, and share buybacks."
        ) {
            decisionSlider(
                title: "Dividends Per Share",
                value: $viewModel.dividendsPerShare,
                range: DecisionInputViewModel.dividendRange,
                step: 0.10,
                format: "$%.2f",
                description: "Investors expect stable or growing dividends. Cutting hurts stock price.",
                accentColor: .orange
            )
            
            decisionSlider(
                title: "New Loan Amount",
                value: $viewModel.newLoanAmount,
                range: DecisionInputViewModel.loanRange,
                step: 1000,
                format: "$%.0f",
                description: "Borrow to fund growth. Interest rate depends on credit rating.",
                accentColor: .orange
            )
            
            Divider()
            
            DecisionInputSectionView(
                title: "Equity Management",
                icon: "chart.line.uptrend.xyaxis",
                description: "Buybacks boost EPS; issuance raises capital but dilutes."
            ) {
                HStack {
                    Text("Share Buyback")
                        .font(.subheadline)
                    Spacer()
                    Stepper(
                        "\(viewModel.sharesBuyback) shares",
                        value: $viewModel.sharesBuyback,
                        in: DecisionInputViewModel.buybackRange,
                        step: 50
                    )
                }
                Text("Buybacks reduce shares outstanding, boosting EPS and ROE.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                
                HStack {
                    Text("Share Issuance")
                        .font(.subheadline)
                    Spacer()
                    Stepper(
                        "\(viewModel.sharesIssued) shares",
                        value: $viewModel.sharesIssued,
                        in: DecisionInputViewModel.issuanceRange,
                        step: 50
                    )
                }
                Text("Issue new shares to raise capital. Dilutes EPS — use sparingly.")
                    .font(.caption)
                    .foregroundStyle(.orange)
                
                FinancialSummary(viewModel: viewModel)
            }
        }
    }
}

// MARK: - Financial Summary Card

fileprivate struct FinancialSummary: View {
    let viewModel: DecisionInputViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text("Current Debt")
                Spacer()
                Text(viewModel.formatted(viewModel.currentDebt))
            }
            HStack {
                Text("Shares Outstanding (After)")
                Spacer()
                Text("\(viewModel.currentShares - viewModel.sharesBuyback + viewModel.sharesIssued)")
            }
            if viewModel.sharesIssued > 0 {
                HStack {
                    Label("EPS Dilution Warning", systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                    Spacer()
                    Text("-\(String(format: "%.1f", Double(viewModel.sharesIssued) / Double(max(1, viewModel.currentShares)) * 100))%")
                        .foregroundStyle(.orange)
                }
            }
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .padding()
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.1)))
    }
}
