// SettingsView.swift
// BizSimAI
//
// X-2: App settings including optional Claude API key, theme preference,
// and about section.

import SwiftUI

struct SettingsView: View {
    @Environment(AppState.self) private var appState

    @State private var apiKey: String = ""
    @State private var showAPIKeyInfo = false
    @State private var apiKeyValid: Bool? = nil
    @State private var isValidating = false

    var body: some View {
        Form {
            aiSection
            appearanceSection
            aboutSection
            dangerZone
        }
        .formStyle(.grouped)
        .navigationTitle("Settings")
        #if os(macOS)
        .frame(minWidth: 450, minHeight: 400)
        #endif
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button {
                    appState.resetToLaunch()
                } label: {
                    Label("Back to Home", systemImage: "house")
                }
            }
        }
        .alert("Claude API Key", isPresented: $showAPIKeyInfo) {
            Button("OK") { }
        } message: {
            Text("The Claude API key enables advanced AI coaching with natural language understanding. Without it, the app uses rule-based coaching which works fully offline.\n\nGet your API key at console.anthropic.com")
        }
    }

    // MARK: - AI Section

    private var aiSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Label("Claude API Key", systemImage: "key.fill")
                        .font(.headline)

                    Spacer()

                    Button {
                        showAPIKeyInfo = true
                    } label: {
                        Image(systemName: "questionmark.circle")
                    }
                    .buttonStyle(.borderless)
                    .foregroundStyle(.secondary)
                }

                SecureField("sk-ant-...", text: $apiKey)
                    .textFieldStyle(.roundedBorder)
                    .fontDesign(.monospaced)
                    .onChange(of: apiKey) { _, _ in
                        apiKeyValid = nil
                    }

                HStack(spacing: 12) {
                    if let valid = apiKeyValid {
                        HStack(spacing: 4) {
                            Image(systemName: valid ? "checkmark.circle.fill" : "xmark.circle.fill")
                            Text(valid ? "API key valid" : "Invalid API key")
                        }
                        .font(.caption)
                        .foregroundStyle(valid ? .green : .red)
                    }

                    Spacer()

                    Button {
                        validateAPIKey()
                    } label: {
                        HStack(spacing: 4) {
                            if isValidating {
                                ProgressView()
                                    .controlSize(.mini)
                            }
                            Text("Validate")
                        }
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .disabled(apiKey.isEmpty || isValidating)
                }

                Text("Optional. Enables advanced AI coaching. Without a key, rule-based coaching is used (works offline).")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            // Coaching mode indicator
            HStack(spacing: 10) {
                Image(systemName: apiKeyValid == true ? "brain.head.profile" : "cpu")
                    .font(.title3)
                    .foregroundStyle(apiKeyValid == true ? .blue : .secondary)
                    .frame(width: 32)

                VStack(alignment: .leading, spacing: 2) {
                    Text(apiKeyValid == true ? "Claude AI Coaching" : "Rule-Based Coaching")
                        .font(.subheadline)
                        .fontWeight(.medium)

                    Text(apiKeyValid == true
                         ? "Natural language coaching powered by Claude"
                         : "Heuristic-based tips and analysis (offline capable)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Image(systemName: "checkmark.circle.fill")
                    .foregroundStyle(.green)
            }
            .padding(.vertical, 4)

        } header: {
            Label("AI Coaching", systemImage: "brain")
        }
    }

    // MARK: - Appearance Section

    private var appearanceSection: some View {
        @Bindable var appState = appState
        return Section {
            Picker("Theme", selection: $appState.themePreference) {
                ForEach(ThemePreference.allCases, id: \.self) { pref in
                    HStack {
                        Image(systemName: themeIcon(for: pref))
                        Text(pref.rawValue)
                    }
                    .tag(pref)
                }
            }
        } header: {
            Label("Appearance", systemImage: "paintbrush")
        }
    }

    // MARK: - About Section

    private var aboutSection: some View {
        Section {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 12) {
                    ZStack {
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(.blue.gradient)
                            .frame(width: 48, height: 48)

                        Image(systemName: "chart.line.uptrend.xyaxis")
                            .font(.title2)
                            .foregroundStyle(.white)
                    }

                    VStack(alignment: .leading, spacing: 2) {
                        Text("BizSim AI")
                            .font(.headline)
                        Text("Version 1.0.0 (MVP)")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }
                }

                Divider()

                aboutRow(label: "Platform", value: "macOS 14+ / iOS 17+")
                aboutRow(label: "Architecture", value: "SwiftUI + MVVM")
                aboutRow(label: "Engine", value: "Deterministic simulation")
                aboutRow(label: "AI", value: "Claude API + rule-based fallback")

                Divider()

                Text("BizSim AI is a business marketplace simulation designed for university courses. Professors create sessions, students run virtual companies making strategic decisions each round.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        } header: {
            Label("About", systemImage: "info.circle")
        }
    }

    // MARK: - Danger Zone

    private var dangerZone: some View {
        Section {
            Button(role: .destructive) {
                clearAllData()
            } label: {
                Label("Clear All Data", systemImage: "trash")
            }
        } header: {
            Label("Data", systemImage: "externaldrive")
        } footer: {
            Text("This will delete all sessions, teams, and history. This cannot be undone.")
        }
    }

    // MARK: - Helpers

    private func themeIcon(for pref: ThemePreference) -> String {
        switch pref {
        case .system: return "circle.lefthalf.filled"
        case .light: return "sun.max.fill"
        case .dark: return "moon.fill"
        }
    }

    private func aboutRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .font(.subheadline)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .font(.subheadline)
                .fontWeight(.medium)
        }
    }

    // MARK: - Actions

    private func validateAPIKey() {
        isValidating = true
        // Simulate validation
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            apiKeyValid = apiKey.hasPrefix("sk-ant-")
            isValidating = false
        }
    }

    private func clearAllData() {
        appState.clearActiveSession()
        appState.professorSessions.removeAll()
    }
}
