// NetworkService.swift
// BizSimAI
//
// REST client for the FastAPI backend.
// Handles all HTTP communication with async/await, JSON encoding/decoding,
// custom error handling, automatic retry on transient failures, and configurable timeout.

import Foundation

// MARK: - Network Error

enum NetworkError: Error, LocalizedError {
    case invalidURL
    case decodingError
    case serverError(Int, String)
    case noData
    case timeout
    case connectionFailed

    var errorDescription: String? {
        switch self {
        case .invalidURL:
            return "Invalid URL. Please check your connection settings."
        case .decodingError:
            return "Failed to decode response from the server."
        case .serverError(let code, let message):
            return "Server error (\(code)): \(message)"
        case .noData:
            return "No data received from the server."
        case .timeout:
            return "Request timed out. Please check your connection."
        case .connectionFailed:
            return "Could not connect to the server. Please check your connection settings."
        }
    }
}

// MARK: - Network Service

@Observable
final class NetworkService {

    static let shared = NetworkService()

    /// Environment-aware base URL. Single source of truth: Info.plist BIZSIMAI_BACKEND_URL key.
    /// Falls back to EC2 IP only if plist key is missing (never at runtime).
    var baseURL: String {
        if let plistURL = Bundle.main.object(forInfoDictionaryKey: "BIZSIMAI_BACKEND_URL") as? String, !plistURL.isEmpty {
            return plistURL
        }
        // Only default to EC2 — no env var fallback (prevents config drift)
        return "http://18.215.180.58:80"
    }

    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder

    // MARK: - Token Refresh

    /// Request body for POST /api/auth/refresh.
    private struct RefreshTokenRequest: Encodable {
        let refreshToken: String
        
        enum CodingKeys: String, CodingKey {
            case refreshToken = "refreshToken"
        }
    }

    /// Lock to serialise concurrent refresh attempts.
    private let refreshLock = NSLock()
    /// Holds any in-flight refresh Task so concurrent 401s share the same refresh.
    private var refreshTask: Task<String, Error>?

    /// Refresh the access token via /api/auth/refresh.
    /// Concurrent callers coalesce — only one refresh HTTP call is made; others await the same result.
    func refreshToken() async throws -> String {
        // Fast path: if a refresh is already in flight, await it.
        refreshLock.lock()
        if let existing = refreshTask {
            refreshLock.unlock()
            return try await existing.value
        }

        // Start a new refresh task.
        // Uses performRequest with retryingAfterRefresh=true so a 401 on the
        // refresh endpoint itself does NOT trigger another refresh (preventing infinite recursion).
        let task = Task<String, Error> { [keychain = KeychainWrapper()] in
            guard let refreshToken = keychain.string(forKey: "refresh_token") else {
                throw AuthError.tokenExpired
            }
            let request = RefreshTokenRequest(refreshToken: refreshToken)
            // Bypass the public post() to avoid double 401 handling.
            let response: AuthLoginResponse = try await self.performRequest(
                method: "POST",
                endpoint: "/api/auth/refresh",
                body: request,
                retryingAfterRefresh: true
            )

            // Persist new tokens to Keychain (single source of truth)
            keychain.set(response.accessToken, forKey: "jwt_token")
            if let rt = response.refreshToken {
                keychain.set(rt, forKey: "refresh_token")
            }
            return response.accessToken
        }

        refreshTask = task
        refreshLock.unlock()

        do {
            let newToken = try await task.value
            refreshLock.lock()
            refreshTask = nil
            refreshLock.unlock()
            return newToken
        } catch {
            refreshLock.lock()
            refreshTask = nil
            refreshLock.unlock()
            throw error
        }
    }

    private init(timeout: TimeInterval = 15) {
        let config = URLSessionConfiguration.default
        let cache = URLCache(memoryCapacity: 10 * 1024 * 1024, diskCapacity: 50 * 1024 * 1024, directory: nil)
        config.urlCache = cache
        config.requestCachePolicy = .returnCacheDataElseLoad
        config.timeoutIntervalForRequest = timeout
        config.timeoutIntervalForResource = timeout
        config.waitsForConnectivity = true
        self.session = URLSession(configuration: config)

        self.encoder = JSONEncoder()
        self.encoder.keyEncodingStrategy = .convertToSnakeCase

        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    // MARK: - HTTP Methods

    func get<T: Decodable>(_ endpoint: String) async throws -> T {
        try await request(method: "GET", endpoint: endpoint, body: nil)
    }

    func post<T: Decodable, B: Encodable>(_ endpoint: String, body: B) async throws -> T {
        try await request(method: "POST", endpoint: endpoint, body: body)
    }

    func post<T: Decodable>(_ endpoint: String) async throws -> T {
        try await request(method: "POST", endpoint: endpoint, body: nil as Encodable?)
    }

    func put<T: Decodable, B: Encodable>(_ endpoint: String, body: B) async throws -> T {
        try await request(method: "PUT", endpoint: endpoint, body: body)
    }

    func delete(_ endpoint: String) async throws {
        try await requestVoid(method: "DELETE", endpoint: endpoint, body: nil)
    }

    func postVoid(_ endpoint: String, body: Encodable? = nil) async throws {
        try await requestVoid(method: "POST", endpoint: endpoint, body: body)
    }

    /// POST that returns a raw JSON dictionary (for endpoints with dynamic responses)
    func postRaw(_ endpoint: String, body: Encodable? = nil) async throws -> [String: Any] {
        let data = try await requestRaw(method: "POST", endpoint: endpoint, body: body)
        guard let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else {
            return [:]
        }
        return json
    }

    // MARK: - Void Request (no response body decoding)

    private func requestVoid(
        method: String,
        endpoint: String,
        body: Encodable?
    ) async throws {
        var lastError: Error?

        // Try up to 2 times (1 retry) for transient failures
        for attempt in 0...1 {
            if attempt > 0 {
                // 2 second delay before retry
                try await Task.sleep(nanoseconds: 2_000_000_000)
            }

            do {
                return try await performVoidRequest(method: method, endpoint: endpoint, body: body)
            } catch let error as NetworkError {
                // Don't retry on client errors (4xx except timeout/429/5xx)
                if case .serverError(let code, _) = error,
                   !(code == 408 || code == 429 || code >= 500) {
                    throw error
                }
                lastError = error
            } catch {
                lastError = error
            }
        }

        throw lastError ?? NetworkError.connectionFailed
    }

    private func performVoidRequest(
        method: String,
        endpoint: String,
        body: Encodable?,
        retryingAfterRefresh: Bool = false
    ) async throws {
        guard let url = URL(string: baseURL + endpoint) else {
            throw NetworkError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Auto-attach auth token from AuthManager if available
        if let token = AuthManager.shared.accessToken, !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        // Encode body
        if let body = body {
            request.httpBody = try encoder.encode(body)
        }

        let (data, response) = try await session.data(for: request)

        // Check response
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.noData
        }

        // Handle 401 — attempt token refresh and retry once
        if httpResponse.statusCode == 401 && !retryingAfterRefresh {
            do {
                let newToken = try await refreshToken()
                request.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                return try await performVoidRequest(method: method, endpoint: endpoint, body: body, retryingAfterRefresh: true)
            } catch {
                // Refresh failed — force logout and surface the error
                await AuthManager.shared.logout()
                throw NetworkError.serverError(401, "Session expired. Please log in again.")
            }
        }

        // Handle success
        if (200...299).contains(httpResponse.statusCode) {
            return
        }

        // Handle error responses — extract detail from JSON body
        let errorBody = String(data: data, encoding: .utf8) ?? "Unknown server error"
        var detail = errorBody
        if let jsonData = errorBody.data(using: .utf8),
           let json = try? JSONSerialization.jsonObject(with: jsonData) as? [String: Any],
           let msg = json["detail"] as? String {
            detail = msg
        }
        throw NetworkError.serverError(httpResponse.statusCode, detail)
    }

    // MARK: - Core Request with Retry

    private func request<T: Decodable>(
        method: String,
        endpoint: String,
        body: Encodable?
    ) async throws -> T {
        var lastError: Error?

        // Try up to 2 times (1 retry) for transient failures
        for attempt in 0...1 {
            if attempt > 0 {
                // 2 second delay before retry
                try await Task.sleep(nanoseconds: 2_000_000_000)
            }

            do {
                return try await performRequest(method: method, endpoint: endpoint, body: body)
            } catch let error as NetworkError {
                // Don't retry on client errors (4xx except timeout/429/5xx)
                if case .serverError(let code, _) = error,
                   !(code == 408 || code == 429 || code >= 500) {
                    throw error
                }
                lastError = error
            } catch {
                lastError = error
            }
        }

        throw lastError ?? NetworkError.connectionFailed
    }

    private func performRequest<T: Decodable>(
        method: String,
        endpoint: String,
        body: Encodable?,
        retryingAfterRefresh: Bool = false
    ) async throws -> T {
        guard let url = URL(string: baseURL + endpoint) else {
            throw NetworkError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        // Auto-attach auth token from AuthManager if available
        if let token = AuthManager.shared.accessToken, !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        // Encode body
        if let body = body {
            request.httpBody = try encoder.encode(body)
        }

        let (data, response) = try await session.data(for: request)

        // Check response
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.noData
        }

        // Handle 401 — attempt token refresh and retry once
        if httpResponse.statusCode == 401 && !retryingAfterRefresh {
            do {
                let newToken = try await refreshToken()
                request.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                return try await performRequest(method: method, endpoint: endpoint, body: body, retryingAfterRefresh: true)
            } catch {
                // Refresh failed — force logout and surface the error
                await AuthManager.shared.logout()
                throw NetworkError.serverError(401, "Session expired. Please log in again.")
            }
        }

        // Handle success
        if (200...299).contains(httpResponse.statusCode) {
            guard !data.isEmpty else {
                throw NetworkError.noData
            }
            do {
                let decoded = try decoder.decode(T.self, from: data)
                return decoded
            } catch {
                throw NetworkError.decodingError
            }
        }

        // Handle error responses
        let errorMsg = String(data: data, encoding: .utf8) ?? "Unknown server error"
        throw NetworkError.serverError(httpResponse.statusCode, errorMsg)
    }

    // MARK: - Raw Request (returns Data, for dynamic JSON responses)

    private func requestRaw(
        method: String,
        endpoint: String,
        body: Encodable?
    ) async throws -> Data {
        guard let url = URL(string: baseURL + endpoint) else {
            throw NetworkError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")

        if let token = AuthManager.shared.accessToken, !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }

        if let body = body {
            request.httpBody = try encoder.encode(body)
        }

        let (data, response) = try await session.data(for: request)

        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.noData
        }

        if httpResponse.statusCode == 401 {
            do {
                let newToken = try await refreshToken()
                request.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                let (retryData, _) = try await session.data(for: request)
                return retryData
            } catch {
                await AuthManager.shared.logout()
                throw NetworkError.serverError(401, "Session expired. Please log in again.")
            }
        }

        if (200...299).contains(httpResponse.statusCode) {
            return data
        }

        let errorMsg = String(data: data, encoding: .utf8) ?? "Unknown server error"
        throw NetworkError.serverError(httpResponse.statusCode, errorMsg)
    }

    // MARK: - Session Operations

    func createSession(config: SessionConfiguration, teams: [TeamConfig]) async throws -> SessionBackend {
        let request = CreateSessionRequestBackend(
            config: config.toBackendConfig(),
            teams: teams.map { $0.toBackend() },
            createdBy: "professor",
            maxHumanTeams: config.maxHumanTeams
        )
        let response: CreateSessionResponseBackend = try await post("/api/sessions", body: request)
        // Return a SessionBackend built from the response
        return SessionBackend(code: response.code)
    }

    func getSession(byCode code: String) async throws -> SessionBackend {
        let response: SessionBackend = try await get("/api/sessions/\(code)")
        return response
    }

    func joinSession(code: String, teamName: String, studentId: String) async throws -> JoinSessionBackend {
        let request = JoinRequestBackend(teamName: teamName, studentId: studentId)
        return try await put("/api/sessions/\(code)/join", body: request)
    }

    func getTeams(code: String) async throws -> [TeamConfigBackend] {
        // Backend returns list of TeamConfig in /teams or within session
        let session: SessionBackend = try await get("/api/sessions/\(code)")
        return session.teams
    }

    func getSessionStatus(code: String) async throws -> SessionStatusBackend {
        try await get("/api/sessions/\(code)/status")
    }

    func endSession(code: String) async throws {
        try await postVoid("/api/sessions/\(code)/end")
    }

    func startSession(code: String) async throws {
        try await postVoid("/api/sessions/\(code)/start")
    }

    func deleteSession(code: String) async throws {
        try await delete("/api/sessions/\(code)")
    }

    // MARK: - Decision Operations

    func submitDecision(code: String, round: Int, teamId: UUID, decision: PlayerDecision, backendTeamId: String? = nil) async throws {
        let backendDecision = decision.toBackendDecision()
        // Backend expects team name as teamId string, not a UUID.
        // Use backendTeamId if provided (from join response), otherwise fall back to uuidString.
        let teamIdString = backendTeamId ?? teamId.uuidString
        let request = SubmitDecisionRequestBackend(
            round: round,
            teamId: teamIdString,
            decision: backendDecision
        )
        try await postVoid("/api/sessions/\(code)/submit_decision", body: request)
    }

    func getDecisions(code: String, round: Int) async throws -> [String: PlayerDecision] {
        // Backend returns {sessionId, round, decisions: [teamId: PlayerDecision]}
        let response: DecisionsResponseBackend = try await get("/api/sessions/\(code)/decisions/\(round)")
        var result: [String: PlayerDecision] = [:]
        for (teamId, backendDecision) in response.decisions {
            if let decision = backendDecision.toPlayerDecision() {
                result[teamId] = decision
            }
        }
        return result
    }

    func processRound(code: String) async throws -> [RoundResultBackend] {
        // POST to process the round — backend returns {round, results}
        // and internally advances currentRound. We must NOT call advance separately.
        let response: ProcessRoundResponseBackend = try await post("/api/sessions/\(code)/process_round", body: EmptyBody())
        return response.results
    }

    func advanceRound(code: String) async throws -> [RoundResultBackend] {
        // POST to advance to next round, then GET results from /results
        try await postVoid("/api/sessions/\(code)/advance")
        let results: [RoundResultBackend] = try await get("/api/sessions/\(code)/results")
        return results
    }

    // MARK: - Results and Leaderboard

    func getResults(code: String) async throws -> [Int: [RoundResultBackend]] {
        let results: [RoundResultBackend] = try await get("/api/sessions/\(code)/results")
        var grouped: [Int: [RoundResultBackend]] = [:]
        for result in results {
            grouped[result.round, default: []].append(result)
        }
        return grouped
    }

    /// Get round results for a specific team and round
    func getResultsForTeam(code: String, teamId: UUID, round: Int) async throws -> [RoundResultBackend] {
        let allResults = try await getResults(code: code)
        return allResults[round]?.filter { $0.teamId == teamId.uuidString } ?? []
    }

    func getLeaderboard(code: String) async throws -> [LeaderboardEntryBackend] {
        let response: LeaderboardResponseBackend = try await get("/api/sessions/\(code)/leaderboard")
        return response.leaderboard
    }

    // MARK: - Announcements

    func sendAnnouncement(code: String, message: String, authorId: String, authorName: String) async throws {
        let request = SendAnnouncementRequestBackend(message: message, authorId: authorId, authorName: authorName)
        try await postVoid("/api/sessions/\(code)/announcements", body: request)
    }

    func getAnnouncements(code: String) async throws -> [AnnouncementBackend] {
        try await get("/api/sessions/\(code)/announcements")
    }

    // MARK: - Professor Dashboard Sessions

    /// Backend response for dashboard session list item.
    struct DashboardSessionResponse: Codable, Identifiable {
        var id: String { code }
        var code: String = ""
        var state: String = "creating"
        var currentRound: Int = 0
        var totalRounds: Int = 20
        var teamsCount: Int = 0
        var aiTeamsCount: Int = 0
        var totalTeams: Int = 0
        var totalSubmissions: Int = 0
        var lastRound: Int = 0
    }

    /// Backend wraps the session list in {"sessions": [...]} — decode the wrapper.
    private struct DashboardSessionListWrapper: Codable {
        var sessions: [DashboardSessionResponse]
    }

    /// Fetch all sessions for the professor dashboard.
    func getDashboardSessions() async throws -> [DashboardSessionResponse] {
        // Backend returns {"sessions": [...]} (wrapped object), not a bare array.
        // Try wrapped decode first; fall back to bare array for older backends.
        do {
            let wrapper: DashboardSessionListWrapper = try await get("/api/dashboard/sessions")
            return wrapper.sessions
        } catch {
            // Older backend may return bare array
            return try await get("/api/dashboard/sessions")
        }
    }

    // MARK: - Grade Export

    /// Fetch grade export CSV as string (for parsing or download).
    func exportGrades(code: String, retryingAfterRefresh: Bool = false) async throws -> String {
        guard let url = URL(string: baseURL + "/api/sessions/\(code)/export/grades") else {
            throw NetworkError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        if let token = AuthManager.shared.accessToken, !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.serverError(0, "Connection failed")
        }

        // Handle 401 — attempt token refresh and retry once
        if httpResponse.statusCode == 401 && !retryingAfterRefresh {
            do {
                let newToken = try await refreshToken()
                request.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                return try await exportGrades(code: code, retryingAfterRefresh: true)
            } catch {
                await AuthManager.shared.logout()
                throw NetworkError.serverError(401, "Session expired. Please log in again.")
            }
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw NetworkError.serverError(httpResponse.statusCode, "Connection failed")
        }
        guard let csv = String(data: data, encoding: .utf8) else {
            throw NetworkError.decodingError
        }
        return csv
    }

    /// Fetch leaderboard export CSV as string.
    func exportLeaderboard(code: String, retryingAfterRefresh: Bool = false) async throws -> String {
        guard let url = URL(string: baseURL + "/api/sessions/\(code)/export/leaderboard") else {
            throw NetworkError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        if let token = AuthManager.shared.accessToken, !token.isEmpty {
            request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        }
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.serverError(0, "Connection failed")
        }

        // Handle 401 — attempt token refresh and retry once
        if httpResponse.statusCode == 401 && !retryingAfterRefresh {
            do {
                let newToken = try await refreshToken()
                request.setValue("Bearer \(newToken)", forHTTPHeaderField: "Authorization")
                return try await exportLeaderboard(code: code, retryingAfterRefresh: true)
            } catch {
                await AuthManager.shared.logout()
                throw NetworkError.serverError(401, "Session expired. Please log in again.")
            }
        }

        guard (200...299).contains(httpResponse.statusCode) else {
            throw NetworkError.serverError(httpResponse.statusCode, "Connection failed")
        }
        guard let csv = String(data: data, encoding: .utf8) else {
            throw NetworkError.decodingError
        }
        return csv
    }

    // MARK: - Health Check

    func healthCheck() async -> Bool {
        do {
            let _: HealthCheckResponse = try await get("/api/health")
            return true
        } catch {
            return false
        }
    }
    
    // MARK: - Auth Methods (Phase 5)
    
    func authLogin(provider: String, username: String? = nil, password: String? = nil, idToken: String? = nil) async throws -> AuthLoginResponse {
        let request = AuthLoginRequest(
            provider: provider,
            username: username,
            password: password,
            idToken: idToken
        )
        return try await post("/api/auth/login", body: request)
    }
    
    func authRegister(username: String, password: String, studentId: String, name: String) async throws -> AuthLoginResponse {
        let request = AuthRegisterRequest(
            studentId: studentId,
            name: name,
            password: password
        )
        return try await post("/api/auth/register", body: request)
    }
}

/// Backend session response (from /api/sessions/{code}).
struct SessionBackend: Codable {
    var id: String = ""
    var code: String = ""
    var config: SessionConfigBackend = SessionConfigBackend()
    var teams: [TeamConfigBackend] = []
    var currentRound: Int = 0
    var state: String = "creating"
    var results: [String: [RoundResultBackend]] = [:]
    var createdBy: String = ""
}

/// Backend session configuration.
struct SessionConfigBackend: Codable {
    var totalRounds: Int = 20
    var numberOfAICompetitors: Int = 3
    var randomSeed: Int = 42
    var startingCash: Double = 500000
    var initialEquity: Double = 300000
    var plantCapacity: Int = 10000
    var maxOvertimePercent: Int = 25
    var minWage: Double = 12000
    var maxWage: Double = 40000
    var minDividend: Double = 0
    var maxDividend: Double = 5
}

/// Backend team config for multiplayer.
struct TeamConfigBackend: Codable, Identifiable {
    var id: String { teamName }
    var teamName: String
    var isAI: Bool = false
    var aiStrategy: String?
    var studentId: String?
}

/// Backend team config as sent from iOS to backend (preserves iOS ID).
struct TeamConfig: Codable {
    var id: UUID
    var name: String
    var isAI: Bool = false
    var playerName: String?
    var studentId: String?
    /// Backend uses team name as teamId (not UUID). Stored here so
    /// submit_decision can send the correct identifier back to the API.
    var backendTeamId: String?
}

/// Backend session status response (from /status).
struct SessionStatusBackend: Codable {
    var sessionId: String = ""
    var code: String = ""
    var state: String = "creating"
    var currentRound: Int = 0
    var totalRounds: Int = 0
    var teamsSubmitted: Int = 0
    var totalTeams: Int = 0
}

/// Backend round result.
struct RoundResultBackend: Codable {
    var teamId: String = ""
    var round: Int = 0
    var revenue: Double = 0
    var costs: Double = 0
    var profit: Double = 0
    var marketShare: Double = 0
    var sqRating: Double = 0
    var reputation: Double = 0
    var cumulativeProfit: Double = 0
    var cash: Double = 0
    var inventory: Double = 0
    var equity: Double = 0
    var debt: Double = 0
    var sharesOutstanding: Double = 0
    var eps: Double = 0
    var roe: Double = 0
    var stockPrice: Double = 0
    var epsScore: Double = 0
    var roeScore: Double = 0
    var stockPriceScore: Double = 0
    var imageScore: Double = 0
    var creditScore: Double = 0
    var totalScore: Double = 0
    var productionCost: Double = 0
    var marketingCost: Double = 0
    var unitCost: Double = 0
}

/// Backend leaderboard entry.
struct LeaderboardEntryBackend: Codable, Identifiable {
    var id: String { teamName }
    var teamName: String = ""
    var studentName: String?
    var totalScore: Double = 0
    var eps: Double = 0
    var roe: Double = 0
    var stockPrice: Double = 0
    var imageRating: Double = 0
    var creditRating: Double = 0
    var cumulativeProfit: Double = 0
    var rank: Int = 0
}

/// Backend announcement.
struct AnnouncementBackend: Codable, Identifiable {
    var id: String = ""
    var sessionId: String = ""
    var message: String = ""
    var authorId: String = ""
    var authorName: String = ""
    var timestamp: String = ""
    var roundNumber: Int? = nil
}

// MARK: - Backend Request/Response Models

struct CreateSessionRequestBackend: Encodable {
    var config: SessionConfigBackend
    var teams: [TeamConfigBackend] = []
    var createdBy: String = "professor"
    var maxHumanTeams: Int = 30
}

struct CreateSessionResponseBackend: Codable {
    var sessionId: String = ""
    var code: String = ""
}

struct JoinRequestBackend: Encodable {
    var teamName: String
    var studentId: String
}

struct JoinSessionBackend: Codable {
    var teamId: String = ""
    var teamName: String = ""
    var round: Int = 0
    var state: String = ""
}

struct SubmitDecisionRequestBackend: Encodable {
    var round: Int
    var teamId: String
    var decision: PlayerDecisionBackend
}

struct SubmitDecisionResponseBackend: Codable {
    var status: String = ""
    var round: Int = 0
    var teamId: String = ""
}

struct DecisionsResponseBackend: Codable {
    var sessionId: String = ""
    var round: Int = 0
    var decisions: [String: PlayerDecisionBackend] = [:]
}

struct HealthCheckResponse: Codable {}

/// Empty body for POST endpoints that don't need a request body.
struct EmptyBody: Encodable {}

/// Response from POST /api/sessions/{code}/process_round
struct ProcessRoundResponseBackend: Decodable {
    var round: Int = 0
    var results: [RoundResultBackend] = []
}

struct LeaderboardResponseBackend: Codable {
    var sessionId: String = ""
    var round: Int = 0
    var leaderboard: [LeaderboardEntryBackend] = []
}

struct SendAnnouncementRequestBackend: Encodable {
    var message: String
    var authorId: String = "professor"
    var authorName: String = "Professor"
}

// MARK: - Backend ↔ iOS Decision Conversion

/// Simplified backend decision model matching the FastAPI pydantic model.
struct PlayerDecisionBackend: Codable {
    var wholesalePrice: Double = 28
    var internetPrice: Double = 30
    var amazonPrice: Double = 32
    var materialsQuality: Double = 0.5   // 0-1 scale
    var stylingBudget: Double = 100000
    var numModels: Int = 2
    var tqmInvestment: Double = 0
    var rdInvestment: Double = 0
    var marketingInvestment: Double = 150000
    var advertisingBudget: Double = 80000
    var celebrityType: String = "none"
    var socialMediaBudget: SocialMediaBudgetBackend = SocialMediaBudgetBackend()
    var baseWage: Double = 25000
    var incentivePay: Double = 0
    var trainingBudget: Double = 0
    var productionQuantity: Int = 8000
    var overtimePercent: Int = 0
    var csrInvestment: Double = 0
    var dividendsPerShare: Double = 0
    var newLoanAmount: Double = 0
    var sharesBuyback: Int = 0
    var sharesIssued: Int = 0
    var retailOutlets: Int = 0
    var fulfillmentMethod: String = "fbm"
    var internetPromotion: Double = 0
}

struct SocialMediaBudgetBackend: Codable {
    var tiktok: Double = 0
    var instagram: Double = 0
    var youtube: Double = 0
}

// MARK: - Conversion Extensions

extension SessionConfiguration {
    func toBackendConfig() -> SessionConfigBackend {
        SessionConfigBackend(
            totalRounds: totalRounds,
            numberOfAICompetitors: numberOfAICompetitors,
            randomSeed: Int(min(randomSeed, UInt64(Int.max))),
            startingCash: startingCash,
            initialEquity: initialEquity,
            plantCapacity: plantCapacity,
            maxOvertimePercent: 25,
            minWage: 12000,
            maxWage: 40000,
            minDividend: 0,
            maxDividend: 5
        )
    }
}

extension TeamConfig {
    func toBackend() -> TeamConfigBackend {
        TeamConfigBackend(
            teamName: name,
            isAI: false,
            studentId: studentId
        )
    }
}

extension MaterialsQuality {
    var backendValue: Double {
        switch self {
        case .standard: return 0.5
        case .superior: return 1.0
        }
    }
}

extension CelebrityEndorsement {
    var backendValue: String {
        switch self {
        case .none: return "none"
        case .local: return "athlete"
        case .national: return "musician"
        case .global: return "actor"
        }
    }
}

extension InfluencerTier {
    var backendValue: String {
        switch self {
        case .none: return "none"
        case .nano: return "social_influencer"
        case .micro: return "social_influencer"
        case .macro: return "social_influencer"
        case .mega: return "social_influencer"
        }
    }
}

extension DeliveryTime {
    var backendValue: String {
        switch self {
        case .standard: return "fbm"
        case .rush: return "fbm"
        }
    }
}

extension FulfillmentMethod {
    var backendValue: String {
        switch self {
        case .fba: return "fba"
        case .fbm: return "fbm"
        }
    }
}

extension PlayerDecision {
    func toBackendDecision() -> PlayerDecisionBackend {
        PlayerDecisionBackend(
            wholesalePrice: pricing.wholesalePrice,
            internetPrice: pricing.internetPrice,
            amazonPrice: pricing.amazonPrice,
            materialsQuality: materialsQuality.backendValue,
            stylingBudget: stylingBudget,
            numModels: modelsOffered,
            tqmInvestment: tqmInvestment,
            rdInvestment: rdInvestment,
            marketingInvestment: marketing.advertisingBudget,
            advertisingBudget: marketing.advertisingBudget,
            celebrityType: celebrityEndorsement.backendValue,
            socialMediaBudget: SocialMediaBudgetBackend(
                tiktok: tiktokBudget,
                instagram: instagramBudget,
                youtube: youtubeBudget
            ),
            baseWage: baseWage,
            incentivePay: incentivePay,
            trainingBudget: trainingHours * 50,
            productionQuantity: productionQuantity,
            overtimePercent: Int(overtimePercent),
            csrInvestment: csrInvestment,
            dividendsPerShare: dividendsPerShare,
            newLoanAmount: newLoanAmount,
            sharesBuyback: sharesBuyback,
            sharesIssued: sharesIssued,
            retailOutlets: retailOutlets,
            fulfillmentMethod: fulfillmentMethod.backendValue,
            internetPromotion: 0
        )
    }
}

extension PlayerDecisionBackend {
    func toPlayerDecision() -> PlayerDecision? {
        PlayerDecision(
            teamId: UUID(),
            round: 0,
            pricing: PricingDecision(
                wholesalePrice: wholesalePrice,
                internetPrice: internetPrice,
                privateLabelBidPrice: wholesalePrice * 0.6,
                privateLabelMaxUnits: 50,
                amazonPrice: amazonPrice,
                amazonAdBudget: 0
            ),
            product: ProductDecision(
                materialsQuality: materialsQuality > 0.75 ? .superior : .standard,
                stylingBudget: stylingBudget,
                modelsOffered: max(1, numModels),
                tqmInvestment: tqmInvestment
            ),
            marketing: MarketingDecision(
                advertisingBudget: advertisingBudget,
                tiktokBudget: socialMediaBudget.tiktok,
                instagramBudget: socialMediaBudget.instagram,
                youtubeBudget: socialMediaBudget.youtube
            ),
            workforce: WorkforceDecision(
                baseWage: baseWage,
                incentivePay: incentivePay,
                trainingHours: max(0, trainingBudget / 50),
                bestPracticesInvestment: 0
            ),
            production: ProductionDecision(
                productionQuantity: productionQuantity,
                overtimePercent: Double(overtimePercent)
            ),
            finance: FinanceDecision(
                csrInvestment: csrInvestment,
                dividendsPerShare: dividendsPerShare,
                newLoanAmount: newLoanAmount,
                sharesBuyback: sharesBuyback,
                sharesIssued: sharesIssued
            )
        )
    }
}
