import SwiftUI
import os

// MARK: - SessionListViewModel
/// ViewModel for the professor's session list screen (P-1).
/// Loads, displays, and manages simulation sessions from the backend API.

@Observable
final class SessionListViewModel {

    // MARK: - Properties

    /// All sessions owned by the professor, sorted by most recent first.
    var sessions: [SimulationSession] = []

    /// Whether the session list is currently being loaded.
    var isLoading: Bool = false

    /// An error message to display if loading or deletion fails.
    var errorMessage: String?

    /// The AppState instance for syncing sessions back to the app state.
    weak var appState: AppState?

    // MARK: - Computed

    var hasSessions: Bool { !sessions.isEmpty }

    var activeSessions: [SimulationSession] {
        sessions.filter { $0.state == .waitingForPlayers || $0.state == .inProgress }
    }

    var completedSessions: [SimulationSession] {
        sessions.filter { $0.state == .completed }
    }

    var sessionCount: Int { sessions.count }

    var activeSessionCount: Int { activeSessions.count }

    // MARK: - Actions

    /// Load all sessions from the backend API and sync to app state.
    func loadSessions() async {
        isLoading = true
        errorMessage = nil

        do {
            let backendSessions = try await NetworkService.shared.getDashboardSessions()
            
            // Clear existing sessions and rebuild from backend
            sessions.removeAll()
            
            for backendSession in backendSessions {
                // Convert backend session to SimulationSession
                let session = createSessionFromBackend(backendSession)
                sessions.insert(session, at: 0) // newest first
                
                // Also sync to app state for cross-view consistency
                if let appState = appState {
                    if !appState.professorSessions.contains(where: { $0.sessionCode == backendSession.code }) {
                        appState.professorSessions.insert(session, at: 0)
                    }
                }
            }
        } catch {
            errorMessage = "Failed to load sessions: \(UserFriendlyError.message(for: error))"
            Logger.sync.error("SessionListViewModel.loadSessions() error: \(error)")
        }
        
        isLoading = false
    }

    /// Create a SimulationSession from backend dashboard session data.
    private func createSessionFromBackend(_ backend: NetworkService.DashboardSessionResponse) -> SimulationSession {
        let config = SessionConfiguration(
            name: "Session \(backend.code)",
            totalRounds: backend.totalRounds,
            startingCash: 500_000,
            marketType: .moderate,
            aiDifficulty: .medium,
            numberOfAICompetitors: backend.aiTeamsCount,
            scoringMetric: .investorScore,
            courseCode: "",
            semester: ""
        )
        
        let session = SimulationSession(config: config)
        session.sessionCode = backend.code
        session.currentRound = backend.currentRound
        session.state = mapBackendState(backend.state)
        
        return session
    }

    /// Map backend session state string to SimulationSession.State enum.
    private func mapBackendState(_ state: String) -> SessionState {
        switch state {
        case "creating":
            return .waitingForPlayers
        case "active":
            return .inProgress
        case "completed", "finished":
            return .completed
        default:
            return .waitingForPlayers
        }
    }

    /// Delete a session at the given offsets (for SwiftUI List onDelete).
    func deleteSessions(at offsets: IndexSet) {
        let sessionsToDelete = offsets.map { sessions[$0] }
        sessions.remove(atOffsets: offsets)

        // Also delete from backend if authenticated
        for session in sessionsToDelete {
            Task {
                do {
                    try await NetworkService.shared.deleteSession(code: session.sessionCode)
                } catch {
                    Logger.network.error("Failed to delete session from backend: \(error)")
                }
            }
        }
    }

    /// Delete a specific session by its ID.
    func deleteSession(id: UUID) {
        guard let index = sessions.firstIndex(where: { $0.id == id }) else { return }
        let session = sessions.remove(at: index)

        // Also delete from backend if authenticated
        Task {
            do {
                try await NetworkService.shared.deleteSession(code: session.sessionCode)
            } catch {
                Logger.network.error("Failed to delete session from backend: \(error)")
            }
        }
    }

    /// Add a newly created session to the list.
    func addSession(_ session: SimulationSession) {
        sessions.insert(session, at: 0) // newest first
        
        // Also sync to app state
        if let appState = appState {
            if !appState.professorSessions.contains(where: { $0.id == session.id }) {
                appState.professorSessions.insert(session, at: 0)
            }
        }
    }

    /// Navigate to the create-session flow.
    /// Returns a new session placeholder; the actual creation happens in CreateSessionViewModel.
    func createNewSession() -> SimulationSession? {
        // Navigation is handled at the View layer; this is a hook for any
        // pre-navigation logic (analytics, validation, etc.).
        return nil
    }

    // MARK: - Display Helpers

    /// Human-readable summary for a session (e.g., "Round 3 of 10 · 4 teams").
    func summary(for session: SimulationSession) -> String {
        let roundInfo = "Round \(session.currentRound) of \(session.totalRounds)"
        let teamCount = session.teams.count
        let teamLabel = teamCount == 1 ? "1 team" : "\(teamCount) teams"
        return "\(roundInfo) · \(teamLabel)"
    }

    /// Status badge text.
    func statusLabel(for session: SimulationSession) -> String {
        session.state.displayName
    }
}
