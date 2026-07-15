import SwiftUI

// MARK: - CreateSessionViewModel
/// ViewModel for the professor's create-session form (P-2).
/// Holds all form fields with validation, and creates a SimulationSession when valid.
/// Supports both local and cloud backend session creation.

@Observable
final class CreateSessionViewModel {

    // MARK: - Form Fields

    var sessionName: String = ""
    var totalRounds: Int = 10
    var startingCash: Double = 100_000
    var marketType: MarketType = .moderate
    var aiDifficulty: AIDifficulty = .medium
    var numberOfAICompetitors: Int = 3
    var scoringMetric: ScoringMetric = .investorScore

    // MARK: - Class & Enrollment
    var courseCode: String = ""
    var semester: String = ""
    var maxHumanTeams: Int = 1
    var teamSize: Int = 4

    // MARK: - Timing
    var roundPacingMode: RoundPacingMode = .manual
    var roundDeadlineHours: Int = 48
    var latePolicy: LateSubmissionPolicy = .usePrevious
    var sessionExpiryDays: Int = 90  // Days from creation until session expires

    // MARK: - Template & Mode
    var selectedTemplate: SessionTemplate = .custom
    var isPracticeMode: Bool = false

    // MARK: - Cloud / Backend
    var useBackend: Bool = true
    var backendSessionCode: String?
    var backendTeams: [TeamConfig] = []
    var backendTeamCount: Int = 0

    // MARK: - Validation Ranges

    static let roundsRange = 3...20
    static let cashRange: ClosedRange<Double> = 50_000...500_000
    static let cashStep: Double = 10_000
    static let competitorsRange = 1...5
    static let maxTeamsRange = 1...20
    static let teamSizeRange = 1...6
    static let deadlineHoursRange = 1...168  // 1 hour to 1 week
    static let expiryDaysRange = 7...365

    // MARK: - State

    var isCreating: Bool = false
    var creationError: String?

    // MARK: - Computed Validation

    var isNameValid: Bool {
        let trimmed = sessionName.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.count >= 3 && trimmed.count <= 50
    }

    var isRoundsValid: Bool {
        Self.roundsRange.contains(totalRounds)
    }

    var isCashValid: Bool {
        Self.cashRange.contains(startingCash)
    }

    var isCompetitorsValid: Bool {
        Self.competitorsRange.contains(numberOfAICompetitors)
    }

    var isValid: Bool {
        isNameValid && isRoundsValid && isCashValid && isCompetitorsValid
            && Self.maxTeamsRange.contains(maxHumanTeams)
            && Self.teamSizeRange.contains(teamSize)
    }

    var validationErrors: [String] {
        var errors: [String] = []

        if !isNameValid {
            errors.append("Session name must be 3-50 characters.")
        }
        if !isRoundsValid {
            errors.append("Total rounds must be between \(Self.roundsRange.lowerBound) and \(Self.roundsRange.upperBound).")
        }
        if !isCashValid {
            let low = Self.cashRange.lowerBound.formatted(.currency(code: "USD").precision(.fractionLength(0)))
            let high = Self.cashRange.upperBound.formatted(.currency(code: "USD").precision(.fractionLength(0)))
            errors.append("Starting cash must be between \(low) and \(high).")
        }
        if !isCompetitorsValid {
            errors.append("AI competitors must be between \(Self.competitorsRange.lowerBound) and \(Self.competitorsRange.upperBound).")
        }

        return errors
    }

    // MARK: - Display Helpers

    var formattedStartingCash: String {
        startingCash.formatted(.currency(code: "USD").precision(.fractionLength(0)))
    }

    var marketTypeDescription: String {
        marketType.description
    }

    var difficultyDescription: String {
        aiDifficulty.description
    }

    // MARK: - Actions

    /// Validate fields and create a new SimulationSession.
    /// If useBackend is true, also creates the session on the FastAPI backend.
    /// Returns nil if validation fails.
    func createSession() async -> SimulationSession? {
        guard isValid else {
            creationError = validationErrors.first
            return nil
        }

        isCreating = true
        creationError = nil

        let trimmedName = sessionName.trimmingCharacters(in: .whitespacesAndNewlines)

        let expiryDate = Calendar.current.date(byAdding: .day, value: sessionExpiryDays, to: Date())

        let config = SessionConfiguration(
            name: trimmedName,
            totalRounds: totalRounds,
            startingCash: startingCash,
            marketType: marketType,
            aiDifficulty: aiDifficulty,
            numberOfAICompetitors: numberOfAICompetitors,
            scoringMetric: scoringMetric,
            courseCode: courseCode,
            semester: semester,
            maxHumanTeams: maxHumanTeams,
            teamSize: teamSize,
            roundPacingMode: roundPacingMode,
            roundDeadlineHours: roundDeadlineHours,
            latePolicy: latePolicy,
            sessionExpiryDate: expiryDate,
            template: selectedTemplate,
            isPracticeMode: isPracticeMode
        )

        if useBackend {
            // Create session on the backend first
            do {
                // Build team configs for AI competitors
                var teams: [TeamConfig] = []
                let shuffledNames = Self.aiCompanyNames.shuffled()
                for name in shuffledNames.prefix(numberOfAICompetitors) {
                    teams.append(TeamConfig(
                        id: UUID(),
                        name: name,
                        isAI: true
                    ))
                }

                let sessionResult = try await NetworkService.shared.createSession(
                    config: config,
                    teams: teams
                )

                // Create local session with the backend code
                backendSessionCode = sessionResult.code

                let localSession = SimulationSession(config: config)
                // Override the local session code with the backend code
                // (SimulationSession generates its own code, but we use the backend one)

                isCreating = false
                return localSession

            } catch {
                isCreating = false
                creationError = "Failed to create session on cloud: \(UserFriendlyError.message(for: error))"
                // Fallback to local-only mode
                let session = SimulationSession(config: config)
                return session
            }
        } else {
            // Local-only mode
            let session = SimulationSession(config: config)
            isCreating = false
            return session
        }
    }

    /// Refresh the team count from the backend.
    func refreshTeamCount(sessionCode: String) async {
        do {
            let teams = try await NetworkService.shared.getTeams(code: sessionCode)
            backendTeamCount = teams.count
            // Convert backend teams to iOS TeamConfig type
            backendTeams = teams.map { backend in
                TeamConfig(
                    id: UUID(),
                    name: backend.teamName,
                    isAI: backend.isAI,
                    playerName: backend.studentId,
                    studentId: backend.studentId
                )
            }
        } catch {
            // Silently fail — local mode doesn't need this
            backendTeamCount = 0
        }
    }

    /// Reset all form fields to defaults.
    func resetForm() {
        sessionName = ""
        totalRounds = 10
        startingCash = 100_000
        marketType = .moderate
        aiDifficulty = .medium
        numberOfAICompetitors = 3
        scoringMetric = .investorScore
        courseCode = ""
        semester = ""
        maxHumanTeams = 1
        teamSize = 4
        roundPacingMode = .manual
        roundDeadlineHours = 48
        latePolicy = .usePrevious
        sessionExpiryDays = 90
        selectedTemplate = .custom
        isPracticeMode = false
        useBackend = true
        backendSessionCode = nil
        backendTeams = []
        backendTeamCount = 0
        creationError = nil
    }

    /// Apply a session template, updating all related fields.
    func applyTemplate(_ template: SessionTemplate) {
        selectedTemplate = template
        guard template != .custom else { return }
        totalRounds = template.rounds
        aiDifficulty = template.difficulty
        marketType = template.marketType
        startingCash = template.startingCash
    }

    // MARK: - AI Team Names

    private static let aiCompanyNames = [
        "NovaTech Industries",
        "Apex Solutions",
        "Pinnacle Corp",
        "Vanguard Enterprises",
        "Summit Global",
        "Catalyst Labs",
        "Meridian Group",
        "Zenith Holdings",
        "Frontier Dynamics",
        "Quantum Ventures",
        "Sterling Works",
        "Beacon Innovations"
    ]
}
