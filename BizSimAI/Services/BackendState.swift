// BackendState.swift
// BizSimAI
//
// State management class that tracks the current session's backend state.
// Used by both professor and student views to coordinate with the backend.

import Foundation

enum SessionBackendState {
    case disconnected
    case creating
    case active
    case roundProcessing
    case completed
}

@MainActor
@Observable
final class BackendState {

    static let shared = BackendState()

    var sessionCode: String?
    var isOnline: Bool = false
    var currentRound: Int = 0
    var sessionState: SessionBackendState = .disconnected
    var teamCount: Int = 0
    var submittedCount: Int = 0

    private var pollTask: Task<Void, Never>?
    private let pollInterval: TimeInterval = 5

    private init() {}

    // MARK: - Connect / Disconnect

    func connect(sessionCode: String) async {
        self.sessionCode = sessionCode
        await checkConnection()
        startPolling()
    }

    func disconnect() {
        sessionCode = nil
        isOnline = false
        sessionState = .disconnected
        currentRound = 0
        stopPolling()
    }

    // MARK: - Polling

    private func startPolling() {
        stopPolling()
        pollTask = Task { [weak self] in
            guard let self = self else { return }
            while self.sessionCode != nil {
                try? await Task.sleep(nanoseconds: UInt64(self.pollInterval * 1_000_000_000))
                guard self.sessionCode != nil else { return }
                await self.pollStatus()
            }
        }
    }

    private func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
    }

    func pollStatus() async {
        guard let code = sessionCode else { return }

        do {
            let status = try await NetworkService.shared.getSessionStatus(code: code)
            self.currentRound = status.currentRound
            self.teamCount = status.totalTeams
            self.submittedCount = status.teamsSubmitted

            switch status.state {
            case "creating":
                self.sessionState = .creating
            case "active":
                self.sessionState = .active
            case "completed", "finished":
                self.sessionState = .completed
            default:
                self.sessionState = .active
            }
        } catch {
            self.sessionState = .disconnected
        }
    }

    // MARK: - Connection Check

    func checkConnection() async {
        let health = await NetworkService.shared.healthCheck()
        isOnline = health
        if health, let code = sessionCode {
            try? await pollStatus()
        }
    }

    // MARK: - Sync Actions

    func processRound() async throws {
        guard let code = sessionCode else {
            throw NetworkError.invalidURL
        }
        try await NetworkService.shared.processRound(code: code)
    }

    func submitDecision(code: String, round: Int, teamId: UUID, decision: PlayerDecision) async throws {
        try await NetworkService.shared.submitDecision(
            code: code,
            round: round,
            teamId: teamId,
            decision: decision
        )
    }

    func endSession() async throws {
        guard let code = sessionCode else {
            throw NetworkError.invalidURL
        }
        try await NetworkService.shared.endSession(code: code)
    }
}
