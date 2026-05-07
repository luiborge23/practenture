// MARK: - Auth Manager (Phase 5)

import Foundation
import AuthenticationServices
import GoogleSignIn

/// Manages authentication lifecycle: login, token storage, session validation.
@Observable
final class AuthManager {
    
    static let shared = AuthManager()
    
    private var _isAuthenticated = false
    var isAuthenticated: Bool { _isAuthenticated }
    
    private var _currentUser: AuthUser?
    var currentUser: AuthUser? { _currentUser }
    
    private var _accessToken: String?
    var accessToken: String? { _accessToken }
    
    private let keychain = KeychainWrapper()
    private let network = NetworkService.shared
    
    var onAuthChange: (() -> Void)?
    
    private init() {
        // Restore session from keychain on init
        restoreSession()
    }
    
    // MARK: - Session Restore
    
    private func restoreSession() {
        if let token = keychain.getString(forKey: "bizsimai_access_token"),
           let userJson = keychain.getString(forKey: "bizsimai_user"),
           let userData = userJson.data(using: .utf8) {
            if let user = try? JSONDecoder().decode(AuthUser.self, from: userData) {
                _accessToken = token
                _currentUser = user
                _isAuthenticated = true
                onAuthChange?()
            }
        }
    }
    
    // MARK: - Login
    
    /// Login with Apple Sign In credential.
    func login(with credential: ASAuthorization) async throws -> AuthLoginResponse {
        guard let appleIDCredential = credential as? ASAuthorizationAppleIDCredential else {
            throw NetworkError.connectionFailed
        }
        
        let idTokenString = String(data: appleIDCredential.identityToken ?? Data(), encoding: .utf8)
        guard let idToken = idTokenString else {
            throw NetworkError.decodingError
        }
        
        let response = try await network.authLogin(provider: "apple", idToken: idToken)
        saveSession(token: response.accessToken, user: response.user)
        return response
    }
    
    /// Login with Google Sign In credential.
    func login(with googleIDToken: String) async throws -> AuthLoginResponse {
        let response = try await network.authLogin(provider: "google", idToken: googleIDToken)
        saveSession(token: response.accessToken, user: response.user)
        return response
    }
    
    /// Login as professor with username/password.
    func loginProfessor(username: String, password: String) async throws -> AuthLoginResponse {
        let response = try await network.authLogin(provider: "professor", username: username, password: password)
        saveSession(token: response.accessToken, user: response.user)
        return response
    }
    
    /// Register a new student account.
    func register(username: String, password: String, studentId: String, name: String) async throws -> AuthLoginResponse {
        let response = try await network.authRegister(username: username, password: password, studentId: studentId, name: name)
        saveSession(token: response.accessToken, user: response.user)
        return response
    }
    
    // MARK: - Session Management
    
    private func saveSession(token: String, user: AuthUser) {
        _accessToken = token
        _currentUser = user
        _isAuthenticated = true
        
        keychain.set(token, forKey: "bizsimai_access_token")
        
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        if let data = try? encoder.encode(user),
           let json = String(data: data, encoding: .utf8) {
            keychain.set(json, forKey: "bizsimai_user")
        }
        
        onAuthChange?()
    }
    
    func logout() {
        _accessToken = nil
        _currentUser = nil
        _isAuthenticated = false
        
        keychain.remove(forKey: "bizsimai_access_token")
        keychain.remove(forKey: "bizsimai_user")
        
        onAuthChange?()
    }
    
    func hasValidToken() -> Bool {
        guard let token = _accessToken else { return false }
        // Check token expiry if available
        return !token.isEmpty
    }
}

// MARK: - Keychain Wrapper

private final class KeychainWrapper {
    
    func set(_ value: String, forKey key: String) {
        let data = value.data(using: .utf8)!
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecValueData as String: data,
            kSecAccessible as String: kSecAttrAccessibleAfterFirstUnlock
        ]
        
        SecItemDelete(query as CFDictionary)
        guard SecItemAdd(query as CFDictionary, nil) == errSecSuccess else {
            return
        }
    }
    
    func getString(forKey key: String) -> String? {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key,
            kSecReturnData as String: true,
            kSecMatchLimit as String: kSecMatchLimitOne
        ]
        
        var item: CFTypeRef?
        guard SecItemCopyMatching(query as CFDictionary, &item) == errSecSuccess,
              let data = item as? Data,
              let string = String(data: data, encoding: .utf8) else {
            return nil
        }
        return string
    }
    
    func remove(forKey key: String) {
        let query: [String: Any] = [
            kSecClass as String: kSecClassGenericPassword,
            kSecAttrAccount as String: key
        ]
        SecItemDelete(query as CFDictionary)
    }
}
