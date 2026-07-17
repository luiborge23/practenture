// WaitingRoomView.swift
// BizSimAI
//
// S-4: Waiting state shown while the round is being processed.
// Features animated spinner, current round number, and rotating business tips.

import SwiftUI
import Combine

struct WaitingRoomView: View {
    let currentRound: Int
    let totalRounds: Int

    @State private var currentTipIndex: Int = 0
    @State private var animatePulse = false
    @State private var dotCount: Int = 0

    private let tips: [String] = [
        "Tip: A balanced approach often beats extreme strategies in the long run.",
        "Tip: Investing in R&D early pays off through compounding quality improvements.",
        "Tip: Watch your competitors' pricing moves -- they reveal their strategy.",
        "Tip: Excess inventory ties up cash. Match production to expected demand.",
        "Tip: Marketing has diminishing returns. Find the sweet spot for your budget.",
        "Tip: Customer satisfaction drives repeat business and word-of-mouth.",
        "Tip: Don't chase market share at the expense of profitability.",
        "Tip: A price war benefits no one -- differentiate on quality instead.",
        "Did you know? Companies that invest consistently in R&D outperform those that cut it during downturns.",
        "Tip: Keep a cash reserve for unexpected market events.",
    ]

    private let timer = Timer.publish(every: 5, on: .main, in: .common).autoconnect()
    private let dotTimer = Timer.publish(every: 0.5, on: .main, in: .common).autoconnect()

    private var dots: String {
        String(repeating: ".", count: (dotCount % 3) + 1)
    }

    init(currentRound: Int = 4, totalRounds: Int = 10) {
        self.currentRound = currentRound
        self.totalRounds = totalRounds
    }

    var body: some View {
        VStack(spacing: 32) {
            Spacer()

            // Current round badge
            VStack(spacing: 4) {
                Text("Round \(currentRound) of \(totalRounds)")
                    .font(.headline)
                    .foregroundStyle(.secondary)

                // Round progress dots
                HStack(spacing: 4) {
                    ForEach(1...totalRounds, id: \.self) { round in
                        RoundedRectangle(cornerRadius: 2)
                            .fill(round <= currentRound
                                ? AnyShapeStyle(LinearGradient(colors: [.blue, .cyan], startPoint: .leading, endPoint: .trailing))
                                : AnyShapeStyle(Color.secondary.opacity(0.2)))
                            .frame(width: round == currentRound ? 24 : 12, height: 6)
                            .animation(.spring(duration: 0.3), value: currentRound)
                    }
                }
            }

            // Animated icon
            ZStack {
                // Pulsing circles
                ForEach(0..<3, id: \.self) { index in
                    Circle()
                        .stroke(Color.blue.opacity(0.15), lineWidth: 2)
                        .frame(width: CGFloat(80 + index * 40), height: CGFloat(80 + index * 40))
                        .scaleEffect(animatePulse ? 1.2 : 0.9)
                        .opacity(animatePulse ? 0 : 0.6)
                        .animation(
                            .easeInOut(duration: 2.0)
                            .repeatForever(autoreverses: false)
                            .delay(Double(index) * 0.4),
                            value: animatePulse
                        )
                }

                // Center icon
                ZStack {
                    Circle()
                        .fill(.blue.gradient)
                        .frame(width: 72, height: 72)

                    Image(systemName: "gearshape.2.fill")
                        .font(.system(size: 30))
                        .foregroundStyle(.white)
                        .rotationEffect(.degrees(animatePulse ? 360 : 0))
                        .animation(
                            .linear(duration: 4).repeatForever(autoreverses: false),
                            value: animatePulse
                        )
                }
            }

            // Status text
            VStack(spacing: 8) {
                Text("Waiting for all teams to submit decisions\(dots)")
                    .font(.title3)
                    .fontWeight(.bold)
                    .frame(width: 420)
                    .multilineTextAlignment(.center)
                    .animation(.none, value: dotCount)

                Text("The simulation will process once everyone is ready")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            ProgressView()
                .controlSize(.large)
                .tint(.blue)

            Spacer()

            // Rotating tips
            VStack(spacing: 12) {
                Image(systemName: "lightbulb.fill")
                    .font(.title3)
                    .foregroundStyle(.yellow)

                Text(tips[currentTipIndex])
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
                    .lineLimit(3)
                    .frame(maxWidth: 400)
                    .id(currentTipIndex)
                    .transition(.asymmetric(
                        insertion: .opacity.combined(with: .move(edge: .bottom)),
                        removal: .opacity.combined(with: .move(edge: .top))
                    ))
            }
            .padding(20)
            .background(
                RoundedRectangle(cornerRadius: 16, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [Color.yellow.opacity(0.12), Color.orange.opacity(0.06)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 16, style: .continuous)
                            .stroke(Color.yellow.opacity(0.15), lineWidth: 1)
                    )
            )
            .shadow(color: .yellow.opacity(0.08), radius: 8, y: 4)
            .frame(maxWidth: 460)

            Spacer()
                .frame(height: 40)
        }
        #if os(macOS)
        .frame(minWidth: 500, minHeight: 450)
        #endif
        .padding(24)
        .onAppear {
            animatePulse = true
        }
        .onReceive(timer) { _ in
            withAnimation(.spring(duration: 0.5)) {
                currentTipIndex = (currentTipIndex + 1) % tips.count
            }
        }
        .onReceive(dotTimer) { _ in
            dotCount += 1
        }
    }
}
