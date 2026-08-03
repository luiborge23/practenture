import AuthenticationServices
import CryptoKit
import SwiftUI
#if canImport(GoogleSignIn)
@preconcurrency import GoogleSignIn
#endif

struct AccountDeletionView: View {
    private struct ProviderProof {
        let token: String
        let nonce: String?
        let authorizationCode: String?
    }

    @Environment(\.dismiss) private var dismiss
    private let requirementsLoader: @MainActor () async throws -> AccountDeletionRequirements
    @State private var requirements: AccountDeletionRequirements?
    @State private var confirmation = ""
    @State private var password = ""
    @State private var mfaCode = ""
    @State private var providerProof: ProviderProof?
    @State private var activeAppleNonce: String?
    @State private var isLoading = true
    @State private var isDeleting = false
    @State private var showFinalConfirmation = false
    @State private var errorMessage: String?

    init(
        requirementsLoader: @escaping @MainActor () async throws -> AccountDeletionRequirements = {
            try await AuthManager.shared.accountDeletionRequirements()
        }
    ) {
        self.requirementsLoader = requirementsLoader
    }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    Text("Deleting your account permanently removes your sign-in credentials, active sessions, memberships, and personal profile data. Institutional gameplay records may be retained only after your identity and team name are anonymized.")
                    Text("Professors must end sessions they own before deleting their account. Students are detached from any active session when deletion completes. Professor classes are deactivated after deletion.")
                } header: {
                    Text("Permanent deletion")
                }

                if isLoading {
                    Section {
                        HStack {
                            Spacer()
                            ProgressView("Loading account requirements…")
                            Spacer()
                        }
                    }
                } else if let requirements {
                    Section {
                        TextField("Type \(requirements.confirmationPhrase)", text: $confirmation)
                            .textInputAutocapitalization(.characters)
                            .autocorrectionDisabled()
                            .accessibilityIdentifier("accountDeletionConfirmation")

                        if requirements.mfaRequired {
                            SecureField("Authenticator or recovery code", text: $mfaCode)
                                .textContentType(.oneTimeCode)
                                .keyboardType(.asciiCapable)
                                .accessibilityIdentifier("accountDeletionMFACode")
                        }

                        switch requirements.reauthentication {
                        case "password":
                            SecureField("Current password", text: $password)
                                .textContentType(.password)
                                .accessibilityIdentifier("accountDeletionPassword")
                            Button("Continue") {
                                providerProof = nil
                                showFinalConfirmation = true
                            }
                            .disabled(!isReadyForPasswordDeletion)
                        case "apple":
                            appleReauthenticationButton
                                .disabled(!hasAllRequiredConfirmation || isDeleting)
                        case "google":
                            googleReauthenticationButton
                                .disabled(!hasAllRequiredConfirmation || isDeleting)
                        default:
                            Text("This account cannot be deleted in the app because its authentication method is unsupported.")
                                .foregroundStyle(.red)
                        }
                    } header: {
                        Text("Confirm your identity")
                    } footer: {
                        Text(reauthenticationFooter(requirements.reauthentication))
                    }
                }

                if let errorMessage {
                    Section {
                        Label(errorMessage, systemImage: "exclamationmark.triangle.fill")
                            .foregroundStyle(.red)
                            .accessibilityIdentifier("accountDeletionError")
                    }
                }
            }
            .navigationTitle("Delete Account")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }
                        .disabled(isDeleting)
                }
            }
            .task { await loadRequirements() }
            .interactiveDismissDisabled(isDeleting)
            .alert("Delete account permanently?", isPresented: $showFinalConfirmation) {
                Button("Cancel", role: .cancel) { providerProof = nil }
                Button("Delete Permanently", role: .destructive) {
                    Task { await performDeletion() }
                }
            } message: {
                Text("This cannot be undone. You will be signed out on this device immediately.")
            }
            .overlay {
                if isDeleting {
                    ZStack {
                        Color.black.opacity(0.25).ignoresSafeArea()
                        ProgressView("Deleting account…")
                            .padding()
                            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12))
                    }
                    .accessibilityElement(children: .combine)
                }
            }
        }
    }

    private var hasExactConfirmation: Bool {
        guard let requirements else { return false }
        return confirmation == requirements.confirmationPhrase
    }

    private var isReadyForPasswordDeletion: Bool {
        hasAllRequiredConfirmation && !password.isEmpty && !isDeleting
    }

    private var hasAllRequiredConfirmation: Bool {
        hasExactConfirmation && (requirements?.mfaRequired != true || !mfaCode.isEmpty)
    }

    private func reauthenticationFooter(_ method: String) -> String {
        switch method {
        case "password":
            return "Enter your current Practenture password."
        case "apple":
            return "Continue with the same Apple ID linked to this account. Practenture deletes the account immediately and durably revokes its Sign in with Apple authorization."
        case "google":
            return "Continue with the same Google account linked to this account. Google access on this device is disconnected after the server confirms deletion."
        default:
            return ""
        }
    }

    @ViewBuilder
    private var appleReauthenticationButton: some View {
        SignInWithAppleButton(.continue) { request in
            guard let nonce = makeAppleProviderNonce() else {
                errorMessage = "The deletion security challenge expired. Reload this screen and try again."
                return
            }
            activeAppleNonce = nonce
            request.nonce = nonce
        } onCompletion: { result in
            handleAppleReauthentication(result)
        }
        .signInWithAppleButtonStyle(.black)
        .frame(maxWidth: .infinity, minHeight: 50)
        .accessibilityLabel("Reauthenticate with Apple to delete account")
    }

    @ViewBuilder
    private var googleReauthenticationButton: some View {
        Button {
            beginGoogleReauthentication()
        } label: {
            Label("Reauthenticate with Google", systemImage: "person.badge.key.fill")
                .frame(maxWidth: .infinity, minHeight: 44)
        }
        .buttonStyle(.borderedProminent)
        .accessibilityIdentifier("accountDeletionGoogleReauthentication")
    }

    @MainActor
    private func loadRequirements() async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        do {
            requirements = try await requirementsLoader()
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
        }
    }

    private func makeAppleProviderNonce() -> String? {
        guard let challenge = requirements?.challenge, !challenge.isEmpty else {
            return nil
        }
        let digest = SHA256.hash(data: Data(challenge.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

    private func handleAppleReauthentication(
        _ result: Result<ASAuthorization, Error>
    ) {
        switch result {
        case .success(let authorization):
            guard
                let credential = authorization.credential as? ASAuthorizationAppleIDCredential,
                let tokenData = credential.identityToken,
                let token = String(data: tokenData, encoding: .utf8),
                let codeData = credential.authorizationCode,
                let authorizationCode = String(data: codeData, encoding: .utf8),
                let nonce = activeAppleNonce
            else {
                errorMessage = "Apple did not return the credentials required to delete this account."
                activeAppleNonce = nil
                return
            }
            providerProof = ProviderProof(
                token: token,
                nonce: nonce,
                authorizationCode: authorizationCode
            )
            activeAppleNonce = nil
            showFinalConfirmation = true
        case .failure(let error):
            activeAppleNonce = nil
            let nsError = error as NSError
            if nsError.code != ASAuthorizationError.canceled.rawValue {
                errorMessage = UserFriendlyError.message(for: error)
            }
        }
    }

    private func beginGoogleReauthentication() {
#if canImport(GoogleSignIn)
        guard let presentingViewController = UIApplication.shared.connectedScenes
            .compactMap({ $0 as? UIWindowScene })
            .flatMap({ $0.windows })
            .first(where: { $0.isKeyWindow })?.rootViewController else {
            errorMessage = "Could not present Google authentication."
            return
        }
        GIDSignIn.sharedInstance.signIn(withPresenting: presentingViewController) { result, error in
            Task { @MainActor in
                if let error {
                    let nsError = error as NSError
                    if nsError.code != -7 {
                        errorMessage = UserFriendlyError.message(for: error)
                    }
                    return
                }
                guard let token = result?.user.idToken?.tokenString else {
                    errorMessage = "Google did not return the credential required to delete this account."
                    return
                }
                providerProof = ProviderProof(
                    token: token,
                    nonce: nil,
                    authorizationCode: nil
                )
                showFinalConfirmation = true
            }
        }
#else
        errorMessage = "Google authentication is unavailable in this build."
#endif
    }

    @MainActor
    private func performDeletion() async {
        guard hasExactConfirmation, let requirements else {
            errorMessage = "Type DELETE exactly to continue."
            return
        }
        isDeleting = true
        errorMessage = nil
        defer { isDeleting = false }
        do {
            try await AuthManager.shared.deleteAccount(
                provider: requirements.provider,
                challengeId: requirements.challengeId,
                operationToken: requirements.operationToken,
                confirmation: confirmation,
                password: requirements.reauthentication == "password" ? password : nil,
                mfaCode: requirements.mfaRequired ? mfaCode : nil,
                providerToken: providerProof?.token,
                providerNonce: providerProof?.nonce,
                providerAuthorizationCode: providerProof?.authorizationCode
            )
            dismiss()
        } catch {
            providerProof = nil
            errorMessage = UserFriendlyError.message(for: error)
        }
    }
}
