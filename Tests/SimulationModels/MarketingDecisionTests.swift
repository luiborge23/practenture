// MarketingDecisionTests.swift
// Practenture Tests
// Unit tests for MarketingDecision data model

import XCTest
@testable import Practenture

final class MarketingDecisionTests: XCTestCase {

    func testDefaultMarketingDecision() {
        let marketing = MarketingDecision()
        XCTAssertEqual(marketing.advertisingBudget, 8_000)
        XCTAssertEqual(marketing.celebrityEndorsement, .none)
        XCTAssertEqual(marketing.retailOutlets, 20)
        XCTAssertEqual(marketing.mailInRebate, 0)
        XCTAssertEqual(marketing.deliveryTime, .standard)
        XCTAssertEqual(marketing.freeShippingThreshold, 100)
    }

    func testValidMarketingDecision() {
        let marketing = MarketingDecision(
            advertisingBudget: 5_000,
            retailOutlets: 15,
            freeShippingThreshold: 75
        )
        XCTAssertTrue(marketing.isValid)
    }

    func testNegativeAdvertisingInvalid() {
        let marketing = MarketingDecision(advertisingBudget: -100)
        XCTAssertFalse(marketing.isValid)
        XCTAssertTrue(marketing.validationErrors.contains { $0.lowercased().contains("advertis") })
    }

    func testNegativeRetailOutletsInvalid() {
        let marketing = MarketingDecision(retailOutlets: -5)
        XCTAssertFalse(marketing.isValid)
        XCTAssertTrue(marketing.validationErrors.contains { $0.lowercased().contains("retail outlet") })
    }

    func testNegativeMailInRebateInvalid() {
        let marketing = MarketingDecision(mailInRebate: -10)
        XCTAssertFalse(marketing.isValid)
        XCTAssertTrue(marketing.validationErrors.contains { $0.lowercased().contains("rebate") })
    }

    func testNegativeFreeShippingThresholdInvalid() {
        let marketing = MarketingDecision(freeShippingThreshold: -5)
        XCTAssertFalse(marketing.isValid)
        XCTAssertTrue(marketing.validationErrors.contains { $0.lowercased().contains("free shipping") || $0.lowercased().contains("shipping threshold") })
    }

    func testNegativeSocialMediaBudgetsInvalid() {
        let marketing = MarketingDecision(
            tiktokBudget: -100,
            instagramBudget: 0,
            youtubeBudget: 0
        )
        XCTAssertFalse(marketing.isValid)
    }

    func testTotalSocialMediaBudget() {
        let marketing = MarketingDecision(tiktokBudget: 500, instagramBudget: 300, youtubeBudget: 200)
        XCTAssertEqual(marketing.totalSocialMediaBudget, 1_000)
    }

    func testZeroValuesValid() {
        let marketing = MarketingDecision(
            advertisingBudget: 0,
            retailOutlets: 0,
            mailInRebate: 0,
            freeShippingThreshold: 0,
            tiktokBudget: 0,
            instagramBudget: 0,
            youtubeBudget: 0
        )
        XCTAssertTrue(marketing.isValid)
    }

    func testMarketingCodable() throws {
        let marketing = MarketingDecision(advertisingBudget: 6_000, retailOutlets: 25)
        let encoder = JSONEncoder()
        let data = try encoder.encode(marketing)
        let decoder = JSONDecoder()
        let decoded = try decoder.decode(MarketingDecision.self, from: data)
        XCTAssertEqual(decoded.advertisingBudget, 6_000)
    }

    func testMarketingHasUUID() {
        let marketing = MarketingDecision()
        XCTAssertNotNil(marketing.id as UUID?)
    }
}
