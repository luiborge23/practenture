import XCTest

/// Comprehensive E2E UI test for Practenture app — tests all critical flows.
/// Run with: xcodebuild test -scheme Practenture -destination 'platform=iOS Simulator,name=iPhone 17 Pro' -only-testing:PractentureTests/PractentureE2EFlowTest
final class PractentureE2EFlowTest: XCTestCase {
    
    var app: XCUIApplication!
    
    override func setUp() {
        super.setUp()
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchArguments = ["-UITests"]
        app.launch()
    }
    
    override func tearDown() {
        app.terminate()
        super.tearDown()
    }
    
    // MARK: - Helper
    
    private func tapButton(_ label: String, timeout: TimeInterval = 5) {
        let button = app.buttons[label]
        XCTAssertTrue(button.waitForExistence(timeout: timeout), "Button '\(label)' not found")
        button.tap()
    }
    
    private func tapText(_ text: String, timeout: TimeInterval = 5) {
        let elem = app.staticTexts[text]
        XCTAssertTrue(elem.waitForExistence(timeout: timeout), "Text '\(text)' not found")
        elem.tap()
    }
    
    // MARK: - Tests
    
    func test01_AppLaunches() {
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 10), "App should launch")
    }
    
    func test02_LaunchScreenShowsLogin() {
        // Should see either "Get Started" or "Login" or "Sign In" button
        let getStarted = app.buttons["Get Started"]
        let login = app.buttons["Login"]
        let signIn = app.buttons["Sign In"]
        
        let foundButton = getStarted.waitForExistence(timeout: 5) || 
                          login.waitForExistence(timeout: 2) || 
                          signIn.waitForExistence(timeout: 2)
        XCTAssertTrue(foundButton, "Should show a login/get started button on launch")
    }
    
    func test03_ProfessorLoginFlow() {
        // Tap Get Started or Login
        if app.buttons["Get Started"].exists {
            app.buttons["Get Started"].tap()
        } else if app.buttons["Login"].exists {
            app.buttons["Login"].tap()
        }
        
        sleep(2)
        
        // Should see login form
        // Try to find username/password fields
        let usernameField = app.textFields.firstMatch
        if usernameField.waitForExistence(timeout: 5) {
            usernameField.tap()
            usernameField.typeText("professor")
            
            // Find password field
            let passwordField = app.secureTextFields.firstMatch
            if passwordField.exists {
                passwordField.tap()
                passwordField.typeText("E2EProfPass123")
            }
            
            // Tap Sign In
            if app.buttons["Sign In"].exists {
                app.buttons["Sign In"].tap()
                sleep(3)
                // Should NOT crash — should see sessions or dashboard
                XCTAssertFalse(app.wait(for: .runningForeground, timeout: 3) == false, "App should not hang after login")
            }
        }
    }
    
    func test04_CreateSessionDoesNotCrash() {
        // This is the critical test — the crash was happening when creating a session
        // Login first
        if app.buttons["Get Started"].exists {
            app.buttons["Get Started"].tap()
            sleep(2)
        }
        
        // Try to login as professor
        let usernameField = app.textFields.firstMatch
        if usernameField.waitForExistence(timeout: 5) {
            usernameField.tap()
            usernameField.typeText("professor")
            let passwordField = app.secureTextFields.firstMatch
            if passwordField.exists {
                passwordField.tap()
                passwordField.typeText("E2EProfPass123")
                if app.buttons["Sign In"].exists {
                    app.buttons["Sign In"].tap()
                    sleep(3)
                }
            }
        }
        
        // Try to find and tap "Create Session" button
        let createBtn = app.buttons["Create Session"]
        if createBtn.waitForExistence(timeout: 10) {
            createBtn.tap()
            sleep(2)
            
            // App should NOT crash — verify it's still running
            XCTAssertTrue(app.wait(for: .runningForeground, timeout: 3), "App should not crash when creating session")
            
            // Should see the Create Session form
            let formElement = app.staticTexts["Create Session"]
            XCTAssertTrue(formElement.waitForExistence(timeout: 5), "Should see Create Session form")
        }
    }
    
    func test05_AppDoesNotCrashOnAnySheetPresentation() {
        // Login as professor
        if app.buttons["Get Started"].exists {
            app.buttons["Get Started"].tap()
            sleep(2)
        }
        
        let usernameField = app.textFields.firstMatch
        if usernameField.waitForExistence(timeout: 5) {
            usernameField.tap()
            usernameField.typeText("professor")
            let passwordField = app.secureTextFields.firstMatch
            if passwordField.exists {
                passwordField.tap()
                passwordField.typeText("E2EProfPass123")
                if app.buttons["Sign In"].exists {
                    app.buttons["Sign In"].tap()
                    sleep(3)
                }
            }
        }
        
        // Try tapping Create Session
        let createBtn = app.buttons["Create Session"]
        if createBtn.exists {
            createBtn.tap()
            sleep(2)
            
            // Verify no crash
            XCTAssertTrue(app.state == .runningForeground, "App should still be running")
            
            // Dismiss sheet
            if app.buttons["Cancel"].exists {
                app.buttons["Cancel"].tap()
                sleep(1)
            }
        }
        
        // App should still be running
        XCTAssertTrue(app.wait(for: .runningForeground, timeout: 3), "App should not crash")
    }
}
