// ContentView.swift
// BizSimAI
//
// Root view that switches between LaunchView, ProfessorTabView, or Student flow
// based on AppState.currentMode.

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

    var body: some View {
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

    @ViewBuilder
    private var studentFlow: some View {
        if !appState.hasActiveSession {
            JoinSessionView()
        } else {
            TeamDashboardView()
        }
    }
}
