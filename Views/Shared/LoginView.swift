// LoginView.swift
// Practenture — Onboarding Wizard with Professor Codes, Student Registration, MFA
// Full user journey: Role → Credentials → Code → MFA → Dashboard
//
// Professional dark theme with vibrant purple (#8b5cf6), clean cards,
// subtle shadows, and smooth animations inspired by practenture.com

import SwiftUI
import AuthenticationServices
#if canImport(GoogleSignIn)
@preconcurrency import GoogleSignIn
#endif

// Practenture theme is now part of the main module
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
                .foregroundStyle(PractentureTheme.warning)

            Text("Student Access Unavailable")
                .font(.headline)

            if let msg = professorStatusMessage {
                Text(msg)
                    .font(.caption)
                    .foregroundStyle(PractentureTheme.textSecondary)
                    .multilineTextAlignment(.center)
            } else {
                Text("No professor account exists in the system. Students can only join classes that have an active professor.")
                    .font(.caption)
                    .foregroundStyle(PractentureTheme.textSecondary)
                    .multilineTextAlignment(.center)
            }

            Button {
                step = .roleSelection
                errorMessage = nil
            } label: {
                Text("← Back to Role Selection")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(PractentureTheme.primary)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Header

    private var headerView: some View {
        VStack(spacing: 12) {
            // Animated logo container
            ZStack {
                Circle()
                    .fill(PractentureTheme.accentColor.opacity(0.12))
                    .frame(width: 80, height: 80)
                
                Image("Logo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 56, height: 56)
                    .shadow(color: PractentureTheme.accentColor.opacity(0.4), radius: 16, y: 8)
            }
            
            VStack(spacing: 4) {
                Text(stepTitle)
                    .font(.system(size: 28, weight: .bold, design: .rounded))
                    .foregroundStyle(
                        LinearGradient(
                            colors: [.white, PractentureTheme.accentColor],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    )
                    .shadow(color: PractentureTheme.accentColor.opacity(0.3), radius: 8, y: 4)
                
                if let stepSubtitle = stepSubtitleText {
                    Text(stepSubtitle)
                        .font(.subheadline)
                        .foregroundStyle(PractentureTheme.textSecondary)
                        .multilineTextAlignment(.center)
                        .lineHeightMultiple(1.5)
                }
            }
        }
        .padding(.top, 20)
        .padding(.bottom, 16)
    }

    private var stepTitle: String {
        switch step {
        case .roleSelection: return "Welcome to Practenture"
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
                    icon: "person.fill.viewfinder"
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
                    icon: "graduationcap.fill"
                )
            }
            .buttonStyle(.borderless)
            .disabled(!professorAvailable)

            // Toggle between login/register
            HStack(spacing: 16) {
                Text("New user?")
                    .font(.caption)
                    .foregroundStyle(PractentureTheme.textSecondary)
                Button("Register as Student") {
                    selectedRole = .student
                    step = .studentRegister
                }
                .font(.caption)
                .fontWeight(.semibold)
                .disabled(!professorAvailable)
                Text("•")
                    .font(.caption)
                    .foregroundStyle(PractentureTheme.textSecondary)
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
                Text(error).font(.caption2).foregroundStyle(PractentureTheme.error).multilineTextAlignment(.center)
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
                    .foregroundStyle(PractentureTheme.primary)
            }

            Button {
                step = .forgotPassword
                errorMessage = nil
            } label: {
                Text("Forgot password?")
                    .font(.caption)
                    .foregroundStyle(PractentureTheme.primary)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Professor Code Entry (new professor)

    private var professorCodeEntryStep: some View {
        VStack(spacing: 12) {
            Image(systemName: "key.fill")
                .font(.system(size: 40))
                .foregroundStyle(PractentureTheme.primary)
                .padding(.bottom, 4)

            Text(pendingOAuthProvider != "" ? "Enter Your Professor Code" : "Professor Access Code")
                .font(.headline)

            let providerName = pendingOAuthProvider == "apple" ? "Apple" : "Google"
            Text(pendingOAuthProvider != ""
                 ? "You signed in with \(providerName). Enter your professor code to create your account."
                 : "You'll create an account first, then redeem your professor code to upgrade your role.")
                .font(.caption2)
                .foregroundStyle(PractentureTheme.textSecondary)
                .multilineTextAlignment(.center)

            TextField("PROF-XXXX-XXXX", text: $professorCode)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .multilineTextAlignment(.center)
                .font(.system(size: 18, weight: .bold, design: .monospaced))
                .textFieldStyle(.roundedBorder)
                .frame(maxWidth: 280)

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(PractentureTheme.error).multilineTextAlignment(.center)
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
                        .foregroundStyle(PractentureTheme.primary)
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
                        .foregroundStyle(PractentureTheme.primary)
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
                Text(error).font(.caption2).foregroundStyle(PractentureTheme.error).multilineTextAlignment(.center)
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
                        Text(error).font(.caption2).foregroundStyle(PractentureTheme.error).multilineTextAlignment(.center)
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
                            .foregroundStyle(PractentureTheme.success)
                    }

                    Button {
                        step = .forgotPassword
                        errorMessage = nil
                    } label: {
                        Text("Forgot password?")
                            .font(.caption)
                            .foregroundStyle(PractentureTheme.primary)
                    }
                }
            }
        }
    }

    // MARK: - Action Button

    private func actionButtonLabel(_ text: String, color: Color) -> some View {
        HStack {
            if isLoading { ProgressView().tint(.white) }
            Text(text).fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 12)
        .background(PractentureTheme.primary)
        .foregroundStyle(.white)
        .cornerRadius(10)
        .shadow(color: PractentureTheme.primary.opacity(0.3), radius: 6, y: 2)
    }
}
