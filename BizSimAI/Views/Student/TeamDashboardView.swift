// TeamDashboardView.swift
// BizSimAI
//
// Student dashboard with investor scorecard, S/Q rating,
// financial health metrics, and quick actions.

import SwiftUI
import Combine

struct TeamDashboardView: View {
    @Environment(AppState.self) private var appState

    @State private var showDecisionInput = false
    @State private var showHistory = false
    @State private var showLeaderboard = false
    @State private var showCoach = false
    @State private var showResults = false
    @State private var showShareSheet = false
    @State private var showAnnouncements = false
    @State private var shareURL: URL? = nil
    @State private var lastProcessedRound: Int = 0
    @State private var liveTeamCount: Int = 0
    @State private var liveSubmittedCount: Int = 0
    @State private var liveSessionState: SessionBackendState = .disconnected

    private var session: SimulationSession? { appState.activeSession }
    private var gameController: GameController? { appState.gameController }
    private var playerTeam: TeamStatus? { session?.playerTeam }
    private var teamName: String { playerTeam?.name ?? "My Team" }
    private var currentRound: Int { max(session?.currentRound ?? 1, 1) }
    private var totalRounds: Int { session?.totalRounds ?? 10 }
    private var cash: Double { playerTeam?.cash ?? session?.startingCash ?? 100_000 }
    private var inventory: Int { playerTeam?.inventory ?? 0 }
    private var sqRating: Double { playerTeam?.sqRating ?? 5.0 }
    private var imageRating: Double { playerTeam?.imageRating ?? 50 }
    private var creditRating: CreditRating { playerTeam?.creditRating ?? .a }
    private var investorScore: Double { playerTeam?.cumulativeInvestorScore ?? 0 }
    private var marketPosition: Int { playerTeam?.rank ?? 1 }
    private var totalTeams: Int { session?.teams.count ?? 1 }

    // MARK: - Live backend status

    private var isOnline: Bool {
        BackendState.shared.isOnline && BackendState.shared.sessionState != .disconnected
    }

    private var isBackendSession: Bool {
        guard let session = session else { return false }
        return !session.sessionCode.isEmpty && session.sessionCode != session.id.uuidString
    }

    private var backendCurrentRound: Int {
        BackendState.shared.currentRound > 0 ? BackendState.shared.currentRound : currentRound
    }

    private var backendTeamCount: Int {
        BackendState.shared.teamCount > 0 ? BackendState.shared.teamCount : (session?.teams.count ?? 1)
    }

    private var backendSubmittedCount: Int {
        BackendState.shared.submittedCount
    }

    private var canSubmitDecisions: Bool {
        guard let team = playerTeam else { return true }
        return !team.hasSubmittedDecisions
    }

    var body: some View {
        ScrollView {
            VStack(spacing: 20) {
                // Processing indicator for Quick Demo
                if gameController?.isProcessing == true {
                    VStack(spacing: 10) {
                        ProgressView()
                            .controlSize(.large)
                        Text("Running simulation...")
                            .font(.headline)
                            .foregroundStyle(.blue)
                        if let results = gameController?.lastRoundResults, !results.isEmpty {
                            Text("Round \(results.first?.round ?? 0) of \(totalRounds) complete")
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(20)
                    .frame(maxWidth: .infinity)
                    .background(RoundedRectangle(cornerRadius: 16).fill(Color.blue.opacity(0.08)))
                }
                roundHeader
                investorScorecard
                metricsGrid
                actionSection
            }
            .padding(24)
        }
        .onAppear {
            NSLog("[BizSimAI] TeamDashboardView onAppear")
            NSLog("[BizSimAI] session exists: \\(session != nil)")
            NSLog("[BizSimAI] gameController exists: \\(gameController != nil)")
            NSLog("[BizSimAI] isProcessing: \\(gameController?.isProcessing ?? false)")
            NSLog("[BizSimAI] totalTeams: \\(totalTeams)")
            NSLog("[BizSimAI] currentRound: \\(currentRound)")
            NSLog("[BizSimAI] totalRounds: \\(totalRounds)")
            NSLog("[BizSimAI] playerTeam exists: \\(playerTeam != nil)")
            NSLog("[BizSimAI] cash: \\(cash)")
            NSLog("[BizSimAI] isOnline: \\(isOnline)")
            NSLog("[BizSimAI] backendCurrentRound: \\(backendCurrentRound)")
            NSLog("[BizSimAI] backendTeamCount: \\(backendTeamCount)")
            NSLog("[BizSimAI] TeamDashboardView onAppear DONE")
            lastProcessedRound = session?.currentRound ?? 0
            // Sync live backend status
            liveTeamCount = BackendState.shared.teamCount
            liveSubmittedCount = BackendState.shared.submittedCount
            liveSessionState = BackendState.shared.sessionState
            // Fetch latest results from backend on appear
            if isBackendSession { Task { await fetchBackendResults() } }
        }
        .onReceive(Timer.publish(every: 10, on: .main, in: .common).autoconnect()) { _ in
            if isBackendSession { Task { await fetchBackendResults() } }
        }
        .navigationTitle(teamName)
        #if os(macOS)
        .frame(minWidth: 500)
        #endif
        .toolbar {
            ToolbarItemGroup(placement: .automatic) {
                Button { appState.clearActiveSession() } label: {
                    Label("Leave Session", systemImage: "arrow.left.circle")
                }
                Button { showHistory = true } label: {
                    Label("History", systemImage: "chart.xyaxis.line")
                }
                Button { showLeaderboard = true } label: {
                    Label("Leaderboard", systemImage: "trophy")
                }
                Button { showCoach = true } label: {
                    Label("AI Coach", systemImage: "brain.head.profile")
                }
                Button { showAnnouncements = true } label: {
                    Label("Announcements", systemImage: "megaphone.fill")
                }
                Button { generatePDF() } label: {
                    Label("Export PDF", systemImage: "doc.badge.plus")
                }
            }
        }
        .sheet(isPresented: $showShareSheet) {
            if let url = shareURL {
                ShareSheet(activityItems: [url])
            }
        }
        .sheet(isPresented: $showDecisionInput, onDismiss: {
            // Auto-show results if a new round was processed
            if let session = session, session.currentRound > lastProcessedRound {
                lastProcessedRound = session.currentRound
                showResults = true
            }
        }) {
            DecisionInputView()
        }
        .sheet(isPresented: $showHistory) {
            NavigationStack {
                PerformanceHistoryView()
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Done") { showHistory = false }
                        }
                    }
            }
            #if os(macOS)
            .frame(minWidth: 600, minHeight: 450)
            #endif
        }
        .sheet(isPresented: $showLeaderboard) {
            NavigationStack {
                StudentLeaderboardView()
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Done") { showLeaderboard = false }
                        }
                    }
            }
            #if os(macOS)
            .frame(minWidth: 500, minHeight: 450)
            #endif
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
            #if os(macOS)
            .frame(minWidth: 520, minHeight: 500)
            #endif
        }
        .sheet(isPresented: $showResults) {
            NavigationStack {
                RoundResultsView()
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Done") { showResults = false }
                        }
                    }
            }
            #if os(macOS)
            .frame(minWidth: 600, minHeight: 500)
            #endif
        }
        .sheet(isPresented: $showAnnouncements) {
            NavigationStack {
                StudentAnnouncementsView()
                    .toolbar {
                        ToolbarItem(placement: .cancellationAction) {
                            Button("Done") { showAnnouncements = false }
                        }
                    }
            }
        }
    }

    // MARK: - Round Header

    private var roundHeader: some View {
        VStack(alignment: .leading, spacing: 8) {
            if session?.state == .completed {
                EmptyView()
            } else {
                HStack(spacing: 8) {
                    Text("Round \(backendCurrentRound)")
                        .font(.title)
                        .fontWeight(.bold)
                    Text("of \(totalRounds)")
                        .font(.title2)
                        .foregroundStyle(.secondary)
                }

                // Progress bar with gradient fill
                HStack(spacing: 3) {
                    ForEach(1...totalRounds, id: \.self) { round in
                        Capsule()
                            .fill(
                                round <= backendCurrentRound
                                    ? AnyShapeStyle(LinearGradient(colors: [Color.blue, Color.blue.opacity(0.7)], startPoint: .top, endPoint: .bottom))
                                    : AnyShapeStyle(Color.secondary.opacity(0.12))
                            )
                            .frame(height: 5)
                            .frame(maxWidth: .infinity)
                    }
                }
            }
        }
        .padding(20)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [Color.gray.opacity(0.08), Color.gray.opacity(0.03)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(Color.gray.opacity(0.06), lineWidth: 0.5)
        )
        .shadow(color: Color.black.opacity(0.04), radius: 6, x: 0, y: 3)
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Investor Scorecard

    private var investorScorecard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack {
                Label("Investor Scorecard", systemImage: "chart.bar.doc.horizontal")
                    .font(.headline)
                Spacer()
                Text("Score: \(String(format: "%.0f", investorScore))/100")
                    .font(.subheadline)
                    .fontWeight(.bold)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 4)
                    .foregroundStyle(investorScore >= 70 ? .green : investorScore < 40 ? .red : .orange)
                    .background(
                        (investorScore >= 70 ? Color.green : investorScore < 40 ? Color.red : Color.orange).opacity(0.10),
                        in: Capsule()
                    )
            }

            LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 10), count: 5), spacing: 10) {
                scorecardMetric(label: "S/Q", value: String(format: "%.1f", sqRating) + "★",
                                color: sqRating >= 7 ? .green : sqRating < 4 ? .red : .blue)
                scorecardMetric(label: "Image", value: String(format: "%.0f", imageRating),
                                color: imageRating >= 60 ? .green : imageRating < 35 ? .red : .orange)
                scorecardMetric(label: "Credit", value: creditRating.displayName,
                                color: creditRating >= .aMinus ? .green : creditRating < .b ? .red : .orange)
                scorecardMetric(label: "Rank", value: "#\(marketPosition)/\(totalTeams)",
                                color: marketPosition <= 2 ? .green : .secondary)
                scorecardMetric(label: "Cash", value: formatCompact(cash),
                                color: cash > 50_000 ? .green : cash < 10_000 ? .red : .orange)
            }
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .fill(
                    LinearGradient(
                        colors: [Color.blue.opacity(0.06), Color.blue.opacity(0.02)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
        )
        .overlay(
            RoundedRectangle(cornerRadius: 16, style: .continuous)
                .strokeBorder(Color.blue.opacity(0.08), lineWidth: 0.5)
        )
        .shadow(color: Color.blue.opacity(0.04), radius: 6, x: 0, y: 3)
    }

    private func scorecardMetric(label: String, value: String, color: Color) -> some View {
        VStack(spacing: 4) {
            Text(value)
                .font(.headline)
                .fontWeight(.bold)
                .foregroundStyle(color)
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(
            RoundedRectangle(cornerRadius: 10)
                .fill(
                    LinearGradient(
                        colors: [Color.gray.opacity(0.06), Color.clear],
                        startPoint: .top,
                        endPoint: .bottom
                    )
                )
        )
    }

    private func formatCompact(_ value: Double) -> String {
        if value >= 1_000_000 { return "$\(String(format: "%.1f", value / 1_000_000))M" }
        if value >= 1_000 { return "$\(String(format: "%.0f", value / 1_000))K" }
        return "$\(String(format: "%.0f", value))"
    }

    // MARK: - Metrics Grid

    private var metricsGrid: some View {
        // Compute real trends from round history
        let history = session?.playerRoundSummaries ?? []
        let prev = history.count >= 2 ? history[history.count - 2] : nil
        let last = history.last

        let profitTrend = compareTrend(last?.profit, prev?.profit)
        let sqTrend = compareTrend(last?.sqRating, prev?.sqRating)
        let scoreTrend = compareTrend(last?.investorScore, prev?.investorScore)

        return LazyVGrid(columns: [
            GridItem(.flexible(), spacing: 16),
            GridItem(.flexible(), spacing: 16)
        ], spacing: 16) {
            MetricCard.currency(
                title: "Cash Balance", amount: cash,
                icon: "dollarsign.circle.fill", trend: profitTrend, color: .green
            )
            MetricCard(
                title: "Inventory", value: "\(inventory) units",
                icon: "shippingbox.fill", trend: .flat, accentColor: .orange
            )
            MetricCard(
                title: "S/Q Rating", value: String(format: "%.1f", sqRating) + "★",
                icon: "star.fill", trend: sqTrend, accentColor: .yellow
            )
            MetricCard(
                title: "Investor Score", value: String(format: "%.0f", investorScore),
                icon: "chart.bar.doc.horizontal", trend: scoreTrend, accentColor: .purple
            )
        }
    }

    private func compareTrend(_ current: Double?, _ previous: Double?) -> TrendDirection {
        guard let cur = current, let prev = previous else { return .flat }
        if cur > prev { return .up }
        if cur < prev { return .down }
        return .flat
    }

    // MARK: - Action Section

    private var actionSection: some View {
        VStack(spacing: 12) {
            if session?.state == .completed {
                // Game over state
                VStack(spacing: 12) {
                    ZStack {
                        Circle()
                            .fill(
                                LinearGradient(
                                    colors: [Color.yellow.opacity(0.2), Color.orange.opacity(0.1)],
                                    startPoint: .top,
                                    endPoint: .bottom
                                )
                            )
                            .frame(width: 60, height: 60)
                        Image(systemName: "trophy.fill")
                            .font(.largeTitle)
                            .foregroundStyle(
                                LinearGradient(
                                    colors: [Color.yellow, Color.orange],
                                    startPoint: .top,
                                    endPoint: .bottom
                                )
                            )
                    }
                    Text("Simulation Complete!")
                        .font(.title3)
                        .fontWeight(.bold)
                    Text("Final Rank: #\(marketPosition) of \(totalTeams)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                    Text("Investor Score: \(String(format: "%.0f", investorScore))/100")
                        .font(.subheadline)
                        .fontWeight(.semibold)
                        .foregroundStyle(investorScore >= 70 ? .green : .orange)
                }
                .padding()
                .frame(maxWidth: .infinity)
                .background(
                    RoundedRectangle(cornerRadius: 16)
                        .fill(
                            LinearGradient(
                                colors: [Color.yellow.opacity(0.08), Color.orange.opacity(0.04)],
                                startPoint: .top,
                                endPoint: .bottom
                            )
                        )
                )
                .overlay(
                    RoundedRectangle(cornerRadius: 16)
                        .strokeBorder(Color.yellow.opacity(0.15), lineWidth: 1)
                )

                Button {
                    showResults = true
                } label: {
                    Label("View Final Results", systemImage: "doc.text.magnifyingglass")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 4)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
            } else if canSubmitDecisions {
                Button {
                    showDecisionInput = true
                } label: {
                    Label("Make Decisions", systemImage: "slider.horizontal.3")
                        .font(.headline)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 4)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)

                Text("Submit your business decisions for Round \(currentRound)")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                HStack(spacing: 8) {
                    Image(systemName: "checkmark.circle.fill")
                        .foregroundStyle(.green)
                    Text("Decisions submitted for Round \(currentRound)")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }
                .padding()
                .frame(maxWidth: .infinity)
                .background(RoundedRectangle(cornerRadius: 12).fill(.green.opacity(0.08)))
            }

            HStack(spacing: 12) {
                quickActionButton(title: "History", icon: "chart.xyaxis.line", color: .purple) {
                    showHistory = true
                }
                quickActionButton(title: "Leaderboard", icon: "trophy", color: .orange) {
                    showLeaderboard = true
                }
                quickActionButton(title: "AI Coach", icon: "brain.head.profile", color: .blue) {
                    showCoach = true
                }
            }
            .padding(.top, 8)
        }
    }

    private func quickActionButton(title: String, icon: String, color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            VStack(spacing: 8) {
                ZStack {
                    Circle()
                        .fill(
                            LinearGradient(
                                colors: [color.opacity(0.15), color.opacity(0.05)],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                            )
                        )
                    Image(systemName: icon)
                        .font(.title3)
                        .foregroundStyle(color)
                }
                .frame(width: 40, height: 40)
                Text(title)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(
                        LinearGradient(
                            colors: [Color.gray.opacity(0.08), Color.gray.opacity(0.03)],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
            )
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(Color.gray.opacity(0.06), lineWidth: 0.5)
            )
            .shadow(color: Color.black.opacity(0.03), radius: 4, x: 0, y: 2)
        }
        .buttonStyle(.borderless)
        .contentShape(Rectangle())
    }
    
    // MARK: - Backend Sync

    /// Fetches latest results from the backend and restores them locally.
    /// This is called on appear and via a 10-second timer so the student
    /// sees new round results automatically after the professor advances.
    private func fetchBackendResults() async {
        guard let session = session else { return }
        do {
            let backendResults = try await NetworkService.shared.getResults(code: session.sessionCode)
            if !backendResults.isEmpty {
                let maxBackendRound = backendResults.keys.max() ?? 0
                if maxBackendRound >= session.currentRound {
                    await MainActor.run {
                        session.restoreResultsFromBackend(backendResults)
                        if session.currentRound > lastProcessedRound {
                            lastProcessedRound = session.currentRound
                            showResults = true
                        }
                    }
                }
            }
        } catch {
            // Silent — the timer will retry
        }
    }

    // MARK: - PDF Export
    
    private func generatePDF() {
        guard let session = session,
              let playerTeam = session.playerTeam else { return }
        
        if let pdfURL = PDFExporter.exportSessionResult(
            session: session,
            playerTeam: playerTeam,
            allRounds: session.playerRoundSummaries
        ) {
            shareURL = pdfURL
            showShareSheet = true
        }
    }
}
