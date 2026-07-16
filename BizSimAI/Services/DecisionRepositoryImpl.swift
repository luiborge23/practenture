// DecisionRepositoryImpl.swift
// BizSimAI
//
// Concrete implementation of DecisionRepository.
// Delegates to NetworkService.shared for all decision operations.

import Foundation

@MainActor
final class DecisionRepositoryImpl: DecisionRepository {

    private let network = NetworkService.shared

    func submit(code: String, round: Int, backendTeamId: String, decision: PlayerDecision) async throws {
        try await network.submitDecision(
            code: code, round: round, decision: decision, backendTeamId: backendTeamId
        )
    }

    func submit(code: String, round: Int, teamId: UUID, decision: PlayerDecision) async throws {
        // A local UUID is not a valid backend team identity. Refuse this legacy API
        // rather than silently submitting under the wrong identifier.
        throw NetworkError.serverError(
            400,
            "Backend team identity is missing. Leave and join the session again."
        )
    }

    func getDecisions(code: String, round: Int) async throws -> [String: PlayerDecision] {
        try await network.getDecisions(code: code, round: round)
    }

    func processRound(code: String) async throws -> [RoundResultBackend] {
        try await network.processRound(code: code)
    }

    func advanceRound(code: String) async throws -> [RoundResultBackend] {
        // Compatibility method: process_round already advances backend state.
        // Never call the removed legacy /advance endpoint.
        try await network.processRound(code: code)
    }

    func getResults(code: String) async throws -> [Int: [RoundResultBackend]] {
        try await network.getResults(code: code)
    }
}
