// CSRSectionView.swift
// BizSimAI
//
// Corporate Citizenship (CSR) decision input with impact note.

import SwiftUI

struct CSRSectionView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        DecisionInputSectionView(
            title: "Corporate Citizenship",
            icon: "leaf",
            description: "CSR spending boosts Image Rating (one of 5 investor metrics)."
        ) {
            decisionSlider(
                title: "CSR Investment",
                value: $viewModel.csrInvestment,
                range: DecisionInputViewModel.csrRange,
                step: 500,
                format: "$%.0f",
                description: "Ethics, sustainability, and community programs."
            )
            
            Text("CSR has diminishing returns — first dollars have the most impact on Image Rating.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
