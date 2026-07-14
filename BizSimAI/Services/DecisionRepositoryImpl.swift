// DecisionRepositoryImpl.swift
// BizSimAI
//
// Concrete implementation of DecisionRepository.
// Delegates to NetworkService.shared for all decision operations.

import Foundation

@MainActor
final class DecisionRepositoryImpl: DecisionRepository {

    private let network = NetworkService.shared

    func submit(code: String, round: Int, teamId: UUID, decision: PlayerDecision) async throws {
        try await network.submitDecision(code: code, round: round, teamId: teamId, decision: decision)
    }

    func getDecisions(code: String, round: Int) async throws -> [String: PlayerDecision] {
        try await network.getDecisions(code: code, round: round)
    }

    func processRound(code: String) async throws -> [RoundResultBackend] {
        try await network.processRound(code: code)
    }

    func advanceRound(code: String) async throws -> [RoundResultBackend] {
        try await network.advanceRound(code: code)
    }

    func getResults(code: String) async throws -> [Int: [RoundResultBackend]] {
        try await network.getResults(code: code)
    }
}
