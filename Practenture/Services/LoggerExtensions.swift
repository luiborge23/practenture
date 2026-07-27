// LoggerExtensions.swift
// Practenture
//
// os.Logger extensions for structured, category-based logging.
// Replaces print() calls throughout the codebase with proper
// subsystem-scoped loggers that show up in Console.app.

import os

extension Logger {
    /// Practenture subsystem for all app logs.
    private static let subsystem = "com.luisborges.practenture.Practenture"

    // MARK: - Domain Loggers

    /// Networking requests, responses, errors.
    static let network = Logger(subsystem: subsystem, category: "Network")

    /// Authentication events (login, logout, token refresh).
    static let auth = Logger(subsystem: subsystem, category: "Auth")

    /// WebSocket connection lifecycle.
    static let webSocket = Logger(subsystem: subsystem, category: "WebSocket")

    /// Simulation engine (round processing, AI competitors).
    static let simulation = Logger(subsystem: subsystem, category: "Simulation")

    /// Data sync (Firebase, offline queue).
    static let sync = Logger(subsystem: subsystem, category: "Sync")

    /// UI events (navigation, view lifecycle).
    static let ui = Logger(subsystem: subsystem, category: "UI")

    /// PDF export operations.
    static let pdf = Logger(subsystem: subsystem, category: "PDF")

    /// AI Coach insights.
    static let coach = Logger(subsystem: subsystem, category: "Coach")

    /// Internationalization.
    static let i18n = Logger(subsystem: subsystem, category: "i18n")
}
