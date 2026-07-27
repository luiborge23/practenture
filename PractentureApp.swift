// PractentureApp.swift
// Practenture
//
// App entry point. Configures the main window and injects AppState
// into the environment for all views.
//
// Practenture Theme: Dark premium with vibrant purple (#8b5cf6), clean cards,
// subtle shadows, and professional typography inspired by practenture.com

import SwiftUI
#if os(macOS)
import AppKit
#endif

// MARK: - Practenture Theme System

/// Color palette for Practenture app - vibrant, opaque colors
struct PractentureColors {
    // Primary brand color - vibrant purple from practenture.com
    static let primary = Color(hex: "#8b5cf6")
    
    // Secondary colors
    static let secondary = Color(hex: "#1f2937")
    static let background = Color(hex: "#050508")
    static let surface = Color(hex: "#111120")
    
    // Text colors
    static let textPrimary = Color(hex: "#ffffff")
    static let textSecondary = Color(hex: "#a0a0b8")
    static let textMuted = Color(hex: "#6a6a82")
    
    // Status colors
    static let success = Color(hex: "#10b981")
    static let warning = Color(hex: "#f59e0b")
    static let error = Color(hex: "#ef4444")
    
    // Border and accent
    static let border = Color(hex: "#1f2937")
    static let accentLight = Color(hex: "#a78bfa")
    
    // Card background with subtle transparency for depth
    static let cardBackground = Color(hex: "#1a1a2e")
}

// MARK: - Theme Struct

/// Main theme configuration for Practenture app
struct PractentureTheme {
    static let colors = PractentureColors()
    
    // Semantic color accessors
    static var primary: Color { colors.primary }
    static var secondary: Color { colors.secondary }
    static var background: Color { colors.background }
    static var surface: Color { colors.surface }
    static var textPrimary: Color { colors.textPrimary }
    static var textSecondary: Color { colors.textSecondary }
    static var textMuted: Color { colors.textMuted }
    static var success: Color { colors.success }
    static var warning: Color { colors.warning }
    static var error: Color { colors.error }
    static var border: Color { colors.border }
    static var accentColor: Color { colors.primary }
    static var cardBackground: Color { colors.cardBackground }
}

// MARK: - Color Extension

extension Color {
    init?(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        guard hex.count == 6 else { return nil }
        
        var rgb: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&rgb)
        
        let red = Double((rgb >> 16) & 0xFF) / 255.0
        let green = Double((rgb >> 8) & 0xFF) / 255.0
        let blue = Double(rgb & 0xFF) / 255.0
        
        self.init(.sRGB, red: red, green: green, blue: blue, opacity: 1.0)
    }
}

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

        print("[Practenture] Activated as regular foreground app")
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
struct PractentureApp: App {
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
