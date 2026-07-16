// BizSimAIApp.swift
// BizSimAI
//
// App entry point. Configures the main window and injects AppState
// into the environment for all views. Sets up SwiftData ModelContainer
// for local persistence of SimulationSession.

import SwiftUI
import SwiftData

@main
struct BizSimAIApp: App {
    @State private var appState = AppState()

    var sharedModelContainer: ModelContainer = {
        // Ensure the Application Support directory exists before SwiftData tries to create the SQLite store.
        // Without this, the first launch in a clean simulator hits NSCocoaErrorDomain 512
        // ("Failed to create file; code = 2") because the parent directory is missing.
        let appSupport = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        try? FileManager.default.createDirectory(at: appSupport, withIntermediateDirectories: true)

        let schema = Schema([SimulationSession.self])
        let config = ModelConfiguration(schema: schema, isStoredInMemoryOnly: false)
        return try! ModelContainer(for: schema, configurations: [config])
    }()

    var body: some Scene {
        WindowGroup {
            rootView
                .environment(appState)
                .preferredColorScheme(appState.themePreference.colorScheme)
        }
        .modelContainer(sharedModelContainer)
    }

    @ViewBuilder
    private var rootView: some View {
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("-UITesting"),
           let rawScenario = ProcessInfo.processInfo.environment["BIZSIMAI_UI_SCENARIO"],
           let scenario = UITestHarnessView.Scenario(rawValue: rawScenario) {
            UITestHarnessView(scenario: scenario)
        } else {
            ContentView()
        }
        #else
        ContentView()
        #endif
    }
}
