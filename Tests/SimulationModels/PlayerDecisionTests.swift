// PlayerDecisionTests.swift
// BizSimAI Tests
// Unit tests for PlayerDecision data model (composed of all sub-decisions)

import XCTest
@testable import BizSimAI

final class PlayerDecisionTests: XCTestCase {

    func testDefaultPlayerDecision() {
        let teamId = UUID()
        let decision = PlayerDecision(teamId: teamId, round: 1)
        XCTAssertEqual(decision.teamId, teamId)
        XCTAssertEqual(decision.round, 1)
        XCTAssertTrue(decision.isValid)
    }

    func testCustomPlayerDecision() {
        let teamId = UUID()
        let pricing = PricingDecision(wholesalePrice: 90, internetPrice: 100)
        let product = ProductDecision(materialsQuality: .premium, stylingBudget: 5_000)
        let marketing = MarketingDecision(advertisingBudget: 10_000, retailOutlets: 30)
        let workforce = WorkforceDecision(baseWage: 28_000, trainingHours: 30)
        let production = ProductionDecision(productionQuantity: 400, overtimePercent: 10)
        let finance = FinanceDecision(csrInvestment: 5_000, newLoanAmount: 20_000)

        let decision = PlayerDecision(
            teamId: teamId, round: 3,
            pricing: pricing, product: product, marketing: marketing,
            workforce: workforce, production: production, finance: finance
        )
        XCTAssertEqual(decision.teamId, teamId)
        XCTAssertEqual(decision.round, 3)
    }

    func testValidPlayerDecision() {
        let decision = PlayerDecision(teamId: UUID(), round: 1)
        XCTAssertTrue(decision.isValid)
    }

    func testInvalidPricingMakesPlayerDecisionInvalid() {
        let pricing = PricingDecision(wholesalePrice: -50)
        let decision = PlayerDecision(teamId: UUID(), round: 1, pricing: pricing)
        XCTAssertFalse(decision.isValid)
    }

    func testInvalidProductMakesPlayerDecisionInvalid() {
        let product = ProductDecision(modelsOffered: 0)
        let decision = PlayerDecision(teamId: UUID(), round: 1, product: product)
        XCTAssertFalse(decision.isValid)
    }

    func testInvalidMarketingMakesPlayerDecisionInvalid() {
        let marketing = MarketingDecision(advertisingBudget: -1000)
        let decision = PlayerDecision(teamId: UUID(), round: 1, marketing: marketing)
        XCTAssertFalse(decision.isValid)
    }

    func testInvalidWorkforceMakesPlayerDecisionInvalid() {
        let workforce = WorkforceDecision(baseWage: -500)
        let decision = PlayerDecision(teamId: UUID(), round: 1, workforce: workforce)
        XCTAssertFalse(decision.isValid)
    }

    func testInvalidProductionMakesPlayerDecisionInvalid() {
        let production = ProductionDecision(overtimePercent: 25)
        let decision = PlayerDecision(teamId: UUID(), round: 1, production: production)
        XCTAssertFalse(decision.isValid)
    }

    func testInvalidFinanceMakesPlayerDecisionInvalid() {
        let finance = FinanceDecision(dividendsPerShare: -1.0)
        let decision = PlayerDecision(teamId: UUID(), round: 1, finance: finance)
        XCTAssertFalse(decision.isValid)
    }

    // MARK: - Legacy Convenience Accessors

    func testLegacyPriceAccessor() {
        let pricing = PricingDecision(wholesalePrice: 85)
        let decision = PlayerDecision(teamId: UUID(), round: 1, pricing: pricing)
        XCTAssertEqual(decision.wholesalePrice, 85)
    }

    func testLegacyInternetPriceAccessor() {
        let pricing = PricingDecision(internetPrice: 95)
        let decision = PlayerDecision(teamId: UUID(), round: 1, pricing: pricing)
        XCTAssertEqual(decision.internetPrice, 95)
    }

    func testLegacyMarketingBudgetAccessor() {
        let marketing = MarketingDecision(advertisingBudget: 7_500)
        let decision = PlayerDecision(teamId: UUID(), round: 1, marketing: marketing)
        XCTAssertEqual(decision.marketingBudget, 7_500)
    }

    func testLegacyRDInvestmentAccessor() {
        let product = ProductDecision(stylingBudget: 3_000, tqmInvestment: 2_000)
        let decision = PlayerDecision(teamId: UUID(), round: 1, product: product)
        XCTAssertEqual(decision.rdInvestment, 5_000)
    }

    func testLegacySocialMediaBudgetAccessor() {
        let marketing = MarketingDecision(tiktokBudget: 400, instagramBudget: 300, youtubeBudget: 200)
        let decision = PlayerDecision(teamId: UUID(), round: 1, marketing: marketing)
        XCTAssertEqual(decision.socialMediaBudget, 900)
    }

    // MARK: - Validation Errors Aggregation

    func testValidationErrorsAggregatesAllSubModels() {
        var pricing = PricingDecision(wholesalePrice: -10)
        var product = ProductDecision(modelsOffered: 0)
        let marketing = MarketingDecision(advertisingBudget: 5_000)
        let workforce = WorkforceDecision()
        let production = ProductionDecision()
        let finance = FinanceDecision()

        let decision = PlayerDecision(
            teamId: UUID(), round: 1,
            pricing: pricing, product: product, marketing: marketing,
            workforce: workforce, production: production, finance: finance
        )
        XCTAssertFalse(decision.isValid)
        XCTAssertEqual(decision.validationErrors.count, 2) // wholesale negative + modelsOffered zero
    }

    // MARK: - Codable

    func testPlayerDecisionCodable() throws {
        let decision = PlayerDecision(teamId: UUID(), round: 1)
        let encoder = JSONEncoder()
        encoder.outputFormatting = .sortedKeys
        let data = try encoder.encode(decision)

        XCTAssertGreaterThan(data.count, 0) // Ensure data was produced

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(PlayerDecision.self, from: data)
        XCTAssertEqual(decoded.teamId, decision.teamId)
        XCTAssertEqual(decoded.round, decision.round)
    }

    // MARK: - Fulfillment Method

    func testDefaultFulfillmentMethodIsFBM() {
        let decision = PlayerDecision(teamId: UUID(), round: 1)
        XCTAssertEqual(decision.fulfillmentMethod, .fbm)
    }

    func testCustomFulfillmentMethod() throws {
        let decision = PlayerDecision(
            teamId: UUID(), round: 1, fulfillmentMethod: .fba
        )
        XCTAssertEqual(decision.fulfillmentMethod, .fba)
    }
}
