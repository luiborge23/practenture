// IncomeStatementTests.swift
// BizSimAI Tests
// Unit tests for IncomeStatement financial model

import XCTest
@testable import BizSimAI

final class IncomeStatementTests: XCTestCase {

    func makeIncomeStatement() -> IncomeStatement {
        return IncomeStatement(
            round: 1, teamName: "Test Team",
            wholesaleRevenue: 50_000, internetRevenue: 30_000, amazonRevenue: 10_000, privateLabelRevenue: 5_000,
            materialsCost: 12_000, laborCost: 5_000, workforceCosts: 8_000, rejectionCost: 3_000,
            advertisingExpense: 5_000, outletExpense: 1_500, endorsementExpense: 2_000, stylingExpense: 2_500,
            tqmExpense: 1_500, bestPracticesExpense: 800, csrExpense: 1_000, storageCosts: 400, rebateCosts: 200,
            deliveryCosts: 300, socialMediaCosts: 800, amazonFees: 600, interestExpense: 500, dividendsPaid: 300
        )
    }

    func testGrossRevenue() {
        let stmt = makeIncomeStatement()
        XCTAssertEqual(stmt.grossRevenue, 95_000) // 50k+30k+10k+5k
    }

    func testCOGS() {
        let stmt = makeIncomeStatement()
        let expected: Double = 12_000 + 5_000 + 8_000 + 3_000
        XCTAssertEqual(stmt.cogs, expected)
    }

    func testGrossProfit() {
        let stmt = makeIncomeStatement()
        // grossRev(95k) - cogs(28k) = 67k
        XCTAssertEqual(stmt.grossProfit, 67_000)
    }

    func testGrossMarginCalculation() {
        let stmt = makeIncomeStatement()
        XCTAssertGreaterThan(stmt.grossMargin, 0)
        XCTAssertTrue(stmt.grossMargin < 1) // Should be between 0 and 1
    }

    func testZeroRevenueMarginIsZero() {
        let stmt = IncomeStatement(
            round: 2, teamName: "Empty", wholesaleRevenue: 0, internetRevenue: 0, amazonRevenue: 0, privateLabelRevenue: 0,
            materialsCost: 5_000, laborCost: 3_000, workforceCosts: 4_000, rejectionCost: 2_000,
            advertisingExpense: 1_000, outletExpense: 500, endorsementExpense: 800, stylingExpense: 1_000,
            tqmExpense: 700, bestPracticesExpense: 400, csrExpense: 500, storageCosts: 200, rebateCosts: 100,
            deliveryCosts: 150, socialMediaCosts: 300, amazonFees: 200, interestExpense: 200, dividendsPaid: 100
        )
        XCTAssertEqual(stmt.grossMargin, 0) // division by zero returns 0
    }

    func testOperatingExpenses() {
        let stmt = makeIncomeStatement()
        let expected: Double = 5_000 + 1_500 + 2_000 + 2_500 + 1_500 + 800 + 1_000 + 400 + 200 + 300 + 800 + 600
        XCTAssertEqual(stmt.operatingExpenses, expected)
    }

    func testOperatingIncome() {
        let stmt = makeIncomeStatement()
        // grossProfit(67k) - operatingExpenses(sum above)
        XCTAssertGreaterThan(stmt.grossProfit, stmt.operatingExpenses)
    }

    func testNetIncome() {
        let stmt = makeIncomeStatement()
        XCTAssertEqual(stmt.netIncome, stmt.operatingIncome - stmt.interestExpense - stmt.dividendsPaid)
    }

    func testNetMarginCalculation() {
        let stmt = makeIncomeStatement()
        XCTAssertGreaterThan(stmt.netMargin, 0)
        XCTAssertTrue(stmt.netMargin < 1)
    }

    func testZeroGrossRevenueNetMarginIsZero() {
        let stmt = IncomeStatement(
            round: 3, teamName: "Empty", wholesaleRevenue: 0, internetRevenue: 0, amazonRevenue: 0, privateLabelRevenue: 0,
            materialsCost: 1_000, laborCost: 500, workforceCosts: 800, rejectionCost: 200,
            advertisingExpense: 200, outletExpense: 100, endorsementExpense: 150, stylingExpense: 200,
            tqmExpense: 130, bestPracticesExpense: 60, csrExpense: 80, storageCosts: 40, rebateCosts: 20,
            deliveryCosts: 30, socialMediaCosts: 50, amazonFees: 40, interestExpense: 10, dividendsPaid: 5
        )
        XCTAssertEqual(stmt.netMargin, 0) // division by zero returns 0
    }

    func testIncomeStatementHasUUID() {
        let stmt = IncomeStatement(
            round: 1, teamName: "Test", wholesaleRevenue: 10_000, internetRevenue: 5_000, amazonRevenue: 2_000, privateLabelRevenue: 1_000,
            materialsCost: 3_000, laborCost: 1_500, workforceCosts: 2_400, rejectionCost: 800,
            advertisingExpense: 1_000, outletExpense: 400, endorsementExpense: 600, stylingExpense: 750,
            tqmExpense: 530, bestPracticesExpense: 280, csrExpense: 330, storageCosts: 130, rebateCosts: 60,
            deliveryCosts: 90, socialMediaCosts: 200, amazonFees: 150, interestExpense: 40, dividendsPaid: 20
        )
        XCTAssertNotNil(stmt.id as UUID?)
    }
}
