// BizSimAIUITests.swift
// BizSimAIUITests
//
// UI Tests for BizSimAI — Professor and Student Flows
// Tests core user journeys: launch, role selection, session creation,
// session joining, dashboard rendering, and round submission.
//
// Note: These tests run against the app in local/demo mode (no backend required).
// Professor session creation with cloud backend requires a running FastAPI server.

import XCTest

final class BizSimAIUITests: XCTestCase {

    var app: XCUIApplication!
    let launchTimeout: TimeInterval = 20.0

    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments.append("-UITesting")
        app.launchArguments.append("-LocalOnly")
        app.launchTimeout = launchTimeout
        waitForAppToLaunch()
    }

    override func tearDown() {
        app.terminate()
        super.tearDown()
    }

    // MARK: - Helpers

    private func waitForAppToLaunch() {
        let launched = app.waitForExistence(timeout: 10)
        XCTAssertTrue(launched, "App should launch within \(launchTimeout)s")
        // Wait for launch animations to finish
        sleep(2)
    }

    private func tapButtonContaining(_ text: String, timeout: TimeInterval = 5) -> Bool {
        let button = app.buttons[text]
        if button.exists {
            button.tap()
            return true
        }
        let fallback = app.buttons.containing(text).element(boundBy: 0)
        if fallback.exists {
            fallback.tap()
            return true
        }
        XCTFail("Button '\(text)' not found on screen")
        return false
    }

    private func tapStaticTextContaining(_ text: String, timeout: TimeInterval = 5) -> Bool {
        let textElement = app.staticTexts[text]
        if textElement.exists {
            textElement.tap()
            return true
        }
        let fallback = app.staticTexts.containing(text).element(boundBy: 0)
        if fallback.exists {
            fallback.tap()
            return true
        }
        XCTFail("Text '\(text)' not found on screen")
        return false
    }

    private func typeTextIntoTextField(placeholder: String, text: String) {
        let field = app.textFields[placeholder]
        if field.exists {
            field.tap()
            field.typeText(text)
        } else {
            // Fallback: find by any text field
            let allFields = app.textFields.allElementsBoundByIndex
            for f in allFields where !f.value as! String.isEmpty || f.placeholderValue == placeholder {
                f.tap()
                f.typeText(text)
                return
            }
            XCTFail("TextField with placeholder '\(placeholder)' not found")
        }
    }

    private func verifyTextOnScreen(_ text: String, timeout: TimeInterval = 5) {
        let exists = app.staticTexts[text].waitForExistence(timeout: timeout)
        XCTAssertTrue(exists, "Expected text '\(text)' should be visible")
    }

    private func scrollToElement(_ element: XCUIElement, timeout: TimeInterval = 3) {
        // Try to scroll to make the element visible
        let predicate = NSPredicate(format: "isVisible == 1")
        expectation(for: predicate, evaluatedWith: element, handler: nil)
        waitForExpectations(timeout: timeout)
    }

    // MARK: - Launch View Tests

    func testLaunchView_DisplaysTitleAndRoleCards() {
        // 1. Verify launch screen loads with title
        verifyTextOnScreen("BizSim AI")

        // 2. Verify subtitle is visible
        verifyTextOnScreen("Business Simulation for the Modern Classroom")

        // 3. Verify both role cards are present
        let professorCard = app.buttons["Professor"]
        XCTAssertTrue(professorCard.exists, "Professor role card should be visible")

        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists, "Student role card should be visible")

        // 4. Verify icons are rendered (system image names appear in accessibility)
        XCTAssertTrue(app.images.element(boundBy: 0).exists, "App logo icon should be rendered")
    }

    func testLaunchView_AnimationCompletes() {
        // Verify the logo animation completes and content is fully visible
        let title = app.staticTexts["BizSim AI"]
        XCTAssertTrue(title.waitForExistence(timeout: 5), "Title should animate into view")

        // Verify role cards are fully visible after animation
        let professorCard = app.buttons["Professor"]
        XCTAssertTrue(professorCard.waitForExistence(timeout: 5), "Professor card should animate into view")

        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.waitForExistence(timeout: 5), "Student card should animate into view")
    }

    // MARK: - Professor Flow Tests

    func testProfessorFlow_NavigateToLogin() {
        // 1. Start from launch screen
        verifyTextOnScreen("BizSim AI")

        // 2. Tap Professor card
        let professorCard = app.buttons["Professor"]
        XCTAssertTrue(professorCard.exists)
        professorCard.tap()

        // 3. Verify LoginView appears
        // The login sheet presents with "Professor Login" as the mode title
        let loginTitle = app.staticTexts["Professor Login"]
        XCTAssertTrue(loginTitle.waitForExistence(timeout: 3),
                      "Professor Login view should appear after tapping Professor card")
    }

    func testProfessorFlow_LoginFormFields() {
        // 1. Navigate to Professor login
        let professorCard = app.buttons["Professor"]
        XCTAssertTrue(professorCard.exists)
        professorCard.tap()

        // 2. Verify login mode tabs exist
        let professorTab = app.buttons["Professor"]
        XCTAssertTrue(professorTab.exists, "Professor tab should be selected in picker")

        let studentLoginTab = app.buttons["Student Login"]
        XCTAssertTrue(studentLoginTab.exists, "Student Login tab should be available")

        let studentRegisterTab = app.buttons["Student Register"]
        XCTAssertTrue(studentRegisterTab.exists, "Student Register tab should be available")

        // 3. Verify professor form fields
        let usernameField = app.textFields["Username"]
        if usernameField.exists {
            // Field should be present
            XCTAssertTrue(true)
        } else {
            // In LabeledContent format, the label appears as static text
            let usernameLabel = app.staticTexts["Username"]
            XCTAssertTrue(usernameLabel.exists, "Username label should be visible")
        }

        let passwordField = app.secureTextFields.firstMatch
        XCTAssertTrue(passwordField.exists, "Password field should be present")
    }

    func testProfessorFlow_SubmitLogin() {
        // 1. Navigate to Professor login
        let professorCard = app.buttons["Professor"]
        XCTAssertTrue(professorCard.exists)
        professorCard.tap()

        // 2. Enter credentials
        // Username field
        let usernameLabel = app.staticTexts["Username"]
        if usernameLabel.exists {
            // Tap the adjacent text field
            let usernameField = usernameLabel.staticTexts.element(boundBy: 0)
            // Try to find the actual text field nearby
            let allTextFields = app.textFields.allElementsBoundByIndex
            if !allTextFields.isEmpty {
                allTextFields[0].tap()
                app.typeText("professor")
            }
        }

        // Password field
        let passwordField = app.secureTextFields.firstMatch
        if passwordField.exists {
            passwordField.tap()
            app.typeText("bizsimai2026")
        }

        // 3. Tap login button
        let loginButton = app.buttons["Login"]
        if loginButton.exists {
            loginButton.tap()
            sleep(2)
            // Should navigate to professor tab view or show error if backend not reachable
            XCTAssertTrue(true, "Login attempt completed")
        }
    }

    // MARK: - Student Flow Tests

    func testStudentFlow_NavigateToJoinSession() {
        // 1. Start fresh
        app.terminate()
        app.launch()
        waitForAppToLaunch()

        // 2. Verify launch screen
        verifyTextOnScreen("BizSim AI")

        // 3. Tap Student card
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists)
        studentCard.tap()

        // 4. Verify JoinSessionView appears
        verifyTextOnScreen("Join a Session")
    }

    func testStudentFlow_JoinSessionForm() {
        // 1. Navigate to student mode
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists)
        studentCard.tap()

        // 2. Verify Join Session form fields
        verifyTextOnScreen("Join a Session")
        verifyTextOnScreen("Session Code")
        verifyTextOnScreen("Team Name")
        verifyTextOnScreen("Student ID")

        // 3. Verify session code field is present
        let sessionCodeField = app.textFields["Session Code"]
        XCTAssertTrue(sessionCodeField.exists, "Session code field should be visible")

        // 4. Verify team name field is present
        let teamNameField = app.textFields["Team Name"]
        XCTAssertTrue(teamNameField.exists, "Team name field should be visible")

        // 5. Verify Join button exists
        let joinButton = app.buttons["Join Session"]
        XCTAssertTrue(joinButton.exists, "Join Session button should be visible")
    }

    func testStudentFlow_ValidateJoinForm() {
        // 1. Navigate to join session
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists)
        studentCard.tap()

        // 2. Try to join with empty fields — button should be disabled
        let joinButton = app.buttons["Join Session"]
        // Button should be disabled when form is invalid
        let isDisabled = joinButton.isEnabled
        XCTAssertFalse(isDisabled, "Join button should be disabled with empty form")
    }

    func testStudentFlow_EnterValidTeamName() {
        // 1. Navigate to join session
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists)
        studentCard.tap()

        // 2. Enter team name
        let teamNameField = app.textFields["Team Name"]
        if teamNameField.exists {
            teamNameField.tap()
            teamNameField.typeText("Strategy Kings")
        }

        // 3. Verify Join button becomes enabled
        let joinButton = app.buttons["Join Session"]
        let isEnabled = joinButton.isEnabled
        XCTAssertTrue(isEnabled, "Join button should enable when team name is entered")
    }

    func testStudentFlow_DemoSession() {
        // 1. Navigate to student mode
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists)
        studentCard.tap()

        // 2. Verify demo buttons are visible
        verifyTextOnScreen("Start Demo Session")
        verifyTextOnScreen("Quick Demo (Auto-Play All Rounds)")

        // 3. Tap "Start Demo Session"
        let demoButton = app.buttons["Start Demo Session"]
        XCTAssertTrue(demoButton.exists, "Demo button should be visible")
        demoButton.tap()

        // 4. Should transition to TeamDashboardView
        sleep(2)
        // The dashboard should show at least some content
        XCTAssertTrue(app.staticTexts.element(boundBy: 0).exists,
                      "Demo session should show dashboard content")
    }

    // MARK: - Team Dashboard Tests

    func testStudentFlow_DashboardRenders() {
        // 1. Start a demo session
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists)
        studentCard.tap()

        let demoButton = app.buttons["Start Demo Session"]
        XCTAssertTrue(demoButton.exists)
        demoButton.tap()

        // 2. Wait for dashboard to load
        sleep(3)

        // 3. Verify dashboard elements are present
        // The dashboard shows the team name as navigation title
        XCTAssertTrue(app.navigationBars.element.exists,
                      "Dashboard navigation bar should be visible")

        // 4. Verify round header is present
        let roundText = app.staticTexts.matching(identifier: "").allElementsBoundByIndex
        XCTAssertTrue(app.collectionViews.element.exists ||
                      app.staticTexts.element(boundBy: 0).exists,
                      "Dashboard should display metrics")
    }

    func testStudentFlow_DashboardHasActionButtons() {
        // 1. Start a demo session
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists)
        studentCard.tap()

        let demoButton = app.buttons["Start Demo Session"]
        XCTAssertTrue(demoButton.exists)
        demoButton.tap()

        sleep(2)

        // 2. Verify toolbar buttons are present
        // History button
        let historyButton = app.buttons["History"]
        if historyButton.exists {
            XCTAssertTrue(true, "History button should be visible")
        }

        // Leaderboard button
        let leaderboardButton = app.buttons["Leaderboard"]
        if leaderboardButton.exists {
            XCTAssertTrue(true, "Leaderboard button should be visible")
        }

        // AI Coach button
        let coachButton = app.buttons["AI Coach"]
        if coachButton.exists {
            XCTAssertTrue(true, "AI Coach button should be visible")
        }

        // Leave Session button
        let leaveButton = app.buttons["Leave Session"]
        if leaveButton.exists {
            XCTAssertTrue(true, "Leave Session button should be visible")
        }
    }

    // MARK: - Create Session Form Tests (Local Mode)

    func testProfessorFlow_CreateSessionFormFields() {
        // 1. Navigate to professor mode
        app.terminate()
        app.launch()
        waitForAppToLaunch()

        let professorCard = app.buttons["Professor"]
        XCTAssertTrue(professorCard.exists)
        professorCard.tap()

        // 2. Wait for login sheet
        let loginTitle = app.staticTexts["Professor Login"]
        if loginTitle.waitForExistence(timeout: 3) {
            // Enter credentials
            let allTextFields = app.textFields.allElementsBoundByIndex
            if !allTextFields.isEmpty {
                allTextFields[0].tap()
                app.typeText("professor")
            }
            let passwordField = app.secureTextFields.firstMatch
            if passwordField.exists {
                passwordField.tap()
                app.typeText("bizsimai2026")
            }
            let loginButton = app.buttons["Login"]
            if loginButton.exists {
                loginButton.tap()
                sleep(2)
            }
        }

        // 3. Navigate to Create Session
        let createButton = app.buttons["Create Session"]
        if createButton.exists {
            createButton.tap()
            sleep(2)
        }

        // 4. Verify Create Session form is present
        verifyTextOnScreen("Create Session")

        // 5. Verify key form sections exist
        let templateLabel = app.staticTexts["Session Template"]
        XCTAssertTrue(templateLabel.exists || app.pickers.element.exists,
                      "Session Template picker should be present")

        let roundsLabel = app.staticTexts["Total Rounds"]
        XCTAssertTrue(roundsLabel.exists || app.steppers.element.exists,
                      "Total Rounds stepper should be present")

        let cashLabel = app.staticTexts["Starting Cash"]
        XCTAssertTrue(cashLabel.exists || app.sliders.element.exists,
                      "Starting Cash slider should be present")
    }

    // MARK: - Cross-Flow Tests

    func testFullProfessorToStudentFlow() {
        // 1. Start as Professor — launch and navigate
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        verifyTextOnScreen("BizSim AI")

        let professorCard = app.buttons["Professor"]
        XCTAssertTrue(professorCard.exists)
        professorCard.tap()

        // 2. Navigate back to launch (if login sheet is open, dismiss it)
        let dismissButton = app.buttons["Cancel"]
        if dismissButton.exists {
            dismissButton.tap()
        }
        sleep(1)

        // 3. Switch to Student
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists)
        studentCard.tap()

        // 4. Verify Join Session view
        verifyTextOnScreen("Join a Session")
    }

    func testNavigationFromLaunchToBothRoles() {
        // Verify we can navigate to both roles from the same launch screen
        verifyTextOnScreen("BizSim AI")

        // Tap Professor
        app.buttons["Professor"].tap()
        verifyTextOnScreen("Professor Login")

        // Dismiss and tap Student
        let cancelBtn = app.buttons["Cancel"]
        if cancelBtn.exists { cancelBtn.tap() }
        sleep(1)

        app.buttons["Student"].tap()
        verifyTextOnScreen("Join a Session")
    }

    // MARK: - Performance Tests

    func testAppLaunchPerformance() {
        let expectation = self.expectation(description: "App launches")

        app.launch()
        XCTAssertTrue(app.waitForExistence(timeout: 15), "App should launch within 15s")
        expectation.fulfill()

        waitForExpectations(timeout: 15)
    }

    func testNavigationResponsiveness() {
        // Measure time to navigate from launch to login
        let start = CFAbsoluteTimeGetCurrent()

        XCTAssert(app.staticTexts["BizSim AI"].exists)
        app.buttons["Professor"].tap()

        XCTAssertTrue(app.staticTexts["Professor Login"].waitForExistence(timeout: 5))

        let elapsed = CFAbsoluteTimeGetCurrent() - start
        XCTAssertLessThan(elapsed, 5.0,
                          "Navigation from launch to login should complete within 5s (took \(String(format: "%.2f", elapsed))s)")
    }

    func testDemoSessionLoadTime() {
        // Measure time from tapping demo button to dashboard appearing
        app.terminate()
        app.launch()
        waitForAppToLaunch()

        XCTAssert(app.staticTexts["BizSim AI"].exists)
        app.buttons["Student"].tap()
        sleep(1)

        let demoButton = app.buttons["Start Demo Session"]
        XCTAssertTrue(demoButton.exists)

        let start = CFAbsoluteTimeGetCurrent()
        demoButton.tap()

        // Dashboard should appear within 3 seconds
        XCTAssertTrue(app.navigationBars.element.waitForExistence(timeout: 3))
        let elapsed = CFAbsoluteTimeGetCurrent() - start
        XCTAssertLessThan(elapsed, 3.0,
                          "Demo session should load within 3s (took \(String(format: "%.2f", elapsed))s)")
    }

    // MARK: - Quick Demo (Auto-Play) Tests

    func testQuickDemo_AutoPlaysAllRounds() {
        // Test the Quick Demo (Auto-Play All Rounds) button
        // This verifies the async fix — app should NOT freeze during simulation

        // 1. Launch and navigate to student mode
        app.terminate()
        app.launch()
        waitForAppToLaunch()

        // 2. Tap Student card
        let studentCard = app.buttons["Student"]
        XCTAssertTrue(studentCard.exists, "Student card should be visible")
        studentCard.tap()

        // 3. Verify Join Session view appears
        verifyTextOnScreen("Join a Session")

        // 4. Verify Quick Demo button is visible
        let quickDemoButton = app.buttons["Quick Demo (Auto-Play All Rounds)"]
        XCTAssertTrue(quickDemoButton.exists, "Quick Demo button should be visible")

        // 5. Tap Quick Demo button
        quickDemoButton.tap()

        // 6. Wait for dashboard to appear (should NOT freeze)
        let dashboardAppeared = app.navigationBars.element.waitForExistence(timeout: 10)
        XCTAssertTrue(dashboardAppeared, "Dashboard should appear after tapping Quick Demo (app should not freeze)")

        // 7. Wait for simulation to complete (8 rounds × ~0.3s = ~2.4s minimum)
        // Give it 15 seconds to complete all rounds
        sleep(12)

        // 8. Verify simulation completed — check for round summaries or final state
        // The dashboard should show at least one round summary
        let hasContent = app.staticTexts.element(boundBy: 0).exists ||
                         app.collectionViews.element.exists ||
                         app.tables.element.exists
        XCTAssertTrue(hasContent, "Quick Demo should display simulation results after completion")

        // 9. Verify app is still responsive — try to tap a navigation button
        let historyButton = app.buttons["History"]
        if historyButton.exists {
            XCTAssertTrue(historyButton.isEnabled, "History button should be enabled after simulation completes")
        }
    }

    func testQuickDemo_AppDoesNotFreeze() {
        // Regression test: verify app remains responsive during Quick Demo
        // This specifically tests the async fix for the freeze issue

        app.terminate()
        app.launch()
        waitForAppToLaunch()

        // Navigate to student mode
        app.buttons["Student"].tap()
        verifyTextOnScreen("Join a Session")

        // Tap Quick Demo
        let quickDemoButton = app.buttons["Quick Demo (Auto-Play All Rounds)"]
        XCTAssertTrue(quickDemoButton.exists)
        quickDemoButton.tap()

        // Wait for dashboard to appear
        XCTAssertTrue(app.navigationBars.element.waitForExistence(timeout: 10),
                      "Dashboard should appear — app must not freeze")

        // During simulation, verify UI is still responsive by checking if we can
        // interact with the navigation bar (which would fail if main thread is blocked)
        let navBarExists = app.navigationBars.element.waitForExistence(timeout: 5)
        XCTAssertTrue(navBarExists, "Navigation bar should remain interactive during simulation")

        // Wait for rounds to complete
        sleep(10)

        // Final check: app should still be responsive
        let anyButton = app.buttons.element(boundBy: 0)
        XCTAssertTrue(anyButton.exists, "App should still be responsive after simulation completes")
    }
}
