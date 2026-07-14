// AuthManager.swift - Fixed post-login blackout + Keychain race + JWT padding
import Foundation
import os
#if canImport(AuthenticationServices)
import AuthenticationServices
#endif
#if canImport(GoogleSignIn)
@preconcurrency import GoogleSignIn
#endif
import Security

/// Central auth state - single source of truth
@MainActor
@Observable
final class AuthManager {
    static let shared = AuthManager()

    var isAuthenticated: Bool = false
    var currentUser: AuthUser?

    var userId: String? { currentUser?.userId }
    var userName: String? { currentUser?.username }

    // MARK: - Single source of truth: Keychain
    private let keychain = KeychainWrapper()
    private let network = NetworkService.shared
    var onAuthChange: (() -> Void)?

    /// Read current access token from Keychain (single source of truth)
    var accessToken: String? {
        keychain.string(forKey: "jwt_token")
    }

    /// Write tokens to Keychain — the ONLY place tokens are persisted
    private func persistTokens(access: String, refresh: String?) {
        keychain.set(access, forKey: "jwt_token")
        if let rt = refresh {
            keychain.set(rt, forKey: "refresh_token")
        }
    }

    /// Check if current access token is valid (decoded + not expired)
    var hasValidToken: Bool {
        guard let token = accessToken, !token.isEmpty else { return false }
        guard decodePayload(token) != nil else { return false }
        return Date().timeIntervalSince1970 < expirationDate(for: token)
    }

    /// Proactively refresh access token if within 2 minutes of expiry.
    /// Returns true if a refresh was performed, false if token still valid.
    @MainActor
    func proactiveTokenRefresh() async -> Bool {
        guard let token = accessToken, !token.isEmpty else { return false }
        let exp = expirationDate(for: token)
        let now = Date().timeIntervalSince1970
        // If token expires within 2 minutes, refresh proactively
        guard exp - now < 120 else { return false } // still valid > 2 min
        do {
            let newToken = try await network.refreshToken()
            persistTokens(access: newToken, refresh: keychain.string(forKey: "refresh_token"))
            // Update currentUser from new token payload — extract name properly
            if let payload = decodePayload(newToken) {
                let sub = payload["sub"] as? String ?? ""
                let role = payload["role"] as? String ?? "student"
                let name = (payload["name"] as? String ?? "").isEmpty ? sub : payload["name"] as? String
                currentUser = AuthUser(
                    userId: sub,
                    username: sub,
                    role: role,
                    studentId: sub,
                    name: name ?? sub
                )
            }
            onAuthChange?()
            return true
        } catch {
            // Refresh failed — force logout
            logout()
            return false
        }
    }

    // MARK: - JWT helpers
    private func decodePayload(_ token: String) -> [String: Any]? {
        let parts = token.split(separator: ".")
        guard parts.count == 3 else { return nil }
        var b64 = String(parts[1])
        b64 = b64.replacingOccurrences(of: "-", with: "+")
               .replacingOccurrences(of: "_", with: "/")
        // Correct base64url padding: length mod 4 must not be 1
        let remainder = b64.count % 4
        switch remainder {
        case 0: break
        case 2: b64 += "=="
        case 3: b64 += "="
        case 1: return nil // invalid
        default: break
        }
        guard let data = Data(base64Encoded: b64),
              let json = try? JSONSerialization.jsonObject(with: data) as? [String: Any] else { return nil }
        return json
    }

    func expirationDate(for token: String) -> TimeInterval {
        guard let payload = decodePayload(token),
              let exp = payload["exp"] as? TimeInterval else {
            return Date().timeIntervalSince1970 + 3600*24
        }
        return exp
    }

    // MARK: - Remember Me

    /// Whether the user has "remember me" enabled. Defaults to true if no value stored.
    var rememberMe: Bool {
        get { UserDefaults.standard.bool(forKey: "bizsimai_remember_me") }
        set { UserDefaults.standard.set(newValue, forKey: "bizsimai_remember_me") }
    }

    @MainActor
    func refreshFromKeychain() {
        restoreSession()
    }

    @MainActor
    func applyLoginState(token: String, username: String?, studentId: String?) {
        persistTokens(access: token, refresh: keychain.string(forKey: "refresh_token"))
        isAuthenticated = true
        if let payload = decodePayload(token) {
            let sub = payload["sub"] as? String ?? username ?? ""
            let role = payload["role"] as? String ?? "student"
            currentUser = AuthUser(
                userId: sub,
                username: username ?? sub,
                role: role,
                studentId: studentId,
                name: username ?? sub
            )
        } else {
            currentUser = AuthUser(userId: username ?? "", username: username ?? "", role: "student", studentId: studentId, name: username)
        }
        onAuthChange?()
    }

    private func clearPersistedTokens() {
        keychain.delete(forKey: "jwt_token")
        keychain.delete(forKey: "refresh_token")
    }

    private func clearAuthState() {
        // accessToken is now a computed property — clearing Keychain handles it
        currentUser = nil
        isAuthenticated = false
    }

    private init() {
        restoreSession()
    }

    // MARK: - Professor Status Check (public, no auth required)

    /// Response model for GET /api/auth/professor-status
    struct ProfessorStatusResponse: Decodable {
        let professorExists: Bool
        let message: String
    }

    /// Check if any professor account exists in the system.
    /// This is a public endpoint (no auth required) that allows iOS to adapt its UI.
    @MainActor
    func checkProfessorStatus() async throws -> ProfessorStatusResponse {
        return try await network.get("/api/auth/professor-status")
    }

    // MARK: - Public API

    @MainActor
    func loginProfessor(username: String, password: String, mfaCode: String? = nil) async throws -> AuthLoginResponse {
        let response: AuthLoginResponse = try await network.post("/api/auth/login", body: AuthLoginRequest(provider: "password", username: username, password: password, idToken: nil, mfaCode: mfaCode))
        if response.mfaRequired == true {
            return response
        }
        persistTokens(access: response.accessToken, refresh: response.refreshToken)
        isAuthenticated = true
        currentUser = AuthUser(
            userId: response.userId,
            username: username,
            role: response.role,
            studentId: nil,
            name: username
        )
        onAuthChange?()
        return response
    }

    @MainActor
    func loginStudent(username: String, password: String, mfaCode: String? = nil) async throws -> AuthLoginResponse {
        // Clear any stale tokens before login to avoid "session expired" errors
        clearPersistedTokens()
        let response: AuthLoginResponse = try await network.post("/api/auth/login", body: AuthLoginRequest(provider: "password", username: username, password: password, idToken: nil, mfaCode: mfaCode))
        if response.mfaRequired == true {
            return response
        }
        persistTokens(access: response.accessToken, refresh: response.refreshToken)
        isAuthenticated = true
        // Extract name from JWT payload (now includes "name" field) — fall back to username if missing
        let displayName: String = {
            guard let payload = decodePayload(response.accessToken),
                  let name = payload["name"] as? String, !name.isEmpty else {
                return username
            }
            return name
        }()
        currentUser = AuthUser(
            userId: response.userId,
            username: username,
            role: response.role,
            studentId: username,
            name: displayName
        )
        onAuthChange?()
        return response
    }

    @MainActor
    func register(username: String, password: String, studentId: String, name: String) async throws -> AuthRegisterResponse {
        // Single atomic call: register now returns tokens (accessToken + refreshToken)
        let response: AuthRegisterResponse = try await network.post("/api/auth/register", body: AuthRegisterRequest(studentId: studentId, name: name, password: password))
        if let accessToken = response.accessToken, let refreshToken = response.refreshToken {
            persistTokens(access: accessToken, refresh: refreshToken)
            isAuthenticated = true
            currentUser = AuthUser(
                userId: studentId,
                username: username,
                role: "student",
                studentId: studentId,
                name: name
            )
            onAuthChange?()
        }
        return response
    }

    /// Full professor onboarding in one atomic operation: register → login → redeem code.
    /// Only sets isAuthenticated=true at the END with role="professor", so LaunchView
    /// doesn't auto-dismiss the onboarding sheet mid-flow.
    @MainActor
    func registerProfessor(username: String, password: String, name: String, professorCode: String) async throws -> AuthLoginResponse {
        // Step 1: Register the base account (creates student role initially)
        do {
            _ = try await network.postVoid("/api/auth/register", body: AuthRegisterRequest(studentId: username, name: name, password: password))
        } catch NetworkError.serverError(409, _) {
            // Username already exists as student — fall through to login + redeem
        } catch {
            throw error
        }
        // Step 2: Login to get tokens (may require MFA)
        let loginResponse: AuthLoginResponse = try await network.post("/api/auth/login", body: AuthLoginRequest(provider: "password", username: username, password: password, idToken: nil, mfaCode: nil))
        if loginResponse.mfaRequired == true {
            // MFA required — persist and return so caller can handle it
            persistTokens(access: loginResponse.accessToken, refresh: loginResponse.refreshToken)
            isAuthenticated = true
            currentUser = AuthUser(userId: loginResponse.userId, username: username, role: loginResponse.role, studentId: username, name: name)
            return loginResponse
        }
        persistTokens(access: loginResponse.accessToken, refresh: loginResponse.refreshToken)
        currentUser = AuthUser(userId: loginResponse.userId, username: username, role: loginResponse.role, studentId: username, name: name)
        // Step 3: Redeem professor code to upgrade role
        let redeemResponse: RedeemCodeResponse = try await network.post("/api/professor/redeem", body: RedeemCodeRequest(code: professorCode))
        persistTokens(access: redeemResponse.accessToken, refresh: loginResponse.refreshToken)
        currentUser = AuthUser(
            userId: currentUser?.userId ?? "",
            username: currentUser?.username ?? "",
            role: "professor",
            studentId: currentUser?.studentId,
            name: currentUser?.name
        )
        // ONLY NOW set authenticated — role is professor
        isAuthenticated = true
        onAuthChange?()
        // Return the login response so caller can check mfaRequired if needed
        return AuthLoginResponse(accessToken: redeemResponse.accessToken, tokenType: redeemResponse.tokenType, role: "professor", userId: currentUser?.userId ?? "", refreshToken: loginResponse.refreshToken)
    }

    @MainActor
    func loginWithApple(credential: AuthenticationServices.ASAuthorizationCredential, professorCode: String? = nil) async throws -> AuthLoginResponse {
        let idToken: String
        if let appleId = credential as? ASAuthorizationAppleIDCredential,
           let jwtData = appleId.identityToken,
           let jwtString = String(data: jwtData, encoding: .utf8) {
            idToken = jwtString
        } else {
            throw AuthError.invalidProviderCredentials
        }
        let response: AuthLoginResponse = try await network.post("/api/auth/login", body: AuthLoginRequest(provider: "apple", username: nil, password: nil, idToken: idToken, mfaCode: nil, professorCode: professorCode))
        if response.professorCodeRequired == true {
            return response
        }
        persistTokens(access: response.accessToken, refresh: response.refreshToken)
        isAuthenticated = true
        currentUser = AuthUser(
            userId: response.userId,
            username: response.userId,
            role: response.role,
            studentId: response.userId,
            name: response.userId
        )
        onAuthChange?()
        return response
    }

    @MainActor
    func loginWithGoogle(idToken: String, professorCode: String? = nil) async throws -> AuthLoginResponse {
        let response: AuthLoginResponse = try await network.post("/api/auth/login", body: AuthLoginRequest(provider: "google", username: nil, password: nil, idToken: idToken, mfaCode: nil, professorCode: professorCode))
        if response.professorCodeRequired == true {
            return response
        }
        persistTokens(access: response.accessToken, refresh: response.refreshToken)
        isAuthenticated = true
        currentUser = AuthUser(
            userId: response.userId,
            username: response.userId,
            role: response.role,
            studentId: response.userId,
            name: response.userId
        )
        onAuthChange?()
        return response
    }

    // Generic OAuth login — used for re-attempting with professor code after initial OAuth login
    @MainActor
    func loginWithOAuth(provider: String, idToken: String, professorCode: String? = nil) async throws -> AuthLoginResponse {
        let response: AuthLoginResponse = try await network.post("/api/auth/login", body: AuthLoginRequest(provider: provider, username: nil, password: nil, idToken: idToken, mfaCode: nil, professorCode: professorCode))
        if response.professorCodeRequired == true {
            return response
        }
        persistTokens(access: response.accessToken, refresh: response.refreshToken)
        isAuthenticated = true
        currentUser = AuthUser(
            userId: response.userId,
            username: response.userId,
            role: response.role,
            studentId: response.userId,
            name: response.userId
        )
        onAuthChange?()
        return response
    }

    // MARK: - SOTA Phase 2: MFA/TOTP

    @MainActor
    func setupMFA() async throws -> MFASetupResponse {
        return try await network.post("/api/auth/mfa/setup")
    }

    @MainActor
    func verifyMFA(code: String) async throws -> [String: Any] {
        return try await network.postRaw("/api/auth/mfa/verify", body: MFAVerifyRequest(code: code))
    }

    @MainActor
    func disableMFA() async throws {
        _ = try await network.postVoid("/api/auth/mfa/disable")
    }

    @MainActor
    func getMFAStatus() async throws -> Bool {
        let response: MFAStatusResponse = try await network.get("/api/auth/mfa/status")
        return response.enabled
    }

    // MARK: - SOTA Phase 2: Professor Code Redemption

    @MainActor
    func redeemProfessorCode(_ code: String) async throws -> RedeemCodeResponse {
        let response: RedeemCodeResponse = try await network.post("/api/professor/redeem", body: RedeemCodeRequest(code: code))
        // Update token with new professor role
        persistTokens(access: response.accessToken, refresh: keychain.string(forKey: "refresh_token"))
        currentUser = AuthUser(
            userId: currentUser?.userId ?? "",
            username: currentUser?.username ?? "",
            role: "professor",
            studentId: currentUser?.studentId,
            name: currentUser?.name
        )
        onAuthChange?()
        return response
    }

    // MARK: - Change Password (first login or voluntary)

    @MainActor
    func changePassword(old: String, new: String) async throws {
        _ = try await network.postVoid("/api/professor/change-password", body: ChangePasswordRequest(oldPassword: old, newPassword: new))
    }

    // MARK: - Password Reset (Forgot Password)

    @MainActor
    func forgotPassword(email: String) async throws -> String? {
        let response: ForgotPasswordResponse = try await network.post("/api/auth/forgot-password", body: ForgotPasswordRequest(email: email))
        return response.token
    }

    @MainActor
    func resetPassword(token: String, newPassword: String) async throws {
        try await network.postVoid("/api/auth/reset-password", body: ResetPasswordRequest(token: token, newPassword: newPassword))
    }

    // MARK: - Join Class (student)

    @MainActor
    func joinClass(joinCode: String) async throws -> JoinClassResponse {
        return try await network.post("/api/classes/join", body: JoinClassRequest(joinCode: joinCode))
    }

    @MainActor
    func logout() {
        clearPersistedTokens()
        clearAuthState()
        onAuthChange?()
    }

    @MainActor
    func signOutFromGoogle() async -> Bool {
#if canImport(GoogleSignIn)
        GIDSignIn.sharedInstance.signOut()
        return true
#else
        return false
#endif
    }

    @MainActor
    func isGoogleSignedIn() -> Bool {
#if canImport(GoogleSignIn)
        return GIDSignIn.sharedInstance.currentUser != nil
#else
        return false
#endif
    }

    // MARK: - Session Restoration

    /// Restore session on app launch. Tries access token first, then refresh token if expired.
    /// Respects `rememberMe` — if disabled, clears all persisted tokens immediately.
    @MainActor
    private func restoreSession() {
        // If rememberMe is disabled, clear all persisted tokens
        if !rememberMe {
            clearPersistedTokens()
            clearAuthState()
            return
        }

        guard let token = keychain.string(forKey: "jwt_token"), !token.isEmpty else {
            clearAuthState()
            return
        }

        // Case 1: Access token still valid — restore directly
        guard let payload = decodePayload(token) else {
            clearPersistedTokens()
            clearAuthState()
            return
        }

        let exp = expirationDate(for: token)
        if Date().timeIntervalSince1970 < exp {
            // Token still valid — restore immediately, extract name properly
            let sub = payload["sub"] as? String ?? ""
            let role = payload["role"] as? String ?? "student"
            let name = (payload["name"] as? String ?? "").isEmpty ? sub : payload["name"] as? String
            currentUser = AuthUser(
                userId: sub,
                username: sub,
                role: role,
                studentId: sub,
                name: name ?? sub
            )
            isAuthenticated = true
            return
        }

        // Case 2: Access token expired — try refresh token
        guard let refreshToken = keychain.string(forKey: "refresh_token"), !refreshToken.isEmpty else {
            clearPersistedTokens()
            clearAuthState()
            return
        }

        Task {
            do {
                // refreshToken() internally persists both new access + refresh tokens to Keychain
                let newAccessToken = try await network.refreshToken()

                if let newPayload = decodePayload(newAccessToken) {
                    currentUser = AuthUser(
                        userId: newPayload["sub"] as? String ?? "",
                        username: newPayload["sub"] as? String ?? "",
                        role: newPayload["role"] as? String ?? "student",
                        studentId: newPayload["sub"] as? String,
                        name: (newPayload["name"] as? String ?? "").isEmpty ? (newPayload["sub"] as? String ?? "") : newPayload["name"] as? String
                    )
                } else {
                    // Fallback: use original payload (refresh token may have changed role info)
                    let sub = payload["sub"] as? String ?? ""
                    currentUser = AuthUser(
                        userId: sub,
                        username: sub,
                        role: payload["role"] as? String ?? "student",
                        studentId: sub,
                        name: (payload["name"] as? String ?? "").isEmpty ? sub : payload["name"] as? String
                    )
                }

                isAuthenticated = true
                onAuthChange?()
            } catch {
                // Refresh failed — clear everything
                await MainActor.run {
                    clearPersistedTokens()
                    clearAuthState()
                }
            }
        }
    }
}

// MARK: - Auth Error Types

enum AuthError: LocalizedError {
    case invalidProviderCredentials
    case tokenExpired
    case professorRequired
    case professorCodeInvalid

    var errorDescription: String? {
        switch self {
        case .invalidProviderCredentials:
            return "Invalid provider credentials."
        case .tokenExpired:
            return "Session expired. Please log in again."
        case .professorRequired:
            return "A professor account is required to access this feature."
        case .professorCodeInvalid:
            return "The professor code you entered is invalid or has already been used."
        }
    }
}

// MARK: - Request/Response Models
