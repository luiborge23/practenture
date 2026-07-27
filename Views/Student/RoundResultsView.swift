// RoundResultsView.swift
// Practenture
//
// Round results with investor scorecard, revenue by channel,
// cost breakdown, competitive intelligence, and coaching tips.
//
// Professional dark theme with vibrant purple (#8b5cf6), clean cards,
// subtle shadows, and smooth animations inspired by practenture.com

import SwiftUI

struct RoundResultsView: View {
    @Environment(\.dismiss) private var dismiss
    @Environment(AppState.self) private var appState

    @State private var viewModel = RoundResultsViewModel()
    @State private var animateMetrics = false
    @State private var showCoach = false
    @State private var roundNumber: Int
    @State private var totalRounds: Int

    init(roundNumber: Int? = nil, totalRounds: Int? = nil) {
        // Resolve from session in onAppear if not provided
        self._roundNumber = State(initialValue: roundNumber ?? 0)
        self._totalRounds = State(initialValue: totalRounds ?? 10)
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                roundHeader
                investorScorecardSection
                channelBreakdown
                incomeStatementSection
                metricsSection
                competitorsSection
                explanationsSection
                coachingSection
                navigationButtons
            }
            .padding(24)
        }
        .navigationTitle("Round Results")
        #if os(macOS)
        .frame(minWidth: 550)
        #endif
        .onAppear {
            if let session = appState.activeSession,
               let teamId = session.playerTeam?.id {
                // Resolve round number from session if not explicitly provided
                if roundNumber == 0 {
                    // When session is completed, show the final round
                    // Otherwise show the most recent completed round (currentRound - 1)
                    if session.state == .completed {
                        roundNumber = session.totalRounds
                    } else {
                        roundNumber = max(1, session.currentRound - 1)
                    }
                }
                totalRounds = session.totalRounds
                viewModel.loadResults(from: session, for: teamId, round: roundNumber)
            } else {
                loadSampleData()
            }
            withAnimation(.spring(duration: 0.6)) {
                animateMetrics = true
            }
        }
        .sheet(isPresented: $showCoach) {
            NavigationStack {
                AICoachView()
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Done") { showCoach = false }
                        }
                    }
            }
            .environment(appState)
            #if os(macOS)
            .frame(minWidth: 520, minHeight: 500)
            #endif
        }
    }

    // MARK: - Round Header

    private var roundHeader: some View {
        VStack(spacing: 8) {
            Text(viewModel.roundLabel.isEmpty ? "Round \(roundNumber) Results" : viewModel.roundLabel)
                .font(.largeTitle)
                .fontWeight(.bold)
                .foregroundStyle(PractentureTheme.textPrimary)

            if roundNumber >= totalRounds {
                Text("Simulation Complete")
                    .font(.subheadline)
                    .foregroundStyle(PractentureTheme.success)
            } else {
                Text("\(totalRounds - roundNumber) rounds remaining")
                    .font(.subheadline)
                    .foregroundStyle(PractentureTheme.textSecondary)
            }
        }
