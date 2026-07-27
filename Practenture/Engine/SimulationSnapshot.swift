// SimulationSnapshot.swift
// Practenture
//
// Plain Sendable value types for background-thread simulation.
// Breaks the @Model/@Observable coupling so the engine can run
// off the main thread without Swift 6 concurrency violations.

import Foundation

/// Immutable snapshot of all data SimulationEngine.processRound() needs.
/// Created on the main thread, consumed on a background thread.
struct SimulationSnapshot: Sendable {
    let config: SessionConfiguration
    let currentRound: Int
    let teams: [TeamStatus]
    let decisions: [UUID: PlayerDecision]
    let previousRoundDecisions: [UUID: PlayerDecision]
    let roundResults: [UUID: [Int: RoundResult]]
}

/// A team status update produced by the simulation, to be applied
/// back to the @Model SimulationSession on the main thread.
struct TeamUpdate: Sendable {
    let teamId: UUID
    let cash: Double
    let inventory: Int
    let sqRating: Double
    let imageRating: Double
    let creditRating: CreditRating
    let reputation: Double
    let equity: Double
    let totalDebt: Double
    let sharesOutstanding: Int
    let cumulativeRD: Double
    let cumulativeMarketing: Double
    let cumulativeCSR: Double
    let cumulativeTQM: Double
    let cumulativeProfit: Double
    let cumulativeInvestorScore: Double
    let roundsScored: Int
    let hasSubmittedDecisions: Bool
    let rank: Int
}

/// All output from processing one round, to be applied on the main thread.
struct RoundOutput: Sendable {
    let round: Int
    let results: [RoundResult]
    let explanations: [ResultExplanation]
    let teamUpdates: [TeamUpdate]
    let updatedRoundResults: [UUID: [Int: RoundResult]]
}
