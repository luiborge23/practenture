// MARK: - Auth Models (Phase 5)

/// Request body for login endpoint.
struct AuthLoginRequest: Encodable {
    let provider: String
    let username: String?
    let password: String?
    let idToken: String?
    
    enum CodingKeys: String, CodingKey {
        case provider
        case username, password
        case idToken = "id_token"
    }
}

/// Response from login endpoint.
struct AuthLoginResponse: Codable {
    let accessToken: String
    let refreshToken: String
    let user: AuthUser
    
    enum CodingKeys: String, CodingKey {
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
        case user
    }
}

/// Authenticated user info.
struct AuthUser: Codable {
    let userId: String
    let username: String
    let role: String
    let studentId: String?
    let name: String?
    
    enum CodingKeys: String, CodingKey {
        case userId = "user_id"
        case username
        case role
        case studentId = "student_id"
        case name
    }
}

/// Request body for register endpoint.
struct AuthRegisterRequest: Encodable {
    let username: String
    let password: String
    let studentId: String
    let name: String
    
    enum CodingKeys: String, CodingKey {
        case username, password
        case studentId = "student_id"
        case name
    }
}

/// Apple Sign In credential type.
enum AuthProvider: String {
    case apple = "apple"
    case google = "google"
    case professor = "professor"
}
