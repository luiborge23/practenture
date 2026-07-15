// SessionListView.swift
// BizSimAI
//
// P-1: Professor dashboard showing list of simulation sessions with status badges,
// create new session, and clone session capabilities.

import SwiftUI
import os

struct SessionListView: View {
    @Environment(AppState.self) private var appState
    @State private var showingCreateSession = false
    @State private var searchText = ""
    @State private var isSyncingFromBackend = false
    @State private var debugStatus: String = "Not loaded yet"
    @State private var debugError: String?

        /// Fetch sessions from the backend and merge with local list.
    private func syncSessionsFromBackend() async {
        isSyncingFromBackend = true
        defer { isSyncingFromBackend = false }
        
        NSLog("🔍 SessionListView: syncSessionsFromBackend() START")
        NSLog("🔍 SessionListView: professorSessions count before = \(appState.professorSessions.count)")
        
        let hasToken = AuthManager.shared.accessToken != nil
        let tokenPreview = AuthManager.shared.accessToken?.prefix(20) ?? "nil"
        await MainActor.run { 
            debugStatus = "Loading... (token: \(hasToken) \(tokenPreview)..." 
        }
        
        do {
            let backendSessions = try await NetworkService.shared.getDashboardSessions()
            NSLog("🔍 SessionListView: API returned \(backendSessions.count) sessions")
            await MainActor.run { debugStatus = "Got \(backendSessions.count) sessions from API" }

            for bs in backendSessions {
                NSLog("🔍 SessionListView: Processing session code='\(bs.code)' state='\(bs.state)'")
            }
            
            await MainActor.run {
                for bs in backendSessions {
                    if let existing = appState.professorSessions.first(where: { $0.code == bs.code || $0.sessionCode == bs.code }) {
                        // Update existing with backend state
                        NSLog("🔍 SessionListView: Found existing session '\(bs.code)', updating")
                        existing.currentRound = bs.currentRound
                        existing.state = mapBackendState(bs.state)
                        existing.lastSyncedAt = Date()
                    } else {
                        NSLog("🔍 SessionListView: Creating new session '\(bs.code)'")
                        let config = SessionConfiguration(
                            name: "Session \(bs.code)",
                            totalRounds: bs.totalRounds,
                            startingCash: 500_000,
                            marketType: .moderate,
                            aiDifficulty: .medium,
                            numberOfAICompetitors: 3,
                            scoringMetric: .investorScore,
                            courseCode: "",
                            semester: ""
                        )
                        // Create local session then immediately overwrite generated code with backend code
                        let session = SimulationSession(config: config)
                        session.code = bs.code
                        session.currentRound = bs.currentRound
                        session.state = mapBackendState(bs.state)
                        session.lastSyncedAt = Date()
                        appState.professorSessions.insert(session, at: 0)
                    }
                }
                // Force @Observable refresh
                appState.professorSessions = appState.professorSessions
                NSLog("🔍 SessionListView: After sync, professorSessions count = \(appState.professorSessions.count)")
            }
        } catch {
            NSLog("🔍 SessionListView: ERROR syncing sessions: \(error)")
            await MainActor.run {
                debugStatus = "ERROR"
                debugError = "\(error)"
            }
            Logger.sync.error("Failed to sync sessions from backend: \(UserFriendlyError.message(for: error))")
        }
    }

    private var filteredSessions: [SimulationSession] {
        if searchText.isEmpty {
            return appState.professorSessions
        }
        return appState.professorSessions.filter {
            $0.config.name.localizedCaseInsensitiveContains(searchText) ||
            $0.sessionCode.localizedCaseInsensitiveContains(searchText)
        }
    }

    /// Map backend session state string to iOS SessionState enum.
    /// Backend uses "creating"/"active"/"completed"/"finished"; iOS uses different raw values.
    private func mapBackendState(_ state: String) -> SessionState {
        switch state {
        case "creating":    return .waitingForPlayers
        case "active":      return .inProgress
        case "completed", "finished": return .completed
        case "roundProcessing": return .roundProcessing
        default:            return .waitingForPlayers
        }
    }

    var body: some View {
        VStack(spacing: 0) {
            if appState.professorSessions.isEmpty {
                emptyState
            } else {
                sessionList
            }
        }
        .navigationTitle("Sessions")
        .searchable(text: $searchText, prompt: "Search sessions")
        .onAppear {
            Task { await syncSessionsFromBackend() }
        }
        .toolbar {
            ToolbarItem(placement: .primaryAction) {
                Button {
                    showingCreateSession = true
                } label: {
                    Label("Create Session", systemImage: "plus.circle.fill")
                }
                .buttonStyle(.borderedProminent)
            }

            ToolbarItem(placement: .automatic) {
                Button {
                    appState.resetToLaunch()
                } label: {
                    Label("Back to Home", systemImage: "house")
                }
            }

            ToolbarItem(placement: .automatic) {
                Button {
                    Task { await syncSessionsFromBackend() }
                } label: {
                    Image(systemName: isSyncingFromBackend ? "hourglass.circle.fill" : "arrow.clockwise")
                }
                .disabled(isSyncingFromBackend)
            }
        }
        .sheet(isPresented: $showingCreateSession) {
            CreateSessionView()
        }
    }

    // MARK: - Session List

    private var sessionList: some View {
        ScrollView {
            // Section: Active Sessions
            let active = filteredSessions.filter { $0.state != .completed }
            let completed = filteredSessions.filter { $0.state == .completed }

            LazyVStack(spacing: 8) {
                if !active.isEmpty {
                    sectionLabel("Active Sessions", count: active.count)
                    ForEach(active) { session in
                        Button {
                            openSession(session)
                        } label: {
                            sessionRow(session)
                        }
                        .buttonStyle(.borderless)
                        .contentShape(Rectangle())
                        .contextMenu {
                            Button {
                                cloneSession(session)
                            } label: {
                                Label("Clone Session", systemImage: "doc.on.doc")
                            }
                            Button(role: .destructive) {
                                appState.professorSessions.removeAll { $0.id == session.id }
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                    }
                }

                if !completed.isEmpty {
                    sectionLabel("Completed Sessions", count: completed.count)
                    ForEach(completed) { session in
                        Button {
                            openSession(session)
                        } label: {
                            sessionRow(session)
                        }
                        .buttonStyle(.borderless)
                        .contentShape(Rectangle())
                        .contextMenu {
                            Button {
                                cloneSession(session)
                            } label: {
                                Label("Clone Session", systemImage: "doc.on.doc")
                            }
                            Button(role: .destructive) {
                                appState.professorSessions.removeAll { $0.id == session.id }
                            } label: {
                                Label("Delete", systemImage: "trash")
                            }
                        }
                    }
                }
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 8)
        }
    }

    private func sectionLabel(_ title: String, count: Int) -> some View {
        HStack {
            Text(title)
                .font(.subheadline)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)
            Spacer()
            Text("\(count)")
                .font(.caption)
                .foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 4)
        .padding(.top, 12)
    }

    // MARK: - Session Row

    private func sessionRow(_ session: SimulationSession) -> some View {
        HStack(spacing: 14) {
            // Status indicator
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .fill(statusColor(session).opacity(0.12))
                    .frame(width: 44, height: 44)

                Image(systemName: session.state == .completed ? "checkmark.circle.fill" : "play.circle.fill")
                    .font(.title2)
                    .foregroundStyle(statusColor(session))
            }

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 6) {
                    Text(session.config.name)
                        .font(.headline)

                    if session.config.isPracticeMode {
                        Text("PRACTICE")
                            .font(.caption2)
                            .fontWeight(.bold)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 1)
                            .background(.yellow.opacity(0.2), in: Capsule())
                            .foregroundStyle(.orange)
                    }
                }

                HStack(spacing: 12) {
                    let roundInfo = "Round \(session.currentRound) of \(session.totalRounds)"
                    let teamCount = session.teams.count
                    let teamLabel = teamCount == 1 ? "1 team" : "\(teamCount) teams"
                    Label("\(roundInfo) · \(teamLabel)", systemImage: "arrow.triangle.2.circlepath")

                    if !session.config.courseCode.isEmpty {
                        Label(session.config.courseCode, systemImage: "book.closed")
                    }
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Spacer()

            VStack(alignment: .trailing, spacing: 4) {
                statusBadge(session)

                Text(session.sessionCode)
                    .font(.caption)
                    .fontDesign(.monospaced)
                    .foregroundStyle(.blue)
            }
        }
        .padding(.vertical, 4)
        .contentShape(Rectangle())
    }

    // MARK: - Status Badge

    private func statusBadge(_ session: SimulationSession) -> some View {
        Text(session.state.displayName)
            .font(.caption)
            .fontWeight(.medium)
            .foregroundStyle(statusColor(session))
            .padding(.horizontal, 10)
            .padding(.vertical, 4)
            .background(statusColor(session).opacity(0.12), in: Capsule())
    }

    private func statusColor(_ session: SimulationSession) -> Color {
        switch session.state {
        case .completed: return .secondary
        case .inProgress: return .green
        case .roundProcessing: return .blue
        case .waitingForPlayers: return .orange
        }
    }

    // MARK: - Empty State

    private var emptyState: some View {
        VStack(spacing: 20) {
            Image(systemName: "rectangle.stack.badge.plus")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)

            Text("No Sessions Yet")
                .font(.title2)
                .fontWeight(.bold)

            Text("Create your first simulation session to get started.\nStudents will use the session code to join.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)

            Button {
                showingCreateSession = true
            } label: {
                Label("Create New Session", systemImage: "plus.circle.fill")
            }
            .buttonStyle(.borderedProminent)
        }
    }

    // MARK: - Actions

    private func openSession(_ session: SimulationSession) {
        appState.setActiveSession(session)
    }

    private func cloneSession(_ session: SimulationSession) {
        let newConfig = SessionConfiguration(
            name: session.config.name + " (Copy)",
            totalRounds: session.config.totalRounds,
            startingCash: session.config.startingCash,
            marketType: session.config.marketType,
            aiDifficulty: session.config.aiDifficulty,
            numberOfAICompetitors: session.config.numberOfAICompetitors,
            scoringMetric: session.config.scoringMetric,
            courseCode: session.config.courseCode,
            semester: session.config.semester,
            maxHumanTeams: session.config.maxHumanTeams,
            teamSize: session.config.teamSize,
            roundPacingMode: session.config.roundPacingMode,
            roundDeadlineHours: session.config.roundDeadlineHours,
            latePolicy: session.config.latePolicy,
            template: session.config.template,
            isPracticeMode: session.config.isPracticeMode
        )
        let cloned = SimulationSession(config: newConfig)
        appState.professorSessions.insert(cloned, at: 0)
    }
}
