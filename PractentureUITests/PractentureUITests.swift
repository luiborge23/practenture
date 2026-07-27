import XCTest

final class PractentureUITests: XCTestCase {
    private var app: XCUIApplication!

    override func setUpWithError() throws {
        continueAfterFailure = false
        app = XCUIApplication()
    }

    override func tearDownWithError() throws {
        app?.terminate()
    }

    private func launch(_ scenario: String) {
        app.launchArguments = ["-UITesting"]
        app.launchEnvironment = ["PRACTENTURE_UI_SCENARIO": scenario]
        app.launch()
        XCTAssertTrue(app.otherElements["qa.harness"].waitForExistence(timeout: 15),
                      "Deterministic QA harness did not launch")
    }

    func testProfessorCreatesSessionAndAdvancesRound() {
        launch("professor")

        XCTAssertTrue(app.staticTexts["professor.title"].exists)
        app.buttons["professor.createSession"].tap()
        XCTAssertEqual(app.staticTexts["professor.sessionCode"].label, "Session QA-PROF")
        XCTAssertEqual(app.staticTexts["professor.round"].label, "Round 1 of 8")

        app.buttons["professor.advanceRound"].tap()
        XCTAssertEqual(app.staticTexts["professor.round"].label, "Round 2 of 8")
    }

    func testStudentJoinsAndSubmitsDecision() {
        launch("student")

        let code = app.textFields["student.sessionCode"]
        XCTAssertTrue(code.waitForExistence(timeout: 5))
        code.tap()
        code.typeText("QA1234")

        let team = app.textFields["student.teamName"]
        team.tap()
        team.typeText("QA Strategists")

        let join = app.buttons["student.join"]
        XCTAssertTrue(join.isEnabled)
        join.tap()
        XCTAssertTrue(app.staticTexts["student.dashboard"].waitForExistence(timeout: 5))

        app.buttons["student.submitDecision"].tap()
        XCTAssertTrue(app.staticTexts["student.submitted"].waitForExistence(timeout: 5))
    }

    func testOfflineDecisionQueuesThenFlushesAfterReconnect() {
        launch("offlineQueue")

        XCTAssertEqual(app.staticTexts["sync.status"].label, "Offline")
        XCTAssertEqual(app.staticTexts["sync.pending"].label, "Pending actions: 0")
        app.buttons["sync.queue"].tap()
        XCTAssertEqual(app.staticTexts["sync.pending"].label, "Pending actions: 1")

        app.buttons["sync.reconnect"].tap()
        XCTAssertTrue(app.staticTexts["Online"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["sync.pending"].label, "Pending actions: 0")
    }

    func testTimeoutErrorIsVisibleAndRetryRecovers() {
        launch("visibleError")

        app.buttons["error.trigger"].tap()
        XCTAssertTrue(app.staticTexts["Sync failed: Request timed out"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["error.message"].label,
                       "Your decision is saved locally and will retry.")

        app.buttons["Retry"].tap()
        XCTAssertTrue(app.staticTexts["error.recovered"].waitForExistence(timeout: 5))
        XCTAssertEqual(app.staticTexts["error.recovered"].label, "Connection restored")
    }
}
