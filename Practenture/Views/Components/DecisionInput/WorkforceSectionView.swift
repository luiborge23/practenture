// WorkforceSectionView.swift
// Practenture
//
// Workforce Compensation decision inputs: base wage, incentive pay,
// and training hours with impact preview.

import SwiftUI

struct WorkforceSectionView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        DecisionInputSectionView(
            title: "Workforce Compensation",
            icon: "person.text.rectangle",
            description: "Better pay and training improve productivity, quality, and reduce defects."
        ) {
            decisionSlider(
                title: "Base Wage (Annual)",
                value: $viewModel.baseWage,
                range: DecisionInputViewModel.baseWageRange,
                step: 1000,
                format: "$%.0f",
                description: "Industry avg: $25,000. Higher wages attract better workers.",
                accentColor: .blue
            )
            
            decisionSlider(
                title: "Incentive Pay (per pair)",
                value: $viewModel.incentivePay,
                range: DecisionInputViewModel.incentivePayRange,
                step: 0.10,
                format: "$%.2f",
                description: "Per-pair bonus motivates output and reduces defects.",
                accentColor: .blue
            )
            
            decisionSlider(
                title: "Training Hours (per worker)",
                value: $viewModel.trainingHours,
                range: DecisionInputViewModel.trainingHoursRange,
                step: 5,
                format: "%.0f hrs",
                description: "More training = higher quality, lower rejection rate, better S/Q.",
                accentColor: .blue
            )
            
            WorkforceImpactPreview(viewModel: viewModel)
        }
    }
}

// MARK: - Workforce Impact Preview

fileprivate struct WorkforceImpactPreview: View {
    let viewModel: DecisionInputViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Workforce Impact Preview")
                .font(.subheadline)
                .fontWeight(.semibold)
            
            HStack {
                Label("Est. Rejection Rate", systemImage: "xmark.circle")
                Spacer()
                Text(String(format: "%.1f%%", viewModel.estimatedRejectionRate * 100))
                    .fontWeight(.medium)
                    .foregroundStyle(rejectionRateColor)
            }
            .font(.caption)
            
            HStack {
                Label("Workforce Cost", systemImage: "dollarsign.circle")
                Spacer()
                Text(viewModel.formatted(viewModel.workforceCost))
                    .fontWeight(.medium)
            }
            .font(.caption)
            
            HStack {
                Label("S/Q Boost from Training", systemImage: "star.circle")
                Spacer()
                Text(String(format: "+%.2f★", min(0.5, viewModel.trainingHours / 80.0)))
                    .fontWeight(.medium)
                    .foregroundStyle(.green)
            }
            .font(.caption)
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.blue.opacity(0.05)))
    }
    
    private var rejectionRateColor: Color {
        let rate = viewModel.estimatedRejectionRate
        if rate > 0.08 { return .red }
        if rate > 0.05 { return .orange }
        return .green
    }
}
