// ContentView.swift
// Practenture
//
// Root view that switches between LaunchView, ProfessorTabView, or Student flow
// based on AppState.currentMode. Also observes AuthManager so 401 logout
// propagates back to launch.

import SwiftUI

// MARK: - Theme Preference

enum ThemePreference: String, Codable, CaseIterable {
    case system = "System"
    case light = "Light"
    case dark = "Dark"

    var colorScheme: ColorScheme? {
        switch self {
        case .system: return nil
        case .light: return .light
        case .dark: return .dark
        }
    }
}

// MARK: - AppState Preview Extensions

extension AppState {
    static var preview: AppState {
        AppState()
    }

    static var professorPreview: AppState {
        let state = AppState()
        state.selectMode(.professor)
        return state
    }

    static var studentPreview: AppState {
        let state = AppState()
        state.selectMode(.student)
        return state
    }
}

// MARK: - Content View

struct ContentView: View {
    @Environment(AppState.self) private var appState
    // Observe auth so a forced logout (401 refresh fail) resets UI
    @State private var authManager = AuthManager.shared
    @State private var showStudentSettings = false

    var body: some View {
        Group {
            switch appState.currentMode {
            case .none:
                LaunchView()
            case .professor:
                ProfessorTabView()
            case .student:
                NavigationStack {
                    studentFlow
                        .toolbar {
                            ToolbarItem(placement: .topBarTrailing) {
                                Button {
                                    showStudentSettings = true
                                } label: {
                                    Label("Settings", systemImage: "gearshape")
                                }
                                .accessibilityIdentifier("studentSettingsButton")
                            }
                        }
                }
                .sheet(isPresented: $showStudentSettings) {
                    SettingsView()
                }
            }
        }
        .onChange(of: authManager.isAuthenticated) { _, isAuthed in
            // If token expired elsewhere (NetworkService 401 path) push back to launch
            if !isAuthed && appState.currentMode != nil {
                appState.resetToLaunch()
            }
        }
    }

    @ViewBuilder
    private var studentFlow: some View {
        if !appState.hasActiveSession {
            JoinSessionView()
        } else {
            TeamDashboardView()
        }
    }
}
