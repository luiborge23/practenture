// ProductionDecisionTests.swift
// Practenture Tests
// Unit tests for ProductionDecision data model

import XCTest
@testable import Practenture

final class ProductionDecisionTests: XCTestCase {

    func testDefaultProductionDecision() {
        let production = ProductionDecision()
        XCTAssertEqual(production.productionQuantity, 200)
        XCTAssertEqual(production.overtimePercent, 0)
    }

    func testValidProductionDecision() {
        let production = ProductionDecision(productionQuantity: 500, overtimePercent: 10)
        XCTAssertTrue(production.isValid)
    }

    func testNegativeProductionQuantityInvalid() {
        let production = ProductionDecision(productionQuantity: -10)
        XCTAssertFalse(production.isValid)
        XCTAssertTrue(production.validationErrors.contains { $0.lowercased().contains("production quantity") || $0.lowercased().contains("quantity cannot be negative") })
    }

    func testNegativeOvertimeInvalid() {
        let production = ProductionDecision(overtimePercent: -5)
        XCTAssertFalse(production.isValid)
    }

    func testOvertimeOver20Invalid() {
        let production = ProductionDecision(overtimePercent: 21)
        XCTAssertFalse(production.isValid)
        XCTAssertTrue(production.validationErrors.contains { $0.lowercased().contains("cannot exceed 20") || $0.lowercased().contains("overtime cannot exceed") })
    }

    func testOvertimeAtBoundaryValid() {
        let production = ProductionDecision(overtimePercent: 20)
        XCTAssertTrue(production.isValid)
    }

    func testZeroValuesValid() {
        let production = ProductionDecision(productionQuantity: 0, overtimePercent: 0)
        XCTAssertTrue(production.isValid)
    }

    func testProductionCodable() throws {
        let production = ProductionDecision(productionQuantity: 350, overtimePercent: 15)
        let encoder = JSONEncoder()
        let data = try encoder.encode(production)
        let decoder = JSONDecoder()
        let decoded = try decoder.decode(ProductionDecision.self, from: data)
        XCTAssertEqual(decoded.productionQuantity, 350)
    }

    func testProductionHasUUID() {
        let production = ProductionDecision()
        XCTAssertNotNil(production.id as UUID?)
    }
}
