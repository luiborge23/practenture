// GradeMappingView.swift
// BizSimAI
//
// Professor view for configuring grade mappings and viewing team grades.

import SwiftUI

struct GradeMappingView: View {
    @Environment(AppState.self) private var appState
    @State private var showShareSheet = false
    @State private var csvText = ""

    private var session: SimulationSession? { appState.activeSession }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                if let session = session {
                    gradeScaleSection(session)
                    teamGradesSection(session)
                    exportSection(session)
                } else {
                    ContentUnavailableView(
                        "No Active Session",
                        systemImage: "graduationcap",
                        description: Text("Create or select a session to configure grades.")
                    )
                }
            }
            .padding(24)
        }
        .navigationTitle("Grading")
        #if !os(macOS)
        .sheet(isPresented: $showShareSheet) {
            if !csvText.isEmpty {
                ShareSheet(activityItems: [csvText])
            }
        }
        #endif
    }

    // MARK: - Grade Scale Configuration

    private func gradeScaleSection(_ session: SimulationSession) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "slider.horizontal.3")
                    .foregroundStyle(.blue)
                Text("Grade Scale")
                    .font(.headline)
            }

            Text("Based on cumulative Investor Score (0-100). Adjust thresholds as needed.")
                .font(.caption)
                .foregroundStyle(.secondary)

            ForEach(session.gradeMappings) { mapping in
                HStack(spacing: 16) {
                    Text(mapping.label)
                        .font(.headline)
                        .fontWeight(.bold)
                        .frame(width: 40, alignment: .leading)
                        .foregroundStyle(gradeColor(mapping.label))

                    Text("\(Int(mapping.minScore)) — \(Int(mapping.maxScore))")
                        .font(.subheadline)
                        .monospacedDigit()
                        .foregroundStyle(.secondary)

                    Spacer()

                    // Visual bar
                    GeometryReader { geo in
                        RoundedRectangle(cornerRadius: 4)
                            .fill(gradeColor(mapping.label).opacity(0.3))
                            .frame(width: geo.size.width * (mapping.maxScore - mapping.minScore) / 100)
                    }
                    .frame(height: 12)
                    .frame(width: 100)
                }
                .padding(.vertical, 4)
            }
        }
        .padding(20)
        .background(RoundedRectangle(cornerRadius: 16).fill(Color.gray.opacity(0.1)))
    }

    // MARK: - Team Grades

    private func teamGradesSection(_ session: SimulationSession) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Team Grades")
                .font(.headline)

            if session.currentRound <= 1 {
                Text("Grades will appear after the first round is processed.")
                    .font(.subheadline)
                    .foregroundStyle(.secondary)
            } else {
                // Header row
                HStack {
                    Text("Rank").font(.caption).fontWeight(.semibold).frame(width: 40, alignment: .leading)
                    Text("Team").font(.caption).fontWeight(.semibold).frame(maxWidth: .infinity, alignment: .leading)
                    Text("Score").font(.caption).fontWeight(.semibold).frame(width: 60, alignment: .trailing)
                    Text("Grade").font(.caption).fontWeight(.semibold).frame(width: 50, alignment: .trailing)
                }
                .foregroundStyle(.secondary)
                .padding(.horizontal, 14)

                let sortedTeams = session.teams.sorted { $0.rank < $1.rank }
                ForEach(sortedTeams) { team in
                    let grade = session.grade(for: team.id) ?? "—"
                    HStack {
                        Text("#\(team.rank)")
                            .font(.subheadline)
                            .fontWeight(.medium)
                            .frame(width: 40, alignment: .leading)

                        HStack(spacing: 4) {
                            Text(team.name)
                                .font(.subheadline)
                                .lineLimit(1)
                            if team.isAI {
                                Image(systemName: "cpu")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }
                        }
                        .frame(maxWidth: .infinity, alignment: .leading)

                        Text(String(format: "%.1f", team.cumulativeInvestorScore))
                            .font(.subheadline)
                            .monospacedDigit()
                            .frame(width: 60, alignment: .trailing)

                        Text(grade)
                            .font(.subheadline)
                            .fontWeight(.bold)
                            .foregroundStyle(gradeColor(grade))
                            .frame(width: 50, alignment: .trailing)
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, 8)
                    .background(
                        RoundedRectangle(cornerRadius: 8)
                            .fill(team.isAI ? Color.clear : Color.blue.opacity(0.04))
                    )
                }
            }
        }
    }

    // MARK: - Export

    private func exportSection(_ session: SimulationSession) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Export Grades")
                .font(.headline)

            Button {
                exportGradesCSV(session)
            } label: {
                Label("Export as CSV", systemImage: "square.and.arrow.up")
                    .frame(maxWidth: .infinity)
            }
            .buttonStyle(.bordered)
            .controlSize(.large)
            .disabled(session.currentRound <= 1)
        }
    }

    // MARK: - Helpers

    private func gradeColor(_ grade: String) -> Color {
        switch grade {
        case "A", "A+": return .green
        case "B+", "B": return .blue
        case "C+", "C": return .orange
        case "D": return .red
        case "F": return .red
        default: return .secondary
        }
    }

    private func exportGradesCSV(_ session: SimulationSession) {
        var csv = "Rank,Team,AI,Score,Grade\n"
        let sorted = session.teams.sorted { $0.rank < $1.rank }
        for team in sorted {
            let grade = session.grade(for: team.id) ?? "—"
            csv += "\(team.rank),\"\(team.name)\",\(team.isAI),\(String(format: "%.1f", team.cumulativeInvestorScore)),\(grade)\n"
        }

        #if os(macOS)
        let panel = NSSavePanel()
        panel.allowedContentTypes = [.commaSeparatedText]
        panel.nameFieldStringValue = "\(session.config.name)_grades.csv"
        if panel.runModal() == .OK, let url = panel.url {
            try? csv.write(to: url, atomically: true, encoding: .utf8)
        }
        #else
        csvText = csv
        showShareSheet = true
        #endif
    }
}

// MARK: - iOS Share Sheet

#if !os(macOS)
import UIKit

struct ShareSheet: UIViewControllerRepresentable {
    let activityItems: [Any]

    func makeUIViewController(context: Context) -> UIActivityViewController {
        UIActivityViewController(activityItems: activityItems, applicationActivities: nil)
    }

    func updateUIViewController(_ uiViewController: UIActivityViewController, context: Context) {}
}
#endif
