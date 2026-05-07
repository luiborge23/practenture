// ProductDesignSectionView.swift
// BizSimAI
//
// Product Design decision inputs: materials quality, styling budget,
// models offered, TQM/Six Sigma, and best practices training.

import SwiftUI

struct ProductDesignSectionView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        DecisionInputSectionView(
            title: "Product Design (S/Q Rating)",
            icon: "star",
            description: "Your S/Q rating drives demand and image. Current: \(String(format: "%.1f", viewModel.currentSQRating))★"
        ) {
            SQRatingPreview(viewModel: viewModel)
            
            Picker("Materials Quality", selection: $viewModel.materialsQuality) {
                ForEach(MaterialsQuality.allCases) { quality in
                    Text(quality.displayName).tag(quality)
                }
            }
            .pickerStyle(.segmented)
            
            materialsDescription
            
            decisionSlider(
                title: "Styling & Features Budget",
                value: $viewModel.stylingBudget,
                range: DecisionInputViewModel.stylingRange,
                step: 500,
                format: "$%.0f",
                description: "Design investment per model — improves S/Q rating."
            )
            
            HStack {
                Text("Models Offered")
                    .font(.subheadline)
                Spacer()
                Stepper(
                    "\(viewModel.modelsOffered) models",
                    value: $viewModel.modelsOffered,
                    in: DecisionInputViewModel.modelsRange
                )
            }
            
            decisionSlider(
                title: "TQM / Six Sigma Investment",
                value: $viewModel.tqmInvestment,
                range: DecisionInputViewModel.tqmRange,
                step: 500,
                format: "$%.0f",
                description: "Quality programs — cumulative effect improves S/Q and reduces defects."
            )
            
            decisionSlider(
                title: "Best Practices Training",
                value: $viewModel.bestPracticesInvestment,
                range: DecisionInputViewModel.bestPracticesRange,
                step: 500,
                format: "$%.0f",
                description: "Workforce quality programs — reduces rejection rate, boosts S/Q."
            )
        }
    }
    
    private var materialsDescription: some View {
        Text(viewModel.materialsQuality == .superior
             ? "Superior materials: +2.0★ S/Q, 40% higher cost"
             : "Standard materials: baseline quality and cost")
            .font(.caption)
            .foregroundStyle(.secondary)
    }
}

// MARK: - S/Q Rating Preview Card

fileprivate struct SQRatingPreview: View {
    let viewModel: DecisionInputViewModel
    
    var body: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Estimated S/Q")
                    .font(.headline)
                Text("Rejection Rate: \(String(format: "%.1f", viewModel.estimatedRejectionRate * 100))%")
                    .font(.caption)
                    .foregroundStyle(estimatedRejectionColor)
            }
            Spacer()
            Text(String(format: "%.1f", viewModel.estimatedSQRating) + "★")
                .font(.title2)
                .fontWeight(.bold)
                .foregroundStyle(sqColor)
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.gray.opacity(0.1)))
    }
    
    private var estimatedRejectionColor: Color {
        viewModel.estimatedRejectionRate > 0.08 ? .red : .green
    }
    
    private var sqColor: Color {
        if viewModel.estimatedSQRating >= 7 { return .green }
        if viewModel.estimatedSQRating < 4 { return .red }
        return .primary
    }
}
