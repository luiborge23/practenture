// PricingSectionView.swift
// Practenture
//
// Pricing & Sales decision inputs: wholesale price, internet price,
// private label bidding, and Amazon pricing.

import SwiftUI

struct PricingSectionView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        DecisionInputSectionView(
            title: "Pricing & Sales",
            icon: "tag",
            description: "Set prices for each sales channel."
        ) {
            decisionSlider(
                title: "Wholesale Price",
                value: $viewModel.wholesalePrice,
                range: DecisionInputViewModel.wholesalePriceRange,
                step: 1,
                format: "$%.0f",
                description: "Price charged to retail chains (primary channel).",
                accentColor: .blue
            )
            
            decisionSlider(
                title: "Internet Price",
                value: $viewModel.internetPrice,
                range: DecisionInputViewModel.internetPriceRange,
                step: 1,
                format: "$%.0f",
                description: "Direct-to-consumer online price (higher margins).",
                accentColor: .purple
            )
            
            Divider()
            
            DecisionInputSectionView(
                title: "Private Label",
                icon: "shippingbox",
                description: "Bid for unbranded contract manufacturing."
            ) {
                decisionSlider(
                    title: "Bid Price",
                    value: $viewModel.privateLabelBidPrice,
                    range: DecisionInputViewModel.privateLabelPriceRange,
                    step: 1,
                    format: "$%.0f",
                    description: "Lowest bid wins. Fills excess capacity.",
                    accentColor: .green
                )
                
                HStack {
                    Text("Max Units to Supply")
                        .font(.subheadline)
                    Spacer()
                    Stepper(
                        "\(viewModel.privateLabelMaxUnits)",
                        value: $viewModel.privateLabelMaxUnits,
                        in: 0...300,
                        step: 10
                    )
                }
            }
            
            Divider()
            
            DecisionInputSectionView(
                title: "Amazon Pricing",
                icon: "shippingbox.fill",
                description: "Set your Amazon listing price and ad spend."
            ) {
                decisionSlider(
                    title: "Amazon Price",
                    value: $viewModel.amazonPrice,
                    range: DecisionInputViewModel.amazonPriceRange,
                    step: 1,
                    format: "$%.0f",
                    description: "Listing price on Amazon. 15% referral fee applies.",
                    accentColor: .orange
                )
                
                Picker("Fulfillment Method", selection: $viewModel.fulfillmentMethod) {
                    ForEach(FulfillmentMethod.allCases) { method in
                        Text(method.displayName).tag(method)
                    }
                }
                
                FBAInfoCard()
                
                decisionSlider(
                    title: "Amazon PPC Ad Budget",
                    value: $viewModel.amazonAdBudget,
                    range: DecisionInputViewModel.amazonAdRange,
                    step: 500,
                    format: "$%.0f",
                    description: "Sponsored product ads. Boosts visibility in search and Buy Box.",
                    accentColor: .orange
                )
                
                AmazonEconomicsPreview(viewModel: viewModel)
            }
        }
    }
}

// MARK: - FBA Info Card

fileprivate struct FBAInfoCard: View {
    var body: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 4) {
                    Image(systemName: "shippingbox.fill")
                        .font(.caption)
                    Text("FBA")
                        .font(.caption)
                        .fontWeight(.bold)
                }
                .foregroundStyle(.orange)
                Text("$4.50/unit, Prime badge, higher Buy Box win rate")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            Spacer()
            VStack(alignment: .leading, spacing: 3) {
                HStack(spacing: 4) {
                    Image(systemName: "shippingbox")
                        .font(.caption)
                    Text("FBM")
                        .font(.caption)
                        .fontWeight(.bold)
                }
                .foregroundStyle(.blue)
                Text("$1.50/unit, you handle shipping, lower visibility")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(12)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(
                    LinearGradient(
                        colors: [Color.gray.opacity(0.06), Color.clear],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
        )
    }
}

// MARK: - Amazon Economics Preview

fileprivate struct AmazonEconomicsPreview: View {
    let viewModel: DecisionInputViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Amazon Economics Preview")
                .font(.subheadline)
                .fontWeight(.semibold)
            
            HStack {
                Label("List Price", systemImage: "tag")
                Spacer()
                Text(String(format: "$%.0f", viewModel.amazonPrice))
                    .fontWeight(.medium)
            }
            .font(.caption)
            
            HStack {
                Label("Referral Fee (15%)", systemImage: "minus.circle")
                Spacer()
                Text(String(format: "-$%.2f", viewModel.amazonPrice * 0.15))
                    .fontWeight(.medium)
                    .foregroundStyle(.red)
            }
            .font(.caption)
            
            HStack {
                Label("Fulfillment Fee", systemImage: "minus.circle")
                Spacer()
                Text(String(format: "-$%.2f", viewModel.fulfillmentMethod.feePerUnit))
                    .fontWeight(.medium)
                    .foregroundStyle(.red)
            }
            .font(.caption)
            
            Divider()
            
            HStack {
                Label("Net per Unit", systemImage: "equal.circle")
                Spacer()
                let net = viewModel.amazonPrice * 0.85 - viewModel.fulfillmentMethod.feePerUnit
                Text(String(format: "$%.2f", net))
                    .fontWeight(.bold)
                    .foregroundStyle(net > 0 ? .green : .red)
            }
            .font(.caption)
            
            if viewModel.fulfillmentMethod == .fba {
                HStack {
                    Label("Prime Badge", systemImage: "checkmark.seal.fill")
                        .foregroundStyle(.blue)
                    Text("+25% Buy Box boost, +15% customer trust")
                        .font(.caption2)
                        .foregroundStyle(.blue)
                }
            }
        }
        .padding()
        .background(
            RoundedRectangle(cornerRadius: 12)
                .fill(
                    LinearGradient(
                        colors: [Color.orange.opacity(0.06), Color.orange.opacity(0.02)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .strokeBorder(Color.orange.opacity(0.12), lineWidth: 0.5)
        )
    }
}
