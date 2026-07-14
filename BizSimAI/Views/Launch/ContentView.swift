// ContentView.swift
// BizSimAI
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
                }
            }
        }
        .onChange(of: authManager.isAuthenticated) { _, isAuthed in
            // If token expired elsewhere (NetworkService 401 path) push back to launch
            if !isAuthed && authManager.accessToken == nil && appState.currentMode != nil {
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
