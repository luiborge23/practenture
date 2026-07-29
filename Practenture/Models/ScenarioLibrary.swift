import Foundation

/// Stable identity sent with sessions so presentation can evolve independently
/// from the footwear simulation's decision model and formulas.
nonisolated struct ScenarioIdentity: Codable, Hashable, Sendable {
    let id: String
    let version: String

    static let athleticFootwearClassic = ScenarioIdentity(
        id: "athletic-footwear-classic",
        version: "1.0.0"
    )

    static let wearableTechnology = ScenarioIdentity(
        id: "wearable-technology",
        version: "1.0.0"
    )
}

/// User-facing scenario metadata. Availability is deliberately presentation and
/// routing metadata only; it does not alter the existing footwear game engine.
nonisolated struct SimulationScenario: Identifiable, Hashable, Sendable {
    enum Availability: Hashable, Sendable {
        case available
        case unavailable(reason: String)
    }

    let identity: ScenarioIdentity
    let title: String
    let edition: String
    let summary: String
    let systemImage: String
    let availability: Availability

    var id: String { identity.id + "@" + identity.version }
    var displayName: String { "\(title) — \(edition)" }
    var isAvailable: Bool {
        if case .available = availability { return true }
        return false
    }

    var availabilityLabel: String {
        switch availability {
        case .available:
            return "Available"
        case .unavailable(let reason):
            return reason
        }
    }
}

nonisolated enum ScenarioLibrary {
    static let athleticFootwearClassic = SimulationScenario(
        identity: .athleticFootwearClassic,
        title: "Athletic Footwear",
        edition: "Classic Scenario",
        summary: "Lead an athletic footwear company through pricing, production, marketing, workforce, and finance decisions.",
        systemImage: "shoe.2.fill",
        availability: .available
    )

    static let wearableTechnology = SimulationScenario(
        identity: .wearableTechnology,
        title: "Wearable Technology",
        edition: "Future Scenario",
        summary: "Design a wearable device — balance battery, sensors, privacy, and sourcing to win the market.",
        systemImage: "applewatch",
        availability: .available
    )

    static let all: [SimulationScenario] = [
        athleticFootwearClassic,
        wearableTechnology
    ]

    /// Missing identity/version values are legacy sessions and therefore resolve
    /// to the original footwear experience. Unknown or unavailable identities do
    /// not silently route into footwear gameplay.
    static func scenario(id: String?, version: String?) -> SimulationScenario {
        guard let id, !id.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            return athleticFootwearClassic
        }

        let normalizedID = normalize(id)
        if normalizedID == normalize(ScenarioIdentity.athleticFootwearClassic.id) {
            return athleticFootwearClassic
        }
        if normalizedID == normalize(ScenarioIdentity.wearableTechnologyResearch.id) {
            return wearableTechnology
        }

        return SimulationScenario(
            identity: ScenarioIdentity(id: id, version: version ?? "unknown"),
            title: "Unsupported Scenario",
            edition: version ?? "Unknown Version",
            summary: "This version of Practenture cannot start this scenario.",
            systemImage: "questionmark.app.dashed",
            availability: .unavailable(reason: "Unavailable in this app version")
        )
    }

    static func scenario(for identity: ScenarioIdentity) -> SimulationScenario {
        scenario(id: identity.id, version: identity.version)
    }

    private static func normalize(_ value: String) -> String {
        value
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .lowercased()
            .replacingOccurrences(of: "_", with: "-")
            .replacingOccurrences(of: " ", with: "-")
    }
}
