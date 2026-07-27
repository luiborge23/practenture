// FinanceDecisionTests.swift
// Practenture Tests
// Unit tests for FinanceDecision data model

import XCTest
@testable import Practenture

final class FinanceDecisionTests: XCTestCase {

    func testDefaultFinanceDecision() {
        let finance = FinanceDecision()
        XCTAssertEqual(finance.csrInvestment, 2_000)
        XCTAssertEqual(finance.dividendsPerShare, 0.50)
        XCTAssertEqual(finance.newLoanAmount, 0)
        XCTAssertEqual(finance.sharesBuyback, 0)
        XCTAssertEqual(finance.sharesIssued, 0)
    }

    func testValidFinanceDecision() {
        let finance = FinanceDecision(
            csrInvestment: 5_000,
            dividendsPerShare: 1.0,
            newLoanAmount: 50_000,
            sharesBuyback: 100,
            sharesIssued: 200
        )
        XCTAssertTrue(finance.isValid)
    }

    func testNegativeCSRInvalid() {
        let finance = FinanceDecision(csrInvestment: -100)
        XCTAssertFalse(finance.isValid)
        XCTAssertTrue(finance.validationErrors.contains { $0.lowercased().contains("csr") })
    }

    func testNegativeDividendsInvalid() {
        let finance = FinanceDecision(dividendsPerShare: -0.5)
        XCTAssertFalse(finance.isValid)
        XCTAssertTrue(finance.validationErrors.contains { $0.lowercased().contains("dividend") })
    }

    func testNegativeLoanAmountInvalid() {
        let finance = FinanceDecision(newLoanAmount: -10_000)
        XCTAssertFalse(finance.isValid)
        XCTAssertTrue(finance.validationErrors.contains { $0.lowercased().contains("loan amount") || $0.lowercased().contains("new loan") })
    }

    func testNegativeSharesBuybackInvalid() {
        let finance = FinanceDecision(sharesBuyback: -50)
        XCTAssertFalse(finance.isValid)
        XCTAssertTrue(finance.validationErrors.contains { $0.lowercased().contains("buyback") || $0.lowercased().contains("shares buyback") })
    }

    func testNegativeSharesIssuedInvalid() {
        let finance = FinanceDecision(sharesIssued: -10)
        XCTAssertFalse(finance.isValid)
        XCTAssertTrue(finance.validationErrors.contains { $0.lowercased().contains("issued") || $0.lowercased().contains("shares issued") })
    }

    func testZeroValuesValid() {
        let finance = FinanceDecision(csrInvestment: 0, dividendsPerShare: 0, newLoanAmount: 0, sharesBuyback: 0, sharesIssued: 0)
        XCTAssertTrue(finance.isValid)
    }

    func testFinanceCodable() throws {
        let finance = FinanceDecision(newLoanAmount: 25_000, dividendsPerShare: 1.5)
        let encoder = JSONEncoder()
        let data = try encoder.encode(finance)
        let decoder = JSONDecoder()
        let decoded = try decoder.decode(FinanceDecision.self, from: data)
        XCTAssertEqual(decoded.newLoanAmount, 25_000)
    }

    func testFinanceHasUUID() {
        let finance = FinanceDecision()
        XCTAssertNotNil(finance.id as UUID?)
    }
}
