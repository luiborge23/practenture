// AuthRepositoryImpl.swift
// Practenture
//
// Concrete implementation of AuthRepository.
// Delegates to AuthManager.shared for all authentication operations.

import Foundation

@MainActor
final class AuthRepositoryImpl: AuthRepository {

    private let auth = AuthManager.shared

    func login(provider: String, username: String? = nil, password: String? = nil, idToken: String? = nil) async throws -> AuthLoginResponse {
        switch provider {
        case "password":
            guard let username, let password else {
                throw AuthError.invalidProviderCredentials
            }
            return try await auth.loginProfessor(username: username, password: password)

        case "google":
            guard let idToken else {
                throw AuthError.invalidProviderCredentials
            }
            return try await auth.loginWithGoogle(idToken: idToken)

        default:
            // For "apple" or any other provider that supplies an idToken,
            // use the network service directly, store the token in keychain,
            // and update AuthManager state.
            let response = try await NetworkService.shared.authLogin(
                provider: provider,
                username: username,
                password: password,
                idToken: idToken
            )
            // Store tokens in keychain (mirrors AuthManager's post-login logic)
            let keychain = KeychainWrapper()
            keychain.set(response.accessToken, forKey: "jwt_token")
            if let refreshToken = response.refreshToken {
                keychain.set(refreshToken, forKey: "refresh_token")
            }
            // Sync AuthManager singleton with the new credentials
            auth.applyLoginState(token: response.accessToken, username: username, studentId: nil)
            return response
        }
    }

    func register(username: String, password: String, studentId: String, name: String) async throws -> AuthLoginResponse {
        let response = try await auth.register(username: username, password: password, studentId: studentId, name: name)
        if let accessToken = response.accessToken {
            return AuthLoginResponse(accessToken: accessToken, tokenType: "Bearer", role: "student", userId: studentId, refreshToken: response.refreshToken)
        }
        // Fallback: login with the credentials
        return try await auth.loginStudent(username: username, password: password)
    }

    func logout() async {
        auth.logout()
    }

    func currentToken() -> String? {
        auth.accessToken
    }

    func isAuthenticated() -> Bool {
        auth.isAuthenticated
    }

    func currentUser() -> AuthUser? {
        auth.currentUser
    }
}
