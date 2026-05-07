// DecisionInputSectionView.swift
// BizSimAI
//
// Generic section wrapper for decision input categories.
// Provides consistent header styling with icon and description.

import SwiftUI

struct DecisionInputSectionView<Content: View>: View {
    let title: String
    let icon: String
    let description: String
    @ViewBuilder let content: () -> Content
    
    var body: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Label(title, systemImage: icon)
                    .font(.headline)
                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            content()
        }
    }
}
