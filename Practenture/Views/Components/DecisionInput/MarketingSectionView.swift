// MarketingSectionView.swift
// Practenture
//
// Marketing & Distribution decision inputs: advertising, celebrity
// endorsement, retail outlets, mail-in rebate, delivery time,
// and free shipping threshold.

import SwiftUI

struct MarketingSectionView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        DecisionInputSectionView(
            title: "Marketing & Distribution",
            icon: "megaphone",
            description: "Build awareness and reach customers."
        ) {
            decisionSlider(
                title: "Advertising Budget",
                value: $viewModel.advertisingBudget,
                range: DecisionInputViewModel.advertisingRange,
                step: 500,
                format: "$%.0f",
                description: "Higher spend increases brand awareness and demand.",
                accentColor: .purple
            )
            
            Picker("Celebrity Endorsement", selection: $viewModel.celebrityEndorsement) {
                ForEach(CelebrityEndorsement.allCases) { level in
                    Text("\(level.displayName) (\(level.annualCost > 0 ? "$\(Int(level.annualCost))/yr" : "Free"))").tag(level)
                }
            }
            
            HStack {
                Text("Retail Outlets")
                    .font(.subheadline)
                Spacer()
                Stepper(
                    "\(viewModel.retailOutlets) outlets",
                    value: $viewModel.retailOutlets,
                    in: DecisionInputViewModel.outletsRange
                )
            }
            Text("More outlets = broader access. Cost: $50/outlet/round.")
                .font(.caption)
                .foregroundStyle(.secondary)
            
            Divider()
            
            DecisionInputSectionView(
                title: "Wholesale Demand Levers",
                icon: "tag.fill",
                description: "Additional ways to boost wholesale channel demand."
            ) {
                decisionSlider(
                    title: "Mail-in Rebate (per pair)",
                    value: $viewModel.mailInRebate,
                    range: DecisionInputViewModel.rebateRange,
                    step: 0.5,
                    format: "$%.1f",
                    description: "Consumer rebate on wholesale purchases. ~60% redemption rate.",
                    accentColor: .purple
                )
                
                Picker("Delivery Time", selection: $viewModel.deliveryTime) {
                    ForEach(DeliveryTime.allCases) { time in
                        Text(time.displayName).tag(time)
                    }
                }
                Text("Rush delivery boosts demand (+6%) but costs $2/unit extra.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            
            Divider()
            
            DecisionInputSectionView(
                title: "Internet Demand Levers",
                icon: "globe",
                description: "Boost online direct sales."
            ) {
                decisionSlider(
                    title: "Free Shipping Threshold",
                    value: $viewModel.freeShippingThreshold,
                    range: DecisionInputViewModel.freeShipRange,
                    step: 5,
                    format: "$%.0f",
                    description: "Lower threshold = more internet orders. $0 = free shipping on all.",
                    accentColor: .purple
                )
            }
        }
    }
}
