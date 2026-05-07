// BizSimAIApp.swift
// BizSimAI
//
// App entry point. Configures the main window and injects AppState
// into the environment for all views.

import SwiftUI
#if os(macOS)
import AppKit
#endif

// MARK: - macOS Activation Helper

#if os(macOS)
/// Ensures the app runs as a regular foreground application.
/// When launched via `swift run`, the process starts as an "accessory" app
/// which prevents text fields, buttons, and other controls from receiving
/// mouse/keyboard events. This helper transforms it into a regular app.
enum MacOSActivation {
    static var hasActivated = false

    static func activate() {
        guard !hasActivated else { return }
        hasActivated = true

        let app = NSApplication.shared
        app.setActivationPolicy(.regular)
        app.activate(ignoringOtherApps: true)

        // Make the first window key so it receives keyboard input
        DispatchQueue.main.async {
            if let window = app.windows.first {
                window.makeKeyAndOrderFront(nil)
                window.makeFirstResponder(window.contentView)
            }
        }

        print("[BizSimAI] Activated as regular foreground app")
    }
}

class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        MacOSActivation.activate()
    }

    func applicationDidBecomeActive(_ notification: Notification) {
        // Redundant: re-activate if the delegate fires after window creation
        MacOSActivation.activate()
    }
}
#endif

@main
struct BizSimAIApp: App {
    #if os(macOS)
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    #endif

    @State private var appState = AppState()

    init() {
        // Earliest possible activation — before any window is created
        #if os(macOS)
        MacOSActivation.activate()
        #endif
    }

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(appState)
                .preferredColorScheme(appState.themePreference.colorScheme)
                #if os(macOS)
                .onAppear {
                    // Belt-and-suspenders: activate again after the view appears
                    MacOSActivation.activate()
                }
                #endif
        }
        #if os(macOS)
        .defaultSize(width: 900, height: 700)
        #endif
    }
}
