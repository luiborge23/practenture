// AnnouncementsView.swift
// BizSimAI
//
// Professor view for posting announcements and round debrief notes.

import SwiftUI

struct AnnouncementsView: View {
    @Environment(AppState.self) private var appState
    @State private var newMessage: String = ""
    @State private var isRoundDebrief: Bool = false

    private var session: SimulationSession? { appState.activeSession }

    var body: some View {
        ScrollView {
            VStack(spacing: 24) {
                if let session = session {
                    composeSection(session)
                    announcementsList(session)
                } else {
                    ContentUnavailableView(
                        "No Active Session",
                        systemImage: "megaphone",
                        description: Text("Create or select a session to post announcements.")
                    )
                }
            }
            .padding(24)
        }
        .navigationTitle("Announcements")
    }

    // MARK: - Compose

    private func composeSection(_ session: SimulationSession) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 8) {
                Image(systemName: "pencil.circle.fill")
                    .foregroundStyle(.blue)
                Text("New Announcement")
                    .font(.headline)
            }

            #if os(macOS)
            TextEditor(text: $newMessage)
                .frame(minHeight: 80, maxHeight: 150)
                .font(.body)
                .padding(4)
                .background(RoundedRectangle(cornerRadius: 8).stroke(Color.gray.opacity(0.3)))
            #else
            TextField("Type your announcement...", text: $newMessage, axis: .vertical)
                .textFieldStyle(.roundedBorder)
                .lineLimit(3...6)
            #endif

            HStack {
                Toggle("Round Debrief (Round \(session.currentRound))", isOn: $isRoundDebrief)
                    .font(.subheadline)

                Spacer()

                Button {
                    let trimmed = newMessage.trimmingCharacters(in: .whitespacesAndNewlines)
                    guard !trimmed.isEmpty else { return }
                    session.addAnnouncement(trimmed, forRound: isRoundDebrief ? session.currentRound : nil)
                    newMessage = ""
                    isRoundDebrief = false
                } label: {
                    Label("Post", systemImage: "paperplane.fill")
                }
                .buttonStyle(.borderedProminent)
                .disabled(newMessage.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            }
        }
        .padding(20)
        .background(RoundedRectangle(cornerRadius: 16).fill(Color.gray.opacity(0.1)))
    }

    // MARK: - Announcements List

    private func announcementsList(_ session: SimulationSession) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Posted Announcements")
                .font(.headline)

            if session.announcements.isEmpty {
                VStack(spacing: 12) {
                    Image(systemName: "text.bubble")
                        .font(.system(size: 36))
                        .foregroundStyle(.secondary)
                    Text("No announcements yet")
                        .foregroundStyle(.secondary)
                }
                .frame(maxWidth: .infinity)
                .padding(40)
            } else {
                ForEach(session.announcements.reversed()) { announcement in
                    announcementCard(announcement)
                }
            }
        }
    }

    private func announcementCard(_ announcement: Announcement) -> some View {
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

                Text(announcement.postedAt, style: .relative)
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
}
