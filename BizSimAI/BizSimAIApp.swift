// BizSimAIApp.swift
// BizSimAI
//
// App entry point. Configures the main window and injects AppState
// into the environment for all views.

import SwiftUI

@main
struct BizSimAIApp: App {
    @State private var appState = AppState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(appState)
                .preferredColorScheme(appState.themePreference.colorScheme)
        }
    }
}
