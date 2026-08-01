// BackendState.swift
// Practenture
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
final class BackendState: WebSocketManagerDelegate {

    private struct RealtimePayload: Decodable {
        let type: String
        let state: String?
        let currentRound: Int?
        let round: Int?
        let nextRound: Int?
        let teamCount: Int?
        let submittedCount: Int?
        let message: String?
    }

    static let shared = BackendState()

    var sessionCode: String?
    var isOnline: Bool = false
    var currentRound: Int = 0
    var sessionState: SessionBackendState = .disconnected
    var teamCount: Int = 0
    var submittedCount: Int = 0
    var latestAnnouncement: String?

    private var pollTask: Task<Void, Never>?
    private let pollInterval: TimeInterval = 5
    private var connectionGeneration: UInt = 0

    private init() {}

    // MARK: - Connect / Disconnect

    func connect(sessionCode: String) async {
        connectionGeneration &+= 1
        let generation = connectionGeneration
        WebSocketManager.shared.delegate = nil
        WebSocketManager.shared.disconnect(reason: "Switching session")
        self.sessionCode = sessionCode
        await checkConnection(generation: generation)
        guard generation == connectionGeneration,
              self.sessionCode == sessionCode else { return }
        if isOnline, let token = AuthManager.shared.accessToken {
            WebSocketManager.shared.delegate = self
            WebSocketManager.shared.connect(
                toSession: sessionCode,
                baseURL: NetworkService.shared.baseURL,
                accessToken: token
            )
        }
        guard generation == connectionGeneration,
              self.sessionCode == sessionCode else { return }
        startPolling(generation: generation)
    }

    func disconnect() {
        connectionGeneration &+= 1
        sessionCode = nil
        isOnline = false
        sessionState = .disconnected
        currentRound = 0
        submittedCount = 0
        teamCount = 0
        latestAnnouncement = nil
        WebSocketManager.shared.delegate = nil
        WebSocketManager.shared.disconnect(reason: "Session disconnected")
        stopPolling()
    }

    // MARK: - Polling

    private func startPolling(generation: UInt) {
        stopPolling()
        pollTask = Task { [weak self] in
            guard let self = self else { return }
            while generation == self.connectionGeneration,
                  self.sessionCode != nil {
                try? await Task.sleep(nanoseconds: UInt64(self.pollInterval * 1_000_000_000))
                guard !Task.isCancelled,
                      generation == self.connectionGeneration,
                      self.sessionCode != nil else { return }
                await self.pollStatus(generation: generation)
            }
        }
    }

    private func stopPolling() {
        pollTask?.cancel()
        pollTask = nil
    }

    func pollStatus() async {
        await pollStatus(generation: connectionGeneration)
    }

    private func pollStatus(generation: UInt) async {
        guard generation == connectionGeneration,
              let code = sessionCode else { return }

        do {
            let status = try await NetworkService.shared.getSessionStatus(code: code)
            guard generation == connectionGeneration,
                  sessionCode == code else { return }
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
            guard generation == connectionGeneration,
                  sessionCode == code else { return }
            self.sessionState = .disconnected
        }
    }

    // MARK: - Connection Check

    func checkConnection() async {
        await checkConnection(generation: connectionGeneration)
    }

    private func checkConnection(generation: UInt) async {
        let health = await NetworkService.shared.healthCheck()
        guard generation == connectionGeneration else { return }
        isOnline = health
        if health, sessionCode != nil {
            await pollStatus(generation: generation)
        }
    }

    // MARK: - Real-time Events

    func didReceive(event: WebSocketEvent, from manager: WebSocketManager) {
        switch event {
        case .connected:
            isOnline = true
        case .message(let text):
            applyRealtimePayload(text)
        case .disconnected, .error:
            break // REST polling remains the authoritative fallback.
        }
    }

    private func applyRealtimePayload(_ text: String) {
        guard let data = text.data(using: .utf8),
              let payload = try? JSONDecoder().decode(RealtimePayload.self, from: data)
        else { return }

        if let teamCount = payload.teamCount { self.teamCount = teamCount }
        if let submittedCount = payload.submittedCount { self.submittedCount = submittedCount }

        switch payload.type {
        case "connected", "status":
            if let currentRound = payload.currentRound { self.currentRound = currentRound }
            applySessionState(payload.state)
        case "session_started":
            currentRound = payload.currentRound ?? 1
            submittedCount = 0
            sessionState = .active
        case "round_complete":
            currentRound = payload.nextRound ?? payload.round ?? currentRound
            submittedCount = 0
            applySessionState(payload.state)
        case "session_ended":
            if let currentRound = payload.currentRound { self.currentRound = currentRound }
            sessionState = .completed
        case "announcement":
            latestAnnouncement = payload.message
        default:
            break
        }
    }

    private func applySessionState(_ state: String?) {
        guard let state else { return }
        switch state {
        case "creating": sessionState = .creating
        case "active": sessionState = .active
        case "completed", "finished": sessionState = .completed
        default: break
        }
    }

    // MARK: - Sync Actions

    func processRound() async throws {
        guard let code = sessionCode else {
            throw NetworkError.invalidURL
        }
        _ = try await NetworkService.shared.processRound(code: code)
    }

    func submitDecision(code: String, round: Int, decision: PlayerDecision, backendTeamId: String) async throws {
        try await NetworkService.shared.submitDecision(
            code: code,
            round: round,
            decision: decision,
            backendTeamId: backendTeamId
        )
    }

    func endSession() async throws {
        guard let code = sessionCode else {
            throw NetworkError.invalidURL
        }
        try await NetworkService.shared.endSession(code: code)
    }
}
