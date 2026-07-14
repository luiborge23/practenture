// SessionRepositoryImpl.swift
// BizSimAI
//
// Concrete implementation of SessionRepository.
// Delegates to NetworkService.shared for all session operations.

import Foundation

@MainActor
final class SessionRepositoryImpl: SessionRepository {

    private let network = NetworkService.shared

    func create(config: SessionConfiguration, teams: [TeamConfig]) async throws -> SessionBackend {
        try await network.createSession(config: config, teams: teams)
    }

    func get(code: String) async throws -> SessionBackend {
        try await network.getSession(byCode: code)
    }

    func delete(code: String) async throws {
        try await network.deleteSession(code: code)
    }

    func getStatus(code: String) async throws -> SessionStatusBackend {
        try await network.getSessionStatus(code: code)
    }

    func join(code: String, teamName: String, studentId: String) async throws -> JoinSessionBackend {
        try await network.joinSession(code: code, teamName: teamName, studentId: studentId)
    }

    func getTeams(code: String) async throws -> [TeamConfigBackend] {
        try await network.getTeams(code: code)
    }

    func listDashboard() async throws -> [NetworkService.DashboardSessionResponse] {
        try await network.getDashboardSessions()
    }
}
