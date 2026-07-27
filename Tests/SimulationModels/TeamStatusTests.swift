// TeamStatusTests.swift
// Practenture Tests
// Unit tests for TeamStatus model

import XCTest
@testable import Practenture

final class TeamStatusTests: XCTestCase {

    func testDefaultTeamStatus() {
        let team = TeamStatus(
            name: "Test Team", cash: 100_000
        )
        XCTAssertEqual(team.name, "Test Team")
        XCTAssertEqual(team.cash, 100_000)
        XCTAssertEqual(team.inventory, 0)
        XCTAssertEqual(team.reputation, 0.5)
        XCTAssertFalse(team.hasSubmittedDecisions)
        XCTAssertFalse(team.isAI)
    }

    func testFullTeamStatus() {
        let team = TeamStatus(
            name: "Alpha", cash: 80_000, inventory: 200, reputation: 0.8,
            equity: 100_000, totalDebt: 50_000, sharesOutstanding: 10_000,
            sqRating: 7.0, imageRating: 75, creditRating: .aa
        )
        XCTAssertEqual(team.name, "Alpha")
        XCTAssertEqual(team.cash, 80_000)
        XCTAssertEqual(team.inventory, 200)
        XCTAssertEqual(team.reputation, 0.8)
        XCTAssertEqual(team.equity, 100_000)
        XCTAssertEqual(team.totalDebt, 50_000)
        XCTAssertEqual(team.sharesOutstanding, 10_000)
        XCTAssertEqual(team.sqRating, 7.0)
        XCTAssertEqual(team.imageRating, 75)
        XCTAssertEqual(team.creditRating, .aa)
    }

    func testAIStatus() {
        let team = TeamStatus(name: "NovaTech", cash: 100_000, isAI: true)
        XCTAssertTrue(team.isAI)
        XCTAssertFalse(team.hasSubmittedDecisions)
    }

    func testTeamCodable() throws {
        let team = TeamStatus(name: "Bravo", cash: 95_000)
        let encoder = JSONEncoder()
        let data = try encoder.encode(team)
        XCTAssertGreaterThan(data.count, 0)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(TeamStatus.self, from: data)
        XCTAssertEqual(decoded.name, "Bravo")
    }

    func testTeamHasUUID() {
        let team = TeamStatus(name: "Charlie", cash: 85_000)
        XCTAssertNotNil(team.id as UUID?)
    }

    func testCumulativeMetricsDefaultToZero() {
        let team = TeamStatus(name: "Delta", cash: 100_000)
        XCTAssertEqual(team.cumulativeRD, 0)
        XCTAssertEqual(team.cumulativeMarketing, 0)
        XCTAssertEqual(team.cumulativeCSR, 0)
        XCTAssertEqual(team.cumulativeTQM, 0)
        XCTAssertEqual(team.cumulativeProfit, 0)
    }

    func testCumulativeInvestorScoreDefault() {
        let team = TeamStatus(name: "Echo", cash: 100_000)
        XCTAssertEqual(team.cumulativeInvestorScore, 0)
        XCTAssertEqual(team.roundsScored, 0)
    }
}
