// StudentAnnouncementsView.swift
// BizSimAI
//
// Student-facing view for viewing professor announcements.

import SwiftUI

struct StudentAnnouncementsView: View {
    @Environment(AppState.self) private var appState
    @State private var isLoading = false
    @State private var announcements: [AnnouncementBackend] = []
    @State private var errorMessage: String?
    
    private var session: SimulationSession? { appState.activeSession }
    
    var body: some View {
        VStack(spacing: 0) {
            if isLoading {
                ProgressView("Loading announcements...")
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if let error = errorMessage {
                VStack(spacing: 16) {
                    Image(systemName: "exclamationmark.triangle")
                        .font(.system(size: 48))
                        .foregroundStyle(.orange)
                    Text("Failed to load announcements")
                        .font(.headline)
                    Text(error)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .multilineTextAlignment(.center)
                    Button("Retry") {
                        Task { await loadAnnouncements() }
                    }
                    .buttonStyle(.borderedProminent)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
            } else if announcements.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "text.bubble")
                        .font(.system(size: 48))
                        .foregroundStyle(.secondary)
                    Text("No announcements yet")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .padding(40)
            } else {
                ScrollView {
                    LazyVStack(spacing: 12) {
                        ForEach(announcements.reversed()) { announcement in
                            announcementCard(announcement)
                        }
                    }
                    .padding(16)
                }
            }
        }
        .navigationTitle("Announcements")
        .onAppear {
            Task { await loadAnnouncements() }
        }
    }
    
    private func loadAnnouncements() async {
        guard let sessionCode = session?.sessionCode else { return }
        isLoading = true
        errorMessage = nil
        
        do {
            let fetched = try await NetworkService.shared.getAnnouncements(code: sessionCode)
            await MainActor.run {
                announcements = fetched
                isLoading = false
            }
        } catch {
            await MainActor.run {
                errorMessage = UserFriendlyError.message(for: error)
                isLoading = false
            }
        }
    }
    
    private func announcementCard(_ announcement: AnnouncementBackend) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack {
                if let round = announcement.roundNumber {
                    Label("Round \(round) Debrief", systemImage: "bookmark.fill")
                        .font(.caption)
                        .foregroundStyle(.blue)
                } else {
                    Label("General", systemImage: "megaphone.fill")
                        .font(.caption)
                        .foregroundStyle(.purple)
                }
                
                Spacer()
                
                if !announcement.authorName.isEmpty {
                    Text("By \(announcement.authorName)")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }
                
                Text(formatRelativeTime(announcement.timestamp))
                    .font(.caption2)
                    .foregroundStyle(.tertiary)
            }
            
            Text(announcement.message)
                .font(.subheadline)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 12).fill(Color.gray.opacity(0.08)))
    }
    
    private func formatRelativeTime(_ dateString: String) -> String {
        let isoFormatter = ISO8601DateFormatter()
        if let date = isoFormatter.date(from: dateString) {
            let formatter = RelativeDateTimeFormatter()
            formatter.unitsStyle = .abbreviated
            return formatter.localizedString(for: date, relativeTo: Date())
        }
        return dateString
    }
}
