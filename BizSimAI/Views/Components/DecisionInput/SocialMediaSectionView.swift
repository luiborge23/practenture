// SocialMediaSectionView.swift
// BizSimAI
//
// Social Media Marketing decision inputs: TikTok, Instagram, YouTube
// budgets, and influencer partnership tiers.

import SwiftUI

struct SocialMediaSectionView: View {
    @State var viewModel: DecisionInputViewModel
    
    init(viewModel: DecisionInputViewModel) {
        _viewModel = State(initialValue: viewModel)
    }
    
    var body: some View {
        DecisionInputSectionView(
            title: "Social Media Advertising",
            icon: "megaphone.fill",
            description: "Leverage TikTok, Instagram, and YouTube to boost awareness and demand."
        ) {
            decisionSlider(
                title: "TikTok Budget",
                value: $viewModel.tiktokBudget,
                range: DecisionInputViewModel.socialMediaRange,
                step: 500,
                format: "$%.0f",
                description: "Viral reach, younger demographic. Best for awareness and internet sales."
            )
            
            decisionSlider(
                title: "Instagram Budget",
                value: $viewModel.instagramBudget,
                range: DecisionInputViewModel.socialMediaRange,
                step: 500,
                format: "$%.0f",
                description: "Brand image & lifestyle positioning. Strongest impact on Image Rating."
            )
            
            decisionSlider(
                title: "YouTube Budget",
                value: $viewModel.youtubeBudget,
                range: DecisionInputViewModel.socialMediaRange,
                step: 500,
                format: "$%.0f",
                description: "Trust & credibility. Builds long-term brand perception and product awareness."
            )
            
            Divider()
            
            DecisionInputSectionView(
                title: "Influencer Partnerships",
                icon: "star.circle.fill",
                description: "Higher tiers reach more people but have lower engagement rates."
            ) {
                Picker("Influencer Tier", selection: $viewModel.influencerTier) {
                    ForEach(InfluencerTier.allCases) { tier in
                        Text("\(tier.displayName)\(tier.costPerInfluencer > 0 ? " — $\(Int(tier.costPerInfluencer))/ea" : "")").tag(tier)
                    }
                }
                
                SocialMediaImpactPreview(viewModel: viewModel)
            }
            
            Text("Social media spending has diminishing returns per platform. Diversify across platforms for best results.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}

// MARK: - Social Media Impact Preview

fileprivate struct SocialMediaImpactPreview: View {
    let viewModel: DecisionInputViewModel
    
    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Social Media Impact Preview")
                .font(.subheadline)
                .fontWeight(.semibold)
            
            HStack {
                Label("Platform Spend", systemImage: "dollarsign.circle")
                Spacer()
                Text(viewModel.formatted(viewModel.tiktokBudget + viewModel.instagramBudget + viewModel.youtubeBudget))
                    .fontWeight(.medium)
            }
            .font(.caption)
            
            HStack {
                Label("Total Social Media Cost", systemImage: "creditcard")
                Spacer()
                Text(viewModel.formatted(viewModel.socialMediaCost))
                    .fontWeight(.medium)
                    .foregroundStyle(viewModel.socialMediaCost > 10000 ? .orange : .primary)
            }
            .font(.caption)
            
            if viewModel.influencerTier != .none {
                HStack {
                    Label("Engagement Rate", systemImage: "hand.thumbsup")
                    Spacer()
                    Text(String(format: "%.1f%%", viewModel.influencerTier.engagementRate * 100))
                        .fontWeight(.medium)
                        .foregroundStyle(.green)
                }
                .font(.caption)
                
                HStack {
                    Label("Image Boost", systemImage: "sparkles")
                    Spacer()
                    Text("+\(Int(viewModel.influencerTier.imageBoost)) pts")
                        .fontWeight(.medium)
                        .foregroundStyle(.blue)
                }
                .font(.caption)
            }
        }
        .padding()
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.purple.opacity(0.05)))
    }
}
