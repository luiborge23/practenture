// SessionMonitorView.swift
// BizSimAI
//
// P-3: Professor's live dashboard for monitoring an active simulation session.
// Shows session header, team status grid with key metrics, and round control buttons.
// Supports both local-only and cloud backend modes with real-time sync.

import SwiftUI

struct SessionMonitorView: View {
    @Environment(AppState.self) private var appState

    @State private var viewModel: SessionMonitorViewModel?
    @State private var showEndSessionAlert = false
    @State private var isBackendConnected = false
    @State private var pollTimer: Task<Void, Never>? = nil

    private var session: SimulationSession? { appState.activeSession }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                if let vm = viewModel {
                    connectionBanner(vm)
                    sessionHeader(vm)
                    deadlineAndPauseSection(vm)
                    progressSection(vm)
                    teamGrid(vm)
                    controlButtons(vm)
                } else {
                    ContentUnavailableView(
                        "No Active Session",
                        systemImage: "rectangle.dashed",
                        description: Text("Select or create a session to begin monitoring.")
                    )
                }
            }
            .padding(24)
        }
        .navigationTitle("Session Monitor")
        #if os(macOS)
        .frame(minWidth: 600)
        #endif
        .onAppear {
            if let session = session {
                viewModel = SessionMonitorViewModel(session: session)
                startBackendPolling()
            }
        }
        .onChange(of: appState.activeSession?.id) { _, _ in
            if let session = session {
                viewModel = SessionMonitorViewModel(session: session)
                startBackendPolling()
            } else {
                viewModel = nil
                stopBackendPolling()
            }
        }
        .onDisappear {
            stopBackendPolling()
        }
        .alert("End Session?", isPresented: $showEndSessionAlert) {
            Button("Cancel", role: .cancel) { }
            Button("End Session", role: .destructive) {
                Task { endSessionWithBackend() }
            }
        } message: {
            Text("This will finalize all results and prevent further rounds. This action cannot be undone.")
        }
    }

    // MARK: - Backend Polling

    private func startBackendPolling() {
        stopBackendPolling()
        pollTimer = Task { [weak viewModel] in
            while !Task.isCancelled {
                try? await Task.sleep(nanoseconds: 5_000_000_000) // 5 seconds
                guard let viewModel = viewModel else { return }
                await viewModel.pollBackendStatus()
            }
        }
    }

    private func stopBackendPolling() {
        pollTimer?.cancel()
        pollTimer = nil
    }

    private func endSessionWithBackend() {
        if let vm = viewModel {
            Task { await vm.endSessionWithBackend() }
            appState.clearActiveSession()
        } else {
            appState.clearActiveSession()
        }
    }

    // MARK: - Connection Banner

    private func connectionBanner(_ vm: SessionMonitorViewModel) -> some View {
        let isBackendActive = isBackendConnected || vm.backendTeamCount > 0

        return AnyView(
            HStack(spacing: 6) {
                Circle()
                    .fill(isBackendActive ? .green : Color.gray.opacity(0.3))
                    .frame(width: 8, height: 8)

                if isBackendActive {
                    Text("Connected to cloud backend")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                } else {
                    Text("Running in local mode")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                // Refresh button for backend status
                if isBackendActive, vm.currentRound > 0 {
                    Button {
                        Task { await vm.pollBackendStatus() }
                    } label: {
                        Image(systemName: "arrow.clockwise")
                            .font(.caption2)
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .background(
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(isBackendActive ? Color.green.opacity(0.08) : Color.blue.opacity(0.05))
            )
        )
    }

    // MARK: - Session Header

    private func sessionHeader(_ vm: SessionMonitorViewModel) -> some View {
        VStack(spacing: 12) {
            // Session code — prominent for sharing with class
            VStack(spacing: 4) {
                Text("Session Code")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                Text(vm.session.sessionCode)
                    .font(.system(size: 32, weight: .bold, design: .monospaced))
                    .foregroundStyle(.blue)
                    .padding(.horizontal, 20)
                    .padding(.vertical, 10)
                    .background(.blue.opacity(0.08), in: RoundedRectangle(cornerRadius: 12))
                    .textSelection(.enabled)
            }

            Text(vm.session.config.name)
                .font(.title3)
                .fontWeight(.bold)

            // Info row — wraps on small screens
            FlowLayout(spacing: 8) {
                Label(vm.roundProgress, systemImage: "arrow.triangle.2.circlepath")
                    .font(.caption)
                    .foregroundStyle(.secondary)

                // Show both local and backend team counts
                HStack(spacing: 2) {
                    Label("\(vm.teams.count) teams", systemImage: "person.3.fill")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    if vm.backendSubmittedCount > 0 {
                        Text("(\(vm.backendSubmittedCount) submitted)")
                            .font(.caption2)
                            .foregroundStyle(.green)
                    }
                }

                if !vm.session.config.courseCode.isEmpty {
                    Label(vm.session.config.courseCode, systemImage: "book.closed")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                if vm.session.config.isPracticeMode {
                    Text("PRACTICE")
                        .font(.caption2)
                        .fontWeight(.bold)
                        .padding(.horizontal, 8)
                        .padding(.vertical, 2)
                        .background(.yellow.opacity(0.2), in: Capsule())
                        .foregroundStyle(.orange)
                }

                Label(vm.sessionStatusLabel, systemImage: "circle.fill")
                    .font(.caption)
                    .foregroundStyle(vm.isSessionComplete ? .red : .green)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    /// Simple flow layout that wraps items to the next line
    private struct FlowLayout: Layout {
        var spacing: CGFloat = 8

        func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
            let result = arrange(proposal: proposal, subviews: subviews)
            return result.size
        }

        func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
            let result = arrange(proposal: ProposedViewSize(width: bounds.width, height: bounds.height), subviews: subviews)
            for (index, position) in result.positions.enumerated() {
                subviews[index].place(at: CGPoint(x: bounds.minX + position.x, y: bounds.minY + position.y), proposal: .unspecified)
            }
        }

        private func arrange(proposal: ProposedViewSize, subviews: Subviews) -> (size: CGSize, positions: [CGPoint]) {
            let maxWidth = proposal.width ?? .infinity
            var positions: [CGPoint] = []
            var x: CGFloat = 0
            var y: CGFloat = 0
            var rowHeight: CGFloat = 0
            var maxX: CGFloat = 0

            for subview in subviews {
                let size = subview.sizeThatFits(.unspecified)
                if x + size.width > maxWidth && x > 0 {
                    x = 0
                    y += rowHeight + spacing
                    rowHeight = 0
                }
                positions.append(CGPoint(x: x, y: y))
                rowHeight = max(rowHeight, size.height)
                x += size.width + spacing
                maxX = max(maxX, x)
            }

            return (CGSize(width: maxX, height: y + rowHeight), positions)
        }
    }

    // MARK: - Deadline & Pause

    private func deadlineAndPauseSection(_ vm: SessionMonitorViewModel) -> some View {
        HStack(spacing: 16) {
            // Pause toggle
            Button {
                if let session = session {
                    session.isPaused.toggle()
                }
            } label: {
                Label(
                    session?.isPaused == true ? "Resume Session" : "Pause Session",
                    systemImage: session?.isPaused == true ? "play.circle" : "pause.circle"
                )
            }
            .buttonStyle(.bordered)
            .tint(session?.isPaused == true ? .green : .orange)

            Spacer()

            // Deadline info
            if let remaining = session?.currentRoundTimeRemaining {
                HStack(spacing: 6) {
                    Image(systemName: remaining > 0 ? "clock" : "exclamationmark.triangle.fill")
                        .foregroundStyle(remaining > 0 ? .blue : .red)
                    if remaining > 0 {
                        let hours = Int(remaining) / 3600
                        let minutes = (Int(remaining) % 3600) / 60
                        Text("\(hours)h \(minutes)m remaining")
                            .font(.subheadline)
                            .fontWeight(.medium)
                    } else {
                        Text("Deadline passed")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .foregroundStyle(.red)
                    }
                }
            }

            // Session expiry
            if let expiry = session?.config.sessionExpiryDate {
                HStack(spacing: 4) {
                    Image(systemName: "calendar.badge.clock")
                        .foregroundStyle(.secondary)
                    Text("Expires: ")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text(expiry, style: .date)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(session?.isPaused == true ? Color.orange.opacity(0.08) : Color.gray.opacity(0.05))
        )
    }

    // MARK: - Progress Section

    private func progressSection(_ vm: SessionMonitorViewModel) -> some View {
        VStack(spacing: 10) {
            HStack {
                Text("Submissions")
                    .font(.headline)

                Spacer()

                Text(vm.submissionSummary)
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(vm.allDecisionsSubmitted ? .green : .orange)
            }

            ProgressView(value: Double(vm.submittedCount), total: Double(max(vm.teams.count, 1)))
                .tint(vm.allDecisionsSubmitted ? .green : .blue)
                .animation(.spring, value: vm.submittedCount)

            // Backend submission count (when connected)
            if vm.backendSubmittedCount > 0 {
                HStack(spacing: 4) {
                    Image(systemName: "cloud.fill")
                        .font(.caption2)
                        .foregroundStyle(.blue)
                    Text("Backend: \(vm.backendSubmittedCount)/\(vm.teams.count) submitted")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
            }

            if vm.allDecisionsSubmitted {
                HStack(spacing: 6) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    Text("All teams have submitted their decisions")
                        .font(.caption)
                        .foregroundStyle(.green)
                }
            } else {
                let pending = vm.teams.filter { !$0.hasSubmittedDecision }.map(\.teamName).joined(separator: ", ")
                HStack(spacing: 6) {
                    Image(systemName: "clock.fill")
                        .foregroundStyle(.orange)
                    Text("Waiting for: \(pending)")
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

    // MARK: - Team Grid

    private func teamGrid(_ vm: SessionMonitorViewModel) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Team Status")
                .font(.headline)

            LazyVGrid(columns: [
                GridItem(.adaptive(minimum: 160), spacing: 12)
            ], spacing: 12) {
                ForEach(vm.teams) { team in
                    teamCard(team, vm: vm)
                }
            }
        }
    }

    private func teamCard(_ team: SessionMonitorViewModel.MonitoredTeamStatus, vm: SessionMonitorViewModel) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    HStack(spacing: 4) {
                        Text(team.teamName)
                            .font(.subheadline)
                            .fontWeight(.semibold)
                            .lineLimit(1)

                        if team.isAI {
                            Image(systemName: "cpu")
                                .font(.caption2)
                                .foregroundStyle(.secondary)
                        }
                    }

                    Text("#\(team.rank)")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Spacer()

                Image(systemName: team.hasSubmittedDecision ? "checkmark.circle.fill" : "circle.dashed")
                    .font(.title3)
                    .foregroundStyle(vm.statusColor(for: team))
            }

            // Investor scorecard metrics row
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 1) {
                    Text("S/Q")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    Text(String(format: "%.1f★", team.sqRating))
                        .font(.caption)
                        .fontWeight(.medium)
                }

                Divider().frame(height: 20)

                VStack(alignment: .leading, spacing: 1) {
                    Text("Score")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    Text(String(format: "%.0f", team.investorScore))
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(team.investorScore >= 70 ? .green : team.investorScore < 40 ? .red : .primary)
                }

                Divider().frame(height: 20)

                VStack(alignment: .leading, spacing: 1) {
                    Text("Cash")
                        .font(.caption2)
                        .foregroundStyle(.tertiary)
                    Text(team.formattedCash)
                        .font(.caption)
                        .fontWeight(.medium)
                        .monospacedDigit()
                }
            }
        }
        .padding(14)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(team.hasSubmittedDecision ? Color.green.opacity(0.2) : Color.orange.opacity(0.2), lineWidth: 1)
        )
    }

    // MARK: - Control Buttons

    private func controlButtons(_ vm: SessionMonitorViewModel) -> some View {
        HStack(spacing: 16) {
            Button(role: .destructive) {
                showEndSessionAlert = true
            } label: {
                Label("End Session", systemImage: "stop.circle")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .controlSize(.large)

            Button {
                // Use backend if connected, otherwise local
                if vm.backendTeamStatus != "" {
                    Task { await vm.processRoundWithBackend() }
                } else {
                    vm.advanceRound()
                }
            } label: {
                Label(
                    vm.isLastRound ? "Finalize Results" : "Advance to Round \(vm.currentRound + 1)",
                    systemImage: "forward.fill"
                )
                .frame(maxWidth: .infinity)
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .disabled(!vm.canAdvanceRound)
        }
        .padding(.top, 8)
    }
}
