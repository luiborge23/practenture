// LaunchView.swift
// BizSimAI
//
// X-1: Role selection screen. Users choose Professor or Student mode.

import SwiftUI

struct LaunchView: View {
    @Environment(AppState.self) private var appState

    @State private var animateCards = false
    @State private var animateLogo = false

    var body: some View {
        VStack(spacing: 0) {
            Spacer()

            // MARK: - Logo & Title
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
                        .foregroundStyle(.primary)

                    Text("Business Simulation for the Modern Classroom")
                        .font(.title3)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                }
            }
            .opacity(animateLogo ? 1 : 0)
            .offset(y: animateLogo ? 0 : -20)

            Spacer()

            // MARK: - Role Selection Cards
            HStack(spacing: 24) {
                roleCard(
                    title: "Professor",
                    subtitle: "Create & manage simulation sessions",
                    icon: "person.fill.viewfinder",
                    color: .blue,
                    delay: 0.1
                ) {
                    appState.selectMode(.professor)
                }

                roleCard(
                    title: "Student",
                    subtitle: "Join a session & run your business",
                    icon: "graduationcap.fill",
                    color: .green,
                    delay: 0.2
                ) {
                    appState.selectMode(.student)
                }
            }
            .padding(.horizontal, 40)

            Spacer()

            // MARK: - Footer
            Text("v1.0 MVP  \u{2022}  Built with SwiftUI & Claude AI")
                .font(.caption)
                .foregroundStyle(.quaternary)
                .padding(.bottom, 20)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(backgroundGradient)
        .onAppear {
            withAnimation(.spring(duration: 0.8, bounce: 0.4)) {
                animateLogo = true
            }
            withAnimation(.spring(duration: 0.6).delay(0.3)) {
                animateCards = true
            }
        }
    }

    // MARK: - Role Card

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
                    Text(title)
                        .font(.title2)
                        .fontWeight(.bold)
                        .foregroundStyle(.primary)

                    Text(subtitle)
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                }

                Image(systemName: "arrow.right.circle.fill")
                    .font(.title3)
                    .foregroundStyle(color)
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
    }

    // MARK: - Background

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
        )
        .ignoresSafeArea()
    }
}
