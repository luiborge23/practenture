// ProductDecisionTests.swift
// Practenture Tests
// Unit tests for ProductDecision data model

import XCTest
@testable import Practenture

final class ProductDecisionTests: XCTestCase {

    func testDefaultProductDecision() {
        let product = ProductDecision()
        XCTAssertEqual(product.materialsQuality, .standard)
        XCTAssertEqual(product.stylingBudget, 3_000)
        XCTAssertEqual(product.modelsOffered, 3)
        XCTAssertEqual(product.tqmInvestment, 2_000)
    }

    func testCustomProductDecision() {
        let product = ProductDecision(
            materialsQuality: .premium,
            stylingBudget: 5_000,
            modelsOffered: 5,
            tqmInvestment: 4_000
        )
        XCTAssertEqual(product.materialsQuality, .premium)
        XCTAssertEqual(product.stylingBudget, 5_000)
        XCTAssertEqual(product.modelsOffered, 5)
        XCTAssertEqual(product.tqmInvestment, 4_000)
    }

    func testValidProductDecision() {
        let product = ProductDecision(
            stylingBudget: 3_000,
            modelsOffered: 3,
            tqmInvestment: 2_000
        )
        XCTAssertTrue(product.isValid)
    }

    func testNegativeStylingBudgetInvalid() {
        let product = ProductDecision(stylingBudget: -100)
        XCTAssertFalse(product.isValid)
        XCTAssertTrue(product.validationErrors.contains { $0.lowercased().contains("styling") })
    }

    func testZeroModelsOfferedInvalid() {
        let product = ProductDecision(modelsOffered: 0)
        XCTAssertFalse(product.isValid)
        XCTAssertTrue(product.validationErrors.contains { $0.lowercased().contains("at least 1 model") || $0.lowercased().contains("must offer") })
    }

    func testNegativeTQMInvalid() {
        let product = ProductDecision(tqmInvestment: -500)
        XCTAssertFalse(product.isValid)
        XCTAssertTrue(product.validationErrors.contains { $0.lowercased().contains("tqm") || $0.lowercased().contains("TQM") })
    }

    func testZeroValuesValid() {
        let product = ProductDecision(stylingBudget: 0, modelsOffered: 1, tqmInvestment: 0)
        XCTAssertTrue(product.isValid)
    }

    func testProductCodable() throws {
        let product = ProductDecision(materialsQuality: .premium, stylingBudget: 4_500, modelsOffered: 4)
        let encoder = JSONEncoder()
        let data = try encoder.encode(product)
        let decoder = JSONDecoder()
        let decoded = try decoder.decode(ProductDecision.self, from: data)
        XCTAssertEqual(decoded.materialsQuality, .premium)
    }

    func testProductHasUUID() {
        let product = ProductDecision()
        XCTAssertNotNil(product.id as UUID?)
    }
}
