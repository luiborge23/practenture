// SimulationSession.swift
// BizSimAI
//
// SwiftData-persisted session model that holds all state for an active simulation.
// Enhanced with investor scorecard, S/Q tracking, and financial state.

import Foundation
import SwiftData
import Observation
import os

@Model
class SimulationSession: Identifiable {

    // MARK: - Shared JSON Coders
    // Centralised coders with consistent date strategy so backend ISO-8601
    // dates decode correctly and nested containers never silently mis-interpret.
    private static let decoder: JSONDecoder = {
        let d = JSONDecoder()
        d.dateDecodingStrategy = .iso8601
        return d
    }()

    private static let encoder: JSONEncoder = {
        let e = JSONEncoder()
        e.dateEncodingStrategy = .iso8601
        return e
    }()

    private static let logger = Logger(subsystem: "com.bizsimai", category: "SimulationSession")
    /// Unique identifier for the session.
    var id: UUID

    /// Short alphanumeric code for multiplayer/sharing (unique constraint).
    @Attribute(.unique)
    var code: String

    /// Current round number (1-based). Starts at 0 meaning "not yet started."
    var currentRound: Int

    /// Session lifecycle state (stored as raw String for SwiftData compatibility).
    var stateRaw: String

    /// Backend's team identifier (team name string, not UUID). Set on join.
    /// Used when submitting decisions so the backend can match the team.
    var backendTeamId: String?

    /// All teams in the session — stored as JSON Data.
    var teamsData: Data?

    /// Round results indexed by team ID, then by round number — stored as JSON Data.
    var roundResultsData: Data?

    /// Decisions submitted for the current round — stored as JSON Data.
    var currentRoundDecisionsData: Data?

    /// Previous round's decisions — stored as JSON Data.
    var previousRoundDecisionsData: Data?

    /// Session configuration — stored as JSON Data.
    var configData: Data?

    /// Coaching messages — stored as JSON Data.
    var coachMessagesData: Data?

    /// Round summaries — stored as JSON Data.
    var playerRoundSummariesData: Data?

    /// Professor announcements — stored as JSON Data.
    var announcementsData: Data?

    /// Enrolled students — stored as JSON Data.
    var enrolledStudentsData: Data?

    /// Grade mappings — stored as JSON Data.
    var gradeMappingsData: Data?

    /// Round deadlines (key = round number, value = deadline date) — stored as JSON Data.
    var roundDeadlinesData: Data?

    /// Whether the session is paused.
    var isPaused: Bool

    /// Timestamp when this session was created.
    var createdAt: Date

    /// Timestamp of last sync with backend (nil if never synced).
    var lastSyncedAt: Date?

    // MARK: - Computed Property Wrappers (backward-compatible API)

    /// Session lifecycle state.
    var state: SessionState {
        get { SessionState(rawValue: stateRaw) ?? .waitingForPlayers }
        set { stateRaw = newValue.rawValue }
    }

    /// All teams in the session (player + AI).
    var teams: [TeamStatus] {
        get {
            guard let data = teamsData else { return [] }
            do {
                return try Self.decoder.decode([TeamStatus].self, from: data)
            } catch {
                Self.logger.error("Failed to decode teams: \(UserFriendlyError.message(for: error))")
                return []
            }
        }
        set {
            teamsData = try? Self.encoder.encode(newValue)
        }
    }

    /// Session configuration.
    var config: SessionConfiguration {
        get {
            guard let data = configData else {
                return SessionConfiguration()
            }
            do {
                return try Self.decoder.decode(SessionConfiguration.self, from: data)
            } catch {
                Self.logger.error("Failed to decode config: \(UserFriendlyError.message(for: error))")
                return SessionConfiguration()
            }
        }
        set {
            configData = try? Self.encoder.encode(newValue)
        }
    }

    /// Round results indexed by team ID, then by round number.
    var roundResults: [UUID: [Int: RoundResult]] {
        get {
            guard let data = roundResultsData else { return [:] }
            do {
                let decoded = try Self.decoder.decode([String: [Int: RoundResult]].self, from: data)
                var result: [UUID: [Int: RoundResult]] = [:]
                for (key, value) in decoded {
                    if let uuid = UUID(uuidString: key) {
                        result[uuid] = value
                    }
                }
                return result
            } catch {
                Self.logger.error("Failed to decode roundResults: \(UserFriendlyError.message(for: error))")
                return [:]
            }
        }
        set {
            var encoded: [String: [Int: RoundResult]] = [:]
            for (key, value) in newValue {
                encoded[key.uuidString] = value
            }
            roundResultsData = try? Self.encoder.encode(encoded)
        }
    }

    /// Decisions submitted for the current round, indexed by team ID.
    var currentRoundDecisions: [UUID: PlayerDecision] {
        get {
            guard let data = currentRoundDecisionsData else { return [:] }
            do {
                let decoded = try Self.decoder.decode([String: PlayerDecision].self, from: data)
                var result: [UUID: PlayerDecision] = [:]
                for (key, value) in decoded {
                    if let uuid = UUID(uuidString: key) {
                        result[uuid] = value
                    }
                }
                return result
            } catch {
                Self.logger.error("Failed to decode currentRoundDecisions: \(UserFriendlyError.message(for: error))")
                return [:]
            }
        }
        set {
            var encoded: [String: PlayerDecision] = [:]
            for (key, value) in newValue {
                encoded[key.uuidString] = value
            }
            currentRoundDecisionsData = try? Self.encoder.encode(encoded)
        }
    }

    /// Previous round's decisions (preserved for AI context).
    var previousRoundDecisions: [UUID: PlayerDecision] {
        get {
            guard let data = previousRoundDecisionsData else { return [:] }
            do {
                let decoded = try Self.decoder.decode([String: PlayerDecision].self, from: data)
                var result: [UUID: PlayerDecision] = [:]
                for (key, value) in decoded {
                    if let uuid = UUID(uuidString: key) {
                        result[uuid] = value
                    }
                }
                return result
            } catch {
                Self.logger.error("Failed to decode previousRoundDecisions: \(UserFriendlyError.message(for: error))")
                return [:]
            }
        }
        set {
            var encoded: [String: PlayerDecision] = [:]
            for (key, value) in newValue {
                encoded[key.uuidString] = value
            }
            previousRoundDecisionsData = try? Self.encoder.encode(encoded)
        }
    }

    /// Coaching messages for this session.
    var coachMessages: [CoachMessage] {
        get {
            guard let data = coachMessagesData else { return [] }
            do {
                return try Self.decoder.decode([CoachMessage].self, from: data)
            } catch {
                Self.logger.error("Failed to decode coachMessages: \(UserFriendlyError.message(for: error))")
                return []
            }
        }
        set {
            coachMessagesData = try? Self.encoder.encode(newValue)
        }
    }

    /// Round summaries for the player, ordered by round.
    var playerRoundSummaries: [RoundSummary] {
        get {
            guard let data = playerRoundSummariesData else { return [] }
            do {
                return try Self.decoder.decode([RoundSummary].self, from: data)
            } catch {
                Self.logger.error("Failed to decode playerRoundSummaries: \(UserFriendlyError.message(for: error))")
                return []
            }
        }
        set {
            playerRoundSummariesData = try? Self.encoder.encode(newValue)
        }
    }

    /// Professor announcements for this session.
    var announcements: [Announcement] {
        get {
            guard let data = announcementsData else { return [] }
            do {
                return try Self.decoder.decode([Announcement].self, from: data)
            } catch {
                Self.logger.error("Failed to decode announcements: \(UserFriendlyError.message(for: error))")
                return []
            }
        }
        set {
            announcementsData = try? Self.encoder.encode(newValue)
        }
    }

    /// Enrolled students roster.
    var enrolledStudents: [EnrolledStudent] {
        get {
            guard let data = enrolledStudentsData else { return [] }
            do {
                return try Self.decoder.decode([EnrolledStudent].self, from: data)
            } catch {
                Self.logger.error("Failed to decode enrolledStudents: \(UserFriendlyError.message(for: error))")
                return []
            }
        }
        set {
            enrolledStudentsData = try? Self.encoder.encode(newValue)
        }
    }

    /// Grade mapping configuration.
    var gradeMappings: [GradeMapping] {
        get {
            guard let data = gradeMappingsData else { return GradeMapping.defaultScale }
            do {
                return try Self.decoder.decode([GradeMapping].self, from: data)
            } catch {
                Self.logger.error("Failed to decode gradeMappings: \(UserFriendlyError.message(for: error))")
                return GradeMapping.defaultScale
            }
        }
        set {
            gradeMappingsData = try? Self.encoder.encode(newValue)
        }
    }

    /// Round deadlines (for timed mode). Key = round number, value = deadline date.
    var roundDeadlines: [Int: Date] {
        get {
            guard let data = roundDeadlinesData else { return [:] }
            do {
                return try Self.decoder.decode([Int: Date].self, from: data)
            } catch {
                Self.logger.error("Failed to decode roundDeadlines: \(UserFriendlyError.message(for: error))")
                return [:]
            }
        }
        set {
            roundDeadlinesData = try? Self.encoder.encode(newValue)
        }
    }

    /// Backward-compatible alias: `sessionCode` maps to `code`.
    var sessionCode: String {
        get { code }
        set { code = newValue }
    }

    // MARK: - Derived Computed Properties (unchanged)

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

    /// Unassigned active students.
    var unassignedStudents: [EnrolledStudent] {
        enrolledStudents.filter { $0.teamId == nil && $0.isActive }
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

    // MARK: - Convenience Accessors (unchanged)

    var totalRounds: Int { config.totalRounds }
    var startingCash: Double { config.startingCash }
    var scoringMetric: ScoringMetric { config.scoringMetric }

    // MARK: - Initialization

    init(config: SessionConfiguration) {
        self.id = UUID()
        self.code = SimulationSession.generateSessionCode()
        self.currentRound = 0
        self.stateRaw = SessionState.waitingForPlayers.rawValue
        self.isPaused = false
        self.createdAt = Date()
        self.lastSyncedAt = nil

        // Encode config
        self.configData = try? Self.encoder.encode(config)

        // Create human teams based on maxHumanTeams config.
        var teamList: [TeamStatus] = []
        let humanTeamNames = Self.humanTeamNames.prefix(config.maxHumanTeams)
        for (_, teamName) in humanTeamNames.enumerated() {
            let player = TeamStatus(
                name: config.maxHumanTeams == 1 ? config.name : teamName,
                cash: config.startingCash,
                isAI: false,
                equity: config.initialEquity,
                sharesOutstanding: config.sharesOutstanding
            )
            teamList.append(player)
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
            teamList.append(aiTeam)
        }

        self.teamsData = try? Self.encoder.encode(teamList)
        self.gradeMappingsData = try? Self.encoder.encode(GradeMapping.defaultScale)

        // Initialize remaining data properties as empty
        self.roundResultsData = nil
        self.currentRoundDecisionsData = nil
        self.previousRoundDecisionsData = nil
        self.coachMessagesData = nil
        self.playerRoundSummariesData = nil
        self.announcementsData = nil
        self.enrolledStudentsData = nil
        self.roundDeadlinesData = nil
    }

    /// Create a SimulationSession with a specific backend-provided code (fixes backend sync wrong-code bug).
    init(code: String, config: SessionConfiguration) {
        self.id = UUID()
        self.code = code
        self.currentRound = 0
        self.stateRaw = SessionState.waitingForPlayers.rawValue
        self.isPaused = false
        self.createdAt = Date()
        self.lastSyncedAt = nil
        self.configData = try? Self.encoder.encode(config)
        var teamList: [TeamStatus] = []
        let humanTeamNames = Self.humanTeamNames.prefix(config.maxHumanTeams)
        for (_, teamName) in humanTeamNames.enumerated() {
            let player = TeamStatus(
                name: config.maxHumanTeams == 1 ? config.name : teamName,
                cash: config.startingCash,
                isAI: false
            )
            teamList.append(player)
        }
        for i in 0..<config.numberOfAICompetitors {
            let ai = TeamStatus(
                name: "Competitor \(i+1)",
                cash: config.startingCash,
                isAI: true
            )
            teamList.append(ai)
        }
        self.teamsData = try? Self.encoder.encode(teamList)
    }


    /// SwiftData required init for fetching from store.
    required init() {
        self.id = UUID()
        self.code = ""
        self.currentRound = 0
        self.stateRaw = SessionState.waitingForPlayers.rawValue
        self.isPaused = false
        self.createdAt = Date()
        self.lastSyncedAt = nil
        self.teamsData = nil
        self.roundResultsData = nil
        self.currentRoundDecisionsData = nil
        self.previousRoundDecisionsData = nil
        self.configData = nil
        self.coachMessagesData = nil
        self.playerRoundSummariesData = nil
        self.announcementsData = nil
        self.enrolledStudentsData = nil
        self.gradeMappingsData = nil
        self.roundDeadlinesData = nil
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
            // Cap currentRound to totalRounds so UI never shows "Round 9 of 8"
            currentRound = config.totalRounds
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

    /// Load announcements from backend and convert to local model.
    func loadAnnouncements(from backendAnnouncements: [AnnouncementBackend]) {
        announcements = backendAnnouncements.map { ba in
            Announcement(message: ba.message, roundNumber: ba.roundNumber)
        }
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

    // MARK: - Result Lookup (unchanged)

    func roundResult(for teamId: UUID, round: Int) -> RoundResult? {
        roundResults[teamId]?[round]
    }

    // MARK: - Restore Results from Backend

    /// Populate roundResults, team financial state, and rankings from backend results.
    /// Direct field mapping — no fabrication or heuristics.
    func restoreResultsFromBackend(_ backendResults: [Int: [RoundResultBackend]]) {
        NSLog("[BizSimAI] restoreResultsFromBackend: received \(backendResults.count) rounds")

        // Build a map from team name (backend key) to team UUID
        var nameToUUID: [String: UUID] = [:]
        for team in teams {
            nameToUUID[team.name] = team.id
        }

        // Process each round's results
        for (round, resultArray) in backendResults.sorted(by: { $0.key < $1.key }) {

            for backendResult in resultArray {
                // Find team by name (backend uses team name as ID)
                guard let teamUUID = nameToUUID[backendResult.teamId] else {
                    NSLog("[BizSimAI] restoreResultsFromBackend: team '\(backendResult.teamId)' not found in local teams")
                    continue
                }

                // Build InvestorScorecard from backend fields
                let scorecard = InvestorScorecard(
                    round: round,
                    eps: backendResult.eps,
                    roe: backendResult.roe,
                    stockPrice: backendResult.stockPrice,
                    imageRating: backendResult.imageRating,
                    creditRating: CreditRating.fromBackendString(backendResult.creditRating),
                    epsScore: backendResult.epsScore,
                    roeScore: backendResult.roeScore,
                    stockPriceScore: backendResult.stockPriceScore,
                    imageScore: backendResult.imageScore,
                    creditScore: backendResult.creditScore
                )

                // Build RoundResult with direct field mapping — no fabrication
                let result = RoundResult(
                    teamId: teamUUID,
                    round: round,
                    wholesaleRevenue: backendResult.wholesaleRevenue,
                    internetRevenue: backendResult.internetRevenue,
                    amazonRevenue: backendResult.amazonRevenue,
                    privateLabelRevenue: backendResult.privateLabelRevenue,
                    productionCosts: backendResult.productionCost,
                    marketingCosts: backendResult.marketingCost,
                    csrCosts: backendResult.csrCosts,
                    endorsementCosts: backendResult.endorsementCosts,
                    interestExpense: backendResult.interestExpense,
                    dividendsPaid: backendResult.dividendsPaid,
                    workforceCosts: backendResult.workforceCosts,
                    storageCosts: backendResult.storageCosts,
                    rebateCosts: backendResult.rebateCosts,
                    deliveryCosts: backendResult.deliveryCosts,
                    socialMediaCosts: backendResult.socialMediaCosts,
                    amazonFees: backendResult.amazonFees,
                    wholesaleUnitsSold: backendResult.wholesaleUnitsSold,
                    internetUnitsSold: backendResult.internetUnitsSold,
                    amazonUnitsSold: backendResult.amazonUnitsSold,
                    privateLabelUnitsSold: backendResult.privateLabelUnitsSold,
                    marketShare: backendResult.marketShare,
                    customerSatisfaction: backendResult.customerSatisfaction,
                    inventory: Int(backendResult.inventory),
                    rejectionRate: backendResult.rejectionRate,
                    cash: backendResult.cash,
                    sqRating: backendResult.sqRating,
                    awarenessScore: backendResult.awarenessScore,
                    scorecard: scorecard,
                    overrideProfit: backendResult.profit
                )

                // Record the result (updates team financial state)
                recordResult(result)

                // Restore TeamStatus fields that recordResult doesn't touch
                if let index = teams.firstIndex(where: { $0.id == teamUUID }) {
                    teams[index].equity = backendResult.equity
                    teams[index].totalDebt = backendResult.debt
                    teams[index].sharesOutstanding = Int(backendResult.sharesOutstanding)
                    teams[index].reputation = backendResult.reputation
                    teams[index].imageRating = backendResult.imageRating
                    teams[index].creditRating = CreditRating.fromBackendString(backendResult.creditRating)
                }
            }
        }

        // Update rankings after all results are restored
        updateRankings()

        // Advance the local round counter to match the backend and reset
        // the submission flag so the student can make decisions for the new round.
        if let maxRound = backendResults.keys.max() {
            currentRound = maxRound + 1
        }
        if let playerIdx = teams.firstIndex(where: { !$0.isAI }) {
            teams[playerIdx].hasSubmittedDecisions = false
        }

        NSLog("[BizSimAI] restoreResultsFromBackend: DONE — \(roundResults.count) teams with results, currentRound=\(currentRound)")
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

    // MARK: - Snapshot / Apply (for background-thread simulation)

    /// Bulk-copy all data the engine needs into a plain Sendable struct.
    /// Call this ONCE on the main thread before dispatching to background.
    /// This avoids 30+ individual JSON decode cycles during computation.
    func takeSnapshot() -> SimulationSnapshot {
        NSLog("[BizSimAI] takeSnapshot: reading config...")
        let snapConfig = config
        NSLog("[BizSimAI] takeSnapshot: reading currentRound...")
        let snapRound = currentRound
        NSLog("[BizSimAI] takeSnapshot: reading teams...")
        let snapTeams = teams
        NSLog("[BizSimAI] takeSnapshot: reading decisions...")
        let snapDecisions = currentRoundDecisions
        NSLog("[BizSimAI] takeSnapshot: reading prevDecisions...")
        let snapPrevDecisions = previousRoundDecisions
        NSLog("[BizSimAI] takeSnapshot: reading roundResults...")
        let snapRoundResults = roundResults
        NSLog("[BizSimAI] takeSnapshot: building struct...")
        let snapshot = SimulationSnapshot(
            config: snapConfig,
            currentRound: snapRound,
            teams: snapTeams,
            decisions: snapDecisions,
            previousRoundDecisions: snapPrevDecisions,
            roundResults: snapRoundResults
        )
        NSLog("[BizSimAI] takeSnapshot: DONE")
        return snapshot
    }

    /// Apply simulation results back to the @Model session.
    /// Call this ONCE on the main thread after background computation.
    /// Performs a single bulk encode per property (not 30+ decode/encode cycles).
    func applyRoundOutput(_ output: RoundOutput) {
        // Record results (updates team financial state)
        for result in output.results {
            recordResult(result)
        }

        // Apply team updates (single decode-modify-encode of teams array)
        var updatedTeams = teams
        for update in output.teamUpdates {
            if let index = updatedTeams.firstIndex(where: { $0.id == update.teamId }) {
                updatedTeams[index].cash = update.cash
                updatedTeams[index].inventory = update.inventory
                updatedTeams[index].sqRating = update.sqRating
                updatedTeams[index].imageRating = update.imageRating
                updatedTeams[index].creditRating = update.creditRating
                updatedTeams[index].reputation = update.reputation
                updatedTeams[index].equity = update.equity
                updatedTeams[index].totalDebt = update.totalDebt
                updatedTeams[index].sharesOutstanding = update.sharesOutstanding
                updatedTeams[index].cumulativeRD = update.cumulativeRD
                updatedTeams[index].cumulativeMarketing = update.cumulativeMarketing
                updatedTeams[index].cumulativeCSR = update.cumulativeCSR
                updatedTeams[index].cumulativeTQM = update.cumulativeTQM
                updatedTeams[index].cumulativeProfit = update.cumulativeProfit
                updatedTeams[index].cumulativeInvestorScore = update.cumulativeInvestorScore
                updatedTeams[index].roundsScored = update.roundsScored
                updatedTeams[index].rank = update.rank
            }
        }
        teams = updatedTeams  // single encode

        // Update rankings
        updateRankings()
    }
}
