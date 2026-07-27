// SessionStateTests.swift
// Practenture Tests
// Unit tests for enum types used in the simulation models

import XCTest
@testable import Practenture

final class EnumTests: XCTestCase {

    // MARK: - SessionState

    func testSessionStatesHaveDisplayNames() {
        XCTAssertEqual(SessionState.waitingForPlayers.displayName, "Waiting")
        XCTAssertEqual(SessionState.inProgress.displayName, "In Progress")
        XCTAssertEqual(SessionState.roundProcessing.displayName, "Processing")
        XCTAssertEqual(SessionState.completed.displayName, "Completed")
    }

    func testAllSessionStatesIterable() {
        let states = SessionState.allCases
        XCTAssertEqual(states.count, 4)
    }

    // MARK: - MarketType

    func testMarketTypesExist() {
        XCTAssertTrue(MarketType.allCases.contains(.moderate))
        XCTAssertTrue(MarketType.allCases.contains(.aggressive))
        XCTAssertTrue(MarketType.allCases.contains(.saturated))
    }

    // MARK: - AIDifficulty

    func testAIDifficultiesExist() {
        XCTAssertEqual(AIDifficulty.allCases.count, 3)
    }

    // MARK: - ScoringMetric

    func testScoringMetricsExist() {
        let metrics = ScoringMetric.allCases
        XCTAssertTrue(metrics.contains(.investorScore))
        XCTAssertTrue(metrics.contains(.cumulativeProfit))
        XCTAssertTrue(metrics.contains(.revenue))
        XCTAssertTrue(metrics.contains(.composite))
    }

    // MARK: - CreditRating

    func testCreditRatings() {
        XCTAssertEqual(CreditRating.aaa.rawValue, "AAA")
        XCTAssertEqual(CreditRating.bbb.rawValue, "BBB")
        XCTAssertEqual(CreditRating.cc.rawValue, "CC")
    }

    // MARK: - PerformanceMetric

    func testPerformanceMetricsDisplayNames() {
        XCTAssertEqual(PerformanceMetric.profit.displayName, "Profit")
        XCTAssertEqual(PerformanceMetric.revenue.displayName, "Revenue")
        XCTAssertEqual(PerformanceMetric.marketShare.displayName, "Market Share")
        XCTAssertEqual(PerformanceMetric.sqRating.displayName, "S/Q Rating")
    }

    func testPerformanceMetricUnits() {
        XCTAssertEqual(PerformanceMetric.profit.unit, "$")
        XCTAssertEqual(PerformanceMetric.revenue.unit, "$")
        XCTAssertEqual(PerformanceMetric.marketShare.unit, "%")
        XCTAssertEqual(PerformanceMetric.satisfaction.unit, "%")
        XCTAssertEqual(PerformanceMetric.sqRating.unit, "★")
    }

    func testAllPerformanceMetricsIterable() {
        let metrics = PerformanceMetric.allCases
        XCTAssertTrue(metrics.contains(.profit))
        XCTAssertTrue(metrics.contains(.revenue))
        XCTAssertTrue(metrics.contains(.marketShare))
        XCTAssertTrue(metrics.contains(.satisfaction))
        XCTAssertTrue(metrics.contains(.cash))
        XCTAssertTrue(metrics.contains(.sqRating))
    }

    // MARK: - RoundPacingMode

    func testRoundPacingModes() {
        XCTAssertEqual(RoundPacingMode.manual.displayName, "Manual Advance")
        XCTAssertEqual(RoundPacingMode.timed.displayName, "Timed Rounds")
    }

    func testAllRoundingPacesIterable() {
        XCTAssertEqual(RoundPacingMode.allCases.count, 2)
    }

    // MARK: - LateSubmissionPolicy

    func testLateSubmissionDisplayNames() {
        XCTAssertTrue(LateSubmissionPolicy.allowWithPenalty.displayName.contains("Allow"))
        XCTAssertTrue(LateSubmissionPolicy.usePrevious.displayName.contains("Previous"))
        XCTAssertTrue(LateSubmissionPolicy.lockOut.displayName.contains("Lock Out") || LateSubmissionPolicy.lockOut.displayName.contains("lock out"))
    }

    // MARK: - Impact

    func testImpactValues() {
        XCTAssertEqual(Impact.positive.rawValue, "positive")
        XCTAssertEqual(Impact.negative.rawValue, "negative")
        XCTAssertEqual(Impact.neutral.rawValue, "neutral")
    }

    // MARK: - GradeMapping

    func testDefaultGradeScaleHasAllLetters() {
        let scale = GradeMapping.defaultScale
        XCTAssertTrue(scale.contains { $0.label == "A" })
        XCTAssertTrue(scale.contains { $0.label == "B+" })
        XCTAssertTrue(scale.contains { $0.label == "B" })
        XCTAssertTrue(scale.contains { $0.label == "C+" })
        XCTAssertTrue(scale.contains { $0.label == "C" })
        XCTAssertTrue(scale.contains { $0.label == "D" })
        XCTAssertTrue(scale.contains { $0.label == "F" })
    }

    func testGradeScaleHas7Grades() {
        XCTAssertEqual(GradeMapping.defaultScale.count, 7)
    }

    // MARK: - ChartDataPoint

    func testChartDataPointCreation() {
        let point = ChartDataPoint(round: 1, value: 50_000, label: "Profit")
        XCTAssertEqual(point.round, 1)
        XCTAssertEqual(point.value, 50_000)
        XCTAssertNotNil(point.id as UUID?)
    }

    // MARK: - Announcement

    func testAnnouncementCreation() {
        let announcement = Announcement(message: "Test message", roundNumber: 3)
        XCTAssertTrue(!announcement.message.isEmpty)
        XCTAssertEqual(announcement.roundNumber, 3)
    }

    func testGeneralAnnouncementNoRound() {
        let announcement = Announcement(message: "General notice")
        XCTAssertNil(announcement.roundNumber)
    }

    // MARK: - EnrolledStudent

    func testEnrolledStudentDefaults() {
        let student = EnrolledStudent(name: "John Doe", email: "john@test.com")
        XCTAssertEqual(student.name, "John Doe")
        XCTAssertEqual(student.email, "john@test.com")
        XCTAssertNil(student.teamId)
        XCTAssertTrue(student.isActive)
    }

    // MARK: - ResultExplanation

    func testResultExplanationCreation() {
        let explanation = ResultExplanation(metric: "Profit", explanation: "Increased due to higher sales", impact: .positive)
        XCTAssertEqual(explanation.metric, "Profit")
        XCTAssertEqual(impact.toString(), "positive")
    }

    // MARK: - CoachMessage

    func testCoachMessageCreation() {
        let msg = CoachMessage(content: "Tip: Consider lowering your price.", isFromAI: true)
        XCTAssertTrue(msg.isFromAI)
        XCTAssertFalse(CoachMessage(content: "Thanks!", isFromAI: false).isFromAI)
    }

    // MARK: - SessionTemplate

    func testAllTemplatesHaveRounds() {
        for template in SessionTemplate.allCases {
            let config = SessionConfiguration(template: template, name: template.displayName)
            XCTAssertGreaterThan(config.totalRounds, 0)
        }
    }

    func testCustomTemplateExists() {
        XCTAssertTrue(SessionTemplate.allCases.contains(.custom))
        XCTAssertEqual(SessionTemplate.custom.rounds, 10)
    }

    // MARK: - FulfillmentMethod (if exists as enum in codebase)

    func testFulfillmentMethodsExist() {
        let fbm = PlayerDecision(teamId: UUID(), round: 1).fulfillmentMethod
        XCTAssertEqual(fbm, .fbm)
    }

    // MARK: - MaterialsQuality (if exists as enum in codebase)

    func testMaterialsQualityExists() {
        let product = ProductDecision(materialsQuality: .standard)
        XCTAssertEqual(product.materialsQuality, .standard)
    }

    // MARK: - CelebrityEndorsement

    func testCelebrityEndorsementValues() {
        let none = MarketingDecision().celebrityEndorsement
        XCTAssertEqual(none, .none)
    }

    // MARK: - DeliveryTime

    func testDeliveryTimeValues() {
        let standard = MarketingDecision().deliveryTime
        XCTAssertEqual(standard, .standard)
    }

    // MARK: - InfluencerTier

    func testInfluencerTierValues() {
        let none = MarketingDecision().influencerTier
        XCTAssertEqual(none, .none)
    }
}

// Helper extension for Impact comparison
extension Impact {
    var toString: String { rawValue }
}
