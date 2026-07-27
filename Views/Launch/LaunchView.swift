// LaunchView.swift
// Practenture - X-1: Role selection screen
//
// Premium dark theme with vibrant purple (#8b5cf6), glassmorphism,
// smooth animations, and professional typography inspired by practenture.com

import SwiftUI

struct LaunchView: View {
    @Environment(AppState.self) private var appState
    @State private var authManager = AuthManager.shared
    
    @State private var animateCards = false
    @State private var animateLogo = false
    @State private var showLogin = false
    
    private var hasActiveSession: Bool {
        authManager.isAuthenticated && authManager.hasValidToken
    }
    
    var body: some View {
        VStack(spacing: 0) {
            // Premium header with gradient and subtle glow
            HStack { Spacer() }
                .frame(height: 160)
                .background(
                    RadialGradient(
                        colors: [PractentureTheme.primary.opacity(0.3), PractentureTheme.background],
                        center: .top,
                        startRadius: 0,
                        endRadius: 400
                    )
                )
            
            VStack(spacing: 32) {
                // Animated logo with glow effect
                ZStack {
                    Circle()
                        .fill(PractentureTheme.accentColor.opacity(0.15))
                        .frame(width: 140, height: 140)
                        .blur(radius: animateLogo ? 50 : 0)
                    
                    Image("Logo")
                        .resizable()
                        .scaledToFit()
                        .frame(width: 100, height: 100)
                        .shadow(color: PractentureTheme.accentColor.opacity(0.6), radius: 32, y: 16)
                        .scaleEffect(animateLogo ? 1 : 0.85)
                }
                .animation(.spring(duration: 1, bounce: 0.3), value: animateLogo)
                
                // Premium title with gradient text effect
                VStack(spacing: 8) {
                    Text("practenture")
                        .font(.system(size: 52, weight: .bold, design: .rounded))
                        .foregroundStyle(
                            LinearGradient(
                                colors: [.white, PractentureTheme.accentColor],
                                startPoint: .leading,
                                endPoint: .trailing
                            )
                        )
                        .shadow(color: PractentureTheme.accentColor.opacity(0.4), radius: 12, y: 6)
                    
                    Text("Practice + Venture")
                        .font(.subheadline)
                        .fontWeight(.medium)
                        .foregroundStyle(PractentureTheme.textSecondary.opacity(0.8))
                        .letterSpacing(2)
                }
                
                // Professional description
                Text("Students don't just learn about business — they practice it. Run a real company, make decisions, and see the results.")
                    .font(.body)
                    .foregroundStyle(PractentureTheme.textSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 40)
                    .lineHeightMultiple(1.6)
            }
            .padding(.top, 20)
            
            Spacer()
            
            // Premium role selection cards with glassmorphism
            VStack(spacing: 24) {
                HStack(spacing: 32) {
                    roleCard(
                        title: "Professor",
                        subtitle: hasActiveSession ? "Manage simulation sessions" : "Login to manage sessions",
                        icon: "person.fill.viewfinder",
                        gradientStart: PractentureTheme.accentColor,
                        gradientEnd: PractentureTheme.primary.opacity(0.8),
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
                        gradientStart: PractentureTheme.accentColor.opacity(0.8),
                        gradientEnd: PractentureTheme.primary,
                        delay: 0.2
                    ) {
                        if hasActiveSession && authManager.currentUser?.role == "student" {
                            appState.selectMode(.student)
                        } else {
                            showLogin = true
                        }
                    }
                }
                .padding(.horizontal, 48)
            }
            
            if hasActiveSession {
                Button {
                    authManager.logout()
                } label: {
                    HStack(spacing: 8) {
                        Image(systemName: "rectangle.portrait.and.arrow.right")
                        Text("Logout")
                    }
                    .font(.subheadline)
                    .foregroundStyle(PractentureTheme.textMuted)
                    .padding(.horizontal, 24)
                    .padding(.vertical, 12)
                    .background(
                        Capsule()
                            .fill(PractentureTheme.background.opacity(0.5))
                    )
                }
                .padding(.top, 32)
            }
            
            Spacer()
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(PractentureTheme.background)
        .sheet(isPresented: $showLogin) {
            LoginView()
                .environment(appState)
                .presentationDetents([.large])
                .presentationDragIndicator(.visible)
        }
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
        gradientStart: Color,
        gradientEnd: Color,
        delay: Double,
        action: @escaping () -> Void
    ) -> some View {
        Button(action: action) {
            VStack(spacing: 24) {
                ZStack {
                    // Glassmorphism card background
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .fill(PractentureTheme.cardBackground.opacity(0.7))
                        .shadow(color: PractentureTheme.primary.opacity(0.2), radius: 24, y: 12)
                    
                    // Gradient border
                    RoundedRectangle(cornerRadius: 28, style: .continuous)
                        .strokeBorder(
                            LinearGradient(colors: [gradientStart, gradientEnd], startPoint: .topLeading, endPoint: .bottomTrailing),
                            lineWidth: 1.5
                        )
                    
                    // Card content
                    VStack(spacing: 20) {
                        ZStack {
                            Circle()
                                .fill(gradientStart.opacity(0.2))
                                .frame(width: 96, height: 96)
                            
                            Image(systemName: icon)
                                .font(.system(size: 42))
                                .foregroundStyle(gradientStart)
                        }
                        
                        VStack(spacing: 10) {
                            Text(title)
                                .font(.title2)
                                .fontWeight(.bold)
                                .foregroundStyle(PractentureTheme.textPrimary)
                            
                            Text(subtitle)
                                .font(.subheadline)
                                .foregroundStyle(PractentureTheme.textSecondary)
                                .multilineTextAlignment(.center)
                                .lineLimit(2)
                        }
                        
                        Image(systemName: "arrow.right.circle.fill")
                            .font(.title3)
                            .foregroundStyle(gradientStart)
                    }
                    .padding(.vertical, 28)
                    .padding(.horizontal, 36)
                }
                .frame(maxWidth: .infinity)
            }
        }
        .buttonStyle(.borderless)
        .contentShape(Rectangle())
        .scaleEffect(animateCards ? 1 : 0.95)
        .opacity(animateCards ? 1 : 0)
        .animation(.spring(duration: 0.5).delay(delay), value: animateCards)
    }
}
