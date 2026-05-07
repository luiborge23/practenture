// DecisionInputSlider.swift
// BizSimAI
//
// Reusable slider component for decision inputs.
// Shows label, formatted value, slider control, and description.
// Used by all category section views.

import SwiftUI

struct DecisionInputSlider: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    let format: String
    let description: String
    
    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(title)
                    .font(.subheadline)
                Spacer()
                Text(String(format: format, value))
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .monospacedDigit()
            }
            Slider(value: $value, in: range, step: step)
            Text(description)
                .font(.caption2)
                .foregroundStyle(.tertiary)
        }
    }
}

// MARK: - Helper Function for Section Views

func decisionSlider(
    title: String,
    value: Binding<Double>,
    range: ClosedRange<Double>,
    step: Double,
    format: String,
    description: String
) -> some View {
    DecisionInputSlider(
        title: title,
        value: value,
        range: range,
        step: step,
        format: format,
        description: description
    )
}
