// RoundControlView.swift
// BizSimAI
//
// P-5: Round management controls for professors.
// Shows current round, submission status, advance/pause/end controls.

import SwiftUI
import Combine

struct RoundControlView: View {
    @Environment(AppState.self) private var appState

    // Session state (will be driven by SessionMonitorViewModel)
    @State private var currentRound: Int = 1
    @State private var totalRounds: Int = 10
    @State private var isPaused: Bool = false
    @State private var showEndSessionAlert: Bool = false

    // Team submission tracking
    @State private var teamSubmissions: [TeamSubmission] = []

    @State private var isProcessing: Bool = false

    private var submittedCount: Int {
        teamSubmissions.filter(\.hasSubmitted).count
    }

    private var allSubmitted: Bool {
        teamSubmissions.allSatisfy(\.hasSubmitted)
    }

    private var isLastRound: Bool {
        currentRound >= totalRounds
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                roundDisplay
                submissionStatus
                teamSubmissionList
                controlButtons
            }
            .padding(24)
        }
        .navigationTitle("Round Control")
        #if os(macOS)
        .frame(minWidth: 500)
        #endif
        .alert("End Session?", isPresented: $showEndSessionAlert) {
            Button("Cancel", role: .cancel) { }
            Button("End Session", role: .destructive) {
                endSession()
            }
        } message: {
            Text("This will finalize all results and prevent further rounds. This action cannot be undone.")
        }
        .onAppear {
            loadFromSession()
        }
        .onReceive(Timer.publish(every: 5, on: .main, in: .common).autoconnect()) { _ in
            loadFromSession()
        }
    }

    private func loadFromSession() {
        guard let session = appState.activeSession else { return }
        currentRound = session.currentRound
        totalRounds = session.config.totalRounds
        isPaused = session.isPaused
        teamSubmissions = session.teams.map { team in
            TeamSubmission(
                id: team.id, name: team.name, isAI: team.isAI,
                hasSubmitted: team.hasSubmittedDecisions || team.isAI,
                submittedAt: team.hasSubmittedDecisions ? Date() : nil
            )
        }
    }

    // MARK: - Round Display

    private var roundDisplay: some View {
        VStack(spacing: 16) {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Current Round")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)

                    HStack(alignment: .firstTextBaseline, spacing: 4) {
                        Text("\(currentRound)")
                            .font(.system(size: 48, weight: .bold, design: .rounded))
                            .foregroundStyle(.blue)

                        Text("of \(totalRounds)")
                            .font(.title2)
                            .foregroundStyle(.secondary)
                    }
                }

                Spacer()

                // Status badge
                if isPaused {
                    StatusBadge.paused()
                } else if isLastRound {
                    StatusBadge(text: "Final Round", color: .orange, icon: "flag.checkered", size: .large)
                } else {
                    StatusBadge.active()
                }
            }

            // Round progress bar
            VStack(spacing: 6) {
                ProgressView(value: Double(currentRound), total: Double(max(totalRounds, 1)))
                    .tint(.blue)
                    .animation(.spring, value: currentRound)

                HStack {
                    Text("Round 1")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    Spacer()
                    Text("Round \(totalRounds)")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                }
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    // MARK: - Submission Status

    private var submissionStatus: some View {
        VStack(spacing: 12) {
            HStack {
                Text("Team Submissions")
                    .font(.headline)

                Spacer()

                Text("\(submittedCount) of \(teamSubmissions.count)")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(allSubmitted ? .green : .orange)
            }

            ProgressView(value: Double(submittedCount), total: Double(max(teamSubmissions.count, 1)))
                .tint(allSubmitted ? .green : .blue)
                .animation(.spring, value: submittedCount)

            if allSubmitted {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    Text("All teams have submitted — ready to advance")
                        .font(.caption)
                        .foregroundStyle(.green)
                }
            } else {
                HStack(spacing: 6) {
                    Image(systemName: "clock.fill")
                        .foregroundStyle(.orange)
                    Text("\(teamSubmissions.count - submittedCount) team(s) still pending")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    // MARK: - Team Submission List

    private var teamSubmissionList: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Submission Details")
                .font(.headline)

            ForEach(teamSubmissions) { team in
                HStack(spacing: 12) {
                    Image(systemName: team.hasSubmitted ? "checkmark.circle.fill" : "circle.dashed")
                        .font(.title3)
                        .foregroundStyle(team.hasSubmitted ? .green : .orange)

                    VStack(alignment: .leading, spacing: 2) {
                        HStack(spacing: 6) {
                            Text(team.name)
                                .font(.subheadline)
                                .fontWeight(.medium)

                            if team.isAI {
                                Image(systemName: "cpu")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }

                        if team.hasSubmitted {
                            Text("Submitted at \(team.submittedAt?.formatted(date: .omitted, time: .shortened) ?? "--")")
                                .font(.caption)
                                .foregroundStyle(.tertiary)
                        } else {
                            Text("Waiting for submission...")
                                .font(.caption)
                                .foregroundStyle(.orange)
                        }
                    }

                    Spacer()

                    if team.hasSubmitted {
                        StatusBadge.submitted()
                    } else {
                        StatusBadge.pending()
                    }
                }
                .padding(12)
                .background(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(team.hasSubmitted ? Color.green.opacity(0.04) : Color.orange.opacity(0.04))
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .strokeBorder(
                            team.hasSubmitted ? Color.green.opacity(0.15) : Color.orange.opacity(0.15),
                            lineWidth: 1
                        )
                )
            }
        }
    }

    // MARK: - Control Buttons

    private var controlButtons: some View {
        VStack(spacing: 12) {
            // Primary: Advance Round
            Button {
                advanceRound()
            } label: {
                Label(
                    isLastRound ? "Finalize Results" : "Advance to Round \(currentRound + 1)",
                    systemImage: isLastRound ? "flag.checkered" : "forward.fill"
                )
                .font(.headline)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 4)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!allSubmitted || isPaused || isProcessing)

            HStack(spacing: 12) {
                // Pause / Resume toggle
                Button {
                    withAnimation(.spring(duration: 0.3)) {
                        isPaused.toggle()
                    }
                } label: {
                    Label(
                        isPaused ? "Resume Session" : "Pause Session",
                        systemImage: isPaused ? "play.circle" : "pause.circle"
                    )
                    .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
                .tint(isPaused ? .green : .yellow)

                // End Session
                Button(role: .destructive) {
                    showEndSessionAlert = true
                } label: {
                    Label("End Session", systemImage: "stop.circle")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.bordered)
                .controlSize(.large)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Actions

    private func advanceRound() {
        guard let gameController = appState.gameController else { return }

        if isLastRound {
            endSession()
            return
        }

        isProcessing = true

        // Run AI decisions + simulation via game controller
        // Uses snapshot→background→apply pattern internally
        gameController.processRoundAfterPlayerSubmit()

        // Poll for completion (processRoundAfterPlayerSubmit runs async)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
            self.isProcessing = gameController.isProcessing
            if !self.isProcessing {
                self.loadFromSession()
            } else {
                // Still processing, check again
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) {
                    self.isProcessing = gameController.isProcessing
                    self.loadFromSession()
                }
            }
        }
    }

    private func endSession() {
        appState.clearActiveSession()
    }
}

// MARK: - Team Submission Model

struct TeamSubmission: Identifiable {
    let id: UUID
    let name: String
    let isAI: Bool
    var hasSubmitted: Bool
    var submittedAt: Date?

    static let samples: [TeamSubmission] = [
        TeamSubmission(id: UUID(), name: "Alpha Corp", isAI: true, hasSubmitted: true, submittedAt: Date().addingTimeInterval(-120)),
        TeamSubmission(id: UUID(), name: "Team Rocket", isAI: false, hasSubmitted: true, submittedAt: Date().addingTimeInterval(-45)),
        TeamSubmission(id: UUID(), name: "Beta Inc", isAI: true, hasSubmitted: true, submittedAt: Date().addingTimeInterval(-118)),
        TeamSubmission(id: UUID(), name: "Gamma LLC", isAI: true, hasSubmitted: true, submittedAt: Date().addingTimeInterval(-115)),
        TeamSubmission(id: UUID(), name: "Delta Co", isAI: false, hasSubmitted: false, submittedAt: nil),
        TeamSubmission(id: UUID(), name: "Omega Group", isAI: false, hasSubmitted: false, submittedAt: nil),
    ]
}
