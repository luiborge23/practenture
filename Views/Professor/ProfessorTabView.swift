// ProfessorTabView.swift
// Practenture
//
// Tab container for Professor mode with Sessions, Active Session, and Settings tabs.
// Uses a custom segmented picker instead of TabView to avoid macOS NSWindow issues.
//
// Professional dark theme with vibrant purple (#8b5cf6), clean cards,
// subtle shadows, and smooth animations inspired by practenture.com

import SwiftUI

struct ProfessorTabView: View {
    @Environment(AppState.self) private var appState
    
    let tabs: [(key: String, title: String, icon: String)] = [
        ("sessions", "Sessions", "calendar"),
        ("monitor", "Active Session", "play.rectangle"),
        ("settings", "Settings", "gearshape")
    ]
    
    var body: some View {
        VStack(spacing: 0) {
            // Scrollable tab bar
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(tabs, id: \.key) { tab in
                        let isSelected = appState.professorSelectedTab == tab.key
                        Button {
                            appState.professorSelectedTab = tab.key
                        } label: {
                            Label(tab.title, systemImage: tab.icon)
                                .font(.subheadline)
                                .fontWeight(isSelected ? .bold : .regular)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 8)
                                .background(
                                    Capsule().fill(isSelected ? PractentureTheme.primary : PractentureTheme.surface)
                                )
                                .foregroundStyle(isSelected ? .white : PractentureTheme.textPrimary)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 16)
            }
            .padding(.vertical, 10)

            Divider()

            // Tab content
            Group {
                switch appState.professorSelectedTab {
                case "sessions":
                    ProfessorSessionsView()
                case "monitor", "activeSession":
                    ProfessorActiveSessionView()
                case "settings":
                    ProfessorSettingsView()
                default:
                    ProfessorSessionsView()
                }
            }
        }
    }
}

// Placeholder views for each tab
struct ProfessorSessionsView: View {
    var body: some View {
        Text("Professor Sessions")
            .padding()
    }
}

struct ProfessorActiveSessionView: View {
    var body: some View {
        Text("Professor Active Session")
            .padding()
    }
}

struct ProfessorSettingsView: View {
    var body: some View {
        Text("Professor Settings")
            .padding()
    }
}
