import SwiftUI

// MARK: - SessionListViewModel
/// ViewModel for the professor's session list screen (P-1).
/// Loads, displays, and manages simulation sessions from local storage.

@Observable
final class SessionListViewModel {

    // MARK: - Properties

    /// All sessions owned by the professor, sorted by most recent first.
    var sessions: [SimulationSession] = []

    /// Whether the session list is currently being loaded.
    var isLoading: Bool = false

    /// An error message to display if loading or deletion fails.
    var errorMessage: String?

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

    /// Load all sessions from the in-memory store (MVP) or local persistence.
    func loadSessions() {
        isLoading = true
        errorMessage = nil

        // MVP: load from in-memory store
        // In the future this will load from CoreData / file-based persistence.
        // For now, sessions are kept in memory and this acts as a refresh.
        isLoading = false
    }

    /// Delete a session at the given offsets (for SwiftUI List onDelete).
    func deleteSessions(at offsets: IndexSet) {
        let sessionsToDelete = offsets.map { sessions[$0] }
        sessions.remove(atOffsets: offsets)

        // MVP: in-memory removal is sufficient.
        // Future: also remove from persistent storage.
        _ = sessionsToDelete // suppress unused warning; will be used for persistence
    }

    /// Delete a specific session by its ID.
    func deleteSession(id: UUID) {
        sessions.removeAll { $0.id == id }
    }

    /// Add a newly created session to the list.
    func addSession(_ session: SimulationSession) {
        sessions.insert(session, at: 0) // newest first
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
