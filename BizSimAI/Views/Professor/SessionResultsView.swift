// SessionResultsView.swift
// BizSimAI
//
// P-6: Final session results with podium visualization, full leaderboard,
// key stats summary, and CSV export.

import SwiftUI

// MARK: - Final Result Data

struct FinalTeamResult: Identifiable {
    let id: UUID
    let rank: Int
    let teamName: String
    let isAI: Bool
    let totalProfit: Double
    let totalRevenue: Double
    let avgMarketShare: Double
    let avgSatisfaction: Double

    static let samples: [FinalTeamResult] = [
        FinalTeamResult(id: UUID(), rank: 1, teamName: "Alpha Corp", isAI: true,
                       totalProfit: 285_400, totalRevenue: 1_250_000, avgMarketShare: 0.31, avgSatisfaction: 0.88),
        FinalTeamResult(id: UUID(), rank: 2, teamName: "Team Rocket", isAI: false,
                       totalProfit: 242_100, totalRevenue: 1_100_000, avgMarketShare: 0.27, avgSatisfaction: 0.82),
        FinalTeamResult(id: UUID(), rank: 3, teamName: "Beta Inc", isAI: true,
                       totalProfit: 198_500, totalRevenue: 950_000, avgMarketShare: 0.22, avgSatisfaction: 0.79),
        FinalTeamResult(id: UUID(), rank: 4, teamName: "Gamma LLC", isAI: true,
                       totalProfit: 156_300, totalRevenue: 820_000, avgMarketShare: 0.14, avgSatisfaction: 0.71),
        FinalTeamResult(id: UUID(), rank: 5, teamName: "Delta Co", isAI: false,
                       totalProfit: 89_200, totalRevenue: 540_000, avgMarketShare: 0.06, avgSatisfaction: 0.65),
    ]
}

// MARK: - CSV Export View Model

/// ViewModel for CSV export from backend.
@Observable
final class CSVExportViewModel {
    var isExporting = false
    var exportError: String?
    var exportSuccess = false

    private let gradesCode: String
    private let leaderboardCode: String

    init(gradesCode: String, leaderboardCode: String) {
        self.gradesCode = gradesCode
        self.leaderboardCode = leaderboardCode
    }

    func exportGrades() async {
        isExporting = true
        exportError = nil
        exportSuccess = false

        do {
            let csv = try await NetworkService.shared.exportGrades(code: gradesCode)
            #if os(macOS)
            let panel = NSSavePanel()
            panel.allowedContentTypes = [.commaSeparatedText]
            panel.nameFieldStringValue = "bizsimai_grades.csv"
            let result = await NSApplication.shared.begin { response in
                if response == .OK, let url = panel.url {
                    try? csv.write(to: url, atomically: true, encoding: .utf8)
                }
                await MainActor.run {
                    isExporting = false
                    exportSuccess = true
                }
            }
            // Non-blocking — handled in the completion handler
            _ = result
            #else
            let tempDir = FileManager.default.temporaryDirectory
            let fileURL = tempDir.appendingPathComponent("bizsimai_grades.csv")
            try csv.write(to: fileURL, atomically: true, encoding: .utf8)
            await MainActor.run {
                isExporting = false
                exportSuccess = true
            }
            #endif
        } catch {
            await MainActor.run {
                isExporting = false
                exportError = "Failed to export grades: \(error.localizedDescription)"
            }
        }
    }

    func exportLeaderboard() async {
        isExporting = true
        exportError = nil
        exportSuccess = false

        do {
            let csv = try await NetworkService.shared.exportLeaderboard(code: leaderboardCode)
            #if os(macOS)
            let panel = NSSavePanel()
            panel.allowedContentTypes = [.commaSeparatedText]
            panel.nameFieldStringValue = "bizsimai_leaderboard.csv"
            let result = await NSApplication.shared.begin { response in
                if response == .OK, let url = panel.url {
                    try? csv.write(to: url, atomically: true, encoding: .utf8)
                }
                await MainActor.run {
                    isExporting = false
                    exportSuccess = true
                }
            }
            _ = result
            #else
            let tempDir = FileManager.default.temporaryDirectory
            let fileURL = tempDir.appendingPathComponent("bizsimai_leaderboard.csv")
            try csv.write(to: fileURL, atomically: true, encoding: .utf8)
            await MainActor.run {
                isExporting = false
                exportSuccess = true
            }
            #endif
        } catch {
            await MainActor.run {
                isExporting = false
                exportError = "Failed to export leaderboard: \(error.localizedDescription)"
            }
        }
    }
}

// MARK: - Session Results View

struct SessionResultsView: View {
    @Environment(AppState.self) private var appState
    @State private var results: [FinalTeamResult] = FinalTeamResult.samples
    @State private var sessionName: String = "MBA 510 - Spring 2026"
    @State private var totalRounds: Int = 10
    @State private var csvExport: CSVExportViewModel?
    @State private var showExportSuccess = false
    @State private var showExportError = false

    var body: some View {
        ScrollView {
            VStack(spacing: 28) {
                headerSection
                podiumSection
                statsSection
                leaderboardSection
                exportSection
            }
            .padding(24)
        }
        .navigationTitle("Final Results")
        #if os(macOS)
        .frame(minWidth: 600)
        #endif
        .alert("Export Successful", isPresented: $showExportSuccess) {
            Button("OK") { }
        } message: {
            Text("Session results have been exported as CSV.")
        }
        .alert("Export Error", isPresented: $showExportError) {
            Button("OK") { }
        } message: {
            if let error = csvExport?.exportError {
                Text(error)
            }
        }
        .onAppear {
            loadFromSession()
            if let session = appState.activeSession {
                csvExport = CSVExportViewModel(
                    gradesCode: session.sessionCode,
                    leaderboardCode: session.sessionCode
                )
            }
        }
        .onChange(of: csvExport?.exportError) {
            if csvExport?.exportError != nil {
                showExportError = true
            }
        }
    }

    private func loadFromSession() {
        guard let session = appState.activeSession else { return }
        sessionName = session.config.name
        totalRounds = session.config.totalRounds
        let sessionTeams = session.teams.sorted { $0.rank < $1.rank }
        var loaded: [FinalTeamResult] = []
        for (idx, team) in sessionTeams.enumerated() {
            let teamResults = session.resultsForTeam(team.id)
            let totalProfit = teamResults.reduce(0) { $0 + $1.profit }
            let totalRevenue = teamResults.reduce(0) { $0 + $1.revenue }
            let avgMarketShare = teamResults.isEmpty ? 0 : teamResults.reduce(0) { $0 + $1.marketShare } / Double(teamResults.count)
            let avgSatisfaction = teamResults.isEmpty ? 0 : teamResults.reduce(0) { $0 + $1.customerSatisfaction } / Double(teamResults.count)
            loaded.append(FinalTeamResult(
                id: team.id, rank: idx + 1, teamName: team.name, isAI: team.isAI,
                totalProfit: totalProfit, totalRevenue: totalRevenue,
                avgMarketShare: avgMarketShare, avgSatisfaction: avgSatisfaction
            ))
        }
        if !loaded.isEmpty {
            results = loaded
        }
    }

    // MARK: - Header

    private var headerSection: some View {
        VStack(spacing: 8) {
            Image(systemName: "trophy.fill")
                .font(.system(size: 44))
                .foregroundStyle(.yellow.gradient)

            Text("Session Complete")
                .font(.largeTitle)
                .fontWeight(.bold)

            Text("\(sessionName) \u{2022} \(totalRounds) Rounds")
                .font(.title3)
                .foregroundStyle(.secondary)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 16)
    }

    // MARK: - Podium

    private var podiumSection: some View {
        HStack(alignment: .bottom, spacing: 16) {
            if results.count >= 2 {
                podiumPlace(result: results[1], height: 100, medal: "🥈", color: .gray)
            }
            if results.count >= 1 {
                podiumPlace(result: results[0], height: 140, medal: "🥇", color: .yellow)
            }
            if results.count >= 3 {
                podiumPlace(result: results[2], height: 80, medal: "🥉", color: .orange)
            }
        }
        .padding(.horizontal, 40)
        .padding(.vertical, 16)
    }

    private func podiumPlace(result: FinalTeamResult, height: CGFloat, medal: String, color: Color) -> some View {
        VStack(spacing: 8) {
            Text(medal)
                .font(.system(size: 36))

            Text(result.teamName)
                .font(.headline)
                .lineLimit(1)

            if result.isAI {
                Label("AI", systemImage: "cpu")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
            }

            Text(result.totalProfit.formatted(.currency(code: "USD").precision(.fractionLength(0))))
                .font(.subheadline)
                .fontWeight(.semibold)
                .monospacedDigit()
                .foregroundStyle(.primary)

            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(color.gradient.opacity(0.3))
                .frame(height: height)
                .overlay(
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .strokeBorder(color.opacity(0.5), lineWidth: 2)
                )
                .overlay(
                    Text("#\(result.rank)")
                        .font(.title)
                        .fontWeight(.bold)
                        .foregroundStyle(color)
                )
        }
        .frame(maxWidth: .infinity)
    }

    // MARK: - Stats Summary

    private var statsSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Key Stats")
                .font(.headline)

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12),
                GridItem(.flexible(), spacing: 12)
            ], spacing: 12) {
                statCard(
                    title: "Total Prize Pool",
                    value: results.reduce(0) { $0 + $1.totalProfit }
                        .formatted(.currency(code: "USD").precision(.fractionLength(0))),
                    icon: "dollarsign.circle.fill",
                    color: .green
                )
                statCard(
                    title: "Avg Profit",
                    value: (results.reduce(0) { $0 + $1.totalProfit } / Double(results.count))
                        .formatted(.currency(code: "USD").precision(.fractionLength(0))),
                    icon: "chart.bar.fill",
                    color: .blue
                )
                statCard(
                    title: "Top Market Share",
                    value: "\(String(format: "%.0f", (results.first?.avgMarketShare ?? 0) * 100))%",
                    icon: "chart.pie.fill",
                    color: .purple
                )
                statCard(
                    title: "Top Satisfaction",
                    value: "\(String(format: "%.0f", (results.max(by: { $0.avgSatisfaction < $1.avgSatisfaction })?.avgSatisfaction ?? 0) * 100))%",
                    icon: "star.fill",
                    color: .yellow
                )
            }
        }
    }

    private func statCard(title: String, value: String, icon: String, color: Color) -> some View {
        VStack(spacing: 8) {
            Image(systemName: icon)
                .font(.title2)
                .foregroundStyle(color)

            Text(value)
                .font(.headline)
                .monospacedDigit()

            Text(title)
                .font(.caption)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
        }
        .frame(maxWidth: .infinity)
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color.gray.opacity(0.1))
        )
    }

    // MARK: - Full Leaderboard Table

    private var leaderboardSection: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Full Leaderboard")
                .font(.headline)

            VStack(spacing: 0) {
                // Table header
                HStack(spacing: 0) {
                    Text("Rank")
                        .frame(width: 50, alignment: .leading)
                    Text("Team")
                        .frame(maxWidth: .infinity, alignment: .leading)
                    Text("Profit")
                        .frame(width: 110, alignment: .trailing)
                    Text("Revenue")
                        .frame(width: 110, alignment: .trailing)
                    Text("Mkt Share")
                        .frame(width: 80, alignment: .trailing)
                    Text("Satisfaction")
                        .frame(width: 90, alignment: .trailing)
                }
                .font(.caption)
                .fontWeight(.semibold)
                .foregroundStyle(.secondary)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .background(Color.gray.opacity(0.1))

                Divider()

                // Table rows
                ForEach(results) { result in
                    HStack(spacing: 0) {
                        Text("#\(result.rank)")
                            .fontWeight(.bold)
                            .frame(width: 50, alignment: .leading)

                        HStack(spacing: 4) {
                            Text(result.teamName)
                                .fontWeight(.medium)
                            if result.isAI {
                                Image(systemName: "cpu")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)

                        Text(result.totalProfit.formatted(.currency(code: "USD").precision(.fractionLength(0))))
                            .monospacedDigit()
                            .frame(width: 110, alignment: .trailing)

                        Text(result.totalRevenue.formatted(.currency(code: "USD").precision(.fractionLength(0))))
                            .monospacedDigit()
                            .frame(width: 110, alignment: .trailing)

                        Text("\(String(format: "%.0f", result.avgMarketShare * 100))%")
                            .monospacedDigit()
                            .frame(width: 80, alignment: .trailing)

                        Text("\(String(format: "%.0f", result.avgSatisfaction * 100))%")
                            .monospacedDigit()
                            .frame(width: 90, alignment: .trailing)
                    }
                    .font(.subheadline)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(result.rank <= 3 ? Color.yellow.opacity(0.04) : Color.clear)

                    if result.rank < results.count {
                        Divider().padding(.horizontal, 16)
                    }
                }
            }
            .background(
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(Color.gray.opacity(0.1))
            )
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
    }

    // MARK: - Export

    private var exportSection: some View {
        VStack(spacing: 16) {
            Text("Export")
                .font(.headline)

            HStack(spacing: 16) {
                Button {
                    Task {
                        await csvExport?.exportGrades()
                        await MainActor.run {
                            showExportSuccess = true
                        }
                    }
                } label: {
                    Label("Export Grades", systemImage: "tablecells.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(csvExport?.isExporting ?? true)

                Button {
                    Task {
                        await csvExport?.exportLeaderboard()
                        await MainActor.run {
                            showExportSuccess = true
                        }
                    }
                } label: {
                    Label("Export Leaderboard", systemImage: "chart.bar.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .controlSize(.large)
                .disabled(csvExport?.isExporting ?? true)
            }

            if let csvExport = csvExport, csvExport.isExporting {
                ProgressView("Exporting...")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            }
        }
    }

}
