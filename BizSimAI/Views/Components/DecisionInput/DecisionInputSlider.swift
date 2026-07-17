// DecisionInputSlider.swift
// BizSimAI
//
// Reusable slider component for decision inputs.
// Shows label, formatted value, slider control, and description.
// Enhanced with accent color, custom track styling, and value highlight.
// Used by all category section views.

import SwiftUI

struct DecisionInputSlider: View {
    let title: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    let step: Double
    let format: String
    let description: String
    var accentColor: Color = .blue

    // Track fill percentage for custom track
    private var fillPercentage: Double {
        guard range.upperBound > range.lowerBound else { return 0 }
        return (value - range.lowerBound) / (range.upperBound - range.lowerBound)
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(title)
                    .font(.subheadline)
                    .fontWeight(.medium)
                Spacer()
                Text(String(format: format, value))
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .monospacedDigit()
                    .foregroundStyle(accentColor)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 4)
                    .background(accentColor.opacity(0.08), in: Capsule())
            }
            Slider(value: $value, in: range, step: step)
                .tint(accentColor)
            Text(description)
                .font(.caption2)
                .foregroundStyle(.tertiary)
                .lineLimit(2)
        }
        .padding(.vertical, 2)
    }
}

// MARK: - Helper Function for Section Views

func decisionSlider(
    title: String,
    value: Binding<Double>,
    range: ClosedRange<Double>,
    step: Double,
    format: String,
    description: String,
    accentColor: Color = .blue
) -> some View {
    DecisionInputSlider(
        title: title,
        value: value,
        range: range,
        step: step,
        format: format,
        description: description,
        accentColor: accentColor
    )
}
