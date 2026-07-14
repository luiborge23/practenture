// RoundResultTests.swift
// BizSimAI Tests
// Unit tests for RoundResult and related models

import XCTest
@testable import BizSimAI

final class RoundResultTests: XCTestCase {

    func makeScorecard(round: Int) -> InvestorScorecard {
        return InvestorScorecard(
            round: round, eps: 2.5, roe: 15.0, stockPrice: 45.0,
            imageRating: 65, creditRating: .a,
            epsScore: 18, roeScore: 17, stockPriceScore: 16,
            imageScore: 14, creditScore: 19
        )
    }

    func makeRoundResult() -> RoundResult {
        let scorecard = makeScorecard(round: 1)
        return RoundResult(
            teamId: UUID(), round: 1,
            wholesaleRevenue: 50_000, internetRevenue: 30_000, amazonRevenue: 10_000, privateLabelRevenue: 5_000,
            productionCosts: 20_000, marketingCosts: 8_000, csrCosts: 2_000, endorsementCosts: 3_000,
            interestExpense: 1_500, dividendsPaid: 500, workforceCosts: 15_000, storageCosts: 500,
            rebateCosts: 200, deliveryCosts: 300, socialMediaCosts: 1_000, amazonFees: 800,
            wholesaleUnitsSold: 500, internetUnitsSold: 300, amazonUnitsSold: 100, privateLabelUnitsSold: 50,
            marketShare: 0.25, customerSatisfaction: 72, inventory: 150, rejectionRate: 0.02, cash: 85_000, sqRating: 6.5, awarenessScore: 0.6, scorecard: scorecard
        )
    }

    func testRevenueCalculation() {
        let result = makeRoundResult()
        XCTAssertEqual(result.revenue, 95_000) // 50k + 30k + 10k + 5k
    }

    func testCostsCalculation() {
        let result = makeRoundResult()
        let expectedCosts: Double = 20_000 + 8_000 + 2_000 + 3_000 + 1_500 + 500 + 15_000 + 500 + 200 + 300 + 1_000 + 800
        XCTAssertEqual(result.costs, expectedCosts)
    }

    func testProfitCalculation() {
        let result = makeRoundResult()
        // revenue 95k - costs (sum above)
        let expectedCosts: Double = 20_000 + 8_000 + 2_000 + 3_000 + 1_500 + 500 + 15_000 + 500 + 200 + 300 + 1_000 + 800
        XCTAssertEqual(result.profit, result.revenue - expectedCosts)
    }

    func testUnitsSoldCalculation() {
        let result = makeRoundResult()
        XCTAssertEqual(result.unitsSold, 950) // 500+300+100+50
    }

    func testSQRatingAndQualityScore() {
        let scorecard = makeScorecard(round: 1)
        let result = RoundResult(
            teamId: UUID(), round: 1, wholesaleRevenue: 10_000, internetRevenue: 5_000, amazonRevenue: 2_000, privateLabelRevenue: 1_000,
            productionCosts: 5_000, marketingCosts: 1_000, csrCosts: 500, endorsementCosts: 800, interestExpense: 300, dividendsPaid: 200,
            workforceCosts: 3_000, storageCosts: 0, rebateCosts: 0, deliveryCosts: 0, socialMediaCosts: 500, amazonFees: 400,
            wholesaleUnitsSold: 100, internetUnitsSold: 50, amazonUnitsSold: 20, privateLabelUnitsSold: 10,
            marketShare: 0.15, customerSatisfaction: 68, inventory: 30, rejectionRate: 0.01, cash: 90_000, sqRating: 7.0, awarenessScore: 0.7, scorecard: scorecard
        )
        XCTAssertEqual(result.sqRating, 7.0)
        XCTAssertEqual(result.qualityScore, 0.7) // sqRating / 10
    }

    func testInvestorScorecardTotal() {
        let scorecard = makeScorecard(round: 1)
        // eps(18) + roe(17) + stockPrice(16) + image(14) + credit(19) = 84
        XCTAssertEqual(scorecard.totalScore, 84)
    }

    func testRoundResultCodable() throws {
        let result = makeRoundResult()
        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(result)
        XCTAssertGreaterThan(data.count, 0)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(RoundResult.self, from: data)
        XCTAssertEqual(decoded.teamId, result.teamId)
        XCTAssertEqual(decoded.round, result.round)
    }

    func testRoundHasUUID() {
        let scorecard = makeScorecard(round: 1)
        let result = RoundResult(
            teamId: UUID(), round: 1, wholesaleRevenue: 0, internetRevenue: 0, amazonRevenue: 0, privateLabelRevenue: 0,
            productionCosts: 0, marketingCosts: 0, csrCosts: 0, endorsementCosts: 0, interestExpense: 0, dividendsPaid: 0,
            workforceCosts: 0, storageCosts: 0, rebateCosts: 0, deliveryCosts: 0, socialMediaCosts: 0, amazonFees: 0,
            wholesaleUnitsSold: 0, internetUnitsSold: 0, amazonUnitsSold: 0, privateLabelUnitsSold: 0,
            marketShare: 0, customerSatisfaction: 50, inventory: 0, rejectionRate: 0, cash: 100_000, sqRating: 5.0, awarenessScore: 0.5, scorecard: scorecard
        )
        XCTAssertNotNil(result.id as UUID?)
    }

    func testZeroValuesRevenueCalculation() {
        let scorecard = makeScorecard(round: 1)
        let result = RoundResult(
            teamId: UUID(), round: 2, wholesaleRevenue: 0, internetRevenue: 0, amazonRevenue: 0, privateLabelRevenue: 0,
            productionCosts: 5_000, marketingCosts: 1_000, csrCosts: 0, endorsementCosts: 0, interestExpense: 0, dividendsPaid: 0,
            workforceCosts: 3_000, storageCosts: 0, rebateCosts: 0, deliveryCosts: 0, socialMediaCosts: 0, amazonFees: 0,
            wholesaleUnitsSold: 0, internetUnitsSold: 0, amazonUnitsSold: 0, privateLabelUnitsSold: 0,
            marketShare: 0, customerSatisfaction: 40, inventory: 0, rejectionRate: 0, cash: 50_000, sqRating: 3.0, awarenessScore: 0.2, scorecard: scorecard
        )
        XCTAssertEqual(result.revenue, 0)
    }
}
