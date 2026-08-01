// NetworkService.swift
// Practenture
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
        case .serverError(let code, _):
            // Map HTTP status codes to user-friendly messages
            switch code {
            case 401:
                return "Incorrect username or password. Please try again."
            case 404:
                return "Account not found. Please check your username or contact support."
            case 429:
                return "Too many login attempts. Please wait a few minutes before trying again."
            case 409:
                return "An account with this username already exists. Please use a different one."
            case 500:
                return "A server error occurred. Please try again later."
            case 502, 503, 504:
                return "The server is temporarily unavailable. Please try again later."
            default:
                // For any other status code, show a generic friendly message
                return "An unexpected error occurred. Please try again."
            }
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

    private let baseURLOverride: String?

    /// Environment-aware base URL. Single source of truth: Info.plist PRACTENTURE_BACKEND_URL key.
    /// Falls back to the canonical HTTPS origin if the plist key is unavailable.
    var baseURL: String {
        if let baseURLOverride { return baseURLOverride }
        if let plistURL = Bundle.main.object(forInfoDictionaryKey: "PRACTENTURE_BACKEND_URL") as? String, !plistURL.isEmpty {
            return plistURL
        }
        // Only default to production — no env var fallback (prevents config drift)
        return "https://practenture.com"
    }

    private let session: URLSession
    private let encoder: JSONEncoder
    private let decoder: JSONDecoder
    private let authTokenProvider: @MainActor () -> String?

    // MARK: - Token Refresh

    /// Request body for POST /api/auth/refresh.
    private struct RefreshTokenRequest: Encodable {
        let refreshToken: String
        
        enum CodingKeys: String, CodingKey {
            case refreshToken = "refreshToken"
        }
    }

    /// Lock to serialise concurrent refresh attempts.
    private let refreshLock = NSRecursiveLock()
    /// Holds any in-flight refresh Task so concurrent 401s share the same refresh.
    private var refreshTask: Task<String, Error>?
    /// Identifies the task generation so an older waiter cannot clear a newer task.
    private var refreshTaskID: UUID?
    
    // DEBUG: raw HTTP response for troubleshooting
    @MainActor var lastRawHTTPCode: Int = 0
    @MainActor var lastRawResponse: String = ""

    /// Refresh the access token via /api/auth/refresh.
    /// Concurrent callers coalesce — only one refresh HTTP call is made; others await the same result.
    func refreshToken() async throws -> String {
        // Atomically reuse the in-flight task or install a new one. No lock is
        // held across an await, which is required by Swift 6 and prevents deadlock.
        let (task, taskID): (Task<String, Error>, UUID) = refreshLock.withLock {
            if let existing = refreshTask, let existingID = refreshTaskID {
                return (existing, existingID)
            }

            let newID = UUID()
            // Uses performRequest with retryingAfterRefresh=true so a 401 on the
            // refresh endpoint itself does NOT trigger another refresh.
            let newTask = Task<String, Error> { [keychain = KeychainWrapper()] in
                guard let refreshToken = keychain.string(forKey: "refresh_token") else {
                    throw AuthError.tokenExpired
                }
                let request = RefreshTokenRequest(refreshToken: refreshToken)
                let response: AuthRefreshResponse = try await self.performRequest(
                    method: "POST",
                    endpoint: "/api/auth/refresh",
                    body: request,
                    retryingAfterRefresh: true
                )
                keychain.set(response.accessToken, forKey: "jwt_token")
                keychain.set(response.refreshToken, forKey: "refresh_token")
                return response.accessToken
            }
            refreshTask = newTask
            refreshTaskID = newID
            return (newTask, newID)
        }

        do {
            let newToken = try await task.value
            refreshLock.withLock {
                if refreshTaskID == taskID {
                    refreshTask = nil
                    refreshTaskID = nil
                }
            }
            return newToken
        } catch {
            refreshLock.withLock {
                if refreshTaskID == taskID {
                    refreshTask = nil
                    refreshTaskID = nil
                }
            }
            throw error
        }
    }

    /// Internal injection points keep XCTest hermetic while the shared production
    /// instance continues to use the normal configuration and Info.plist URL.
    init(
        timeout: TimeInterval = 15,
        configuration: URLSessionConfiguration = .default,
        baseURLOverride: String? = nil,
        authTokenProvider: @escaping @MainActor () -> String? = { AuthManager.shared.accessToken }
    ) {
        self.baseURLOverride = baseURLOverride
        self.authTokenProvider = authTokenProvider
        let config = configuration
        // Disable URL caching — API responses must always hit the network.
        // Previously .returnCacheDataElseLoad caused stale empty session lists.
        config.urlCache = nil
        config.requestCachePolicy = .reloadIgnoringLocalAndRemoteCacheData
        config.timeoutIntervalForRequest = timeout
        config.timeoutIntervalForResource = timeout
        config.waitsForConnectivity = true
        self.session = URLSession(configuration: config)

        self.encoder = JSONEncoder()
        // FastAPI's mobile contract uses camelCase aliases (teamName, studentId,
        // wholesalePrice, etc.). Preserve DTO CodingKeys exactly; a global
        // snake_case strategy corrupts otherwise-correct request payloads.
        self.encoder.keyEncodingStrategy = .useDefaultKeys

        self.decoder = JSONDecoder()
        self.decoder.keyDecodingStrategy = .convertFromSnakeCase
    }

    /// Login credentials must not inherit an unrelated active session or invoke
    /// refresh/logout handling when the password is rejected.
    func postUnauthenticated<T: Decodable, B: Encodable>(_ endpoint: String, body: B) async throws -> T {
        guard let url = URL(string: baseURL + endpoint) else {
            throw NetworkError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        let (data, response) = try await session.data(for: request)
        guard let httpResponse = response as? HTTPURLResponse else {
            throw NetworkError.noData
        }
        guard (200...299).contains(httpResponse.statusCode) else {
            throw NetworkError.serverError(
                httpResponse.statusCode,
                String(data: data, encoding: .utf8) ?? "Unknown server error"
            )
        }
        do {
            return try decoder.decode(T.self, from: data)
        } catch {
            throw NetworkError.decodingError
        }
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

        // Try up to 3 times with exponential backoff (2s, 4s, 8s) for transient failures
        let maxRetries = 3
        for attempt in 0..<maxRetries {
            if attempt > 0 {
                // Exponential backoff: 2s, 4s, 8s...
                let delaySeconds = pow(2.0, Double(attempt))
                try await Task.sleep(nanoseconds: UInt64(delaySeconds * 1_000_000_000))
            }

            do {
                return try await performVoidRequest(method: method, endpoint: endpoint, body: body)
            } catch let error as NetworkError {
                // Retry on transient errors only: timeout (408), rate limit (429), server errors (5xx)
                if case .serverError(let code, _) = error {
                    if !(code == 408 || code == 429 || code >= 500) {
                        throw error // Client error — don't retry
                    }
                }
                lastError = error
            } catch {
                // Network errors (noConnection, timeout, connectionFailed) — retry
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
        if let token = authTokenProvider(), !token.isEmpty {
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
                AuthManager.shared.logout()
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
        body: Encodable?,
        headers: [String: String] = [:]
    ) async throws -> T {
        var lastError: Error?

        // Try up to 3 times with exponential backoff (2s, 4s, 8s) for transient failures
        let maxRetries = 3
        for attempt in 0..<maxRetries {
            if attempt > 0 {
                // Exponential backoff: 2s, 4s, 8s...
                let delaySeconds = pow(2.0, Double(attempt))
                try await Task.sleep(nanoseconds: UInt64(delaySeconds * 1_000_000_000))
            }

            do {
                return try await performRequest(method: method, endpoint: endpoint, body: body, headers: headers)
            } catch let error as NetworkError {
                // Retry on transient errors only: timeout (408), rate limit (429), server errors (5xx)
                if case .serverError(let code, _) = error {
                    if !(code == 408 || code == 429 || code >= 500) {
                        throw error // Client error — don't retry
                    }
                }
                lastError = error
            } catch {
                // Network errors (noConnection, timeout, connectionFailed) — retry
                lastError = error
            }
        }

        throw lastError ?? NetworkError.connectionFailed
    }

    private func performRequest<T: Decodable>(
        method: String,
        endpoint: String,
        body: Encodable?,
        headers: [String: String] = [:],
        retryingAfterRefresh: Bool = false
    ) async throws -> T {
        guard let url = URL(string: baseURL + endpoint) else {
            throw NetworkError.invalidURL
        }

        var request = URLRequest(url: url)
        request.httpMethod = method
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        for (name, value) in headers {
            request.setValue(value, forHTTPHeaderField: name)
        }

        // Auto-attach auth token from AuthManager if available
        if let token = authTokenProvider(), !token.isEmpty {
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
                return try await performRequest(
                    method: method,
                    endpoint: endpoint,
                    body: body,
                    headers: headers,
                    retryingAfterRefresh: true
                )
            } catch {
                // Refresh failed — force logout and surface the error
                AuthManager.shared.logout()
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

        if let token = authTokenProvider(), !token.isEmpty {
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
                AuthManager.shared.logout()
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

    func createSession(
        config: SessionConfiguration,
        teams: [TeamConfig],
        idempotencyKey: String = UUID().uuidString
    ) async throws -> SessionBackend {
        let request = CreateSessionRequestBackend(
            config: config.toBackendConfig(),
            teams: teams.map { $0.toBackend() },
            createdBy: "professor",
            maxHumanTeams: config.maxHumanTeams,
            scenarioId: config.scenarioIdentity.id,
            scenarioVersion: config.scenarioIdentity.version
        )
        let response: CreateSessionResponseBackend = try await self.request(
            method: "POST",
            endpoint: "/api/sessions",
            body: request,
            headers: ["Idempotency-Key": idempotencyKey]
        )
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

    func submitDecision(code: String, round: Int, decision: PlayerDecision, backendTeamId: String) async throws {
        let backendDecision = decision.toBackendDecision()
        // Backend uses the join-returned team name as teamId. Never substitute a local UUID.
        let request = SubmitDecisionRequestBackend(
            round: round,
            teamId: backendTeamId,
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
        // Do not route this irreversible mutation through the generic retry loop:
        // a transport timeout can occur after the server commits the round.
        let response: ProcessRoundResponseBackend = try await performRequest(
            method: "POST",
            endpoint: "/api/sessions/\(code)/process_round",
            body: EmptyBody()
        )
        return response.results
    }

    // MARK: - Results and Leaderboard

    func getResults(code: String) async throws -> [Int: [RoundResultBackend]] {
        // Backend returns {"results": {"1": [...], "2": [...]}}.
        // Preserve full round history and convert JSON string keys to Int for the app.
        let response: SessionResultsResponseBackend = try await get("/api/sessions/\(code)/results")
        return Dictionary(uniqueKeysWithValues: response.results.compactMap { key, value in
            guard let round = Int(key) else { return nil }
            return (round, value)
        })
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
        var name: String?
        var courseCode: String?
        var semester: String?
        var state: String = "creating"
        var currentRound: Int = 0
        var totalRounds: Int = 20
        var teamsCount: Int = 0
        var aiTeamsCount: Int = 0
        var totalTeams: Int = 0
        var totalSubmissions: Int = 0
        var lastRound: Int = 0
        var maxHumanTeams: Int?
        var marketType: String?
        var aiDifficulty: String?
        var scoringMetric: String?
        var startingCash: Double?
        var randomSeed: UInt64?
        var fixedCostsPerRound: Double?
        var baseCostPerUnit: Double?
        var baseMarketDemand: Int?
        var sharesOutstanding: Int?
        var initialEquity: Double?
        var baseInterestRate: Double?
        var plantCapacity: Int?
        var scenarioId: String?
        var scenarioVersion: String?
    }

    /// Backend wraps the session list in {"sessions": [...]} — decode the wrapper.
    private struct DashboardSessionListWrapper: Codable {
        var sessions: [DashboardSessionResponse]
    }

    /// Fetch all sessions for the professor dashboard.
    func getDashboardSessions() async throws -> [DashboardSessionResponse] {
        // Backend returns {"sessions": [...]} (wrapped object), not a bare array.
        // If auth token is expired/missing, the 401 error propagates to the caller
        // so LoginView can be shown — do NOT swallow it with a fallback.
        let wrapper: DashboardSessionListWrapper = try await get("/api/dashboard/sessions")
        return wrapper.sessions
    }

    // MARK: - Grade Export

    /// Fetch grade export CSV as string (for parsing or download).
    func exportGrades(code: String, retryingAfterRefresh: Bool = false) async throws -> String {
        guard let url = URL(string: baseURL + "/api/sessions/\(code)/export/grades") else {
            throw NetworkError.invalidURL
        }
        var request = URLRequest(url: url)
        request.httpMethod = "GET"
        if let token = authTokenProvider(), !token.isEmpty {
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
                AuthManager.shared.logout()
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
        if let token = authTokenProvider(), !token.isEmpty {
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
                AuthManager.shared.logout()
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
    
    func authRegister(username: String, password: String, studentId: String, name: String) async throws -> AuthRegisterResponse {
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
    var name: String = "Untitled session"
    var courseCode: String = ""
    var semester: String = ""
    var totalRounds: Int = 20
    var numberOfAICompetitors: Int = 3
    var marketType: String = "moderate"
    var aiDifficulty: String = "medium"
    var scoringMetric: String = "investor_score"
    var randomSeed: Int = 42
    var startingCash: Double = 500000
    var initialEquity: Double = 300000
    var plantCapacity: Int = 10000
    var maxOvertimePercent: Int = 25
    var minWage: Double = 12000
    var maxWage: Double = 40000
    var minDividend: Double = 0
    var maxDividend: Double = 5

    // Optional DTO fields preserve decoding of sessions created before scenario
    // identity existed. Resolved accessors route those sessions to footwear.
    var scenarioId: String? = ScenarioIdentity.athleticFootwearClassic.id
    var scenarioVersion: String? = ScenarioIdentity.athleticFootwearClassic.version

    var scenarioIdentity: ScenarioIdentity {
        ScenarioIdentity(
            id: scenarioId ?? ScenarioIdentity.athleticFootwearClassic.id,
            version: scenarioVersion ?? ScenarioIdentity.athleticFootwearClassic.version
        )
    }

    var scenario: SimulationScenario {
        ScenarioLibrary.scenario(id: scenarioId, version: scenarioVersion)
    }
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
    var humanTeams: Int = 0
}

/// Backend round result.
struct RoundResultBackend: Codable {
    var teamId: String = ""
    var round: Int = 0
    // Aggregate
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
    // Scorecard
    var epsScore: Double = 0
    var roeScore: Double = 0
    var stockPriceScore: Double = 0
    var imageScore: Double = 0
    var awarenessScore: Double = 0
    var creditScore: Double = 0
    var totalScore: Double = 0
    // Detailed financials
    var productionCost: Double = 0
    var marketingCost: Double = 0
    var unitCost: Double = 0
    var demand: [String: Double] = [:]
    // Per-channel revenue breakdown
    var wholesaleRevenue: Double = 0
    var internetRevenue: Double = 0
    var amazonRevenue: Double = 0
    var privateLabelRevenue: Double = 0
    // Per-channel units sold
    var wholesaleUnitsSold: Int = 0
    var internetUnitsSold: Int = 0
    var amazonUnitsSold: Int = 0
    var privateLabelUnitsSold: Int = 0
    // Detailed cost breakdown
    var workforceCosts: Double = 0
    var csrCosts: Double = 0
    var endorsementCosts: Double = 0
    var rebateCosts: Double = 0
    var deliveryCosts: Double = 0
    var storageCosts: Double = 0
    var interestExpense: Double = 0
    var dividendsPaid: Double = 0
    var socialMediaCosts: Double = 0
    var amazonFees: Double = 0
    // Display metrics
    var imageRating: Double = 0
    var creditRating: String = "A"
    var customerSatisfaction: Double = 0
    var rejectionRate: Double = 0
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
    var classId: String? = nil
    var scenarioId: String = ScenarioIdentity.athleticFootwearClassic.id
    var scenarioVersion: String = ScenarioIdentity.athleticFootwearClassic.version
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

struct SessionResultsResponseBackend: Codable {
    var results: [String: [RoundResultBackend]] = [:]
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
    var privateLabelBidPrice: Double = 0
    var privateLabelMaxUnits: Int = 0
    var amazonAdBudget: Double = 0
    var materialsQuality: Double = 0.5   // Legacy 0...1 value translated by FastAPI.
    var stylingBudget: Double = 100000
    var numModels: Int = 2               // Transitional legacy alias.
    var modelsOffered: Int = 2            // Modern authoritative field.
    var tqmInvestment: Double = 0
    var rdInvestment: Double = 0
    var marketingInvestment: Double = 150000
    var advertisingBudget: Double = 80000
    var celebrityType: String = "none"   // Transitional legacy alias.
    var celebrityEndorsement: String = "none"
    var retailOutlets: Int = 0
    var mailInRebate: Double = 0
    var deliveryTime: String = "standard"
    var freeShippingThreshold: Double = 0
    var socialMediaBudget: SocialMediaBudgetBackend = SocialMediaBudgetBackend()
    var tiktokBudget: Double = 0
    var instagramBudget: Double = 0
    var youtubeBudget: Double = 0
    var influencerTier: String = "none"
    var baseWage: Double = 25000
    var incentivePay: Double = 0
    var trainingBudget: Double = 0        // Transitional legacy alias.
    var trainingHours: Double = 0         // Modern authoritative field.
    var bestPracticesInvestment: Double = 0
    var productionQuantity: Int = 8000
    var overtimePercent: Int = 0
    var csrInvestment: Double = 0
    var dividendsPerShare: Double = 0
    var newLoanAmount: Double = 0
    var sharesBuyback: Int = 0
    var sharesIssued: Int = 0
    var fulfillmentMethod: String = "fbm"
    var internetPromotion: Double = 0
    // Wearable Technology
    var batteryLife: Int = 24
    var sensorAccuracy: Double = 7.0
    var privacyCompliance: Int = 5000
    var componentSourcing: String = "standard"
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
            name: name,
            courseCode: courseCode,
            semester: semester,
            totalRounds: totalRounds,
            numberOfAICompetitors: numberOfAICompetitors,
            marketType: marketType.rawValue,
            aiDifficulty: aiDifficulty.rawValue,
            scoringMetric: {
                switch scoringMetric {
                case .investorScore: return "investor_score"
                case .cumulativeProfit: return "cumulative_profit"
                case .revenue: return "revenue"
                case .composite: return "composite"
                }
            }(),
            randomSeed: Int(min(randomSeed, UInt64(Int.max))),
            startingCash: startingCash,
            initialEquity: initialEquity,
            plantCapacity: plantCapacity,
            maxOvertimePercent: 25,
            minWage: 12000,
            maxWage: 40000,
            minDividend: 0,
            maxDividend: 5,
            scenarioId: scenarioIdentity.id,
            scenarioVersion: scenarioIdentity.version
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
            wholesalePrice: wholesalePrice,
            internetPrice: internetPrice,
            amazonPrice: amazonPrice,
            privateLabelBidPrice: privateLabelBidPrice,
            privateLabelMaxUnits: privateLabelMaxUnits,
            amazonAdBudget: amazonAdBudget,
            materialsQuality: materialsQuality.backendValue,
            stylingBudget: stylingBudget,
            numModels: modelsOffered,
            modelsOffered: modelsOffered,
            tqmInvestment: tqmInvestment,
            rdInvestment: rdInvestment,
            marketingInvestment: advertisingBudget,
            advertisingBudget: advertisingBudget,
            celebrityType: celebrityEndorsement.backendValue,
            celebrityEndorsement: celebrityEndorsement.rawValue,
            retailOutlets: retailOutlets,
            mailInRebate: mailInRebate,
            deliveryTime: deliveryTime.rawValue,
            freeShippingThreshold: freeShippingThreshold,
            socialMediaBudget: SocialMediaBudgetBackend(
                tiktok: tiktokBudget,
                instagram: instagramBudget,
                youtube: youtubeBudget
            ),
            tiktokBudget: tiktokBudget,
            instagramBudget: instagramBudget,
            youtubeBudget: youtubeBudget,
            influencerTier: influencerTier.rawValue,
            baseWage: baseWage,
            incentivePay: incentivePay,
            trainingBudget: trainingHours * 50,
            trainingHours: trainingHours,
            bestPracticesInvestment: bestPracticesInvestment,
            productionQuantity: productionQuantity,
            overtimePercent: Int(overtimePercent),
            csrInvestment: csrInvestment,
            dividendsPerShare: dividendsPerShare,
            newLoanAmount: newLoanAmount,
            sharesBuyback: sharesBuyback,
            sharesIssued: sharesIssued,
            fulfillmentMethod: fulfillmentMethod.backendValue,
            internetPromotion: 0,
            batteryLife: batteryLife,
            sensorAccuracy: sensorAccuracy,
            privacyCompliance: privacyCompliance,
            componentSourcing: componentSourcing.rawValue
        )
    }
}

extension PlayerDecisionBackend {
    func toPlayerDecision() -> PlayerDecision? {
        PlayerDecision(
            teamId: UUID(),
            round: 0,
            wholesalePrice: wholesalePrice,
            internetPrice: internetPrice,
            privateLabelBidPrice: privateLabelBidPrice,
            privateLabelMaxUnits: privateLabelMaxUnits,
            materialsQuality: materialsQuality > 0.75 ? MaterialsQuality.superior : MaterialsQuality.standard,
            stylingBudget: stylingBudget,
            modelsOffered: max(1, modelsOffered),
            tqmInvestment: tqmInvestment,
            advertisingBudget: advertisingBudget,
            celebrityEndorsement: CelebrityEndorsement(rawValue: celebrityEndorsement) ?? .none,
            retailOutlets: retailOutlets,
            mailInRebate: mailInRebate,
            deliveryTime: DeliveryTime(rawValue: deliveryTime) ?? .standard,
            freeShippingThreshold: freeShippingThreshold,
            amazonPrice: amazonPrice,
            amazonAdBudget: amazonAdBudget,
            fulfillmentMethod: FulfillmentMethod(rawValue: fulfillmentMethod) ?? .fbm,
            tiktokBudget: tiktokBudget,
            instagramBudget: instagramBudget,
            youtubeBudget: youtubeBudget,
            influencerTier: InfluencerTier(rawValue: influencerTier) ?? .none,
            baseWage: baseWage,
            incentivePay: incentivePay,
            trainingHours: trainingHours,
            bestPracticesInvestment: bestPracticesInvestment,
            productionQuantity: productionQuantity,
            overtimePercent: Double(overtimePercent),
            csrInvestment: csrInvestment,
            dividendsPerShare: dividendsPerShare,
            newLoanAmount: newLoanAmount,
            sharesBuyback: sharesBuyback,
            sharesIssued: sharesIssued,
            batteryLife: batteryLife,
            sensorAccuracy: sensorAccuracy,
            privacyCompliance: privacyCompliance,
            componentSourcing: ComponentSourcing(rawValue: componentSourcing) ?? .standard
        )
    }
}
