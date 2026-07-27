// MockRepos.swift
// PractentureTests
//
// Mock repository implementations for unit testing.
// Each mock conforms to its respective protocol from RepositoryProtocols.swift
// and supports configurable results and error injection.

import Foundation
@testable import Practenture

// MARK: - MockAuthRepository

final class MockAuthRepository: AuthRepository, @unchecked Sendable {

    // Configurable results
    var loginResult: Result<AuthLoginResponse, Error> = .success(AuthLoginResponse(
        accessToken: "mock_access_token",
        tokenType: "Bearer",
        role: "professor",
        userId: "user123",
        refreshToken: "mock_refresh_token"
    ))

    var registerResult: Result<AuthLoginResponse, Error> = .success(AuthLoginResponse(
        accessToken: "mock_access_token",
        tokenType: "Bearer",
        role: "student",
        userId: "student123",
        refreshToken: "mock_refresh_token"
    ))

    var logoutResult: Result<Void, Error> = .success(())
    var currentTokenResult: String? = "mock_access_token"
    var isAuthenticatedResult: Bool = true
    var currentUserResult: AuthUser? = AuthUser(
        userId: "user123",
        username: "testuser",
        role: "professor",
        studentId: nil,
        name: "Test User"
    )

    // Call tracking
    private(set) var loginCallCount = 0
    private(set) var registerCallCount = 0
    private(set) var logoutCallCount = 0
    private(set) var currentTokenCallCount = 0
    private(set) var isAuthenticatedCallCount = 0
    private(set) var currentUserCallCount = 0

    private(set) var lastLoginProvider: String?
    private(set) var lastLoginUsername: String?
    private(set) var lastLoginPassword: String?
    private(set) var lastLoginIdToken: String?

    private(set) var lastRegisterUsername: String?
    private(set) var lastRegisterPassword: String?
    private(set) var lastRegisterStudentId: String?
    private(set) var lastRegisterName: String?

    func login(provider: String, username: String?, password: String?, idToken: String?) async throws -> AuthLoginResponse {
        loginCallCount += 1
        lastLoginProvider = provider
        lastLoginUsername = username
        lastLoginPassword = password
        lastLoginIdToken = idToken
        return try loginResult.get()
    }

    func register(username: String, password: String, studentId: String, name: String) async throws -> AuthLoginResponse {
        registerCallCount += 1
        lastRegisterUsername = username
        lastRegisterPassword = password
        lastRegisterStudentId = studentId
        lastRegisterName = name
        return try registerResult.get()
    }

    func logout() async {
        logoutCallCount += 1
        if case .failure(let error) = logoutResult {
            // For logout, we don't throw but track the call
            _ = error
        }
    }

    func currentToken() -> String? {
        currentTokenCallCount += 1
        return currentTokenResult
    }

    func isAuthenticated() -> Bool {
        isAuthenticatedCallCount += 1
        return isAuthenticatedResult
    }

    func currentUser() -> AuthUser? {
        currentUserCallCount += 1
        return currentUserResult
    }
}

// MARK: - MockSessionRepository

final class MockSessionRepository: SessionRepository, @unchecked Sendable {

    // Configurable results
    var createResult: Result<SessionBackend, Error> = .success(SessionBackend(code: "TEST01"))
    var getResult: Result<SessionBackend, Error> = .success(SessionBackend(code: "TEST01"))
    var deleteResult: Result<Void, Error> = .success(())
    var getStatusResult: Result<SessionStatusBackend, Error> = .success(SessionStatusBackend(code: "TEST01", state: "active", currentRound: 1, totalRounds: 20, teamsSubmitted: 1, totalTeams: 4))
    var joinResult: Result<JoinSessionBackend, Error> = .success(JoinSessionBackend(teamId: "team1", teamName: "Team A", round: 1, state: "active"))
    var getTeamsResult: Result<[TeamConfigBackend], Error> = .success([
        TeamConfigBackend(teamName: "Team A", isAI: false),
        TeamConfigBackend(teamName: "AI 1", isAI: true, aiStrategy: "aggressive")
    ])
    var listDashboardResult: Result<[NetworkService.DashboardSessionResponse], Error> = .success([
        NetworkService.DashboardSessionResponse(code: "TEST01", state: "active", currentRound: 1, totalRounds: 20, teamsCount: 2, aiTeamsCount: 1, totalTeams: 3, totalSubmissions: 5, lastRound: 1)
    ])

    // Call tracking
    private(set) var createCallCount = 0
    private(set) var getCallCount = 0
    private(set) var deleteCallCount = 0
    private(set) var getStatusCallCount = 0
    private(set) var joinCallCount = 0
    private(set) var getTeamsCallCount = 0
    private(set) var listDashboardCallCount = 0

    private(set) var lastCreateConfig: SessionConfiguration?
    private(set) var lastCreateTeams: [TeamConfig]?
    private(set) var lastGetCode: String?
    private(set) var lastDeleteCode: String?
    private(set) var lastGetStatusCode: String?
    private(set) var lastJoinCode: String?
    private(set) var lastJoinTeamName: String?
    private(set) var lastJoinStudentId: String?
    private(set) var lastGetTeamsCode: String?

    func create(config: SessionConfiguration, teams: [TeamConfig]) async throws -> SessionBackend {
        createCallCount += 1
        lastCreateConfig = config
        lastCreateTeams = teams
        return try createResult.get()
    }

    func get(code: String) async throws -> SessionBackend {
        getCallCount += 1
        lastGetCode = code
        return try getResult.get()
    }

    func delete(code: String) async throws {
        deleteCallCount += 1
        lastDeleteCode = code
        try deleteResult.get()
    }

    func getStatus(code: String) async throws -> SessionStatusBackend {
        getStatusCallCount += 1
        lastGetStatusCode = code
        return try getStatusResult.get()
    }

    func join(code: String, teamName: String, studentId: String) async throws -> JoinSessionBackend {
        joinCallCount += 1
        lastJoinCode = code
        lastJoinTeamName = teamName
        lastJoinStudentId = studentId
        return try joinResult.get()
    }

    func getTeams(code: String) async throws -> [TeamConfigBackend] {
        getTeamsCallCount += 1
        lastGetTeamsCode = code
        return try getTeamsResult.get()
    }

    func listDashboard() async throws -> [NetworkService.DashboardSessionResponse] {
        listDashboardCallCount += 1
        return try listDashboardResult.get()
    }
}

// MARK: - MockDecisionRepository

final class MockDecisionRepository: DecisionRepository, @unchecked Sendable {

    // Configurable results
    var submitResult: Result<Void, Error> = .success(())
    var getDecisionsResult: Result<[String: PlayerDecision], Error> = .success([:])
    var processRoundResult: Result<[RoundResultBackend], Error> = .success([])
    var advanceRoundResult: Result<[RoundResultBackend], Error> = .success([])
    var getResultsResult: Result<[Int: [RoundResultBackend]], Error> = .success([:])

    // Call tracking
    private(set) var submitCallCount = 0
    private(set) var getDecisionsCallCount = 0
    private(set) var processRoundCallCount = 0
    private(set) var advanceRoundCallCount = 0
    private(set) var getResultsCallCount = 0

    private(set) var lastSubmitCode: String?
    private(set) var lastSubmitRound: Int?
    private(set) var lastSubmitTeamId: UUID?
    private(set) var lastSubmitDecision: PlayerDecision?
    private(set) var lastGetDecisionsCode: String?
    private(set) var lastGetDecisionsRound: Int?
    private(set) var lastProcessRoundCode: String?
    private(set) var lastAdvanceRoundCode: String?
    private(set) var lastGetResultsCode: String?

    func submit(code: String, round: Int, teamId: UUID, decision: PlayerDecision) async throws {
        submitCallCount += 1
        lastSubmitCode = code
        lastSubmitRound = round
        lastSubmitTeamId = teamId
        lastSubmitDecision = decision
        try submitResult.get()
    }

    func getDecisions(code: String, round: Int) async throws -> [String: PlayerDecision] {
        getDecisionsCallCount += 1
        lastGetDecisionsCode = code
        lastGetDecisionsRound = round
        return try getDecisionsResult.get()
    }

    func processRound(code: String) async throws -> [RoundResultBackend] {
        processRoundCallCount += 1
        lastProcessRoundCode = code
        return try processRoundResult.get()
    }

    func advanceRound(code: String) async throws -> [RoundResultBackend] {
        advanceRoundCallCount += 1
        lastAdvanceRoundCode = code
        return try advanceRoundResult.get()
    }

    func getResults(code: String) async throws -> [Int: [RoundResultBackend]] {
        getResultsCallCount += 1
        lastGetResultsCode = code
        return try getResultsResult.get()
    }
}

// MARK: - MockLeaderboardRepository

final class MockLeaderboardRepository: LeaderboardRepository, @unchecked Sendable {

    // Configurable results
    var getLeaderboardResult: Result<[LeaderboardEntryBackend], Error> = .success([
        LeaderboardEntryBackend(teamName: "Team A", studentName: "Alice", totalScore: 85, eps: 2.5, roe: 15, stockPrice: 120, imageRating: 75, creditRating: 90, cumulativeProfit: 50000, rank: 1),
        LeaderboardEntryBackend(teamName: "Team B", studentName: "Bob", totalScore: 72, eps: 1.8, roe: 12, stockPrice: 95, imageRating: 65, creditRating: 80, cumulativeProfit: 35000, rank: 2)
    ])
    var exportGradesResult: Result<String, Error> = .success("team,score,eps\nTeam A,85,2.5\nTeam B,72,1.8\n")
    var exportLeaderboardResult: Result<String, Error> = .success("rank,team,score\n1,Team A,85\n2,Team B,72\n")

    // Call tracking
    private(set) var getLeaderboardCallCount = 0
    private(set) var exportGradesCallCount = 0
    private(set) var exportLeaderboardCallCount = 0

    private(set) var lastGetLeaderboardCode: String?
    private(set) var lastExportGradesCode: String?
    private(set) var lastExportLeaderboardCode: String?

    func getLeaderboard(code: String) async throws -> [LeaderboardEntryBackend] {
        getLeaderboardCallCount += 1
        lastGetLeaderboardCode = code
        return try getLeaderboardResult.get()
    }

    func exportGrades(code: String) async throws -> String {
        exportGradesCallCount += 1
        lastExportGradesCode = code
        return try exportGradesResult.get()
    }

    func exportLeaderboard(code: String) async throws -> String {
        exportLeaderboardCallCount += 1
        lastExportLeaderboardCode = code
        return try exportLeaderboardResult.get()
    }
}
