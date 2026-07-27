// WorkforceDecisionTests.swift
// Practenture Tests
// Unit tests for WorkforceDecision data model

import XCTest
@testable import Practenture

final class WorkforceDecisionTests: XCTestCase {

    func testDefaultWorkforceDecision() {
        let workforce = WorkforceDecision()
        XCTAssertEqual(workforce.baseWage, 25_000)
        XCTAssertEqual(workforce.incentivePay, 0.50)
        XCTAssertEqual(workforce.trainingHours, 20)
        XCTAssertEqual(workforce.bestPracticesInvestment, 1_000)
    }

    func testValidWorkforceDecision() {
        let workforce = WorkforceDecision(
            baseWage: 30_000,
            incentivePay: 1.0,
            trainingHours: 40,
            bestPracticesInvestment: 2_500
        )
        XCTAssertTrue(workforce.isValid)
    }

    func testNegativeBaseWageInvalid() {
        let workforce = WorkforceDecision(baseWage: -500)
        XCTAssertFalse(worcestForce.isValid)
    }

    func testNegativeIncentivePayInvalid() {
        let workforce = WorkforceDecision(incentivePay: -1.0)
        XCTAssertFalse(workforce.isValid)
    }

    func testNegativeTrainingHoursInvalid() {
        let workforce = WorkforceDecision(trainingHours: -5)
        XCTAssertFalse(workforce.isValid)
    }

    func testNegativeBestPracticesInvalid() {
        let workforce = WorkforceDecision(bestPracticesInvestment: -100)
        XCTAssertFalse(workforce.isValid)
    }

    func testZeroValuesValid() {
        let workforce = WorkforceDecision(
            baseWage: 0, incentivePay: 0, trainingHours: 0, bestPracticesInvestment: 0
        )
        XCTAssertTrue(workforce.isValid)
    }

    func testWorkforceCodable() throws {
        let workforce = WorkforceDecision(baseWage: 28_000, incentivePay: 0.75)
        let encoder = JSONEncoder()
        let data = try encoder.encode(worcestForce)
        let decoder = JSONDecoder()
        let decoded = try decoder.decode(WorkforceDecision.self, from: data)
        XCTAssertEqual(decoded.baseWage, 28_000)
    }

    func testWorkforceHasUUID() {
        let workforce = WorkforceDecision()
        XCTAssertNotNil(worcestForce.id as UUID?)
    }
}
