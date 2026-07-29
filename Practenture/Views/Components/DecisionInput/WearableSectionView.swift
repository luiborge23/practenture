// WearableSectionView.swift
// Practenture
//
// Wearable Technology decision inputs: battery life, sensor accuracy,
// privacy compliance, and component sourcing.

import SwiftUI

struct WearableSectionView: View {
    @State var viewModel: DecisionInputViewModel

    var body: some View {
        Section {
            // Battery Life
            LabeledContent("Battery Life") {
                HStack {
                    Text("\(Int(viewModel.batteryLife))h")
                        .monospacedDigit()
                    Spacer()
                    Text("12h")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Slider(
                        value: Binding(
                            get: { Double(viewModel.batteryLife) },
                            set: { viewModel.batteryLife = Int($0) }
                        ),
                        in: 12...48,
                        step: 1
                    )
                    .frame(maxWidth: 160)
                    Text("48h")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))

            // Sensor Accuracy
            LabeledContent("Sensor Accuracy") {
                HStack {
                    Text(String(format: "%.1f", viewModel.sensorAccuracy))
                        .monospacedDigit()
                    Spacer()
                    Text("0")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Slider(
                        value: $viewModel.sensorAccuracy,
                        in: 0...10,
                        step: 0.1
                    )
                    .frame(maxWidth: 160)
                    Text("10")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))

            // Privacy Compliance
            LabeledContent("Privacy Compliance") {
                HStack {
                    Text(String(format: "%d", viewModel.privacyCompliance))
                        .monospacedDigit()
                    Spacer()
                    Text("0")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Slider(
                        value: Binding(
                            get: { Double(viewModel.privacyCompliance) },
                            set: { viewModel.privacyCompliance = Int($0) }
                        ),
                        in: 0...10000,
                        step: 100
                    )
                    .frame(maxWidth: 160)
                    Text("10,000")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
            }
            .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))

            // Component Sourcing
            LabeledContent("Component Sourcing") {
                Picker("Sourcing", selection: $viewModel.componentSourcing) {
                    ForEach(ComponentSourcing.allCases) { sourcing in
                        Text(sourcing.displayName)
                            .tag(sourcing.rawValue)
                    }
                }
                .pickerStyle(.menu)
                .frame(maxWidth: .infinity)
            }
            .listRowInsets(EdgeInsets(top: 8, leading: 16, bottom: 8, trailing: 16))
        } header: {
            Label("Wearable Technology", systemImage: "watch")
                .font(.headline)
        } footer: {
            Text("Configure wearable-specific features. Battery life affects rejection rates, sensor accuracy influences quality metrics, privacy compliance impacts image ratings, and component sourcing affects production costs.")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
    }
}
