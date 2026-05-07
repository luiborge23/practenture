// LoginView.swift
// BizSimAI
//
// X-3: Login screen for professor authentication and student registration.
// Supports professor username/password login and student registration with
// auto-creation of account on the backend.

import SwiftUI

struct LoginView: View {
    @Environment(AppState.self) private var appState
    @Environment(\.dismiss) private var dismiss
    
    @State private var mode: LoginMode = .professor
    @State private var username: String = ""
    @State private var password: String = ""
    @State private var studentId: String = ""
    @State private var fullName: String = ""
    @State private var teamName: String = ""
    @State private var isLoading: Bool = false
    @State private var errorMessage: String? = nil
    
    enum LoginMode {
        case professor
        case studentRegister
        case studentLogin
    }
    
    var body: some View {
        NavigationStack {
            VStack(spacing: 24) {
                // MARK: - Logo
                VStack(spacing: 8) {
                    Circle()
                        .fill(.blue.gradient)
                        .frame(width: 64, height: 64)
                        .shadow(color: .blue.opacity(0.3), radius: 12, y: 4)
                    
                    Image(systemName: mode == .professor ? "person.fill.viewfinder" : "graduationcap.fill")
                        .font(.system(size: 28))
                        .foregroundStyle(.white)
                    
                    Text(mode == .professor ? "Professor Login" : "Student Access")
                        .font(.title2.weight(.bold))
                    
                    Text(mode == .professor 
                         ? "Enter your professor credentials to manage sessions"
                         : "Register or login to join a simulation")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, 40)
                }
                
                // MARK: - Login Mode Tabs
                Picker("Login Mode", selection: $mode) {
                    Text("Professor").tag(LoginMode.professor)
                    Text("Student Login").tag(LoginMode.studentLogin)
                    Text("Student Register").tag(LoginMode.studentRegister)
                }
                .pickerStyle(.segmented)
                .padding(.horizontal, 24)
                
                // MARK: - Form
                VStack(spacing: 16) {
                    if mode == .professor {
                        // Professor login
                        LabeledContent("Username") {
                            TextField("professor", text: $username)
                                .textInputAutocapitalization(.never)
                                .autocorrectionDisabled()
                        }
                        
                        SecureField("Password", text: $password)
                    }
                    
                    if mode == .studentLogin || mode == .studentRegister {
                        LabeledContent("Student ID") {
                            TextField("S12345678", text: $studentId)
                                .textInputAutocapitalization(.never)
                                .keyboardType(.numberPad)
                        }
                        
                        LabeledContent("Full Name") {
                            TextField("John Smith", text: $fullName)
                        }
                        
                        if mode == .studentRegister {
                            LabeledContent("Team Name") {
                                TextField("Team Alpha", text: $teamName)
                                    .textInputAutocapitalization(.words)
                            }
                        }
                        
                        SecureField("Password", text: $password)
                    }
                    
                    // Error message
                    if let error = errorMessage {
                        HStack(spacing: 8) {
                            Image(systemName: "exclamationmark.triangle.fill")
                                .foregroundStyle(.red)
                            Text(error)
                                .font(.subheadline)
                            Spacer()
                        }
                        .padding(12)
                        .background(Color.red.opacity(0.1))
                        .cornerRadius(8)
                    }
                }
                .textFieldStyle(.roundedBorder)
                .padding(.horizontal, 24)
                
                // MARK: - Action Button
                Button {
                    Task {
                        await handleLogin()
                    }
                } label: {
                    HStack {
                        if isLoading {
                            ProgressView()
                                .progressViewStyle(.circular)
                                .tint(.white)
                        }
                        
                        Text(mode == .professor ? "Login" : 
                             mode == .studentLogin ? "Join Session" : "Register & Join")
                            .fontWeight(.semibold)
                    }
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 14)
                    .background(mode == .professor ? .blue : .green)
                    .foregroundStyle(.white)
                    .cornerRadius(12)
                }
                .disabled(isLoading)
                
                // MARK: - Alternative Login
                if mode == .studentRegister {
                    Text("Already have an account? Use Student Login above.")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }
                
                Spacer()
            }
            .navigationTitle("")
            .navigationBarHidden(true)
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    Button {
                        dismiss()
                    } label: {
                        Image(systemName: "chevron.left")
                            .foregroundStyle(.secondary)
                    }
                }
            }
        }
    }
    
    // MARK: - Login Handler
    
    private func handleLogin() async {
        isLoading = true
        errorMessage = nil
        
        do {
            if mode == .professor {
                guard !username.isEmpty, !password.isEmpty else {
                    errorMessage = "Please enter both username and password."
                    return
                }
                
                let response = try await AuthManager.shared.loginProfessor(
                    username: username,
                    password: password
                )
                
                // Verify professor role
                do {
                    _ = try await NetworkService.shared.post("/api/auth/professor-only")
                    
                    // Store professor mode preference
                    UserDefaults.standard.set(true, forKey: "bizsimai_professor_mode")
                    appState.selectMode(.professor)
                    
                } catch {
                    errorMessage = "Logged in but failed to verify professor access. Please try again."
                }
                
            } else if mode == .studentLogin {
                guard !studentId.isEmpty, !password.isEmpty else {
                    errorMessage = "Please enter your student ID and password."
                    return
                }
                
                // Student login - register first (idempotent) then login
                let response = try await AuthManager.shared.register(
                    username: studentId,
                    password: password,
                    studentId: studentId,
                    name: fullName
                )
                
                // Store student mode preference
                UserDefaults.standard.set(false, forKey: "bizsimai_professor_mode")
                appState.selectMode(.student)
                
            } else {
                // Student register
                guard !studentId.isEmpty, !fullName.isEmpty, !teamName.isEmpty, !password.isEmpty else {
                    errorMessage = "Please fill in all fields."
                    return
                }
                
                let response = try await AuthManager.shared.register(
                    username: studentId,
                    password: password,
                    studentId: studentId,
                    name: fullName
                )
                
                // Store student mode preference
                UserDefaults.standard.set(false, forKey: "bizsimai_professor_mode")
                appState.selectMode(.student)
            }
            
        } catch {
            errorMessage = error.localizedDescription
        }
        
        isLoading = false
    }
}

#Preview {
    LoginView()
        .environment(AppState())
}
