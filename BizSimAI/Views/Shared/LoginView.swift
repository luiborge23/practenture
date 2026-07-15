// LoginView.swift
// BizSimAI — Onboarding Wizard with Professor Codes, Student Registration, MFA
// Full user journey: Role → Credentials → Code → MFA → Dashboard

import SwiftUI
import AuthenticationServices
#if canImport(GoogleSignIn)
@preconcurrency import GoogleSignIn
#endif

struct LoginView: View {
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    // Wizard state
    @State private var step: OnboardingStep = .roleSelection
    @State private var selectedRole: SelectedRole = .student

    // Form fields
    @State private var username: String = ""
    @State private var password: String = ""
    @State private var confirmPassword: String = ""
    @State private var fullName: String = ""
    @State private var studentId: String = ""
    @State private var professorCode: String = ""
    @State private var classJoinCode: String = ""
    @State private var mfaCode: String = ""
    @State private var forgotEmail: String = ""
    @State private var resetToken: String = ""
    @State private var newPassword: String = ""
    @State private var confirmPasswordReset: String = ""

    // UI state
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    @State private var mfaSetupData: MFASetupResponse?
    @State private var mfaBackupCodes: [String] = []
    @State private var showingMFASetup = false

    // Pending login state (for MFA retry)
    @State private var pendingUsername = ""
    @State private var pendingPassword = ""
    @State private var pendingIsProfessor = false
    
    // Pending OAuth login state (for professor code entry)
    @State private var pendingOAuthProvider = ""
    @State private var pendingOAuthIdToken = ""

    // Professor existence — gates student onboarding
    @State private var professorAvailable: Bool = true
    @State private var professorStatusMessage: String? = nil

    enum OnboardingStep {
        case roleSelection
        case professorLogin          // existing professor: username + password
        case professorCodeEntry     // new professor: enter access code
        case professorCreateAccount // new professor: create username + password
        case studentLogin           // existing student: student ID + password
        case studentRegister        // new student: register
        case studentJoinClass       // student: enter class join code
        case mfaEntry               // MFA code entry (after login if enabled)
        case mfaSetup               // MFA setup (optional, after professor onboarding)
        case forgotPassword         // enter email for password reset
        case resetPassword          // enter token + new password
    }

    enum SelectedRole {
        case professor
        case student
    }

    var body: some View {
        NavigationStack {
            VStack(spacing: 0) {
                // Header
                headerView

                // Step content
                switch step {
                case .roleSelection:
                    roleSelectionStep
                case .professorLogin:
                    professorLoginStep
                case .professorCodeEntry:
                    professorCodeEntryStep
                case .professorCreateAccount:
                    professorCreateAccountStep
                case .studentLogin:
                    studentLoginStep
                case .studentRegister:
                    studentRegisterStep
                case .studentJoinClass:
                    studentJoinClassStep
                case .mfaEntry:
                    mfaEntryStep
                case .mfaSetup:
                    mfaSetupStep
                case .forgotPassword:
                    forgotPasswordStep
                case .resetPassword:
                    resetPasswordStep
                }

                Spacer(minLength: 8)

                // Social login (always available except on MFA steps and OAuth code entry)
                if step != .mfaEntry && step != .mfaSetup && step != .roleSelection && !(step == .professorCodeEntry && pendingOAuthProvider != "") {
                    socialLoginSection
                }
            }
            .padding(.horizontal, 24)
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if step != .roleSelection {
                        Button("Back") {
                            goBack()
                        }
                    }
                }
                ToolbarItem(placement: .cancellationAction) {
                    if step == .roleSelection {
                        Button("Cancel") { dismiss() }
                    }
                }
            }
            .sheet(isPresented: $showingMFASetup) {
                if let setupData = mfaSetupData {
                    MFASetupView(
                        setupData: setupData,
                        mfaVerifyCode: $mfaCode,
                        isLoading: $isLoading,
                        errorMessage: $errorMessage,
                        onVerify: { Task { await verifyAndEnableMFA() } },
                        onCancel: {
                            showingMFASetup = false
                            mfaCode = ""
                            errorMessage = nil
                            finishOnboarding()
                        }
                    )
                }
            }
            .task {
                // Check professor existence on load — gates student onboarding
                await checkProfessorAvailability()
            }
        }
    }

    // MARK: - Professor Availability Check

    @MainActor
    private func checkProfessorAvailability() async {
        do {
            let status = try await AuthManager.shared.checkProfessorStatus()
            professorAvailable = status.professorExists
            if !status.professorExists {
                professorStatusMessage = status.message
            }
        } catch {
            // If the endpoint is unreachable, assume professor exists (optimistic)
            professorAvailable = true
            professorStatusMessage = nil
        }
    }

    // MARK: - Professor Dependency Error View

    private var professorDependencyErrorView: some View {
        VStack(spacing: 12) {
            Image(systemName: "exclamationmark.triangle.fill")
                .font(.system(size: 40))
                .foregroundStyle(.orange)

            Text("Student Access Unavailable")
                .font(.headline)

            if let msg = professorStatusMessage {
                Text(msg)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            } else {
                Text("No professor account exists in the system. Students can only join classes that have an active professor.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            Button {
                step = .roleSelection
                errorMessage = nil
            } label: {
                Text("← Back to Role Selection")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(.blue)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Header

    private var headerView: some View {
        VStack(spacing: 8) {
            Circle()
                .fill(.blue.gradient)
                .frame(width: 48, height: 48)
                .overlay(
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.system(size: 22, weight: .bold))
                        .foregroundStyle(.white)
                )
                .shadow(color: .blue.opacity(0.3), radius: 10, y: 4)

            Text(stepTitle)
                .font(.title2)
                .fontWeight(.bold)

            if let stepSubtitle = stepSubtitleText {
                Text(stepSubtitle)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }
        }
        .padding(.top, 16)
        .padding(.bottom, 12)
    }

    private var stepTitle: String {
        switch step {
        case .roleSelection: return "Welcome to BizSimAI"
        case .professorLogin: return "Professor Login"
        case .professorCodeEntry: return "Professor Access"
        case .professorCreateAccount: return "Create Professor Account"
        case .studentLogin: return "Student Login"
        case .studentRegister: return "Student Registration"
        case .studentJoinClass: return "Join Your Class"
        case .mfaEntry: return "MFA Verification"
        case .mfaSetup: return "Set Up MFA"
        case .forgotPassword: return "Reset Password"
        case .resetPassword: return "Create New Password"
        }
    }

    private var stepSubtitleText: String? {
        switch step {
        case .roleSelection: return "Choose your role to get started"
        case .professorLogin: return "Enter your credentials to manage sessions"
        case .professorCodeEntry: return "Enter the access code provided by your administrator"
        case .professorCreateAccount: return "Set up your professor account"
        case .studentLogin: return "Enter your student ID and password"
        case .studentRegister: return "Create your student account"
        case .studentJoinClass: return "Enter the class code your professor shared"
        case .mfaEntry: return "Enter the 6-digit code from your authenticator app"
        case .mfaSetup: return "Secure your account with two-factor authentication"
        case .forgotPassword: return "Enter your email address and we'll send you a reset token"
        case .resetPassword: return "Enter the token from your email and set a new password"
        }
    }

    // MARK: - Step 1: Role Selection

    private var roleSelectionStep: some View {
        VStack(spacing: 16) {
            Button {
                selectedRole = .professor
                step = .professorLogin
            } label: {
                roleCard(
                    title: "I'm a Professor",
                    subtitle: "Create and manage business simulations",
                    icon: "person.fill.viewfinder",
                    color: .blue
                )
            }
            .buttonStyle(.borderless)

            Button {
                selectedRole = .student
                step = .studentLogin
            } label: {
                roleCard(
                    title: "I'm a Student",
                    subtitle: professorAvailable ? "Join a class and run your business" : "Student access requires an active professor",
                    icon: "graduationcap.fill",
                    color: .green
                )
            }
            .buttonStyle(.borderless)
            .disabled(!professorAvailable)

            // Toggle between login/register
            HStack(spacing: 16) {
                Text("New user?")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Button("Register as Student") {
                    selectedRole = .student
                    step = .studentRegister
                }
                .font(.caption)
                .fontWeight(.semibold)
                .disabled(!professorAvailable)
                Text("•")
                    .font(.caption)
                    .foregroundStyle(.secondary)
                Button("Have Professor Code") {
                    selectedRole = .professor
                    step = .professorCodeEntry
                }
                .font(.caption)
                .fontWeight(.semibold)
            }
            .padding(.top, 8)
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Professor Login (existing professor)

    private var professorLoginStep: some View {
        VStack(spacing: 12) {
            TextField("Username", text: $username)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)

            SecureField("Password", text: $password)
                .textFieldStyle(.roundedBorder)

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await handleProfessorLogin() } } label: {
                actionButtonLabel("Login", color: .blue)
            }
            .disabled(isLoading || username.isEmpty || password.isEmpty)

            Button {
                step = .professorCodeEntry
                errorMessage = nil
            } label: {
                Text("Have a professor access code? Redeem it →")
                    .font(.caption)
                    .foregroundStyle(.blue)
            }

            Button {
                step = .forgotPassword
                errorMessage = nil
            } label: {
                Text("Forgot password?")
                    .font(.caption)
                    .foregroundStyle(.blue)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Professor Code Entry (new professor)

    private var professorCodeEntryStep: some View {
        VStack(spacing: 12) {
            Image(systemName: "key.fill")
                .font(.system(size: 40))
                .foregroundStyle(.blue)
                .padding(.bottom, 4)

            Text(pendingOAuthProvider != "" ? "Enter Your Professor Code" : "Professor Access Code")
                .font(.headline)

            let providerName = pendingOAuthProvider == "apple" ? "Apple" : "Google"
            Text(pendingOAuthProvider != ""
                 ? "You signed in with \(providerName). Enter your professor code to create your account."
                 : "You'll create an account first, then redeem your professor code to upgrade your role.")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            TextField("PROF-XXXX-XXXX", text: $professorCode)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .multilineTextAlignment(.center)
                .font(.system(size: 18, weight: .bold, design: .monospaced))
                .textFieldStyle(.roundedBorder)
                .frame(maxWidth: 280)

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await handleProfessorCodeRedeem() } } label: {
                actionButtonLabel("Continue", color: .blue)
            }
            .disabled(isLoading || professorCode.isEmpty)

            if pendingOAuthProvider == "" {
                Button {
                    step = .professorLogin
                    errorMessage = nil
                } label: {
                    Text("Already have a professor account? Login →")
                        .font(.caption)
                        .foregroundStyle(.blue)
                }
            } else {
                Button {
                    pendingOAuthProvider = ""
                    pendingOAuthIdToken = ""
                    professorCode = ""
                    errorMessage = nil
                    step = .roleSelection
                } label: {
                    Text("← Back to role selection")
                        .font(.caption)
                        .foregroundStyle(.blue)
                }
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Professor Create Account (after code validated)

    private var professorCreateAccountStep: some View {
        VStack(spacing: 12) {
            TextField("Username", text: $username)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)

            TextField("Full Name", text: $fullName)
                .textInputAutocapitalization(.words)
                .textFieldStyle(.roundedBorder)

            SecureField("Password", text: $password)
                .textFieldStyle(.roundedBorder)

            SecureField("Confirm Password", text: $confirmPassword)
                .textFieldStyle(.roundedBorder)

            passwordValidationView

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await handleProfessorCreateAccount() } } label: {
                actionButtonLabel("Create Account & Redeem Code", color: .blue)
            }
            .disabled(isLoading || username.isEmpty || fullName.isEmpty || !isPasswordValid)
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Student Login (existing student)

    private var studentLoginStep: some View {
        Group {
            if !professorAvailable {
                professorDependencyErrorView
            } else {
                VStack(spacing: 12) {
                    TextField("Student ID (S12345678)", text: $studentId)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textFieldStyle(.roundedBorder)

                    SecureField("Password", text: $password)
                        .textFieldStyle(.roundedBorder)

                    if let error = errorMessage {
                        Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
                    }

                    Button { Task { await handleStudentLogin() } } label: {
                        actionButtonLabel("Login", color: .green)
                    }
                    .disabled(isLoading || studentId.isEmpty || password.isEmpty)

                    Button {
                        step = .studentRegister
                        errorMessage = nil
                    } label: {
                        Text("New student? Register →")
                            .font(.caption)
                            .foregroundStyle(.green)
                    }

                    Button {
                        step = .forgotPassword
                        errorMessage = nil
                    } label: {
                        Text("Forgot password?")
                            .font(.caption)
                            .foregroundStyle(.blue)
                    }
                }
                .padding(.top, 8)
            }
        }
    }

    // MARK: - Step: Student Register (new student)

    private var studentRegisterStep: some View {
        Group {
            if !professorAvailable {
                professorDependencyErrorView
            } else {
                VStack(spacing: 12) {
                    TextField("Student ID (S12345678)", text: $studentId)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .textFieldStyle(.roundedBorder)

                    TextField("Full Name", text: $fullName)
                        .textInputAutocapitalization(.words)
                        .textFieldStyle(.roundedBorder)

                    SecureField("Password", text: $password)
                        .textFieldStyle(.roundedBorder)

                    SecureField("Confirm Password", text: $confirmPassword)
                        .textFieldStyle(.roundedBorder)

                    passwordValidationView

                    if let error = errorMessage {
                        Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
                    }

                    Button { Task { await handleStudentRegister() } } label: {
                        actionButtonLabel("Register", color: .green)
                    }
                    .disabled(isLoading || studentId.isEmpty || fullName.isEmpty || !isPasswordValid)

                    Button {
                        step = .studentLogin
                        errorMessage = nil
                    } label: {
                        Text("Already registered? Login →")
                            .font(.caption)
                            .foregroundStyle(.green)
                    }
                }
                .padding(.top, 8)
            }
        }
    }

    // MARK: - Step: Student Join Class

    private var studentJoinClassStep: some View {
        VStack(spacing: 12) {
            Image(systemName: "person.badge.plus")
                .font(.system(size: 40))
                .foregroundStyle(.green)
                .padding(.bottom, 4)

            TextField("Class Code (e.g., ABC123)", text: $classJoinCode)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .multilineTextAlignment(.center)
                .font(.system(size: 18, weight: .bold, design: .monospaced))
                .textFieldStyle(.roundedBorder)
                .frame(maxWidth: 280)

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await handleJoinClass() } } label: {
                actionButtonLabel("Join Class", color: .green)
            }
            .disabled(isLoading || classJoinCode.isEmpty)

            Button {
                // Skip — go to student dashboard without joining a class
                finishOnboarding()
            } label: {
                Text("Skip for now →")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: MFA Entry (login with MFA)

    private var mfaEntryStep: some View {
        VStack(spacing: 16) {
            Image(systemName: "lock.shield.fill")
                .font(.system(size: 50))
                .foregroundStyle(.blue)

            Text("Enter the 6-digit code from your authenticator app")
                .font(.caption)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)

            TextField("000000", text: $mfaCode)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.center)
                .font(.system(size: 28, weight: .bold, design: .monospaced))
                .textFieldStyle(.roundedBorder)
                .frame(maxWidth: 200)
                .onChange(of: mfaCode) { _, newValue in
                    if newValue.count > 6 { mfaCode = String(newValue.prefix(6)) }
                }

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await verifyMFAAndLogin() } } label: {
                actionButtonLabel("Verify", color: .blue)
            }
            .disabled(isLoading || mfaCode.count != 6)
        }
        .padding(.top, 8)
    }

    // MARK: - Step: MFA Setup (optional after professor onboarding)

    private var mfaSetupStep: some View {
        VStack(spacing: 16) {
            Image(systemName: "checkmark.seal.fill")
                .font(.system(size: 50))
                .foregroundStyle(.green)

            Text("Professor Account Created!")
                .font(.headline)
                .foregroundStyle(.green)

            Text("Welcome, \(AuthManager.shared.currentUser?.name ?? "Professor"). Your professor account is ready.")
                .font(.subheadline)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)

            Divider().padding(.horizontal, 20)

            Image(systemName: "lock.shield")
                .font(.system(size: 40))
                .foregroundStyle(.blue)

            Text("Would you like to enable two-factor authentication?")
                .font(.subheadline)
                .multilineTextAlignment(.center)

            Text("This adds an extra layer of security. You'll need an authenticator app like Google Authenticator or Authy.")
                .font(.caption)
                .multilineTextAlignment(.center)
                .foregroundStyle(.secondary)

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await startMFASetup() } } label: {
                actionButtonLabel("Set Up MFA", color: .blue)
            }
            .disabled(isLoading)

            Button {
                finishOnboarding()
            } label: {
                Text("Skip — Go to Dashboard →")
                    .font(.subheadline)
                    .fontWeight(.semibold)
                    .foregroundStyle(.blue)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Forgot Password (enter email)

    private var forgotPasswordStep: some View {
        VStack(spacing: 12) {
            Image(systemName: "key.circle.fill")
                .font(.system(size: 40))
                .foregroundStyle(.blue)
                .padding(.bottom, 4)

            Text("Enter your email address")
                .font(.headline)

            Text("We'll generate a reset token for you to use on the next screen.")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            TextField("email@example.com", text: $forgotEmail)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.emailAddress)
                .textFieldStyle(.roundedBorder)

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await handleForgotPassword() } } label: {
                actionButtonLabel("Send Reset Token", color: .blue)
            }
            .disabled(isLoading || forgotEmail.isEmpty)

            Button {
                step = pendingIsProfessor ? .professorLogin : .studentLogin
                errorMessage = nil
            } label: {
                Text("← Back to login")
                    .font(.caption)
                    .foregroundStyle(.blue)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Reset Password (token + new password)

    private var resetPasswordStep: some View {
        VStack(spacing: 12) {
            Image(systemName: "lock.open.circle.fill")
                .font(.system(size: 40))
                .foregroundStyle(.blue)
                .padding(.bottom, 4)

            Text("Create New Password")
                .font(.headline)

            Text("Enter the reset token from your email and set a new password.")
                .font(.caption2)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)

            TextField("Reset Token", text: $resetToken)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(.roundedBorder)

            SecureField("New Password", text: $newPassword)
                .textFieldStyle(.roundedBorder)

            SecureField("Confirm New Password", text: $confirmPasswordReset)
                .textFieldStyle(.roundedBorder)

            passwordValidationView

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await handleResetPassword() } } label: {
                actionButtonLabel("Reset Password", color: .blue)
            }
            .disabled(isLoading || resetToken.isEmpty || !isPasswordValid)

            Button {
                step = .forgotPassword
                errorMessage = nil
            } label: {
                Text("← Back to email entry")
                    .font(.caption)
                    .foregroundStyle(.blue)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Social Login Section

    private var socialLoginSection: some View {
        VStack(spacing: 8) {
            Divider().padding(.horizontal, 20)
            Text("Or sign in with")
                .font(.caption2)
                .foregroundStyle(.secondary)

            HStack(spacing: 8) {
                SignInWithAppleButton(.signIn) { request in
                    request.requestedScopes = [.fullName, .email]
                } onCompletion: { result in
                    Task { await handleAppleSignIn(result) }
                }
                .signInWithAppleButtonStyle(.black)
                .frame(height: 36)

                Button { handleGoogleSignIn() } label: {
                    HStack(spacing: 6) {
                        Circle().fill(Color(red: 0.95, green: 0.28, blue: 0.23)).frame(width: 16, height: 16)
                        Text("Google").font(.caption2).fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 8)
                    .background(Color.gray.opacity(0.1))
                    .cornerRadius(8)
                }
                .disabled(isLoading)
            }
            .padding(.horizontal, 8)
        }
        .padding(.bottom, 12)
    }

    // MARK: - Helper Views

    private func roleCard(title: String, subtitle: String, icon: String, color: Color) -> some View {
        VStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(color.gradient.opacity(0.15))
                    .frame(width: 56, height: 56)
                Image(systemName: icon)
                    .font(.system(size: 24))
                    .foregroundStyle(color)
            }
            VStack(spacing: 4) {
                Text(title).font(.headline).foregroundStyle(.primary)
                Text(subtitle).font(.caption).foregroundStyle(.secondary).multilineTextAlignment(.center)
            }
            Image(systemName: "arrow.right.circle.fill").font(.title3).foregroundStyle(color)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
        .padding(.horizontal, 16)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(Color.gray.opacity(0.08))
                .shadow(color: color.opacity(0.1), radius: 10, y: 4)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(color.opacity(0.15), lineWidth: 1)
        )
    }

    private func actionButtonLabel(_ text: String, color: Color) -> some View {
        HStack {
            if isLoading { ProgressView().tint(.white) }
            Text(text).fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(color)
        .foregroundStyle(.white)
        .cornerRadius(10)
    }

    // MARK: - Password Validation

    /// All password requirements with real-time check status.
    private struct PasswordCheck: Identifiable {
        let id = UUID()
        let label: String
        let isMet: Bool
    }

    private var passwordChecks: [PasswordCheck] {
        [
            PasswordCheck(label: "8+ characters", isMet: password.count >= 8),
            PasswordCheck(label: "1 uppercase letter (A-Z)", isMet: password.contains { $0.isUppercase }),
            PasswordCheck(label: "1 lowercase letter (a-z)", isMet: password.contains { $0.isLowercase }),
            PasswordCheck(label: "1 digit (0-9)", isMet: password.contains { $0.isNumber }),
            PasswordCheck(label: "1 special character (!@#$%^&*)", isMet: password.contains { "!@#$%^&*()_+-=[]{}|;':\",./<>?`~".contains($0) }),
        ]
    }

    private var passwordsMatch: Bool {
        !confirmPassword.isEmpty && password == confirmPassword
    }

    /// True only when every password requirement is met AND passwords match.
    private var isPasswordValid: Bool {
        passwordChecks.allSatisfy { $0.isMet } && passwordsMatch
    }

    /// Real-time password validation checklist — green checkmarks appear as user types.
    /// Only shows when the user has started typing a password.
    private var passwordValidationView: some View {
        Group {
            if !password.isEmpty {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Password requirements:")
                        .font(.caption2)
                        .foregroundStyle(.secondary)

                    ForEach(passwordChecks) { check in
                        HStack(spacing: 6) {
                            Image(systemName: check.isMet ? "checkmark.circle.fill" : "circle")
                                .font(.caption2)
                                .foregroundStyle(check.isMet ? .green : .secondary)
                            Text(check.label)
                                .font(.caption2)
                                .foregroundStyle(check.isMet ? .green : .secondary)
                        }
                    }

                    // Password match indicator
                    if !confirmPassword.isEmpty {
                        HStack(spacing: 6) {
                            Image(systemName: passwordsMatch ? "checkmark.circle.fill" : "xmark.circle.fill")
                                .font(.caption2)
                                .foregroundStyle(passwordsMatch ? .green : .red)
                            Text(passwordsMatch ? "Passwords match" : "Passwords don't match")
                                .font(.caption2)
                                .foregroundStyle(passwordsMatch ? .green : .red)
                        }
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.top, 2)
            }
        }
    }

    // MARK: - Navigation

    private func goBack() {
        switch step {
        case .professorLogin:
            step = .roleSelection
        case .professorCodeEntry:
            step = .professorLogin
        case .professorCreateAccount:
            step = .professorCodeEntry
        case .studentLogin:
            step = .roleSelection
        case .studentRegister:
            step = .studentLogin
        case .studentJoinClass:
            step = .studentLogin
        case .mfaEntry:
            step = pendingIsProfessor ? .professorLogin : .studentLogin
        case .mfaSetup:
            finishOnboarding()
        default:
            step = .roleSelection
        }
        errorMessage = nil
    }

    private func finishOnboarding() {
        let isProf = AuthManager.shared.currentUser?.role == "professor"
        UserDefaults.standard.set(isProf, forKey: "bizsimai_professor_mode")
        HapticsManager.success()
        // Set mode BEFORE dismiss so ContentView switches immediately
        appState.selectMode(isProf ? .professor : .student)
        dismiss()
    }

    // MARK: - Handlers

    private func handleProfessorLogin() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        do {
            let response = try await AuthManager.shared.loginProfessor(username: username, password: password)
            if response.mfaRequired == true {
                pendingUsername = username
                pendingPassword = password
                pendingIsProfessor = true
                step = .mfaEntry
                return
            }
            finishOnboarding()
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            HapticsManager.error()
        }
    }

    private func handleProfessorCodeRedeem() async {
        errorMessage = nil
        guard !professorCode.isEmpty else {
            errorMessage = "Please enter your professor code."
            return
        }
        
        if pendingOAuthProvider != "" && pendingOAuthIdToken != "" {
            // OAuth flow: login with stored token + professor code
            do {
                let response = try await AuthManager.shared.loginWithOAuth(
                    provider: pendingOAuthProvider,
                    idToken: pendingOAuthIdToken,
                    professorCode: professorCode
                )
                
                if response.professorCodeRequired == true {
                    errorMessage = "Invalid professor code. Please check and try again."
                    return
                }
                
                // Clear pending state
                pendingOAuthProvider = ""
                pendingOAuthIdToken = ""
                
                // Success — proceed to onboarding
                step = .studentJoinClass
            } catch {
                errorMessage = UserFriendlyError.message(for: error)
            }
        } else {
            // Traditional flow: proceed to account creation
            step = .professorCreateAccount
        }
    }

    private func handleProfessorCreateAccount() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        guard !username.isEmpty, !fullName.isEmpty, !password.isEmpty else {
            errorMessage = "Please fill in all fields."
            return
        }
        guard password == confirmPassword else {
            errorMessage = "Passwords don't match."
            return
        }
        do {
            // Atomic: register → login → redeem professor code → set role=professor
            let response = try await AuthManager.shared.registerProfessor(
                username: username,
                password: password,
                name: fullName,
                professorCode: professorCode
            )
            // Check if MFA is required after registration (shouldn't normally happen for new accounts)
            if response.mfaRequired == true {
                pendingUsername = username
                pendingPassword = password
                pendingIsProfessor = true
                step = .mfaEntry
                return
            }
            // Success — role is now "professor", offer MFA setup
            step = .mfaSetup
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
        }
    }

    private func handleStudentLogin() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        guard !studentId.isEmpty, !password.isEmpty else {
            errorMessage = "Please enter your student ID and password."
            return
        }
        do {
            let response = try await AuthManager.shared.loginStudent(username: studentId, password: password)
            if response.mfaRequired == true {
                pendingUsername = studentId
                pendingPassword = password
                pendingIsProfessor = false
                step = .mfaEntry
                return
            }
            step = .studentJoinClass
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            HapticsManager.error()
        }
    }

    private func handleStudentRegister() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        guard !studentId.isEmpty, !fullName.isEmpty, !password.isEmpty else {
            errorMessage = "Please fill in all fields."
            return
        }
        guard password == confirmPassword else {
            errorMessage = "Passwords don't match."
            return
        }
        do {
            _ = try await AuthManager.shared.register(username: studentId, password: password, studentId: studentId, name: fullName)
            step = .studentJoinClass
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            HapticsManager.error()
        }
    }

    private func handleJoinClass() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        guard !classJoinCode.isEmpty else {
            errorMessage = "Please enter a class code."
            return
        }
        do {
            _ = try await AuthManager.shared.joinClass(joinCode: classJoinCode)
            finishOnboarding()
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            HapticsManager.error()
        }
    }

    // MARK: - MFA

    private func verifyMFAAndLogin() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        do {
            if pendingIsProfessor {
                let response = try await AuthManager.shared.loginProfessor(username: pendingUsername, password: pendingPassword, mfaCode: mfaCode)
                if response.mfaRequired == true {
                    errorMessage = "Invalid MFA code. Try again."
                    return
                }
            } else {
                let response = try await AuthManager.shared.loginStudent(username: pendingUsername, password: pendingPassword, mfaCode: mfaCode)
                if response.mfaRequired == true {
                    errorMessage = "Invalid MFA code. Try again."
                    return
                }
                // Student goes to join class after MFA, not directly to dashboard
                step = .studentJoinClass
                mfaCode = ""
                return
            }
            mfaCode = ""
            finishOnboarding()
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
        }
    }

    private func startMFASetup() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        do {
            let setup = try await AuthManager.shared.setupMFA()
            mfaSetupData = setup
            showingMFASetup = true
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
        }
    }

    private func verifyAndEnableMFA() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        do {
            let result = try await AuthManager.shared.verifyMFA(code: mfaCode)
            if let backupCodes = result["backup_codes"] as? [String] {
                mfaBackupCodes = backupCodes
            }
            showingMFASetup = false
            mfaCode = ""
            errorMessage = nil
            finishOnboarding()
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
        }
    }

    // MARK: - Apple Sign In

    private func handleAppleSignIn(_ result: Result<ASAuthorization, Error>) async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        switch result {
        case .success(let auth):
            guard let appleIdCredential = auth.credential as? ASAuthorizationAppleIDCredential,
                  let idTokenData = appleIdCredential.identityToken,
                  let idToken = String(data: idTokenData, encoding: .utf8) else {
                errorMessage = "Failed to get Apple ID token."
                return
            }
            do {
                let response = try await AuthManager.shared.loginWithApple(credential: auth.credential)
                if response.professorCodeRequired == true {
                    // New user — store token and ask for professor code
                    pendingOAuthProvider = "apple"
                    pendingOAuthIdToken = idToken
                    step = .professorCodeEntry
                    return
                }
                // Existing user — proceed normally
                step = .studentJoinClass
            } catch {
                errorMessage = "Apple Sign-In failed: \(UserFriendlyError.message(for: error))"
            }
        case .failure(let error):
            let nsError = error as NSError
            if nsError.code != ASAuthorizationError.canceled.rawValue {
                errorMessage = "Apple Sign-In: \(UserFriendlyError.message(for: error))"
            }
        }
    }

    // MARK: - Google Sign In

    private func handleGoogleSignIn() {
        #if canImport(GoogleSignIn)
        // Check Google Sign-In is configured via GIDClientID in Info.plist
        guard let plistPath = Bundle.main.path(forResource: "Info", ofType: "plist"),
              let plist = NSDictionary(contentsOfFile: plistPath),
              let clientID = plist["GIDClientID"] as? String,
              !clientID.isEmpty, !clientID.hasPrefix("YOUR_") else {
            errorMessage = "Google Sign-In not configured. Contact your administrator."
            return
        }
        guard let presentingVC = UIApplication.shared.connectedScenes
            .compactMap({ $0 as? UIWindowScene })
            .flatMap({ $0.windows })
            .first(where: { $0.isKeyWindow })?.rootViewController else {
            errorMessage = "Could not find presenting view controller."
            return
        }
        isLoading = true; errorMessage = nil
        GIDSignIn.sharedInstance.signIn(withPresenting: presentingVC) { [self] signInResult, error in
            Task { @MainActor in
                defer { isLoading = false }
                if let error {
                    let nsError = error as NSError
                    if nsError.code != -7 {
                        errorMessage = "Google Sign-In failed: \(UserFriendlyError.message(for: error))"
                    }
                    return
                }
                guard let idToken = signInResult?.user.idToken?.tokenString else {
                    errorMessage = "Failed to get Google ID token."
                    return
                }
                do {
                    let response = try await AuthManager.shared.loginWithGoogle(idToken: idToken)
                    if response.professorCodeRequired == true {
                        // New user — store token and ask for professor code
                        pendingOAuthProvider = "google"
                        pendingOAuthIdToken = idToken
                        step = .professorCodeEntry
                        return
                    }
                    // Existing user — proceed normally
                    step = .studentJoinClass
                } catch {
                    errorMessage = "Google Sign-In failed: \(UserFriendlyError.message(for: error))"
                }
            }
        }
        #else
        errorMessage = "Google Sign-In is not available on this device."
        #endif
    }

    // MARK: - Password Reset Handlers

    private func handleForgotPassword() async {
        isLoading = true; errorMessage = nil
        guard !forgotEmail.isEmpty else {
            errorMessage = "Please enter your email address."
            isLoading = false
            return
        }
        do {
            let token = try await AuthManager.shared.forgotPassword(email: forgotEmail)
            // Backend always returns success (security — prevents email enumeration).
            if let token = token {
                // Token generated — show it to user so they can use it on the next screen
                errorMessage = nil
                resetToken = token  // Pre-fill the token field on next screen
                try await Task.sleep(nanoseconds: 1_500_000_000) // 1.5 seconds so user sees the message
                newPassword = ""
                confirmPasswordReset = ""
                step = .resetPassword
            } else {
                // No user found with that email — still show success to prevent enumeration
                errorMessage = "If an account exists for \(forgotEmail), a reset token has been generated. Enter it on the next screen."
                try await Task.sleep(nanoseconds: 1_500_000_000) // 1.5 seconds
                step = .resetPassword
            }
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            HapticsManager.error()
        }
        isLoading = false
    }

    private func handleResetPassword() async {
        isLoading = true; errorMessage = nil; defer { isLoading = false }
        guard !resetToken.isEmpty else {
            errorMessage = "Please enter the reset token."
            return
        }
        guard !newPassword.isEmpty, !confirmPasswordReset.isEmpty else {
            errorMessage = "Please enter and confirm your new password."
            return
        }
        guard newPassword == confirmPasswordReset else {
            errorMessage = "Passwords don't match."
            return
        }
        do {
            try await AuthManager.shared.resetPassword(token: resetToken, newPassword: newPassword)
            errorMessage = "Password reset successful! You can now log in with your new password."
            HapticsManager.success()
            // Clear all reset fields
            forgotEmail = ""
            resetToken = ""
            newPassword = ""
            confirmPasswordReset = ""
            // Small delay so user sees success message before going back to login
            try await Task.sleep(nanoseconds: 2_000_000_000) // 2 seconds
            step = pendingIsProfessor ? .professorLogin : .studentLogin
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
            HapticsManager.error()
        }
    }
}

// MARK: - MFA Setup View (sheet with QR code + backup codes)

struct MFASetupView: View {
    let setupData: MFASetupResponse
    @Binding var mfaVerifyCode: String
    @Binding var isLoading: Bool
    @Binding var errorMessage: String?
    let onVerify: () async -> Void
    let onCancel: () -> Void

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(spacing: 16) {
                    Image(systemName: "qrcode")
                        .font(.system(size: 60))
                        .foregroundStyle(.blue)

                    Text("Set Up Authenticator")
                        .font(.headline)

                    Text("1. Open Google Authenticator or Authy")
                        .font(.caption).foregroundStyle(.secondary)
                    Text("2. Add a new account manually")
                        .font(.caption).foregroundStyle(.secondary)
                    Text("3. Enter this secret:")
                        .font(.caption).foregroundStyle(.secondary)

                    Text(setupData.secret)
                        .font(.system(size: 16, weight: .bold, design: .monospaced))
                        .padding(8)
                        .background(Color.gray.opacity(0.15))
                        .cornerRadius(8)
                        .textSelection(.enabled)

                    Text("4. Enter the 6-digit code from your app:")
                        .font(.caption).foregroundStyle(.secondary)

                    TextField("000000", text: $mfaVerifyCode)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.center)
                        .font(.system(size: 24, weight: .bold, design: .monospaced))
                        .textFieldStyle(.roundedBorder)
                        .frame(maxWidth: 200)
                        .onChange(of: mfaVerifyCode) { _, newValue in
                            if newValue.count > 6 { mfaVerifyCode = String(newValue.prefix(6)) }
                        }

                    if let error = errorMessage {
                        Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
                    }

                    Button { Task { await onVerify() } } label: {
                        HStack {
                            if isLoading { ProgressView().tint(.white) }
                            Text("Verify & Enable MFA").fontWeight(.semibold)
                        }
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 12)
                        .background(.blue)
                        .foregroundStyle(.white)
                        .cornerRadius(10)
                    }
                    .disabled(isLoading || mfaVerifyCode.count != 6)

                    DisclosureGroup("QR Code URL (for web)") {
                        Text(setupData.qrCodeUrl)
                            .font(.system(size: 10, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .textSelection(.enabled)
                    }

                    DisclosureGroup("Backup Codes (save these!)") {
                        VStack(alignment: .leading, spacing: 4) {
                            ForEach(setupData.backupCodes, id: \.self) { code in
                                Text(code)
                                    .font(.system(size: 14, weight: .medium, design: .monospaced))
                            }
                        }
                        .padding(8)
                        .background(Color.yellow.opacity(0.1))
                        .cornerRadius(8)
                    }
                }
                .padding(.horizontal, 20)
            }
            .navigationTitle("MFA Setup")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Skip") { onCancel() }
                }
            }
        }
    }
}

#Preview {
    LoginView().environment(AppState())
}
