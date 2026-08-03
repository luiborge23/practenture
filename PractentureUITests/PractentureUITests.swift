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
        if app.state != .notRunning {
            app.terminate()
        }
        app.launchArguments = ["-UITesting"]
        app.launchEnvironment = ["PRACTENTURE_UI_SCENARIO": scenario]
        app.launch()
        XCTAssertTrue(app.otherElements["qa.harness"].waitForExistence(timeout: 15),
                      "Deterministic QA harness did not launch")
    }

    private func launchAuthentication(
        role: String,
        step: String = "authenticationMethods",
        expectedTitle: String? = nil
    ) {
        if app.state != .notRunning {
            app.terminate()
        }
        app.launchArguments = ["-UITesting"]
        app.launchEnvironment = [
            "PRACTENTURE_UI_AUTH_ROLE": role,
            "PRACTENTURE_UI_AUTH_STEP": step,
        ]
        app.launch()
        let title = expectedTitle ?? (role == "professor" ? "Professor access" : "Student access")
        XCTAssertTrue(app.staticTexts[title].waitForExistence(timeout: 15),
                      "Authentication step \(step) did not launch for \(role)")
    }

    func testProfessorAuthenticationOffersThreePrimaryMethods() {
        launchAuthentication(role: "professor")

        XCTAssertTrue(app.buttons["Sign in with Apple"].exists)
        XCTAssertTrue(app.buttons["Sign in with Google"].exists)
        XCTAssertTrue(app.buttons["Use Practenture credentials"].exists)
        XCTAssertTrue(app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS %@", "same method they enrolled with")
        ).firstMatch.exists)
    }

    func testStudentAuthenticationLimitsProvidersToReturningLinkedAccounts() {
        launchAuthentication(role: "student")

        XCTAssertTrue(app.buttons["Sign in with Apple"].exists)
        XCTAssertTrue(app.buttons["Sign in with Google"].exists)
        XCTAssertTrue(app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS %@", "returning linked student accounts")
        ).firstMatch.exists)
        XCTAssertTrue(app.buttons["Use student credentials"].exists)
        XCTAssertTrue(app.buttons["Create student account"].exists)
    }

    func testProfessorCredentialRecoveryNavigation() {
        launchAuthentication(role: "professor")

        app.buttons["Use Practenture credentials"].tap()
        XCTAssertTrue(app.staticTexts["Professor Login"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.textFields["Username"].exists)
        XCTAssertTrue(app.secureTextFields["Password"].exists)
        XCTAssertFalse(app.buttons["Sign in"].isEnabled)

        app.buttons["Forgot password?"].tap()
        XCTAssertTrue(app.staticTexts["Reset Password"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.textFields["email@example.com"].exists)
        XCTAssertFalse(app.buttons["Send Reset Token"].isEnabled)

        app.buttons["← Back to login"].tap()
        XCTAssertTrue(app.staticTexts["Professor Login"].waitForExistence(timeout: 5))
    }

    func testStudentRegistrationRequiresStrongMatchingPassword() {
        launchAuthentication(role: "student")

        let createAccount = app.buttons["Create student account"]
        XCTAssertTrue(createAccount.waitForExistence(timeout: 5))
        XCTAssertTrue(createAccount.isEnabled)
        createAccount.tap()
        XCTAssertTrue(app.staticTexts["Student Registration"].waitForExistence(timeout: 5))

        app.textFields["Student ID (S12345678)"].tap()
        app.textFields["Student ID (S12345678)"].typeText("S12345678")
        app.textFields["Full Name"].tap()
        app.textFields["Full Name"].typeText("QA Student")
        app.secureTextFields["Password"].tap()
        app.secureTextFields["Password"].typeText("weak")

        XCTAssertTrue(app.staticTexts["Password requirements:"].waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Register"].isEnabled)
    }

    func testMFAEntryRequiresExactlySixDigits() {
        launchAuthentication(role: "professor", step: "mfaEntry", expectedTitle: "MFA Verification")

        let code = app.textFields["000000"]
        XCTAssertTrue(code.waitForExistence(timeout: 5))
        XCTAssertFalse(app.buttons["Verify"].isEnabled)

        code.tap()
        code.typeText("12345")
        XCTAssertFalse(app.buttons["Verify"].isEnabled)

        code.typeText("67")
        XCTAssertEqual(code.value as? String, "123456")
        XCTAssertTrue(app.buttons["Verify"].isEnabled)
    }

    func testProfessorAuthenticationAccessibilityAudit() throws {
        launchAuthentication(role: "professor")

        let providerChoice = app.buttons["Sign in with Apple"]
        XCTAssertTrue(providerChoice.waitForExistence(timeout: 10))
        let verifiedHighContrastLabels: Set<String> = [
            "First-time Apple or Google professors will need a one-time invitation. Returning professors should use the same method they enrolled with.",
            "First-time professor?",
            "Redeem professor invitation",
            "Sign in with Google",
            "Use Practenture credentials",
        ]
        try app.performAccessibilityAudit { issue in
            issue.auditType == .contrast
                && issue.element.map { verifiedHighContrastLabels.contains($0.label) } == true
        }
    }

    func testProfessorInvitationNavigationDoesNotExposeAccountFormBeforeValidation() {
        launchAuthentication(role: "professor")

        app.buttons["Redeem professor invitation"].tap()
        XCTAssertTrue(app.staticTexts["Professor Access"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.textFields["One-time invitation code"].exists)
        XCTAssertFalse(app.buttons["Continue"].isEnabled)
        XCTAssertFalse(app.textFields["Invitation email (must match administrator invitation)"].exists)
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

    func testAccountDeletionIsDiscoverableInSettings() {
        launch("accountSettings")

        let deleteAccount = app.buttons["deleteAccountButton"]
        for _ in 0..<4 where !deleteAccount.isHittable {
            app.swipeUp()
        }
        XCTAssertTrue(deleteAccount.waitForExistence(timeout: 5))
        XCTAssertTrue(deleteAccount.isHittable)
        XCTAssertEqual(deleteAccount.label, "Delete Account")
        deleteAccount.tap()

        XCTAssertTrue(app.staticTexts["Permanent deletion"].waitForExistence(timeout: 5))
        XCTAssertTrue(app.staticTexts.matching(
            NSPredicate(format: "label CONTAINS %@", "Students are detached")
        ).firstMatch.exists)
        XCTAssertTrue(app.buttons["Cancel"].isHittable)
    }

    func testStudentAccountDeletionIsDiscoverableThroughSettingsGear() {
        launch("accountSettingsStudent")

        let settings = app.buttons["studentSettingsButton"]
        XCTAssertTrue(settings.waitForExistence(timeout: 5))
        settings.tap()
        let deleteAccount = app.buttons["deleteAccountButton"]
        for _ in 0..<4 where !deleteAccount.isHittable { app.swipeUp() }
        XCTAssertTrue(deleteAccount.waitForExistence(timeout: 5))
        XCTAssertTrue(deleteAccount.isHittable)
    }

    func testProfessorAccountDeletionIsDiscoverableThroughSettingsTab() {
        launch("accountSettingsProfessor")

        let settings = app.tabBars.buttons["Settings"]
        XCTAssertTrue(settings.waitForExistence(timeout: 5))
        settings.tap()
        let deleteAccount = app.buttons["deleteAccountButton"]
        for _ in 0..<4 where !deleteAccount.isHittable { app.swipeUp() }
        XCTAssertTrue(deleteAccount.waitForExistence(timeout: 5))
        XCTAssertTrue(deleteAccount.isHittable)
    }

    func testPasswordAndMFADeletionRequirementsRenderAndGateContinuation() {
        launch("accountDeletionPasswordMFA")

        let confirmation = app.textFields["accountDeletionConfirmation"]
        let password = app.secureTextFields["accountDeletionPassword"]
        let mfa = app.secureTextFields["accountDeletionMFACode"]
        let continueButton = app.buttons["Continue"]
        XCTAssertTrue(confirmation.waitForExistence(timeout: 5))
        XCTAssertTrue(password.exists)
        XCTAssertTrue(mfa.exists)
        XCTAssertFalse(continueButton.isEnabled)
        confirmation.tap()
        confirmation.typeText("DELETE")
        password.tap()
        password.typeText("DeleteMe123!")
        mfa.tap()
        mfa.typeText("123456")
        XCTAssertTrue(continueButton.isEnabled)
    }

    func testAppleDeletionRequiresProviderReauthentication() {
        launch("accountDeletionApple")

        XCTAssertTrue(app.buttons[
            "Reauthenticate with Apple to delete account"
        ].waitForExistence(timeout: 5))
    }

    func testGoogleDeletionRequiresProviderReauthentication() {
        launch("accountDeletionGoogle")

        XCTAssertTrue(app.buttons[
            "accountDeletionGoogleReauthentication"
        ].waitForExistence(timeout: 5))
    }

    func testOfflineDecisionQueuesThenFlushesAfterReconnect() {
        launch("offlineQueue")

        XCTAssertEqual(app.staticTexts["sync.status"].label, "Offline")
        XCTAssertEqual(app.staticTexts["sync.pending"].label, "Pending actions: 0")
        app.buttons["sync.queue"].tap()
        let pending = app.staticTexts["sync.pending"]
        expectation(
            for: NSPredicate(format: "label == %@", "Pending actions: 1"),
            evaluatedWith: pending
        )
        waitForExpectations(timeout: 5)

        app.buttons["sync.reconnect"].tap()
        XCTAssertTrue(app.staticTexts["Online"].waitForExistence(timeout: 5))
        expectation(
            for: NSPredicate(format: "label == %@", "Pending actions: 0"),
            evaluatedWith: pending
        )
        waitForExpectations(timeout: 5)
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
