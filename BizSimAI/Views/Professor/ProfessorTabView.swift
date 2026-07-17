// ProfessorTabView.swift
// BizSimAI
//
// Tab container for Professor mode with Sessions, Active Session, and Settings tabs.
// Uses a custom segmented picker instead of TabView to avoid macOS NSTabView
// event routing issues when launched via `swift run`.

import SwiftUI

struct ProfessorTabView: View {
    @Environment(AppState.self) private var appState

    enum ProfessorTab: String, Hashable, CaseIterable {
        case sessions = "Sessions"
        case activeSession = "Monitor"
        case teams = "Teams"
        case announcements = "Announcements"
        case grading = "Grading"
        case settings = "Settings"

        var icon: String {
            switch self {
            case .sessions: return "list.bullet.rectangle.portrait"
            case .activeSession: return "play.circle.fill"
            case .teams: return "person.crop.circle.badge.checkmark"
            case .announcements: return "megaphone"
            case .grading: return "graduationcap"
            case .settings: return "gearshape"
            }
        }

        var key: String {
            switch self {
            case .sessions: return "sessions"
            case .activeSession: return "monitor"
            case .teams: return "teams"
            case .announcements: return "announcements"
            case .grading: return "grading"
            case .settings: return "settings"
            }
        }

        init?(key: String) {
            switch key {
            case "sessions": self = .sessions
            case "monitor": self = .activeSession
            case "teams": self = .teams
            case "announcements": self = .announcements
            case "grading": self = .grading
            case "settings": self = .settings
            default: return nil
            }
        }
    }

    private var selectedTab: Binding<ProfessorTab> {
        Binding(
            get: { ProfessorTab(key: appState.professorSelectedTab) ?? .sessions },
            set: { appState.professorSelectedTab = $0.key }
        )
    }

    var body: some View {
        VStack(spacing: 0) {
            // Scrollable tab bar
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(spacing: 6) {
                    ForEach(ProfessorTab.allCases, id: \.self) { tab in
                        Button {
                            appState.professorSelectedTab = tab.key
                        } label: {
                            Label(tab.rawValue, systemImage: tab.icon)
                                .font(.subheadline)
                                .fontWeight(selectedTab.wrappedValue == tab ? .bold : .regular)
                                .padding(.horizontal, 14)
                                .padding(.vertical, 8)
                                .background(
                                    Capsule().fill(selectedTab.wrappedValue == tab ? Color.accentColor : Color.gray.opacity(0.15))
                                )
                                .foregroundStyle(selectedTab.wrappedValue == tab ? .white : .primary)
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(.horizontal, 16)
            }
            .padding(.vertical, 10)

            Divider()

            // Tab content
            NavigationStack {
                switch selectedTab.wrappedValue {
                case .sessions:
                    SessionListView()
                case .activeSession:
                    if appState.hasActiveSession {
                        SessionMonitorView()
                    } else {
                        noActiveSessionView
                    }
                case .teams:
                    if appState.hasActiveSession {
                        TeamManagementView()
                    } else {
                        noActiveSessionView
                    }
                case .announcements:
                    if appState.hasActiveSession {
                        AnnouncementsView()
                    } else {
                        noActiveSessionView
                    }
                case .grading:
                    if appState.hasActiveSession {
                        GradeMappingView()
                    } else {
                        noActiveSessionView
                    }
                case .settings:
                    SettingsView()
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var noActiveSessionView: some View {
        VStack(spacing: 20) {
            Image(systemName: "play.slash")
                .font(.system(size: 48))
                .foregroundStyle(.secondary)

            Text("No Active Session")
                .font(.title2)
                .fontWeight(.bold)

            Text("Create a new session or select an existing one from the Sessions tab to begin monitoring.")
                .font(.body)
                .foregroundStyle(.secondary)
                .multilineTextAlignment(.center)
                .frame(maxWidth: 400)

            Button {
                appState.professorSelectedTab = "sessions"
            } label: {
                Text("Go to Sessions")
            }
            .buttonStyle(.borderedProminent)
        }
        .navigationTitle("Active Session")
        .toolbar {
            ToolbarItem(placement: .automatic) {
                Button {
                    appState.resetToLaunch()
                } label: {
                    Label("Back to Home", systemImage: "house")
                }
            }
        }
    }
}
