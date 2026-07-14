// LaunchView.swift
// BizSimAI - X-1: Role selection screen

import SwiftUI

struct LaunchView: View {
    @Environment(AppState.self) private var appState
    // @State-owned singleton so SwiftUI tracks @Observable changes
    @State private var authManager = AuthManager.shared

    @State private var animateCards = false
    @State private var animateLogo = false
    @State private var showLogin = false

    private var hasActiveSession: Bool {
        authManager.isAuthenticated && authManager.hasValidToken
    }

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            VStack(spacing: 12) {
                ZStack {
                    Circle()
                        .fill(.blue.gradient)
                        .frame(width: 80, height: 80)
                        .shadow(color: .blue.opacity(0.3), radius: 20, y: 8)
                    Image(systemName: "chart.line.uptrend.xyaxis")
                        .font(.system(size: 36, weight: .bold))
                        .foregroundStyle(.white)
                        .rotationEffect(.degrees(animateLogo ? 0 : -10))
                }
                .scaleEffect(animateLogo ? 1.0 : 0.8)

                VStack(spacing: 6) {
                    Text("BizSim AI")
                        .font(.system(size: 40, weight: .bold, design: .rounded))
                    if hasActiveSession {
                        Text("Welcome back, \(authManager.currentUser?.username ?? authManager.currentUser?.userId ?? "User")")
                            .font(.title3)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    } else {
                        Text("Business Simulation for the Modern Classroom")
                            .font(.title3)
                            .foregroundStyle(.secondary)
                            .multilineTextAlignment(.center)
                    }
                }
            }
            .opacity(animateLogo ? 1 : 0)
            .offset(y: animateLogo ? 0 : -20)

            Spacer()

            HStack(spacing: 24) {
                roleCard(
                    title: "Professor",
                    subtitle: hasActiveSession ? "Manage simulation sessions" : "Login to manage sessions",
                    icon: "person.fill.viewfinder",
                    color: .blue,
                    delay: 0.1
                ) {
                    if hasActiveSession && authManager.currentUser?.role == "professor" {
                        appState.selectMode(.professor)
                    } else {
                        showLogin = true
                    }
                }

                roleCard(
                    title: "Student",
                    subtitle: hasActiveSession ? "Continue your business" : "Register or login",
                    icon: "graduationcap.fill",
                    color: .green,
                    delay: 0.2
                ) {
                    if hasActiveSession && authManager.currentUser?.role == "student" {
                        appState.selectMode(.student)
                    } else {
                        showLogin = true
                    }
                }
            }
            .padding(.horizontal, 40)

            if hasActiveSession {
                Button {
                    authManager.logout()
                } label: {
                    HStack(spacing: 6) {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                        Text("Logout")
                    }
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                }
                .padding(.top, 20)
            }

            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(backgroundGradient)
        .sheet(isPresented: $showLogin) {
            LoginView()
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
        // Note: We intentionally do NOT auto-close the login sheet on isAuthenticated.
        // LoginView calls dismiss() itself via finishOnboarding() when the full
        // onboarding flow (including professor code redemption, MFA setup, class join)
        // is complete. Auto-closing here would cut off multi-step onboarding mid-flow.
        .onAppear {
            withAnimation(.spring(duration: 0.8, bounce: 0.4)) {
                animateLogo = true
            }
            withAnimation(.spring(duration: 0.6).delay(0.3)) {
                animateCards = true
            }
            authManager.refreshFromKeychain()
        }
    }

    private func roleCard(
        title: String,
        subtitle: String,
        icon: String,
        color: Color,
        delay: Double,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            VStack(spacing: 16) {
                ZStack {
                    RoundedRectangle(cornerRadius: 16, style: .continuous)
                        .fill(color.gradient.opacity(0.15))
                        .frame(width: 72, height: 72)
                    Image(systemName: icon)
                        .font(.system(size: 32))
                        .foregroundStyle(color)
                }
                VStack(spacing: 6) {
                    Text(title).font(.title2).fontWeight(.bold).foregroundStyle(.primary)
                    Text(subtitle).font(.subheadline).foregroundStyle(.secondary).multilineTextAlignment(.center).lineLimit(2)
                }
                Image(systemName: "arrow.right.circle.fill").font(.title3).foregroundStyle(color)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 32)
            .padding(.horizontal, 24)
            .background(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(Color.gray.opacity(0.1))
                    .shadow(color: color.opacity(0.15), radius: 16, y: 8)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .strokeBorder(color.opacity(0.2), lineWidth: 1)
            )
        }
        .buttonStyle(.borderless)
        .contentShape(Rectangle())
        .scaleEffect(animateCards ? 1 : 0.9)
        .opacity(animateCards ? 1 : 0)
        .animation(.spring(duration: 0.5).delay(delay), value: animateCards)
    }

    private var backgroundGradient: some View {
        #if os(macOS)
        let bgColor = Color(nsColor: .windowBackgroundColor)
        #else
        let bgColor = Color(uiColor: .systemBackground)
        #endif
        return LinearGradient(
            colors: [bgColor, Color.blue.opacity(0.03), bgColor],
            startPoint: .topLeading,
            endPoint: .bottomTrailing
        ).ignoresSafeArea()
    }
}
