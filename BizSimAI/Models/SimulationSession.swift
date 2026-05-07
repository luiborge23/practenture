// SimulationSession.swift
// BizSimAI
//
// Observable session object that holds all state for an active simulation.
// Enhanced with investor scorecard, S/Q tracking, and financial state.

import Foundation
import Observation

@Observable
class SimulationSession: Identifiable {
    let id: UUID
    let config: SessionConfiguration

    /// Current round number (1-based). Starts at 0 meaning "not yet started."
    var currentRound: Int = 0

    /// Session lifecycle state.
    var state: SessionState = .waitingForPlayers

    /// All teams in the session (player + AI).
    var teams: [TeamStatus] = []

    /// The human player's team (convenience reference).
    var playerTeam: TeamStatus? {
        get { teams.first(where: { !$0.isAI }) }
        set {
            if let newValue, let index = teams.firstIndex(where: { $0.id == newValue.id }) {
                teams[index] = newValue
            }
        }
    }

    /// AI competitor teams.
    var aiCompetitors: [TeamStatus] {
        teams.filter { $0.isAI }
    }

    /// Round results indexed by team ID, then by round number.
    var roundResults: [UUID: [Int: RoundResult]] = [:]

    /// Decisions submitted for the current round, indexed by team ID.
    var currentRoundDecisions: [UUID: PlayerDecision] = [:]

    /// Previous round's decisions (preserved for AI context).
    var previousRoundDecisions: [UUID: PlayerDecision] = [:]

    /// Short alphanumeric code for multiplayer/sharing.
    let sessionCode: String

    /// Coaching messages for this session.
    var coachMessages: [CoachMessage] = []

    /// Round summaries for the player, ordered by round.
    var playerRoundSummaries: [RoundSummary] = []

    /// Professor announcements for this session.
    var announcements: [Announcement] = []

    /// Enrolled students roster.
    var enrolledStudents: [EnrolledStudent] = []

    /// Grade mapping configuration.
    var gradeMappings: [GradeMapping] = GradeMapping.defaultScale

    /// Round deadlines (for timed mode). Key = round number, value = deadline date.
    var roundDeadlines: [Int: Date] = [:]

    /// Whether the session is paused (prevents decision submissions).
    var isPaused: Bool = false

    // MARK: - Initialization

    init(config: SessionConfiguration) {
        self.id = UUID()
        self.config = config
        self.sessionCode = SimulationSession.generateSessionCode()

        // Create human teams based on maxHumanTeams config.
        let humanTeamNames = Self.humanTeamNames.prefix(config.maxHumanTeams)
        for (_, teamName) in humanTeamNames.enumerated() {
            let player = TeamStatus(
                name: config.maxHumanTeams == 1 ? config.name : teamName,
                cash: config.startingCash,
                isAI: false,
                equity: config.initialEquity,
                sharesOutstanding: config.sharesOutstanding
            )
            teams.append(player)
        }

        // Create AI competitor teams (use deterministic shuffle based on session seed)
        var rng = SeededRandomGenerator(seed: config.randomSeed)
        let shuffledNames = Self.aiCompanyNames.shuffled(using: &rng)
        let aiNames = shuffledNames.prefix(config.numberOfAICompetitors)
        for name in aiNames {
            let aiTeam = TeamStatus(
                name: name,
                cash: config.startingCash,
                isAI: true,
                equity: config.initialEquity,
                sharesOutstanding: config.sharesOutstanding
            )
            teams.append(aiTeam)
        }
    }

    // MARK: - Session Code Generation

    static func generateSessionCode() -> String {
        let characters = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        let suffix = (0..<4).map { _ in
            characters[characters.index(characters.startIndex, offsetBy: Int.random(in: 0..<characters.count))]
        }
        return "BIZ-" + String(suffix)
    }

    // MARK: - Round State

    func isRoundComplete() -> Bool {
        let allTeamIds = Set(teams.map { $0.id })
        let submittedIds = Set(currentRoundDecisions.keys)
        return allTeamIds.isSubset(of: submittedIds)
    }

    @discardableResult
    func submitDecision(_ decision: PlayerDecision) -> Bool {
        guard !isPaused else { return false }
        currentRoundDecisions[decision.teamId] = decision

        if let index = teams.firstIndex(where: { $0.id == decision.teamId }) {
            teams[index].hasSubmittedDecisions = true
        }

        return isRoundComplete()
    }

    /// Record a round result for a team. Updates team financial state.
    func recordResult(_ result: RoundResult) {
        // Guard against duplicate recordResult calls
        guard roundResults[result.teamId]?[result.round] == nil else { return }

        if roundResults[result.teamId] == nil {
            roundResults[result.teamId] = [:]
        }
        roundResults[result.teamId]?[result.round] = result

        // Update team status from the result.
        if let index = teams.firstIndex(where: { $0.id == result.teamId }) {
            teams[index].cash = result.cash
            teams[index].inventory = result.inventory
            teams[index].sqRating = result.sqRating
            teams[index].imageRating = result.scorecard.imageRating
            teams[index].creditRating = result.scorecard.creditRating

            // Update cumulative investor score
            let prevTotal = teams[index].cumulativeInvestorScore * Double(teams[index].roundsScored)
            teams[index].roundsScored += 1
            teams[index].cumulativeInvestorScore = (prevTotal + result.scorecard.totalScore) / Double(teams[index].roundsScored)

            // Update cumulative profit
            teams[index].cumulativeProfit += result.profit
        }
    }

    func advanceRound() {
        currentRound += 1
        previousRoundDecisions = currentRoundDecisions
        currentRoundDecisions.removeAll()

        for index in teams.indices {
            teams[index].hasSubmittedDecisions = false
        }

        if currentRound > config.totalRounds {
            state = .completed
        } else {
            state = .inProgress
        }
    }

    func resultsForTeam(_ teamId: UUID) -> [RoundResult] {
        guard let teamResults = roundResults[teamId] else { return [] }
        return teamResults.values.sorted { $0.round < $1.round }
    }

    func latestResult(for teamId: UUID) -> RoundResult? {
        roundResults[teamId]?[currentRound] ?? roundResults[teamId]?[currentRound - 1]
    }

    func cumulativeProfit(for teamId: UUID) -> Double {
        resultsForTeam(teamId).reduce(0) { $0 + $1.profit }
    }

    func cumulativeRevenue(for teamId: UUID) -> Double {
        resultsForTeam(teamId).reduce(0) { $0 + $1.revenue }
    }

    /// Update team rankings based on the current scoring metric.
    func updateRankings() {
        let scored: [(index: Int, score: Double)] = teams.indices.map { index in
            let teamId = teams[index].id
            let score: Double
            switch config.scoringMetric {
            case .investorScore:
                score = teams[index].cumulativeInvestorScore
            case .cumulativeProfit:
                score = cumulativeProfit(for: teamId)
            case .revenue:
                score = cumulativeRevenue(for: teamId)
            case .composite:
                let profit = cumulativeProfit(for: teamId)
                let revenue = cumulativeRevenue(for: teamId)
                let share = latestResult(for: teamId)?.marketShare ?? 0
                let normalizedProfit = profit / config.startingCash
                let normalizedRevenue = revenue / config.startingCash
                score = (normalizedProfit * 0.4) + (normalizedRevenue * 0.3) + (share * 0.3)
            }
            return (index, score)
        }

        let ranked = scored.sorted { $0.score > $1.score }
        for (rank, entry) in ranked.enumerated() {
            teams[entry.index].rank = rank + 1
        }
    }

    // MARK: - Chart Data

    func chartData(for teamId: UUID, metric: PerformanceMetric) -> [ChartDataPoint] {
        resultsForTeam(teamId).map { result in
            let value: Double
            switch metric {
            case .profit: value = result.profit
            case .revenue: value = result.revenue
            case .marketShare: value = result.marketShare * 100
            case .satisfaction: value = result.customerSatisfaction * 100
            case .cash: value = result.cash
            case .sqRating: value = result.sqRating
            case .eps: value = result.scorecard.eps
            case .imageRating: value = result.scorecard.imageRating
            case .investorScore: value = result.scorecard.totalScore
            case .rejectionRate: value = result.rejectionRate * 100
            }
            return ChartDataPoint(
                round: result.round,
                value: value,
                label: metric.displayName
            )
        }
    }

    // MARK: - Announcement Management

    func addAnnouncement(_ message: String, forRound round: Int? = nil) {
        announcements.append(Announcement(message: message, roundNumber: round))
    }

    // MARK: - Student Enrollment

    @discardableResult
    func enrollStudent(name: String, email: String) -> EnrolledStudent {
        let student = EnrolledStudent(name: name, email: email)
        enrolledStudents.append(student)
        return student
    }

    func removeStudent(_ studentId: UUID) {
        if let index = enrolledStudents.firstIndex(where: { $0.id == studentId }) {
            enrolledStudents[index].isActive = false
        }
    }

    func assignStudentToTeam(_ studentId: UUID, teamId: UUID?) {
        if let index = enrolledStudents.firstIndex(where: { $0.id == studentId }) {
            enrolledStudents[index].teamId = teamId
        }
    }

    /// Auto-assign unassigned active students to human teams evenly.
    func autoAssignStudents() {
        let humanTeams = teams.filter { !$0.isAI }
        guard !humanTeams.isEmpty else { return }

        var unassigned = enrolledStudents.filter { $0.isActive && $0.teamId == nil }
        unassigned.shuffle()

        var teamIndex = 0
        for i in unassigned.indices {
            guard let globalIndex = enrolledStudents.firstIndex(where: { $0.id == unassigned[i].id }) else { continue }
            enrolledStudents[globalIndex].teamId = humanTeams[teamIndex % humanTeams.count].id
            teamIndex += 1
        }
    }

    /// Students assigned to a specific team.
    func studentsForTeam(_ teamId: UUID) -> [EnrolledStudent] {
        enrolledStudents.filter { $0.teamId == teamId && $0.isActive }
    }

    /// Unassigned active students.
    var unassignedStudents: [EnrolledStudent] {
        enrolledStudents.filter { $0.teamId == nil && $0.isActive }
    }

    // MARK: - Deadline Management

    /// Set deadline for a specific round based on hours from now.
    func setDeadline(forRound round: Int, hoursFromNow: Int) {
        roundDeadlines[round] = Date().addingTimeInterval(Double(hoursFromNow) * 3600)
    }

    /// Initialize all round deadlines based on config.
    func initializeDeadlines() {
        guard config.roundPacingMode == .timed, config.totalRounds >= 1 else { return }
        for round in 1...config.totalRounds {
            let hoursOffset = config.roundDeadlineHours * round
            roundDeadlines[round] = Date().addingTimeInterval(Double(hoursOffset) * 3600)
        }
    }

    /// Time remaining for current round's deadline, nil if no deadline.
    var currentRoundTimeRemaining: TimeInterval? {
        guard let deadline = roundDeadlines[currentRound] else { return nil }
        return deadline.timeIntervalSinceNow
    }

    /// Whether the current round deadline has passed.
    var isCurrentRoundOverdue: Bool {
        guard let remaining = currentRoundTimeRemaining else { return false }
        return remaining <= 0
    }

    /// Whether the session has expired.
    var isExpired: Bool {
        guard let expiry = config.sessionExpiryDate else { return false }
        return Date() > expiry
    }

    /// Grade for a given team based on their cumulative investor score.
    func grade(for teamId: UUID) -> String? {
        guard let team = teams.first(where: { $0.id == teamId }) else { return nil }
        let score = team.cumulativeInvestorScore
        // Use half-open ranges: score >= min and score < max (except top grade includes max)
        return gradeMappings
            .sorted(by: { $0.minScore > $1.minScore })  // Check highest grade first
            .first(where: { score >= $0.minScore })?.label
    }

    // MARK: - Human Team Names

    private static let humanTeamNames = [
        "Team Alpha", "Team Bravo", "Team Charlie", "Team Delta",
        "Team Echo", "Team Foxtrot", "Team Golf", "Team Hotel",
        "Team India", "Team Juliet", "Team Kilo", "Team Lima",
        "Team Mike", "Team November", "Team Oscar", "Team Papa",
        "Team Quebec", "Team Romeo", "Team Sierra", "Team Tango"
    ]

    // MARK: - AI Company Names

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

    // MARK: - Convenience Accessors

    var totalRounds: Int { config.totalRounds }
    var startingCash: Double { config.startingCash }
    var scoringMetric: ScoringMetric { config.scoringMetric }

    func roundResult(for teamId: UUID, round: Int) -> RoundResult? {
        roundResults[teamId]?[round]
    }

    func hasDecision(for teamId: UUID, round: Int) -> Bool {
        if round == currentRound {
            return currentRoundDecisions[teamId] != nil
        }
        return roundResults[teamId]?[round] != nil
    }

    func rank(for teamId: UUID) -> Int? {
        teams.first(where: { $0.id == teamId })?.rank
    }
}
