// CreateSessionView.swift
// Practenture
//
// P-2: Form for creating a new simulation session with configuration options.
// Uses CreateSessionViewModel for validation and session creation.
// Supports both cloud backend and local-only modes.

import SwiftUI

struct CreateSessionView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AppState.self) private var appState

    @State private var viewModel = CreateSessionViewModel()
    @State private var showingSessionCreated: Bool = false

    var body: some View {
        ZStack(alignment: .bottom) {
            NavigationStack {
                Form {
                    scenarioLibrarySection
                    templateSection
                    backendToggleSection
                    basicInfoSection
                    classSection
                    enrollmentSection
                    timingSection
                    economySection
                    competitionSection
                    scoringSection
                    validationSection
                    summarySection
                }
                .formStyle(.grouped)
                .onChange(of: viewModel.selectedTemplate) { _, newTemplate in
                    viewModel.applyTemplate(newTemplate)
                }
                .navigationTitle("Create Session")
                #if os(macOS)
                .frame(minWidth: 500, minHeight: 600)
                #endif
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("Cancel") {
                            dismiss()
                        }
                    }

                    ToolbarItem(placement: .confirmationAction) {
                        Button {
                            Task { await createSession() }
                        } label: {
                            Label("Create Session", systemImage: "plus.circle.fill")
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!viewModel.isValid || viewModel.isCreating)
                    }
                }
            }

            // Floating "Create Session" button at the bottom
            if viewModel.isValid && !viewModel.isCreating {
                Button {
                    Task { await createSession() }
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "checkmark.circle.fill")
                        Text("Create Session")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 12)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .padding(.horizontal)
                .padding(.bottom, 16)
                .background(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(Color.blue)
                        .shadow(color: .black.opacity(0.15), radius: 8, y: 4)
                )
            }
        }
        .alert("Session Created", isPresented: $showingSessionCreated) {
            Button("Copy Code") {
                if let code = viewModel.backendSessionCode {
                    UIPasteboard.general.string = code
                }
            }
            Button("Open Session") {
                dismiss()
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            if let code = viewModel.backendSessionCode {
                VStack(spacing: 8) {
                    Text("Session code: \(code)")
                        .font(.title2.monospaced())
                        .fontWeight(.bold)

                    Text("Share this code with your students so they can join the session.")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    Text("\(viewModel.backendTeamCount) team(s) already registered")
                        .font(.caption)
                        .foregroundStyle(.green)
                }
                .frame(maxWidth: .infinity)
                .multilineTextAlignment(.center)
            } else {
                Text("Session created in local mode. Students can use a demo session instead.")
            }
        }
    }

    // MARK: - Scenario Library

    private var scenarioLibrarySection: some View {
        Section {
            ForEach(ScenarioLibrary.all) { scenario in
                Button {
                    viewModel.selectScenario(scenario)
                } label: {
                    HStack(alignment: .top, spacing: 14) {
                        Image(systemName: scenario.systemImage)
                            .font(.title2)
                            .frame(width: 32)
                            .foregroundStyle(scenario.isAvailable ? Color.accentColor : Color.secondary)

                        VStack(alignment: .leading, spacing: 5) {
                            Text(scenario.displayName)
                                .font(.headline)
                                .foregroundStyle(.primary)

                            Text(scenario.summary)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .fixedSize(horizontal: false, vertical: true)

                            Label(
                                scenario.availabilityLabel,
                                systemImage: scenario.isAvailable ? "checkmark.circle.fill" : "lock.fill"
                            )
                            .font(.caption.weight(.semibold))
                            .foregroundStyle(scenario.isAvailable ? Color.green : Color.orange)
                        }

                        Spacer(minLength: 8)

                        if scenario.identity == viewModel.selectedScenario {
                            Image(systemName: "checkmark.circle.fill")
                                .foregroundStyle(Color.accentColor)
                                .accessibilityLabel("Selected")
                        }
                    }
                    .padding(.vertical, 6)
                }
                .buttonStyle(.plain)
                .disabled(!scenario.isAvailable)
                .accessibilityIdentifier("scenario.\(scenario.identity.id)")
                .accessibilityValue(scenario.availabilityLabel)
            }
        } header: {
            Label("Scenario Library", systemImage: "books.vertical")
        } footer: {
            Text("Only calibrated scenarios can be selected and started.")
        }
    }

    // MARK: - Cloud Backend Toggle

    private var backendToggleSection: some View {
        Section {
            Toggle("Use Cloud Backend", isOn: $viewModel.useBackend)

            if viewModel.useBackend {
                Text("Students join via a unique session code connected to the FastAPI server. Disable for local-only demo mode.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                Text("Running in local mode. No internet required. Best for demo and testing.")
                    .font(.caption)
                    .foregroundStyle(.orange)
            }
        } header: {
            Label("Connection", systemImage: "network")
        }
    }

    // MARK: - Template

    private var templateSection: some View {
        Section {
            Picker("Session Template", selection: $viewModel.selectedTemplate) {
                ForEach(SessionTemplate.allCases) { template in
                    Text(template.displayName).tag(template)
                }
            }

            Text(viewModel.selectedTemplate.description)
                .font(.caption)
                .foregroundStyle(.secondary)

            Toggle("Practice Mode (non-graded)", isOn: $viewModel.isPracticeMode)
        } header: {
            Label("Quick Setup", systemImage: "wand.and.stars")
        } footer: {
            Text("Templates pre-fill settings. Choose Custom to configure everything manually.")
        }
    }

    // MARK: - Basic Info

    private var basicInfoSection: some View {
        Section {
            TextField("Session Name", text: $viewModel.sessionName, prompt: Text("e.g., MBA 510 - Spring 2026"))
                .textFieldStyle(.roundedBorder)

            Stepper("Total Rounds: \(viewModel.totalRounds)", value: $viewModel.totalRounds, in: CreateSessionViewModel.roundsRange)

        } header: {
            Label("Basic Info", systemImage: "info.circle")
        }
    }

    // MARK: - Course Info

    private var classSection: some View {
        Section {
            TextField("Course Code", text: $viewModel.courseCode, prompt: Text("e.g., MKT 301"))
                .textFieldStyle(.roundedBorder)

            TextField("Semester", text: $viewModel.semester, prompt: Text("e.g., Spring 2026"))
                .textFieldStyle(.roundedBorder)
        } header: {
            Label("Course Info (Optional)", systemImage: "book.closed")
        } footer: {
            Text("Helps organize sessions across semesters.")
        }
    }

    // MARK: - Enrollment

    private var enrollmentSection: some View {
        Section {
            Stepper("Max Teams: \(viewModel.maxHumanTeams)", value: $viewModel.maxHumanTeams, in: CreateSessionViewModel.maxTeamsRange)

            Stepper("Students per Team: \(viewModel.teamSize)", value: $viewModel.teamSize, in: CreateSessionViewModel.teamSizeRange)

            HStack {
                Text("Total Student Capacity")
                    .foregroundStyle(.secondary)
                Spacer()
                Text("\(viewModel.maxHumanTeams * viewModel.teamSize)")
                    .fontWeight(.semibold)
            }
            .font(.subheadline)
        } header: {
            Label("Teams & Enrollment", systemImage: "person.crop.circle.badge.checkmark")
        } footer: {
            Text("Students join using the session code. Teams can be auto-assigned or manually configured.")
        }
    }

    // MARK: - Timing

    private var timingSection: some View {
        Section {
            Picker("Round Pacing", selection: $viewModel.roundPacingMode) {
                ForEach(RoundPacingMode.allCases) { mode in
                    Text(mode.displayName).tag(mode)
                }
            }

            Text(viewModel.roundPacingMode.description)
                .font(.caption)
                .foregroundStyle(.secondary)

            if viewModel.roundPacingMode == .timed {
                Stepper("Deadline: \(viewModel.roundDeadlineHours) hours per round",
                        value: $viewModel.roundDeadlineHours, in: CreateSessionViewModel.deadlineHoursRange)

                Picker("Late Submission Policy", selection: $viewModel.latePolicy) {
                    ForEach(LateSubmissionPolicy.allCases) { policy in
                        Text(policy.displayName).tag(policy)
                    }
                }
            }

            Stepper("Session Expires: \(viewModel.sessionExpiryDays) days",
                    value: $viewModel.sessionExpiryDays, in: CreateSessionViewModel.expiryDaysRange)
        } header: {
            Label("Timing & Deadlines", systemImage: "clock")
        } footer: {
            Text("Timed rounds auto-advance after the deadline. Manual mode gives you full control.")
        }
    }

    // MARK: - Economy

    private var economySection: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text("Starting Cash")
                    Spacer()
                    Text(viewModel.formattedStartingCash)
                        .fontWeight(.semibold)
                        .foregroundStyle(.green)
                        .monospacedDigit()
                }

                Slider(
                    value: $viewModel.startingCash,
                    in: CreateSessionViewModel.cashRange,
                    step: CreateSessionViewModel.cashStep
                ) {
                    Text("Starting Cash")
                } minimumValueLabel: {
                    Text("$50K")
                        .font(.caption2)
                } maximumValueLabel: {
                    Text("$500K")
                        .font(.caption2)
                }
            }

            Picker("Market Type", selection: $viewModel.marketType) {
                ForEach(MarketType.allCases) { type in
                    HStack {
                        Text(type.displayName)
                    }
                    .tag(type)
                }
            }

        } header: {
            Label("Economy", systemImage: "banknote")
        }
    }

    // MARK: - Competition

    private var competitionSection: some View {
        Section {
            Picker("AI Difficulty", selection: $viewModel.aiDifficulty) {
                ForEach(AIDifficulty.allCases) { difficulty in
                    Text(difficulty.displayName).tag(difficulty)
                }
            }
            .pickerStyle(.segmented)

            Stepper(
                "AI Competitors: \(viewModel.numberOfAICompetitors)",
                value: $viewModel.numberOfAICompetitors,
                in: CreateSessionViewModel.competitorsRange
            )

        } header: {
            Label("Competition", systemImage: "cpu")
        } footer: {
            Text("AI competitors simulate real market pressure. Higher difficulty means smarter opponent strategies.")
        }
    }

    // MARK: - Scoring

    private var scoringSection: some View {
        Section {
            Picker("Scoring Metric", selection: $viewModel.scoringMetric) {
                ForEach(ScoringMetric.allCases) { metric in
                    Text(metric.displayName).tag(metric)
                }
            }

            Text(viewModel.scoringMetric.description)
                .font(.caption)
                .foregroundStyle(.secondary)

        } header: {
            Label("Scoring", systemImage: "trophy")
        }
    }

    // MARK: - Validation Errors

    @ViewBuilder
    private var validationSection: some View {
        if !viewModel.validationErrors.isEmpty && !viewModel.sessionName.isEmpty {
            Section {
                ForEach(viewModel.validationErrors, id: \.self) { error in
                    Label(error, systemImage: "exclamationmark.triangle.fill")
                        .foregroundStyle(.red)
                        .font(.caption)
                }
            }
        }

        if let error = viewModel.creationError {
            Section {
                Label(error, systemImage: "xmark.circle.fill")
                    .foregroundStyle(.red)
                    .font(.caption)
            }
        }
    }

    // MARK: - Summary

    private var summarySection: some View {
        Section {
            VStack(alignment: .leading, spacing: 8) {
                if viewModel.selectedTemplate != .custom {
                    summaryRow(label: "Template", value: viewModel.selectedTemplate.displayName)
                }
                if !viewModel.courseCode.isEmpty {
                    summaryRow(label: "Course", value: "\(viewModel.courseCode) — \(viewModel.semester)")
                }
                summaryRow(label: "Rounds", value: "\(viewModel.totalRounds)")
                summaryRow(label: "Starting Cash", value: viewModel.formattedStartingCash)
                summaryRow(label: "Market", value: viewModel.marketType.displayName)
                summaryRow(label: "AI Competitors", value: "\(viewModel.numberOfAICompetitors) (\(viewModel.aiDifficulty.displayName))")
                summaryRow(label: "Scoring", value: viewModel.scoringMetric.displayName)
                summaryRow(label: "Teams", value: "\(viewModel.maxHumanTeams) teams × \(viewModel.teamSize) students")
                summaryRow(label: "Pacing", value: viewModel.roundPacingMode.displayName)
                if viewModel.isPracticeMode {
                    summaryRow(label: "Mode", value: "Practice (non-graded)")
                }
            }

            // Prominent create button at the bottom of the form
            Button {
                Task { await createSession() }
            } label: {
                HStack(spacing: 8) {
                    if viewModel.isCreating {
                        ProgressView()
                            .controlSize(.small)
                    }
                    Image(systemName: "plus.circle.fill")
                    Text("Create Session")
                        .fontWeight(.semibold)
                }
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!viewModel.isValid || viewModel.isCreating)
            .padding(.top, 8)
        } header: {
            Label("Summary", systemImage: "doc.text")
        }
    }

    private func summaryRow(label: String, value: String) -> some View {
        HStack {
            Text(label)
                .foregroundStyle(.secondary)
            Spacer()
            Text(value)
                .fontWeight(.medium)
        }
        .font(.subheadline)
    }

    // MARK: - Actions

    private func createSession() async {
        guard let session = await viewModel.createSession() else {
            return
        }

        if viewModel.backendSessionCode != nil {
            // Cloud backend was used — show session code alert
            showingSessionCreated = true
        } else {
            // Local-only mode
            appState.setActiveSession(session)
            dismiss()
        }
    }
}
