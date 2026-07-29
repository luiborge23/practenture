// LoginView.swift
// Practenture — Onboarding Wizard with Professor Codes, Student Registration, MFA
// Full user journey: Role → Credentials → Code → MFA → Dashboard

import SwiftUI
import AuthenticationServices
import CryptoKit
#if canImport(GoogleSignIn)
@preconcurrency import GoogleSignIn
#endif
#if canImport(GoogleSignInSwift)
import GoogleSignInSwift
#endif

// Practenture theme is now part of the main module
struct LoginView: View {
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss

    // Wizard state
    @State private var step: OnboardingStep = .authenticationMethods
    @State private var selectedRole: SelectedRole = .student

    init(
        initialRole: SelectedRole = .student,
        initialStep: OnboardingStep = .authenticationMethods
    ) {
        _selectedRole = State(initialValue: initialRole)
        _step = State(initialValue: initialStep)
    }

    // Form fields
    @State private var username: String = ""
    @State private var password: String = ""
    @State private var confirmPassword: String = ""
    @State private var fullName: String = ""
    @State private var email: String = ""
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
    @State private var pendingOAuthNonce: String? = nil
    @State private var activeAppleNonce: String? = nil

    // Professor existence — gates student onboarding
    @State private var professorAvailable: Bool = true
    @State private var professorStatusMessage: String? = nil

    enum OnboardingStep: String {
        case authenticationMethods
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

    enum SelectedRole: String, Identifiable {
        case professor
        case student

        var id: Self { self }
    }

    var body: some View {
        NavigationStack {
            ZStack {
                authenticationBackground

                ScrollView {
                    VStack(spacing: 22) {
                        headerView

                        Group {
                            switch step {
                            case .authenticationMethods:
                                authenticationMethodsStep
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
                        }
                        .padding(20)
                        .frame(maxWidth: 520)
                        .background(.white.opacity(0.065), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                        .overlay {
                            RoundedRectangle(cornerRadius: 24, style: .continuous)
                                .strokeBorder(.white.opacity(0.10), lineWidth: 1)
                        }
                        .shadow(color: .black.opacity(0.22), radius: 24, y: 12)

                        Text("Secure access powered by Practenture")
                            .font(.caption)
                            .foregroundStyle(.white.opacity(0.42))
                            .padding(.bottom, 24)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.horizontal, 20)
                    .padding(.top, 8)
                }
                .scrollIndicators(.hidden)
                .scrollDismissesKeyboard(.interactively)
            }
            .navigationBarTitleDisplayMode(.inline)
            .toolbarBackground(PractentureTheme.background.opacity(0.94), for: .navigationBar)
            .toolbarBackground(.visible, for: .navigationBar)
            .toolbarColorScheme(.dark, for: .navigationBar)
            .tint(PractentureTheme.accentColor)
            .toolbar {
                ToolbarItem(placement: .navigationBarLeading) {
                    if step != .authenticationMethods {
                        Button { goBack() } label: {
                            Label("Back", systemImage: "chevron.left")
                        }
                    }
                }
                ToolbarItem(placement: .cancellationAction) {
                    if step == .authenticationMethods {
                        Button("Close") { dismiss() }
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
                    .presentationBackground(PractentureTheme.background)
                }
            }
            .task { await checkProfessorAvailability() }
        }
        .preferredColorScheme(.dark)
    }

    private var authenticationBackground: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.055, green: 0.047, blue: 0.12),
                    Color(red: 0.09, green: 0.065, blue: 0.18),
                    PractentureTheme.background
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            Circle()
                .fill(PractentureTheme.accentColor.opacity(0.16))
                .frame(width: 320, height: 320)
                .blur(radius: 90)
                .offset(x: 170, y: -280)
            Circle()
                .fill(Color.cyan.opacity(0.07))
                .frame(width: 260, height: 260)
                .blur(radius: 100)
                .offset(x: -170, y: 350)
        }
        .ignoresSafeArea()
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
                    .foregroundStyle(.white.opacity(0.64))
                    .multilineTextAlignment(.center)
            } else {
                Text("No professor account exists in the system. Students can only join classes that have an active professor.")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.64))
                    .multilineTextAlignment(.center)
            }

            Button {
                step = .roleSelection
                errorMessage = nil
            } label: {
                Text("← Back to Role Selection")
                    .font(.caption)
                    .fontWeight(.semibold)
                    .foregroundStyle(PractentureTheme.accentColor)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Header

    private var headerView: some View {
        VStack(spacing: 12) {
            ZStack {
                Circle()
                    .fill(.white.opacity(0.07))
                    .frame(width: 86, height: 86)
                Circle()
                    .stroke(PractentureTheme.accentColor.opacity(0.26), lineWidth: 1)
                    .frame(width: 76, height: 76)
                Image("Logo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 60, height: 60)
                    .accessibilityLabel("Practenture")
            }
            .shadow(color: PractentureTheme.accentColor.opacity(0.24), radius: 20, y: 8)

            Text(stepTitle)
                .font(.system(.title2, design: .rounded, weight: .bold))
                .foregroundStyle(.white)
                .multilineTextAlignment(.center)

            if let stepSubtitle = stepSubtitleText {
                Text(stepSubtitle)
                    .font(.subheadline)
                    .foregroundStyle(.white.opacity(0.64))
                    .multilineTextAlignment(.center)
                    .lineSpacing(2)
                    .frame(maxWidth: 380)
            }
        }
        .padding(.top, 8)
    }

    private var stepTitle: String {
        switch step {
        case .authenticationMethods: return selectedRole == .professor ? "Professor access" : "Student access"
        case .roleSelection: return "Practenture Credentials"
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
        case .authenticationMethods: return selectedRole == .professor ? "Sign in to manage simulations or enroll with an invitation" : "Sign in to join your class and run your business"
        case .roleSelection: return "Choose your account type"
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

    // MARK: - Step 1: Authentication Method

    private var authenticationMethodsStep: some View {
        VStack(spacing: 14) {
            if let error = errorMessage {
                authenticationMessage(error, isError: true)
            }

            SignInWithAppleButton(.signIn) { request in
                let nonce = makeAppleProviderNonce()
                activeAppleNonce = nonce
                request.requestedScopes = [.fullName, .email]
                request.nonce = nonce
            } onCompletion: { result in
                Task { await handleAppleSignIn(result) }
            }
            .signInWithAppleButtonStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 54)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .disabled(isLoading)
            .accessibilityLabel("Sign in with Apple")

            #if canImport(GoogleSignInSwift)
            GoogleSignInButton(
                scheme: .dark,
                style: .wide,
                state: isLoading ? .disabled : .normal,
                action: handleGoogleSignIn
            )
            .frame(maxWidth: .infinity, minHeight: 54)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .contentShape(Rectangle())
            .accessibilityLabel("Sign in with Google")
            #else
            Button("Sign in with Google", action: handleGoogleSignIn)
                .frame(maxWidth: .infinity, minHeight: 54)
                .buttonStyle(.bordered)
                .disabled(isLoading)
            #endif

            authenticationDivider("OR USE PRACTENTURE")
                .padding(.vertical, 2)

            Button {
                errorMessage = nil
                pendingIsProfessor = selectedRole == .professor
                step = selectedRole == .professor ? .professorLogin : .studentLogin
            } label: {
                Label(
                    selectedRole == .professor ? "Professor credentials" : "Student credentials",
                    systemImage: "person.badge.key.fill"
                )
                .font(.headline)
                .frame(maxWidth: .infinity, minHeight: 54)
            }
            .buttonStyle(.borderedProminent)
            .buttonBorderShape(.roundedRectangle(radius: 14))
            .tint(PractentureTheme.accentColor)
            .accessibilityHint("Use your Practenture ID and password")

            Divider()
                .overlay(.white.opacity(0.12))
                .padding(.vertical, 2)

            if selectedRole == .student {
                VStack(spacing: 8) {
                    Text("New to Practenture?")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text("Create a student account, then join the class code your professor shares.")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.58))
                        .multilineTextAlignment(.center)
                    Button("Create student account") {
                        errorMessage = nil
                        step = .studentRegister
                    }
                    .font(.subheadline.weight(.semibold))
                    .frame(minHeight: 44)
                    .disabled(!professorAvailable)
                }
            } else {
                VStack(spacing: 8) {
                    Text("First-time professor?")
                        .font(.subheadline.weight(.semibold))
                        .foregroundStyle(.white)
                    Text("Use your one-time invitation to enroll securely.")
                        .font(.caption)
                        .foregroundStyle(.white.opacity(0.58))
                        .multilineTextAlignment(.center)
                    Button("Redeem professor invitation") {
                        pendingOAuthProvider = ""
                        pendingOAuthIdToken = ""
                        pendingOAuthNonce = nil
                        errorMessage = nil
                        step = .professorCodeEntry
                    }
                    .font(.subheadline.weight(.semibold))
                    .frame(minHeight: 44)
                }
            }
        }
    }

    private func authenticationDivider(_ title: String) -> some View {
        HStack(spacing: 12) {
            Rectangle().fill(.white.opacity(0.14)).frame(height: 1)
            Text(title)
                .font(.caption2.weight(.bold))
                .tracking(0.7)
                .foregroundStyle(.white.opacity(0.52))
                .fixedSize()
            Rectangle().fill(.white.opacity(0.14)).frame(height: 1)
        }
    }

    private func authenticationMessage(_ message: String, isError: Bool) -> some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: isError ? "exclamationmark.circle.fill" : "checkmark.circle.fill")
            Text(message)
                .font(.caption)
                .frame(maxWidth: .infinity, alignment: .leading)
        }
        .foregroundStyle(isError ? Color.red.opacity(0.95) : PractentureTheme.successColor)
        .padding(12)
        .background((isError ? Color.red : PractentureTheme.successColor).opacity(0.10), in: RoundedRectangle(cornerRadius: 12))
        .accessibilityElement(children: .combine)
    }

    // MARK: - Step 2: Role Selection

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
                    .foregroundStyle(.white.opacity(0.64))
                Button("Register as Student") {
                    selectedRole = .student
                    step = .studentRegister
                }
                .font(.caption)
                .fontWeight(.semibold)
                .disabled(!professorAvailable)
                Text("•")
                    .font(.caption)
                    .foregroundStyle(.white.opacity(0.64))
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
                .textFieldStyle(AuthenticationTextFieldStyle())

            SecureField("Password", text: $password)
                .textFieldStyle(AuthenticationTextFieldStyle())

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await handleProfessorLogin() } } label: {
                actionButtonLabel("Sign in", color: PractentureTheme.accentColor)
            }
            .disabled(isLoading || username.isEmpty || password.isEmpty)

            Button {
                step = .professorCodeEntry
                errorMessage = nil
            } label: {
                Text("Have a professor access code? Redeem it →")
                    .font(.caption)
                    .foregroundStyle(PractentureTheme.accentColor)
            }

            Button {
                step = .forgotPassword
                errorMessage = nil
            } label: {
                Text("Forgot password?")
                    .font(.caption)
                    .foregroundStyle(PractentureTheme.accentColor)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Professor Code Entry (new professor)

    private var professorCodeEntryStep: some View {
        VStack(spacing: 12) {
            Image(systemName: "key.fill")
                .font(.system(size: 40))
                .foregroundStyle(PractentureTheme.accentColor)
                .padding(.bottom, 4)

            Text(pendingOAuthProvider != "" ? "Enter Your Professor Code" : "Professor Access Code")
                .font(.headline)

            let providerName = pendingOAuthProvider == "apple" ? "Apple" : "Google"
            Text(pendingOAuthProvider != ""
                 ? "You signed in with \(providerName). Enter your professor code to create your account."
                 : "You'll create an account first, then redeem your professor code to upgrade your role.")
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.64))
                .multilineTextAlignment(.center)

            TextField("PROF-XXXX-XXXX", text: $professorCode)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .multilineTextAlignment(.center)
                .font(.system(size: 18, weight: .bold, design: .monospaced))
                .textFieldStyle(AuthenticationTextFieldStyle())
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
                        .foregroundStyle(PractentureTheme.accentColor)
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
                        .foregroundStyle(PractentureTheme.accentColor)
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
                .textFieldStyle(AuthenticationTextFieldStyle())

            TextField("Full Name", text: $fullName)
                .textInputAutocapitalization(.words)
                .textFieldStyle(AuthenticationTextFieldStyle())

            TextField("Invitation email", text: $email)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.emailAddress)
                .textFieldStyle(AuthenticationTextFieldStyle())

            SecureField("Password", text: $password)
                .textFieldStyle(AuthenticationTextFieldStyle())

            SecureField("Confirm Password", text: $confirmPassword)
                .textFieldStyle(AuthenticationTextFieldStyle())

            passwordValidationView

            if let error = errorMessage {
                Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
            }

            Button { Task { await handleProfessorCreateAccount() } } label: {
                actionButtonLabel("Create Account & Redeem Code", color: .blue)
            }
            .disabled(isLoading || username.isEmpty || fullName.isEmpty || email.isEmpty || !isPasswordValid)
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
                        .textFieldStyle(AuthenticationTextFieldStyle())

                    SecureField("Password", text: $password)
                        .textFieldStyle(AuthenticationTextFieldStyle())

                    if let error = errorMessage {
                        Text(error).font(.caption2).foregroundStyle(.red).multilineTextAlignment(.center)
                    }

                    Button { Task { await handleStudentLogin() } } label: {
                        actionButtonLabel("Sign in", color: PractentureTheme.accentColor)
                    }
                    .disabled(isLoading || studentId.isEmpty || password.isEmpty)

                    Button {
                        step = .studentRegister
                        errorMessage = nil
                    } label: {
                        Text("New student? Register →")
                            .font(.caption)
                            .foregroundStyle(PractentureTheme.accentColor)
                    }

                    Button {
                        step = .forgotPassword
                        errorMessage = nil
                    } label: {
                        Text("Forgot password?")
                            .font(.caption)
                            .foregroundStyle(PractentureTheme.accentColor)
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
                        .textFieldStyle(AuthenticationTextFieldStyle())

                    TextField("Full Name", text: $fullName)
                        .textInputAutocapitalization(.words)
                        .textFieldStyle(AuthenticationTextFieldStyle())

                    SecureField("Password", text: $password)
                        .textFieldStyle(AuthenticationTextFieldStyle())

                    SecureField("Confirm Password", text: $confirmPassword)
                        .textFieldStyle(AuthenticationTextFieldStyle())

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
                            .foregroundStyle(PractentureTheme.accentColor)
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
                .foregroundStyle(PractentureTheme.accentColor)
                .padding(.bottom, 4)

            TextField("Class Code (e.g., ABC123)", text: $classJoinCode)
                .textInputAutocapitalization(.characters)
                .autocorrectionDisabled()
                .multilineTextAlignment(.center)
                .font(.system(size: 18, weight: .bold, design: .monospaced))
                .textFieldStyle(AuthenticationTextFieldStyle())
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
                    .foregroundStyle(.white.opacity(0.64))
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: MFA Entry (login with MFA)

    private var mfaEntryStep: some View {
        VStack(spacing: 16) {
            Image(systemName: "lock.shield.fill")
                .font(.system(size: 50))
                .foregroundStyle(PractentureTheme.accentColor)

            Text("Enter the 6-digit code from your authenticator app")
                .font(.caption)
                .multilineTextAlignment(.center)
                .foregroundStyle(.white.opacity(0.64))

            TextField("000000", text: $mfaCode)
                .keyboardType(.numberPad)
                .multilineTextAlignment(.center)
                .font(.system(size: 28, weight: .bold, design: .monospaced))
                .textFieldStyle(AuthenticationTextFieldStyle())
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
                .foregroundStyle(PractentureTheme.accentColor)

            Text("Professor Account Created!")
                .font(.headline)
                .foregroundStyle(PractentureTheme.accentColor)

            Text("Welcome, \(AuthManager.shared.currentUser?.name ?? "Professor"). Your professor account is ready.")
                .font(.subheadline)
                .multilineTextAlignment(.center)
                .foregroundStyle(.white.opacity(0.64))

            Divider().padding(.horizontal, 20)

            Image(systemName: "lock.shield")
                .font(.system(size: 40))
                .foregroundStyle(PractentureTheme.accentColor)

            Text("Would you like to enable two-factor authentication?")
                .font(.subheadline)
                .multilineTextAlignment(.center)

            Text("This adds an extra layer of security. You'll need an authenticator app like Google Authenticator or Authy.")
                .font(.caption)
                .multilineTextAlignment(.center)
                .foregroundStyle(.white.opacity(0.64))

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
                    .foregroundStyle(PractentureTheme.accentColor)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Forgot Password (enter email)

    private var forgotPasswordStep: some View {
        VStack(spacing: 12) {
            Image(systemName: "key.circle.fill")
                .font(.system(size: 40))
                .foregroundStyle(PractentureTheme.accentColor)
                .padding(.bottom, 4)

            Text("Enter your email address")
                .font(.headline)

            Text("We'll generate a reset token for you to use on the next screen.")
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.64))
                .multilineTextAlignment(.center)

            TextField("email@example.com", text: $forgotEmail)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .keyboardType(.emailAddress)
                .textFieldStyle(AuthenticationTextFieldStyle())

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
                    .foregroundStyle(PractentureTheme.accentColor)
            }
        }
        .padding(.top, 8)
    }

    // MARK: - Step: Reset Password (token + new password)

    private var resetPasswordStep: some View {
        VStack(spacing: 12) {
            Image(systemName: "lock.open.circle.fill")
                .font(.system(size: 40))
                .foregroundStyle(PractentureTheme.accentColor)
                .padding(.bottom, 4)

            Text("Create New Password")
                .font(.headline)

            Text("Enter the reset token from your email and set a new password.")
                .font(.caption2)
                .foregroundStyle(.white.opacity(0.64))
                .multilineTextAlignment(.center)

            TextField("Reset Token", text: $resetToken)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
                .textFieldStyle(AuthenticationTextFieldStyle())

            SecureField("New Password", text: $newPassword)
                .textFieldStyle(AuthenticationTextFieldStyle())

            SecureField("Confirm New Password", text: $confirmPasswordReset)
                .textFieldStyle(AuthenticationTextFieldStyle())

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
                    .foregroundStyle(PractentureTheme.accentColor)
            }
        }
        .padding(.top, 8)
    }


    // MARK: - Helper Views

    private func roleCard(title: String, subtitle: String, icon: String) -> some View {
        VStack(spacing: 12) {
            ZStack {
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(PractentureTheme.accentColor.opacity(0.15))
                    .frame(width: 56, height: 56)
                Image(systemName: icon)
                    .font(.system(size: 24))
                    .foregroundStyle(PractentureTheme.accentColor)
            }
            VStack(spacing: 4) {
                Text(title).font(.headline).foregroundStyle(.white)
                Text(subtitle).font(.caption).foregroundStyle(.white.opacity(0.64)).multilineTextAlignment(.center)
            }
            Image(systemName: "arrow.right.circle.fill").font(.title3).foregroundStyle(PractentureTheme.accentColor)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 20)
        .padding(.horizontal, 16)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(PractentureTheme.secondary)
                .shadow(color: PractentureTheme.accentColor.opacity(0.1), radius: 10, y: 4)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(PractentureTheme.accentColor.opacity(0.15), lineWidth: 1)
        )
    }

    private func actionButtonLabel(_ text: String, color: Color) -> some View {
        HStack {
            if isLoading { ProgressView().tint(.white) }
            Text(text).fontWeight(.semibold)
        }
        .frame(maxWidth: .infinity)
        .frame(minHeight: 54)
        .background(
            LinearGradient(
                colors: [PractentureTheme.accentColor, Color(red: 0.39, green: 0.24, blue: 0.78)],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            ),
            in: RoundedRectangle(cornerRadius: 14, style: .continuous)
        )
        .foregroundStyle(.white)
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
                        .foregroundStyle(.white.opacity(0.64))

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
        case .roleSelection:
            step = .authenticationMethods
        case .professorLogin:
            step = .roleSelection
        case .professorCodeEntry:
            if pendingOAuthProvider.isEmpty {
                step = .roleSelection
            } else {
                pendingOAuthProvider = ""
                pendingOAuthIdToken = ""
                pendingOAuthNonce = nil
                professorCode = ""
                step = .authenticationMethods
            }
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
            step = .authenticationMethods
        }
        errorMessage = nil
    }

    private func finishOnboarding() {
        let isProf = AuthManager.shared.currentUser?.role == "professor"
        UserDefaults.standard.set(isProf, forKey: "practenture_professor_mode")
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
                    professorCode: professorCode,
                    providerNonce: pendingOAuthNonce
                )
                
                if response.professorCodeRequired == true {
                    errorMessage = "Invalid professor code. Please check and try again."
                    return
                }
                
                // Clear pending state
                pendingOAuthProvider = ""
                pendingOAuthIdToken = ""
                pendingOAuthNonce = nil
                
                // Social enrollment always creates a professor. Complete as professor.
                finishOnboarding()
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
        guard !username.isEmpty, !fullName.isEmpty, !email.isEmpty, !password.isEmpty else {
            errorMessage = "Please fill in all fields."
            return
        }
        guard password == confirmPassword else {
            errorMessage = "Passwords don't match."
            return
        }
        do {
            // Atomic backend activation: invitation + identity + membership.
            let response = try await AuthManager.shared.registerProfessor(
                username: username,
                email: email,
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
            // Go directly to student dashboard — JoinSessionView handles session code entry
            finishOnboarding()
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
            // Go directly to student dashboard — JoinSessionView handles session code entry
            finishOnboarding()
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
            mfaBackupCodes = result.backupCodes
            showingMFASetup = false
            mfaCode = ""
            errorMessage = nil
            finishOnboarding()
        } catch {
            errorMessage = UserFriendlyError.message(for: error)
        }
    }

    // MARK: - Apple Sign In

    /// Apple receives the SHA-256 value as its nonce and returns that same value
    /// in the signed identity token. The backend compares it in constant time.
    private func makeAppleProviderNonce() -> String {
        let rawNonce = UUID().uuidString + UUID().uuidString
        let digest = SHA256.hash(data: Data(rawNonce.utf8))
        return digest.map { String(format: "%02x", $0) }.joined()
    }

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
                guard let nonce = activeAppleNonce else {
                    errorMessage = "Apple Sign-In could not be verified. Please try again."
                    return
                }
                let response = try await AuthManager.shared.loginWithApple(
                    credential: auth.credential,
                    providerNonce: nonce
                )
                if response.professorCodeRequired == true {
                    // New user — store token and ask for professor code
                    pendingOAuthProvider = "apple"
                    pendingOAuthIdToken = idToken
                    pendingOAuthNonce = nonce
                    step = .professorCodeEntry
                    return
                }
                activeAppleNonce = nil
                // Existing social identities retain their backend-authoritative role.
                finishOnboarding()
            } catch {
                errorMessage = "Apple Sign-In failed: \(UserFriendlyError.message(for: error))"
            }
        case .failure(let error):
            activeAppleNonce = nil
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
                        pendingOAuthNonce = nil
                        step = .professorCodeEntry
                        return
                        }
                        // Existing social identities retain their backend-authoritative role.
                        finishOnboarding()
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
            ZStack {
                PractentureTheme.background.ignoresSafeArea()
                ScrollView {
                    VStack(spacing: 16) {
                    Image(systemName: "qrcode")
                        .font(.system(size: 60))
                        .foregroundStyle(PractentureTheme.accentColor)

                    Text("Set Up Authenticator")
                        .font(.headline)

                    Text("1. Open Google Authenticator or Authy")
                        .font(.caption).foregroundStyle(.white.opacity(0.64))
                    Text("2. Add a new account manually")
                        .font(.caption).foregroundStyle(.white.opacity(0.64))
                    Text("3. Enter this secret:")
                        .font(.caption).foregroundStyle(.white.opacity(0.64))

                    Text(setupData.secret)
                        .font(.system(size: 16, weight: .bold, design: .monospaced))
                        .padding(8)
                        .background(Color.gray.opacity(0.15))
                        .cornerRadius(8)
                        .textSelection(.enabled)

                    Text("4. Enter the 6-digit code from your app:")
                        .font(.caption).foregroundStyle(.white.opacity(0.64))

                    TextField("000000", text: $mfaVerifyCode)
                        .keyboardType(.numberPad)
                        .multilineTextAlignment(.center)
                        .font(.system(size: 24, weight: .bold, design: .monospaced))
                        .textFieldStyle(AuthenticationTextFieldStyle())
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
                            .foregroundStyle(.white.opacity(0.64))
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
                    .padding(.vertical, 24)
                }
            }
            .preferredColorScheme(.dark)
            .navigationTitle("MFA Setup")
            .toolbar {
                ToolbarItem(placement: .cancellationAction) {
                    Button("Skip") { onCancel() }
                }
            }
        }
    }
}

private struct AuthenticationTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .environment(\.colorScheme, .dark)
            .font(.body)
            .foregroundStyle(.white)
            .padding(.horizontal, 15)
            .frame(minHeight: 52)
            .background(.white.opacity(0.075), in: RoundedRectangle(cornerRadius: 13, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 13, style: .continuous)
                    .strokeBorder(.white.opacity(0.13), lineWidth: 1)
            }
            .tint(PractentureTheme.accentColor)
    }
}

#Preview {
    LoginView(initialRole: .student).environment(AppState())
}


