// SessionConfigurationTests.swift
// Practenture Tests
// Unit tests for SessionConfiguration and templates

import XCTest
@testable import Practenture

final class SessionConfigurationTests: XCTestCase {

    func testDefaultConfig() {
        let config = SessionConfiguration(
            name: "Test Sim", totalRounds: 5, startingCash: 100_000, marketType: .moderate
        )
        XCTAssertEqual(config.name, "Test Sim")
        XCTAssertEqual(config.totalRounds, 5)
        XCTAssertNotNil(config.randomSeed)
    }

    func testConfigDefaults() {
        let config = SessionConfiguration(
            name: "Default", totalRounds: 10, startingCash: 80_000, marketType: .moderate, aiDifficulty: .medium
        )
        XCTAssertEqual(config.numberOfAICompetitors, 3)
        XCTAssertEqual(config.scoringMetric, .investorScore)
        XCTAssertEqual(config.baseCostPerUnit, 40)
        XCTAssertEqual(config.baseMarketDemand, 1000)
        XCTAssertEqual(config.sharesOutstanding, 10_000)
        XCTAssertEqual(config.initialEquity, 80_000)
        XCTAssertEqual(config.baseInterestRate, 0.05)
        XCTAssertEqual(config.plantCapacity, 300)
        XCTAssertNil(config.sessionExpiryDate)
    }

    func testFixedCostsPerUnitDefault() {
        let config = SessionConfiguration(
            name: "Test", totalRounds: 3, startingCash: 50_000, marketType: .moderate
        )
        XCTAssertEqual(config.fixedCostsPerRound[.rent], 2_000)
        XCTAssertEqual(config.fixedCostsPerRound[.insurance], 1_000)
        XCTAssertEqual(config.fixedCostsPerRound[.admin], 500)
    }

    func testSessionTemplateIntroMarketing() {
        let config = SessionConfiguration(template: .introMarketing, name: "Demo")
        XCTAssertEqual(config.totalRounds, 5)
        XCTAssertEqual(config.aiDifficulty, .easy)
        XCTAssertGreaterThan(config.startingCash, 0)
    }

    func testSessionTemplateAdvancedStrategy() {
        let config = SessionConfiguration(template: .advancedStrategy, name: "Expert")
        XCTAssertEqual(config.totalRounds, 12)
        XCTAssertEqual(config.aiDifficulty, .hard)
        XCTAssertEqual(config.marketType, .aggressive)
    }

    func testSessionTemplateQuickDemo() {
        let config = SessionConfiguration(template: .quickDemo, name: "Mini")
        XCTAssertEqual(config.totalRounds, 3)
        XCTAssertEqual(config.aiDifficulty, .easy)
    }

    func testSessionTemplateEntrepreneurship() {
        let config = SessionConfiguration(template: .entrepreneurship, name: "Startup")
        XCTAssertEqual(config.totalRounds, 8)
        XCTAssertEqual(config.marketType, .moderate)
    }

    func testAllTemplatesHaveConfigs() {
        for template in SessionTemplate.allCases {
            let config = SessionConfiguration(template: template, name: "\(template.displayName)")
            XCTAssertGreaterThan(config.totalRounds, 0)
            XCTAssertGreaterThan(config.startingCash, 0)
            XCTAssertTrue(!config.name.isEmpty)
        }
    }

    func testSessionConfigurationCodable() throws {
        let config = SessionConfiguration(
            name: "Test", totalRounds: 5, startingCash: 100_000, marketType: .moderate
        )
        let encoder = JSONEncoder()
        let data = try encoder.encode(config)
        XCTAssertGreaterThan(data.count, 0)

        let decoder = JSONDecoder()
        let decoded = try decoder.decode(SessionConfiguration.self, from: data)
        XCTAssertEqual(decoded.name, config.name)
    }
}
