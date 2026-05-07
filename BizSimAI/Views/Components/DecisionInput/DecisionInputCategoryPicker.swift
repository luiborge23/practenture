// DecisionInputCategoryPicker.swift
// BizSimAI
//
// Scrollable tab bar for selecting decision input categories.
// Used at the top of DecisionInputView.

import SwiftUI

struct DecisionInputCategoryPicker: View {
    @Binding var selectedCategory: DecisionInputViewModel.DecisionCategory
    let categories: [DecisionInputViewModel.DecisionCategory]
    
    var body: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                ForEach(categories, id: \.self) { category in
                    let isSelected = selectedCategory == category
                    Button {
                        selectedCategory = category
                    } label: {
                        VStack(spacing: 2) {
                            Text(category.icon)
                                .font(.title3)
                            Text(category.rawValue)
                                .font(.caption)
                                .fontWeight(isSelected ? .bold : .regular)
                        }
                        .padding(.horizontal, 12)
                        .padding(.vertical, 8)
                        .background(
                            Capsule().fill(isSelected ? Color.accentColor : Color.gray.opacity(0.15))
                        )
                        .foregroundStyle(isSelected ? .white : .primary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
        }
        .padding(.vertical, 10)
    }
}
