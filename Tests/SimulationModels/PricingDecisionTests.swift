// PricingDecisionTests.swift
// BizSimAI Tests
// Unit tests for PricingDecision data model

import XCTest
@testable import BizSimAI

final class PricingDecisionTests: XCTestCase {

    // MARK: - Default Initialization

    func testDefaultPricingDecision() {
        let pricing = PricingDecision()
        XCTAssertEqual(pricing.wholesalePrice, 80)
        XCTAssertEqual(pricing.internetPrice, 90)
        XCTAssertEqual(pricing.privateLabelBidPrice, 45)
        XCTAssertEqual(pricing.privateLabelMaxUnits, 50)
        XCTAssertEqual(pricing.amazonPrice, 85)
        XCTAssertEqual(pricing.amazonAdBudget, 0)
    }

    func testCustomPricingDecision() {
        let pricing = PricingDecision(
            wholesalePrice: 100,
            internetPrice: 120,
            privateLabelBidPrice: 60,
            privateLabelMaxUnits: 100,
            amazonPrice: 95,
            amazonAdBudget: 500
        )
        XCTAssertEqual(pricing.wholesalePrice, 100)
        XCTAssertEqual(pricing.internetPrice, 120)
        XCTAssertEqual(pricing.privateLabelBidPrice, 60)
        XCTAssertEqual(pricing.privateLabelMaxUnits, 100)
        XCTAssertEqual(pricing.amazonPrice, 95)
        XCTAssertEqual(pricing.amazonAdBudget, 500)
    }

    // MARK: - Validation

    func testValidPricingDecision() {
        let pricing = PricingDecision(
            wholesalePrice: 80,
            internetPrice: 90,
            privateLabelBidPrice: 45,
            amazonPrice: 85
        )
        XCTAssertTrue(pricing.isValid)
    }

    func testNegativeWholesalePriceInvalid() {
        let pricing = PricingDecision(wholesalePrice: -10)
        XCTAssertFalse(pricing.isValid)
        XCTAssertEqual(pricing.validationErrors.count, 1)
        XCTAssertTrue(pricing.validationErrors[0].contains("Wholesale"))
    }

    func testNegativeInternetPriceInvalid() {
        let pricing = PricingDecision(internetPrice: -5)
        XCTAssertFalse(pricing.isValid)
        XCTAssertTrue(pricing.validationErrors.contains { $0.contains("Internet") })
    }

    func testNegativePrivateLabelBidInvalid() {
        let pricing = PricingDecision(privateLabelBidPrice: -1)
        XCTAssertFalse(pricing.isValid)
        XCTAssertTrue(pricing.validationErrors.contains { $0.contains("private label bid") || $0.contains("Private label bid") })
    }

    func testNegativeAmazonPriceInvalid() {
        let pricing = PricingDecision(amazonPrice: -50)
        XCTAssertFalse(pricing.isValid)
        XCTAssertTrue(pricing.validationErrors.contains { $0.contains("Amazon price") })
    }

    func testNegativePrivateLabelMaxUnitsInvalid() {
        let pricing = PricingDecision(privateLabelMaxUnits: -10)
        XCTAssertFalse(pricing.isValid)
        XCTAssertTrue(pricing.validationErrors.contains { $0.contains("max units") || $0.contains("Max units") })
    }

    func testAllNegativeValuesInvalid() {
        let pricing = PricingDecision(
            wholesalePrice: -1,
            internetPrice: -2,
            privateLabelBidPrice: -3,
            amazonPrice: -4,
            privateLabelMaxUnits: -5
        )
        XCTAssertFalse(pricing.isValid)
        XCTAssertEqual(pricing.validationErrors.count, 5)
    }

    func testZeroValuesValid() {
        let pricing = PricingDecision(
            wholesalePrice: 0,
            internetPrice: 0,
            privateLabelBidPrice: 0,
            amazonPrice: 0,
            privateLabelMaxUnits: 0
        )
        XCTAssertTrue(pricing.isValid)
    }

    // MARK: - Codable

    func testPricingDecisionCodable() throws {
        let pricing = PricingDecision(wholesalePrice: 75, internetPrice: 85, amazonAdBudget: 300)
        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(pricing)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(PricingDecision.self, from: data)
        XCTAssertEqual(decoded.wholesalePrice, pricing.wholesalePrice)
        XCTAssertEqual(decoded.internetPrice, pricing.internetPrice)
        XCTAssertEqual(decoded.amazonAdBudget, pricing.amazonAdBudget)
    }

    // MARK: - ID Property

    func testPricingDecisionHasUUID() {
        let pricing = PricingDecision()
        XCTAssertNotNil(pricing.id as UUID?)
    }
}
