// DecisionInputCategoryPicker.swift
// Practenture
//
// Scrollable tab bar for selecting decision input categories.
// Used at the top of DecisionInputView.
//
// Professional dark theme with vibrant purple (#8b5cf6), clean cards,
// subtle shadows, and smooth animations inspired by practenture.com

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
                            Capsule().fill(isSelected ? PractentureTheme.primary : PractentureTheme.surface)
                        )
                        .foregroundStyle(isSelected ? .white : PractentureTheme.textPrimary)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 16)
        }
        .padding(.vertical, 10)
    }
}
