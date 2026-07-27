// RepositoryProtocols.swift
// Practenture
//
// Protocol definitions for the repository layer (DI-friendly).
// Each protocol abstracts a backend domain so ViewModels can be
// tested with mock implementations.

import Foundation

// MARK: - Auth Repository

protocol AuthRepository: Sendable {
    func login(provider: String, username: String?, password: String?, idToken: String?) async throws -> AuthLoginResponse
    func register(username: String, password: String, studentId: String, name: String) async throws -> AuthLoginResponse
    func logout() async
    func currentToken() -> String?
    func isAuthenticated() -> Bool
    func currentUser() -> AuthUser?
}

// MARK: - Session Repository

protocol SessionRepository: Sendable {
    func create(config: SessionConfiguration, teams: [TeamConfig]) async throws -> SessionBackend
    func get(code: String) async throws -> SessionBackend
    func delete(code: String) async throws
    func getStatus(code: String) async throws -> SessionStatusBackend
    func join(code: String, teamName: String, studentId: String) async throws -> JoinSessionBackend
    func getTeams(code: String) async throws -> [TeamConfigBackend]
    func listDashboard() async throws -> [NetworkService.DashboardSessionResponse]
}

// MARK: - Decision Repository

protocol DecisionRepository: Sendable {
    // Legacy protocol surface retained for existing repository consumers/tests.
    // Production online submission uses the backendTeamId overload on
    // DecisionRepositoryImpl/NetworkService and never substitutes this UUID.
    func submit(code: String, round: Int, teamId: UUID, decision: PlayerDecision) async throws
    func getDecisions(code: String, round: Int) async throws -> [String: PlayerDecision]
    func processRound(code: String) async throws -> [RoundResultBackend]
    func advanceRound(code: String) async throws -> [RoundResultBackend]
    func getResults(code: String) async throws -> [Int: [RoundResultBackend]]
}

// MARK: - Leaderboard Repository

protocol LeaderboardRepository: Sendable {
    func getLeaderboard(code: String) async throws -> [LeaderboardEntryBackend]
    func exportGrades(code: String) async throws -> String
    func exportLeaderboard(code: String) async throws -> String
}
