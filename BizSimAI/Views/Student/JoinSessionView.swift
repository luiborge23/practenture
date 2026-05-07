// JoinSessionView.swift
// BizSimAI
//
// S-1: Session code entry and team creation for students.
// Includes a "Start Demo" button for MVP testing without a real session.
// Supports both cloud backend and local fallback.

import SwiftUI

struct JoinSessionView: View {
    @Environment(AppState.self) private var appState
    @State private var viewModel = JoinSessionViewModel()
    @State private var startDemoTeamName: String = ""

    private var isValid: Bool {
        viewModel.isValid
    }

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 32) {
                // Header
                VStack(spacing: 12) {
                    ZStack {
                        Circle()
                            .fill(.green.gradient)
                            .frame(width: 64, height: 64)
                            .shadow(color: .green.opacity(0.3), radius: 16, y: 6)

                        Image(systemName: "graduationcap.fill")
                            .font(.system(size: 28))
                            .foregroundStyle(.white)
                    }

                    VStack(spacing: 4) {
                        Text("Join a Session")
                            .font(.title)
                            .fontWeight(.bold)

                        Text("Enter the code from your professor to join")
                            .font(.subheadline)
                            .foregroundStyle(.secondary)
                    }
                }

                // Form
                VStack(spacing: 20) {
                    // Session Code
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Session Code", systemImage: "number")
                            .font(.headline)

                        TextField("Enter session code", text: $viewModel.sessionCode)
                            .textFieldStyle(.roundedBorder)
                            .font(.system(size: 24, weight: .bold, design: .monospaced))
                            .multilineTextAlignment(.center)
                            .frame(maxWidth: 280)
                            .textInputAutocapitalization(.characters)
                            .onChange(of: viewModel.sessionCode) {
                                Task { await viewModel.verifySessionCode() }
                            }
                    }
                    .frame(maxWidth: .infinity)

                    // Available teams indicator
                    if !viewModel.sessionCode.isEmpty {
                        Text(viewModel.availableTeams > 0
                             ? "\(viewModel.availableTeams) team(s) already in session"
                             : "Session not found or not started yet")
                            .font(.caption)
                            .foregroundStyle(viewModel.availableTeams > 0 ? .green : .secondary)
                    }

                    // Team Name
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Team Name", systemImage: "person.2.fill")
                            .font(.headline)

                        TextField("e.g., Strategy Kings", text: $viewModel.teamName)
                            .textFieldStyle(.roundedBorder)
                            .frame(maxWidth: 320)
                    }
                    .frame(maxWidth: .infinity)

                    // Student ID
                    VStack(alignment: .leading, spacing: 8) {
                        Label("Student ID", systemImage: "person.fill")
                            .font(.headline)

                        TextField("Your student ID (optional)", text: $viewModel.studentId)
                            .textFieldStyle(.roundedBorder)
                            .frame(maxWidth: 320)
                    }
                    .frame(maxWidth: .infinity)

                    // Error
                    if let errorMessage = viewModel.errorMessage {
                        Text(errorMessage)
                            .font(.caption)
                            .foregroundStyle(.red)
                    }

                    // Join Button
                    Button {
                        Task { await viewModel.join() }
                    } label: {
                        HStack(spacing: 8) {
                            if viewModel.isLoading {
                                ProgressView()
                                    .controlSize(.small)
                            }
                            Text("Join Session")
                                .fontWeight(.semibold)
                        }
                        .frame(maxWidth: 280)
                    }
                    .buttonStyle(.borderedProminent)
                    .controlSize(.large)
                    .disabled(!isValid || viewModel.isLoading)
                    .onChange(of: viewModel.joinedTeamId) { _, newId in
                        onTeamJoined(teamId: newId)
                    }
                }
                .padding(32)
                .background(
                    RoundedRectangle(cornerRadius: 20, style: .continuous)
                        .fill(Color.gray.opacity(0.1))
                        .shadow(color: .black.opacity(0.08), radius: 20, y: 8)
                )
                .frame(maxWidth: 420)

                // Demo Buttons
                VStack(spacing: 8) {
                    Text("or")
                        .font(.caption)
                        .foregroundStyle(.tertiary)

                    Button {
                        startDemo()
                    } label: {
                        Label("Start Demo Session", systemImage: "play.fill")
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.regular)
                    .tint(.green)

                    Button {
                        startQuickDemo()
                    } label: {
                        Label("Quick Demo (Auto-Play All Rounds)", systemImage: "forward.fill")
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.regular)
                    .tint(.blue)
                }
            }

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .navigationTitle("Join Session")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button {
                    appState.resetToLaunch()
                } label: {
                    Label("Back to Home", systemImage: "house")
                }
            }
        }
    }

    // MARK: - Demo Actions

    private func startDemo() {
        let config = SessionConfiguration(
            name: startDemoTeamName.isEmpty ? "Demo Team" : startDemoTeamName,
            totalRounds: 10,
            startingCash: 100_000,
            numberOfAICompetitors: 3
        )
        let session = SimulationSession(config: config)
        appState.setActiveSession(session)
    }

    private func startQuickDemo() {
        let config = SessionConfiguration(
            name: startDemoTeamName.isEmpty ? "Demo Team" : startDemoTeamName,
            totalRounds: 8,
            startingCash: 100_000,
            numberOfAICompetitors: 3,
            scoringMetric: .investorScore
        )
        let session = SimulationSession(config: config)
        appState.setActiveSession(session)

        // Auto-run all rounds
        appState.gameController?.runQuickDemo()
    }

    // MARK: - Helper Functions

    private func onTeamJoined(teamId: UUID?) {
        guard let teamId else { return }
        guard let team = viewModel.joinedTeam, teamId == team.id else { return }
        let config = SessionConfiguration(
            name: "Joined Session",
            totalRounds: 10,
            startingCash: 100_000,
            marketType: .moderate,
            aiDifficulty: .medium,
            numberOfAICompetitors: 3,
            plantCapacity: 500
        )
        let session = SimulationSession(config: config)
        appState.setActiveSession(session, joinedTeam: team)
    }
}
