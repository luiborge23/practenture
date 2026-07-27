// DecisionSlider.swift
// Practenture
//
// Reusable slider for business decisions with label, formatted value, and color coding.

import SwiftUI

enum DecisionFormat {
    case currency
    case integer
    case percentage
}

struct DecisionSlider: View {
    let label: String
    @Binding var value: Double
    let range: ClosedRange<Double>
    var step: Double = 1.0
    var format: DecisionFormat = .currency
    var icon: String = "slider.horizontal.3"
    var description: String? = nil

    private var normalizedValue: Double {
        let span = range.upperBound - range.lowerBound
        guard span > 0 else { return 0 }
        return (value - range.lowerBound) / span
    }

    private var intensityColor: Color {
        if normalizedValue < 0.33 {
            return .green
        } else if normalizedValue < 0.66 {
            return .orange
        } else {
            return .red
        }
    }

    private var formattedValue: String {
        switch format {
        case .currency:
            return value.formatted(.currency(code: "USD").precision(.fractionLength(0)))
        case .integer:
            return "\(Int(value))"
        case .percentage:
            return "\(String(format: "%.0f", value))%"
        }
    }

    private var formattedMin: String {
        switch format {
        case .currency:
            return range.lowerBound.formatted(.currency(code: "USD").precision(.fractionLength(0)))
        case .integer:
            return "\(Int(range.lowerBound))"
        case .percentage:
            return "\(String(format: "%.0f", range.lowerBound))%"
        }
    }

    private var formattedMax: String {
        switch format {
        case .currency:
            return range.upperBound.formatted(.currency(code: "USD").precision(.fractionLength(0)))
        case .integer:
            return "\(Int(range.upperBound))"
        case .percentage:
            return "\(String(format: "%.0f", range.upperBound))%"
        }
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .firstTextBaseline) {
                Label(label, systemImage: icon)
                    .font(.headline)
                    .foregroundStyle(.primary)

                Spacer()

                Text(formattedValue)
                    .font(.title3)
                    .fontWeight(.semibold)
                    .foregroundStyle(intensityColor)
                    .contentTransition(.numericText(value: value))
                    .animation(.snappy, value: value)
            }

            if let description {
                Text(description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Slider(value: $value, in: range, step: step) {
                Text(label)
            } minimumValueLabel: {
                Text(formattedMin)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            } maximumValueLabel: {
                Text(formattedMax)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }
            .tint(intensityColor)

            // Intensity indicator bar
            GeometryReader { geometry in
                ZStack(alignment: .leading) {
                    Capsule()
                        .fill(Color.secondary.opacity(0.15))
                        .frame(height: 4)

                    Capsule()
                        .fill(intensityColor.gradient)
                        .frame(width: max(4, geometry.size.width * normalizedValue), height: 4)
                }
            }
            .frame(height: 4)
        }
        .padding(.vertical, 4)
    }
}
