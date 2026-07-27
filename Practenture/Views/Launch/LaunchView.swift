// LaunchView.swift
// Practenture - Role selection screen

import SwiftUI

struct LaunchView: View {
    @Environment(AppState.self) private var appState
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var authManager = AuthManager.shared

    @State private var animateContent = false
    // The selected role is also the presentation identity. Keeping a separate
    // Boolean allowed SwiftUI to construct the sheet with the previous role.
    @State private var selectedLoginRole: LoginView.SelectedRole?

    private var hasActiveSession: Bool {
        authManager.isAuthenticated && authManager.hasValidToken
    }

    var body: some View {
        ZStack {
            brandBackground

            ScrollView {
                VStack(spacing: 0) {
                    brandHeader
                        .padding(.top, 30)

                    VStack(alignment: .leading, spacing: 14) {
                        Text(hasActiveSession ? "Welcome back" : "Choose your experience")
                            .font(.headline)
                            .foregroundStyle(.white.opacity(0.72))

                        roleCard(
                            title: "Professor",
                            subtitle: hasActiveSession ? "Manage your simulation sessions" : "Create and manage simulations",
                            icon: "person.crop.rectangle.stack.fill",
                            isPrimary: true,
                            delay: 0.08
                        ) {
                            if hasActiveSession && authManager.currentUser?.role == "professor" {
                                appState.selectMode(.professor)
                            } else {
                                selectedLoginRole = .professor
                            }
                        }

                        roleCard(
                            title: "Student",
                            subtitle: hasActiveSession ? "Continue running your business" : "Join a class or continue playing",
                            icon: "graduationcap.fill",
                            isPrimary: false,
                            delay: 0.16
                        ) {
                            if hasActiveSession && authManager.currentUser?.role == "student" {
                                appState.selectMode(.student)
                            } else {
                                selectedLoginRole = .student
                            }
                        }
                    }
                    .padding(.top, 42)

                    if hasActiveSession {
                        Button {
                            authManager.logout()
                        } label: {
                            Label("Sign out", systemImage: "rectangle.portrait.and.arrow.right")
                                .font(.subheadline.weight(.semibold))
                                .foregroundStyle(.white.opacity(0.68))
                                .frame(minHeight: 44)
                        }
                        .padding(.top, 16)
                        .accessibilityHint("Signs out of your Practenture account")
                    }

                    Text("Learn by doing. Lead with confidence.")
                        .font(.footnote.weight(.medium))
                        .foregroundStyle(.white.opacity(0.46))
                        .padding(.top, 32)
                        .padding(.bottom, 24)
                }
                .frame(maxWidth: 560)
                .padding(.horizontal, 24)
                .frame(maxWidth: .infinity)
            }
            .scrollIndicators(.hidden)
        }
        .sheet(item: $selectedLoginRole) { role in
            LoginView(initialRole: role)
                .id(role)
                .environment(appState)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
                .presentationBackground(PractentureTheme.background)
        }
        // LoginView owns dismissal so MFA, enrollment, and class-join steps are not interrupted.
        .onAppear {
            if reduceMotion {
                animateContent = true
            } else {
                withAnimation(.smooth(duration: 0.65)) {
                    animateContent = true
                }
            }
            authManager.refreshFromKeychain()
        }
    }

    private var brandHeader: some View {
        VStack(spacing: 22) {
            ZStack {
                Circle()
                    .fill(.white.opacity(0.07))
                    .frame(width: 132, height: 132)

                Circle()
                    .stroke(PractentureTheme.accentColor.opacity(0.28), lineWidth: 1)
                    .frame(width: 116, height: 116)

                Image("Logo")
                    .resizable()
                    .scaledToFit()
                    .frame(width: 92, height: 92)
                    .accessibilityLabel("Practenture")
            }
            .shadow(color: PractentureTheme.accentColor.opacity(0.24), radius: 28, y: 12)

            VStack(spacing: 10) {
                Text("Build the business.\nOwn the decisions.")
                    .font(.system(.largeTitle, design: .rounded, weight: .bold))
                    .foregroundStyle(.white)
                    .multilineTextAlignment(.center)
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)

                Text("A hands-on business simulation for classrooms that learn by doing.")
                    .font(.body)
                    .foregroundStyle(.white.opacity(0.68))
                    .multilineTextAlignment(.center)
                    .lineSpacing(3)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: 390)
            }
        }
        .opacity(animateContent ? 1 : 0)
        .offset(y: animateContent ? 0 : 12)
    }

    private func roleCard(
        title: String,
        subtitle: String,
        icon: String,
        isPrimary: Bool,
        delay: Double,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            HStack(spacing: 16) {
                ZStack {
                    RoundedRectangle(cornerRadius: 15, style: .continuous)
                        .fill(isPrimary ? .white.opacity(0.18) : PractentureTheme.accentColor.opacity(0.18))
                        .frame(width: 58, height: 58)

                    Image(systemName: icon)
                        .font(.system(size: 24, weight: .semibold))
                        .foregroundStyle(isPrimary ? .white : PractentureTheme.accentColor)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(.title3.weight(.bold))
                        .foregroundStyle(.white)

                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.white.opacity(isPrimary ? 0.78 : 0.64))
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer(minLength: 8)

                Image(systemName: "arrow.right")
                    .font(.system(size: 16, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: 38, height: 38)
                    .background(.white.opacity(isPrimary ? 0.18 : 0.10), in: Circle())
            }
            .padding(.horizontal, 18)
            .padding(.vertical, 17)
            .frame(maxWidth: .infinity, minHeight: 94, alignment: .leading)
            .background {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .fill(
                        isPrimary
                            ? AnyShapeStyle(LinearGradient(
                                colors: [PractentureTheme.accentColor, Color(red: 0.39, green: 0.24, blue: 0.78)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            ))
                            : AnyShapeStyle(Color.white.opacity(0.075))
                    )
                    .shadow(
                        color: isPrimary ? PractentureTheme.accentColor.opacity(0.28) : .black.opacity(0.16),
                        radius: 18,
                        y: 10
                    )
            }
            .overlay {
                RoundedRectangle(cornerRadius: 22, style: .continuous)
                    .strokeBorder(.white.opacity(isPrimary ? 0.16 : 0.11), lineWidth: 1)
            }
        }
        .buttonStyle(LaunchRoleButtonStyle())
        .accessibilityElement(children: .combine)
        .accessibilityHint("Opens \(title.lowercased()) sign in")
        .opacity(animateContent ? 1 : 0)
        .offset(y: animateContent ? 0 : 18)
        .animation(reduceMotion ? nil : .smooth(duration: 0.5).delay(delay), value: animateContent)
    }

    private var brandBackground: some View {
        ZStack {
            LinearGradient(
                colors: [
                    Color(red: 0.055, green: 0.047, blue: 0.12),
                    Color(red: 0.09, green: 0.065, blue: 0.18),
                    Color(red: 0.045, green: 0.045, blue: 0.09)
                ],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )

            Circle()
                .fill(PractentureTheme.accentColor.opacity(0.16))
                .frame(width: 340, height: 340)
                .blur(radius: 90)
                .offset(x: 150, y: -290)

            Circle()
                .fill(Color.cyan.opacity(0.08))
                .frame(width: 280, height: 280)
                .blur(radius: 100)
                .offset(x: -180, y: 360)
        }
        .ignoresSafeArea()
    }
}

private struct LaunchRoleButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.985 : 1)
            .opacity(configuration.isPressed ? 0.9 : 1)
            .animation(.easeOut(duration: 0.14), value: configuration.isPressed)
    }
}

