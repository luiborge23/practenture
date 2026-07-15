// SyncService.swift
// BizSimAI
//
// Sync service that maps between local SimulationSession and backend data.
// Handles conflict resolution, optimistic updates, and offline-first caching.

import Foundation
import SwiftUI

/// Action to queue for backend sync when offline.
enum SyncAction: Sendable, Identifiable {
    case joinSession(sessionId: String, teamName: String, studentId: String)
    case submitDecision(sessionId: String, round: Int, teamId: UUID, decision: PlayerDecision, backendTeamId: String?)
    case syncResults(sessionId: String)
    case sendAnnouncement(sessionId: String, message: String, authorId: String, authorName: String)

    var id: String {
        switch self {
        case .joinSession(let sessionId, _, _): return "join_\(sessionId)"
        case .submitDecision(let sessionId, let round, let teamId, _, let backendTeamId): return "decision_\(sessionId)_\(round)_\(teamId)"
        case .syncResults(let sessionId): return "results_\(sessionId)"
        case .sendAnnouncement(let sessionId, _, _, _): return "announce_\(sessionId)"
        }
    }
}

@MainActor
@Observable
final class SyncService {

    static let shared = SyncService()

    var isConnected: Bool = false
    var lastSyncTime: Date?
    var syncError: String?
    var isSynced: Bool = false

    private var syncQueue: [SyncAction] = []
    private var syncQueueQueue = DispatchQueue(label: "syncQueue")

    private init() {}

    // MARK: - Session Operations

    func syncSessionCreation(localSession: SimulationSession) async throws -> String {
        let teams: [TeamConfig] = localSession.teams.map { team in
            TeamConfig(
                id: UUID(),
                name: team.name,
                isAI: team.isAI
            )
        }
        let result = try await NetworkService.shared.createSession(
            config: localSession.config,
            teams: teams
        )
        isSynced = true
        lastSyncTime = Date()
        return result.code
    }

    func syncSessionJoin(sessionCode: String, teamName: String, studentId: String) async throws -> JoinSessionBackend {
        let result = try await NetworkService.shared.joinSession(
            code: sessionCode,
            teamName: teamName,
            studentId: studentId
        )
        isSynced = true
        lastSyncTime = Date()
        return result
    }

    // MARK: - Decision Operations

    func syncDecisionSubmission(
        sessionCode: String,
        round: Int,
        teamId: UUID,
        decision: PlayerDecision,
        backendTeamId: String? = nil
    ) async throws {
        try await NetworkService.shared.submitDecision(
            code: sessionCode,
            round: round,
            teamId: teamId,
            decision: decision,
            backendTeamId: backendTeamId
        )
        isSynced = true
        lastSyncTime = Date()
    }

    func syncRoundResults(sessionCode: String) async throws -> [RoundResultBackend] {
        let results = try await NetworkService.shared.getResults(code: sessionCode)
        isSynced = true
        lastSyncTime = Date()
        return results.values.flatMap { $0 }
    }

    func syncLeaderboard(sessionCode: String) async throws -> [LeaderboardEntryBackend] {
        let entries = try await NetworkService.shared.getLeaderboard(code: sessionCode)
        isSynced = true
        lastSyncTime = Date()
        return entries
    }

    func syncAnnouncements(sessionCode: String) async throws -> [AnnouncementBackend] {
        let announcements = try await NetworkService.shared.getAnnouncements(code: sessionCode)
        isSynced = true
        lastSyncTime = Date()
        return announcements
    }

    func syncTeamStatus(sessionCode: String) async throws -> SessionStatusBackend {
        let status = try await NetworkService.shared.getSessionStatus(code: sessionCode)
        isSynced = true
        lastSyncTime = Date()
        return status
    }

    // MARK: - Offline-First Queue

    func queueForSync(_ action: SyncAction) {
        syncQueueQueue.sync {
            syncQueue.append(action)
        }
    }

    func flushSyncQueue() async {
        // Copy queue under dispatch queue safety
        var actionsToFlush: [SyncAction] = []
        syncQueueQueue.sync {
            actionsToFlush = syncQueue
            syncQueue.removeAll()
        }

        // Process sequentially
        for action in actionsToFlush {
            do {
                try await executeSyncAction(action)
            } catch {
                syncError = "Failed to sync: \(UserFriendlyError.message(for: error))"
                // Put it back for later retry
                syncQueueQueue.sync {
                    syncQueue.append(action)
                }
                return
            }
        }

        if !syncQueue.isEmpty {
            syncError = "\(syncQueue.count) actions pending sync"
        }
    }

    private func executeSyncAction(_ action: SyncAction) async throws {
        switch action {
        case .joinSession(let sessionId, let teamName, let studentId):
            _ = try await syncSessionJoin(sessionCode: sessionId, teamName: teamName, studentId: studentId)
        case .submitDecision(let sessionId, let round, let teamId, let decision, let backendTeamId):
            // teamId is UUID for local SwiftData; backendTeamId is the backend's team name string.
            try await NetworkService.shared.submitDecision(
                code: sessionId,
                round: round,
                teamId: teamId,
                decision: decision,
                backendTeamId: backendTeamId
            )
        case .syncResults(let sessionId):
            _ = try await syncRoundResults(sessionCode: sessionId)
        case .sendAnnouncement(let sessionId, let message, let authorId, let authorName):
            try await NetworkService.shared.sendAnnouncement(
                code: sessionId,
                message: message,
                authorId: authorId,
                authorName: authorName
            )
        }
    }

    // MARK: - Connection Check

    func checkConnection() async -> Bool {
        let health = await NetworkService.shared.healthCheck()
        isConnected = health
        return health
    }
}
