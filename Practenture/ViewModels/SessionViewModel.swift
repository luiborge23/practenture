// SessionViewModel.swift
// Practenture
//
// ViewModel for session management (startSession, findSession).
// Handles both professor and student session flows.
//
// This file replaces placeholder APIs for:
// - startSession: Start a new simulation session
// - findSession: Retrieve and monitor an existing session

import Foundation
import SwiftUI

// MARK: - Session State for UI

@MainActor
// MARK: - Session ViewModel

/// ViewModel for session management operations.
/// Handles creating, starting, and finding sessions via the backend API.
@Observable
final class SessionViewModel {
    
    // MARK: - Properties
    
    /// The current session code (empty until a session is found/created)
    var sessionCode: String = ""
    
    /// Whether the operation is currently loading
    var isLoading: Bool = false
    
    /// Error message to display
    var errorMessage: String?
    
    /// Whether a session is currently active
    var hasActiveSession: Bool { !sessionCode.isEmpty }
    
    /// Current session state from backend
    var currentSessionState: SessionState = .waitingForPlayers
    
    /// Number of teams currently in the session
    var teamCount: Int = 0
    
    /// Current round (0 until session starts)
    var currentRound: Int = 0
    
    /// Total rounds configured for the session
    var totalRounds: Int = 20
    
    // MARK: - Create/Start Session (Professor)
    
    /// Start a new session with the given configuration.
    /// Returns the session code on success, or nil on failure.
    ///
    /// - Parameters:
    ///   - config: Session configuration (rounds, teams, etc.)
    ///   - teamConfigs: Array of team configurations
    /// - Returns: Session code string on success, nil on failure
    func startSession(config: SessionConfiguration, teams: [TeamConfig]) async -> String? {
        isLoading = true
        errorMessage = nil
        
        do {
            let result = try await NetworkService.shared.createSession(config: config, teams: teams)
            sessionCode = result.code
            currentSessionState = .waitingForPlayers
            totalRounds = config.totalRounds
            
            isLoading = false
            return sessionCode
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            isLoading = false
            return nil
        }
    }
    
    /// Start an existing session (professor action).
    /// Marks the session as active and ready for decisions.
    func startExistingSession(sessionCode: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        do {
            try await NetworkService.shared.startSession(code: sessionCode)
            
            // Update local state
            self.sessionCode = sessionCode
            currentSessionState = .inProgress
            
            isLoading = false
            return true
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            isLoading = false
            return false
        }
    }
    
    // MARK: - Find Session (Student)
    
    /// Find and join an existing session by code.
    /// Returns true on success, false on failure.
    ///
    /// - Parameters:
    ///   - sessionCode: The session code to find
    ///   - teamName: The team name to use when joining
    ///   - studentId: The student's ID
    /// - Returns: true if found and joined successfully, false otherwise
    func findSession(sessionCode: String, teamName: String, studentId: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        do {
            // First verify session exists and get status
            let status = try await NetworkService.shared.getSessionStatus(code: sessionCode)
            
            // Join the session with team
            _ = try await NetworkService.shared.joinSession(
                code: sessionCode,
                teamName: teamName,
                studentId: studentId
            )
            
            // Update state
            self.sessionCode = sessionCode
            currentSessionState = status.state == "creating" ? .waitingForPlayers : 
                                  status.state == "active" ? .inProgress : .completed
            currentRound = status.currentRound
            totalRounds = status.totalRounds
            
            isLoading = false
            return true
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            
            // Clear session code on failure
            self.sessionCode = ""
            currentSessionState = .waitingForPlayers
            
            isLoading = false
            return false
        }
    }
    
    /// Find session status without joining (just for info).
    func findSessionInfo(sessionCode: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        do {
            let status = try await NetworkService.shared.getSessionStatus(code: sessionCode)
            
            self.sessionCode = sessionCode
            currentSessionState = status.state == "creating" ? .waitingForPlayers : 
                                  status.state == "active" ? .inProgress : .completed
            currentRound = status.currentRound
            totalRounds = status.totalRounds
            teamCount = status.humanTeams
            
            isLoading = false
            return true
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            
            // Clear session code on failure
            self.sessionCode = ""
            currentSessionState = .waitingForPlayers
            
            isLoading = false
            return false
        }
    }
    
    // MARK: - Session Operations
    
    /// Get the current session details from backend.
    func loadSessionDetails(sessionCode: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        do {
            let session = try await NetworkService.shared.getSession(byCode: sessionCode)
            
            self.sessionCode = session.code
            currentSessionState = session.state == "creating" ? .waitingForPlayers : 
                                  session.state == "active" ? .inProgress : .completed
            currentRound = session.currentRound
            totalRounds = session.config.totalRounds
            
            isLoading = false
            return true
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            isLoading = false
            return false
        }
    }
    
    /// End a session (professor action).
    func endSession(sessionCode: String) async -> Bool {
        isLoading = true
        errorMessage = nil
        
        do {
            try await NetworkService.shared.endSession(code: sessionCode)
            
            currentSessionState = .completed
            isLoading = false
            return true
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            isLoading = false
            return false
        }
    }
    
    // MARK: - Team Operations
    
    /// Get teams in a session.
    func getTeams(sessionCode: String) async -> [TeamConfigBackend] {
        isLoading = true
        errorMessage = nil
        
        do {
            let teams = try await NetworkService.shared.getTeams(code: sessionCode)
            isLoading = false
            return teams
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            isLoading = false
            return []
        }
    }
    
    // MARK: - Session Code Validation
    
    /// Check if a session code is valid (4+ characters, alphanumeric).
    func isValidSessionCode(_ code: String) -> Bool {
        let pattern = "^[A-Za-z0-9]{4,}$"
        return code.range(of: pattern, options: .regularExpression) != nil
    }
}

// MARK: - Session Configuration (from existing models)

extension SessionViewModel {
    /// Convert TeamConfig to backend format for session creation.
    private func toBackendTeamConfigs(_ teams: [TeamConfig]) -> [TeamConfigBackend] {
        teams.map { team in
            TeamConfigBackend(
                teamName: team.name,
                isAI: team.isAI,
                aiStrategy: nil,
                studentId: team.studentId
            )
        }
    }
}
