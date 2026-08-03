// MARK: - Auth Models (Phase 5 + SOTA Phase 2)

/// Request body for login endpoint.
struct AuthLoginRequest: Encodable {
    let provider: String
    let username: String?
    let password: String?
    let idToken: String?
    let mfaCode: String?
    let professorCode: String?
    let providerNonce: String?
    
    init(provider: String, username: String? = nil, password: String? = nil, idToken: String? = nil, mfaCode: String? = nil, professorCode: String? = nil, providerNonce: String? = nil) {
        self.provider = provider
        self.username = username
        self.password = password
        self.idToken = idToken
        self.mfaCode = mfaCode
        self.professorCode = professorCode
        self.providerNonce = providerNonce
    }
    
    enum CodingKeys: String, CodingKey {
        case provider
        case username, password
        case idToken = "id_token"
        case mfaCode = "mfa_code"
        case professorCode = "professor_code"
        case providerNonce = "provider_nonce"
    }
}

/// Response from login endpoint.
struct AuthLoginResponse: Codable {
    var accessToken: String
    var tokenType: String
    var role: String
    var userId: String
    var refreshToken: String? = nil
    var mustChangePassword: Bool? = false
    var mfaRequired: Bool? = false
    var professorCodeRequired: Bool? = false
    
    enum CodingKeys: String, CodingKey {
        case accessToken
        case tokenType
        case role
        case userId
        case refreshToken
        case mustChangePassword
        case mfaRequired
        case professorCodeRequired = "professorCodeRequired"
    }
}

/// Response from refresh endpoint.
struct AuthRefreshResponse: Codable {
    var accessToken: String
    var refreshToken: String
    var tokenType: String
    
    enum CodingKeys: String, CodingKey {
        case accessToken
        case refreshToken
        case tokenType
    }
}

/// Authenticated user info.
struct AuthUser: Codable, Identifiable {
    let userId: String
    let username: String
    let role: String
    let studentId: String?
    let name: String?
    
    var id: String { userId }
}

struct AccountDeletionRequirements: Decodable {
    let provider: String
    let reauthentication: String
    let mfaRequired: Bool
    let confirmationPhrase: String
    let challengeId: String?
    let challenge: String?
    let challengeExpiresAt: Double?
    let operationToken: String
}

struct DeleteAccountRequest: Encodable {
    let confirmation: String
    let password: String?
    let mfaCode: String?
    let providerToken: String?
    let providerNonce: String?
    let providerAuthorizationCode: String?
    let challengeId: String?
    let operationToken: String
}

struct AccountDeletionStatusRequest: Encodable {
    let operationToken: String
}

struct AccountDeletionStatusResponse: Decodable {
    let status: String
}

/// Request body for register endpoint.
/// Backend RegisterRequest only accepts: student_id, name, password
struct AuthRegisterRequest: Encodable {
    let studentId: String
    let name: String
    let password: String
    
    enum CodingKeys: String, CodingKey {
        case studentId = "student_id"
        case name, password
    }
}

/// Response from register endpoint — backend returns student_id, name, message.
/// But the login endpoint also accepts register-style calls. We use login response for register+auto-login.
struct AuthRegisterResponse: Codable {
    let studentId: String?
    let name: String?
    let message: String?
    var accessToken: String? = nil
    var refreshToken: String? = nil
    
    enum CodingKeys: String, CodingKey {
        case studentId = "student_id"
        case name, message
        case accessToken = "access_token"
        case refreshToken = "refresh_token"
    }
}

/// Atomic professor enrollment request. The backend consumes the invitation,
/// creates the account and organization membership, and returns tokens.
struct ProfessorActivationRequest: Encodable {
    let professorCode: String
    let username: String
    let email: String
    let name: String
    let password: String
    let confirmPassword: String
}

// MARK: - SOTA Phase 2: MFA Models

/// MFA setup response from /api/auth/mfa/setup
struct MFASetupRequest: Encodable {
    let password: String
}

struct MFASetupResponse: Codable {
    let secret: String
    let qrCodeUrl: String
    let backupCodes: [String]
    
    enum CodingKeys: String, CodingKey {
        case secret
        case qrCodeUrl
        case backupCodes
    }
}

/// MFA verify request
struct MFAVerifyRequest: Encodable {
    let code: String
}

/// MFA verification response from /api/auth/mfa/verify.
struct MFAVerifyResponse: Decodable {
    let status: String
    let backupCodes: [String]
}

/// MFA disable request (requires password confirmation)
struct MFADisableRequest: Encodable {
    let password: String
}

/// MFA status response
struct MFAStatusResponse: Codable {
    let enabled: Bool
}

// MARK: - Professor Code Models

/// Professor code redemption request
struct RedeemCodeRequest: Encodable {
    let code: String
}

/// Professor code redemption response
struct RedeemCodeResponse: Codable {
    let status: String
    let role: String
    let accessToken: String
    let tokenType: String
    
    enum CodingKeys: String, CodingKey {
        case status, role
        case accessToken = "accessToken"
        case tokenType = "tokenType"
    }
}

// MARK: - Change Password Models

struct ChangePasswordRequest: Encodable {
    let oldPassword: String
    let newPassword: String
    
    enum CodingKeys: String, CodingKey {
        case oldPassword = "old_password"
        case newPassword = "new_password"
    }
}

struct ChangePasswordResponse: Codable {
    let status: String
}

// MARK: - Join Class Models

struct JoinClassRequest: Encodable {
    let joinCode: String
    
    enum CodingKeys: String, CodingKey {
        case joinCode = "join_code"
    }
}

struct JoinClassResponse: Codable {
    let classId: String
    let className: String
    
    enum CodingKeys: String, CodingKey {
        case classId
        case className
    }
}

// MARK: - Password Reset Models

struct ForgotPasswordRequest: Encodable {
    let email: String
    
    enum CodingKeys: String, CodingKey {
        case email
    }
}

struct ForgotPasswordResponse: Codable {
    let status: String
    let token: String?
    
    enum CodingKeys: String, CodingKey {
        case status
        case token
    }
}

struct ResetPasswordRequest: Encodable {
    let token: String
    let newPassword: String
    
    enum CodingKeys: String, CodingKey {
        case token
        case newPassword = "new_password"
    }
}

struct ResetPasswordResponse: Codable {
    let status: String
    
    enum CodingKeys: String, CodingKey {
        case status
    }
}

/// Apple Sign In credential type.
enum AuthProvider: String {
    case apple = "apple"
    case google = "google"
    case professor = "professor"
}
