// LeaderboardRepositoryImpl.swift
// BizSimAI
//
// Concrete implementation of LeaderboardRepository.
// Delegates to NetworkService.shared for all leaderboard and export operations.

import Foundation

@MainActor
final class LeaderboardRepositoryImpl: LeaderboardRepository {

    private let network = NetworkService.shared

    func getLeaderboard(code: String) async throws -> [LeaderboardEntryBackend] {
        try await network.getLeaderboard(code: code)
    }

    func exportGrades(code: String) async throws -> String {
        try await network.exportGrades(code: code)
    }

    func exportLeaderboard(code: String) async throws -> String {
        try await network.exportLeaderboard(code: code)
    }
}
