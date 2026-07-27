// ProductionSectionView.swift
// Practenture
//
// Production decision inputs: quantity, overtime, and capacity
// management with net production preview.

import SwiftUI

struct ProductionSectionView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        DecisionInputSectionView(
            title: "Production",
            icon: "hammer",
            description: "Plant capacity: \(viewModel.maxProductionCapacity) units."
        ) {
            HStack {
                Text("Production Quantity")
                    .font(.subheadline)
                Spacer()
                Stepper(
                    "\(viewModel.productionQuantity) units",
                    value: $viewModel.productionQuantity,
                    in: DecisionInputViewModel.productionRange,
                    step: 10
                )
            }
            
            decisionSlider(
                title: "Overtime",
                value: $viewModel.overtimePercent,
                range: DecisionInputViewModel.overtimeRange,
                step: 1,
                format: "%.0f%%",
                description: "Up to 20% above capacity. 50% premium on overtime units.",
                accentColor: .green
            )
            
            ProductionPreview(viewModel: viewModel)
        }
    }
}

// MARK: - Production Preview

fileprivate struct ProductionPreview: View {
    let viewModel: DecisionInputViewModel
    
    private var effectiveCapacity: Int {
        viewModel.maxProductionCapacity + Int(Double(viewModel.maxProductionCapacity) * viewModel.overtimePercent / 100)
    }
    
    private var netProduction: Int {
        let producible = min(viewModel.productionQuantity, effectiveCapacity)
        return producible - Int(Double(producible) * viewModel.estimatedRejectionRate)
    }
    
    private var rejectedUnits: Int {
        min(viewModel.productionQuantity, effectiveCapacity) - netProduction
    }
    
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Effective Capacity")
                Spacer()
                Text("\(effectiveCapacity) units")
                    .fontWeight(.medium)
            }
            HStack {
                Text("Est. Rejected Units")
                Spacer()
                Text("\(rejectedUnits) units (\(String(format: "%.1f", viewModel.estimatedRejectionRate * 100))%)")
                    .fontWeight(.medium)
                    .foregroundStyle(viewModel.estimatedRejectionRate > 0.08 ? .red : .secondary)
            }
            HStack {
                Text("Net Usable Production")
                Spacer()
                Text("\(netProduction) units")
                    .fontWeight(.semibold)
                    .foregroundStyle(.green)
            }
        }
        .font(.caption)
        .padding()
        .background(RoundedRectangle(cornerRadius: 8).fill(Color.gray.opacity(0.1)))
    }
}
