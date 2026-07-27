// PractentureApp.swift
// Practenture
//
// App entry point. Configures the main window and injects AppState
// into the environment for all views. Sets up SwiftData ModelContainer
// for local persistence of SimulationSession.

import SwiftUI
import SwiftData
import GoogleSignIn

// MARK: - PractentureTheme
// Theme configuration for Practenture app with purple accent color (#8b5cf6)
// and consistent visual design system.

struct PractentureTheme {
    // MARK: - Accent Color
    static let accentColor = Color(red: 0.545, green: 0.373, blue: 0.965) // #8b5cf6
    
    // MARK: - Color Palette
    static let successColor = Color(red: 0.341, green: 0.686, blue: 0.290) // #57a342
    static let warningColor = Color(red: 0.980, green: 0.733, blue: 0.145) // #fab823
    static let errorColor = Color(red: 0.769, green: 0.216, blue: 0.235) // #c43e3c
    
    static let primary = Color(red: 0.129, green: 0.129, blue: 0.184) // #21212e
    static let secondary = Color(red: 0.184, green: 0.184, blue: 0.251) // #2e2e40
    static let background = Color(red: 0.071, green: 0.071, blue: 0.129) // #121221
    static let surface = Color(red: 0.161, green: 0.161, blue: 0.235) // #29293c
    static let textPrimary = Color.white
    static let textSecondary = Color(red: 0.627, green: 0.627, blue: 0.745) // #a0a0be
    
    // MARK: - Typography
    static let fontHeading1 = Font.system(size: 32, weight: .bold)
    static let fontHeading2 = Font.system(size: 24, weight: .semibold)
    static let fontHeading3 = Font.system(size: 20, weight: .semibold)
    static let fontBody = Font.system(size: 16, weight: .regular)
    static let fontCaption = Font.system(size: 14, weight: .regular)
    
    // MARK: - Spacing
    static let spacingSmall = CGFloat(8)
    static let spacingMedium = CGFloat(16)
    static let spacingLarge = CGFloat(24)
    static let spacingXLarge = CGFloat(32)
    
    // MARK: - Border Radius
    static let cornerRadiusSmall = CGFloat(8)
    static let cornerRadiusMedium = CGFloat(12)
    static let cornerRadiusLarge = CGFloat(16)
    static let cornerRadiusXLarge = CGFloat(24)
    
    // MARK: - Color Palette
    // Success, Warning, Error colors for status indicators
    static let success = Color(red: 0.341, green: 0.686, blue: 0.290) // #57a342
    static let warning = Color(red: 0.980, green: 0.733, blue: 0.145) // #fab823
    static let error = Color(red: 0.769, green: 0.216, blue: 0.235) // #c43e3c
}

// MARK: - PractentureTheme Extension for View Modifiers
extension PractentureTheme {
    static func cardStyle() -> some ViewModifier {
        CardStyle()
    }
}

// MARK: - CardStyle
struct CardStyle: ViewModifier {
    func body(content: Content) -> some View {
        content
            .padding(.vertical, 16)
            .padding(.horizontal, 20)
            .background(
                RoundedRectangle(cornerRadius: PractentureTheme.cornerRadiusMedium)
                    .fill(PractentureTheme.surface)
            )
            .shadow(color: PractentureTheme.primary.opacity(0.15), radius: 12, x: 0, y: 6)
    }
}

@main
struct PractentureApp: App {
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
                .onOpenURL { url in
                    GIDSignIn.sharedInstance.handle(url)
                }
        }
        .modelContainer(sharedModelContainer)
    }

    @ViewBuilder
    private var rootView: some View {
        #if DEBUG
        if let rawRole = ProcessInfo.processInfo.environment["PRACTENTURE_UI_AUTH_ROLE"],
           let role = LoginView.SelectedRole(rawValue: rawRole),
           let step = LoginView.OnboardingStep(
                rawValue: ProcessInfo.processInfo.environment["PRACTENTURE_UI_AUTH_STEP"] ?? "authenticationMethods"
           ) {
            LoginView(initialRole: role, initialStep: step)
        } else if ProcessInfo.processInfo.arguments.contains("-UITesting"),
                  let rawScenario = ProcessInfo.processInfo.environment["PRACTENTURE_UI_SCENARIO"],
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

