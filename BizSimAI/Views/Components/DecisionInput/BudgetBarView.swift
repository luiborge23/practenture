// BudgetBarView.swift
// BizSimAI
//
// Budget summary bar showing total spend, remaining budget,
// progress indicator, and warnings.

import SwiftUI

struct BudgetBarView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        VStack(spacing: 8) {
            HStack {
                Text("Total Spend: \(viewModel.formattedTotalSpend)")
                    .font(.subheadline)
                    .fontWeight(.medium)
                Spacer()
                Text("Remaining: \(viewModel.formattedRemainingBudget)")
                    .font(.subheadline)
                    .foregroundStyle(viewModel.isOverBudget ? .red : .green)
                    .fontWeight(.medium)
            }
            
            ProgressView(value: min(viewModel.budgetUtilization, 1.0))
                .tint(viewModel.isOverBudget ? .red : .blue)
            
            if !viewModel.warnings.isEmpty {
                ForEach(viewModel.warnings, id: \.self) { warning in
                    HStack {
                        Image(systemName: "exclamationmark.triangle.fill")
                            .foregroundStyle(.orange)
                        Text(warning)
                            .font(.caption)
                    }
                }
            }
        }
        .padding(16)
        .background(Color.gray.opacity(0.05))
    }
}
