import SwiftUI

// MARK: - AppState
/// Root application state managing mode selection and the active session.

@MainActor
@Observable
final class AppState {

    // MARK: - Types

    enum AppMode: String, Codable, Identifiable {
        case professor
        case student

        var id: String { rawValue }

        var displayName: String {
            switch self {
            case .professor: "Professor"
            case .student: "Student"
            }
        }
    }

    // MARK: - Properties

    /// The currently selected mode, nil when no mode has been chosen (launch screen).
    var currentMode: AppMode?

    /// The simulation session that is currently active.
    var activeSession: SimulationSession?

    /// Game controller that manages the game loop (AI decisions + engine).
    var gameController: GameController?

    /// Theme preference for the app.
    var themePreference: ThemePreference = .system

    /// All professor sessions (persisted across tab switches).
    var professorSessions: [SimulationSession] = []

    /// Which professor tab is selected.
    var professorSelectedTab: String = "sessions"

    // MARK: - Init

    init() {
        // Wire auth change -> reset when logout happens externally
        AuthManager.shared.onAuthChange = { [weak self] in
            Task { @MainActor in
                // Do not auto-switch mode on login; LoginView drives selectMode explicitly.
                // Only reset to launch on explicit logout (accessToken nil and not authenticated)
                let auth = AuthManager.shared
                if !auth.isAuthenticated && auth.accessToken == nil {
                    self?.resetToLaunch()
                }
            }
        }
    }

    // MARK: - Computed

    var isLaunchScreen: Bool { currentMode == nil }

    var isProfessorMode: Bool { currentMode == .professor }

    var isStudentMode: Bool { currentMode == .student }

    var hasActiveSession: Bool { activeSession != nil }

    // MARK: - Actions

    /// Select a mode and transition away from the launch screen.
    func selectMode(_ mode: AppMode) {
        currentMode = mode
    }

    /// Set the active session (e.g., after creating or joining one).
    func setActiveSession(_ session: SimulationSession) {
        activeSession = session
        gameController = GameController(session: session)

        // For professor mode, add to sessions list and switch to Monitor tab
        if currentMode == .professor {
            if !professorSessions.contains(where: { $0.id == session.id }) {
                professorSessions.insert(session, at: 0)
            }
            professorSelectedTab = "monitor"
        }

        // Integrate with backend if this session has a backend code
        if !session.sessionCode.isEmpty, session.sessionCode != session.id.uuidString {
            Task {
                await BackendState.shared.connect(sessionCode: session.sessionCode)
            }
        }
    }

    /// Set the active session with a joined team (student joining via backend).
    func setActiveSession(_ session: SimulationSession, joinedTeam: TeamConfig) {
        // Ensure the session has the joined team
        let trimmedName = joinedTeam.name
        let updatedSession = session

        // Replace or add the non-AI team
        if let index = updatedSession.teams.firstIndex(where: { !$0.isAI }) {
            // TeamStatus.id is let (immutable), so we replace the whole team
            let oldTeam = updatedSession.teams[index]
            updatedSession.teams[index] = TeamStatus(
                id: joinedTeam.id,
                name: trimmedName,
                cash: oldTeam.cash,
                inventory: oldTeam.inventory,
                reputation: oldTeam.reputation,
                rank: oldTeam.rank,
                hasSubmittedDecisions: oldTeam.hasSubmittedDecisions,
                isAI: false,
                cumulativeRD: oldTeam.cumulativeRD,
                cumulativeMarketing: oldTeam.cumulativeMarketing,
                cumulativeCSR: oldTeam.cumulativeCSR,
                cumulativeTQM: oldTeam.cumulativeTQM,
                cumulativeProfit: oldTeam.cumulativeProfit,
                equity: oldTeam.equity,
                totalDebt: oldTeam.totalDebt,
                sharesOutstanding: oldTeam.sharesOutstanding,
                sqRating: oldTeam.sqRating,
                imageRating: oldTeam.imageRating,
                creditRating: oldTeam.creditRating,
                cumulativeInvestorScore: oldTeam.cumulativeInvestorScore,
                roundsScored: oldTeam.roundsScored
            )
        } else {
            updatedSession.teams.append(TeamStatus(
                id: joinedTeam.id,
                name: trimmedName,
                cash: session.startingCash
            ))
        }

        activeSession = updatedSession
        // Store the backend's team identifier (team name string) so
        // submit_decision can send the correct teamId to the API.
        updatedSession.backendTeamId = joinedTeam.backendTeamId
        gameController = GameController(session: updatedSession)

        // Integrate with backend if this session has a backend code
        if !updatedSession.sessionCode.isEmpty, updatedSession.sessionCode != updatedSession.id.uuidString {
            Task {
                await BackendState.shared.connect(sessionCode: updatedSession.sessionCode)
            }
        }
    }

    /// Clear the active session (e.g., when leaving a session).
    func clearActiveSession() {
        activeSession = nil
        gameController = nil
    }

    /// Find a professor session by its session code.
    func findSession(byCode code: String) -> SimulationSession? {
        let trimmed = code.trimmingCharacters(in: .whitespacesAndNewlines).uppercased()
        return professorSessions.first { $0.sessionCode == trimmed }
    }

    /// Reset everything back to the launch screen.
    func resetToLaunch() {
        currentMode = nil
        activeSession = nil
        gameController = nil
    }
}
