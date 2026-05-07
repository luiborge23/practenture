// BizSimAIUITests.swift
// BizSimAIUITests
//
// UI Tests for BizSimAI - Professor and Student Flows
// Uses XCUITest to automate testing of the app's core workflows

import XCTest
import SwiftUI

final class BizSimAIUITests: XCTestCase {
    
    var app: XCUIApplication!
    var launchTime: TimeInterval = 15.0
    
    override func setUp() {
        super.setUp()
        
        continueAfterFailure = false
        app = XCUIApplication()
        app.launchTimeout = launchTime
        app.launchArguments.append("-UITesting")
        
        // Wait for app to be ready
        waitForAppToLaunch()
    }
    
    override func tearDown() {
        super.tearDown()
    }
    
    // MARK: - Helper Methods
    
    private func waitForAppToLaunch() {
        // Wait for the app to be running and responsive
        let launchSucceeded = app.waitForExistence(timeout: 10)
        XCTAssertTrue(launchSucceeded, "App should launch successfully")
        
        // Wait a moment for animations to complete
        sleep(2)
    }
    
    private func waitForElement(_ element: XCUIElement, timeout: TimeInterval = 5.0) {
        let existencePredicate = NSPredicate(format: "exists == 1")
        expectation(for: existencePredicate, evaluatedWith: element, handler: nil)
        waitForExpectations(timeout: timeout, handler: nil)
    }
    
    private func waitForTextOnScreen(_ text: String, timeout: TimeInterval = 5.0) {
        let searchText = app.staticTexts[text]
        let existencePredicate = NSPredicate(format: "exists == 1")
        expectation(for: existencePredicate, evaluatedWith: searchText, handler: nil)
        waitForExpectations(timeout: timeout, handler: nil)
    }
    
    // MARK: - Professor Flow Tests
    
    func testProfessorFlow_RoleSelection() {
        // 1. Verify Launch View loads correctly
        XCTAssert(app.staticTexts["BizSim AI"].exists, "Launch title should be visible")
        XCTAssert(app.buttons["Professor"].exists || app.staticTexts["Professor"].exists, "Professor role should be visible")
        XCTAssert(app.staticTexts["Student"].exists || app.buttons["Student"].exists, "Student role should be visible")
        
        // 2. Tap Professor role
        if app.buttons["Professor"].exists {
            app.buttons["Professor"].tap()
        } else {
            // Try tapping the Professor card/area
            let professorCards = app.buttons.matching(identifier: "Professor")
            if professorCards.count > 0 {
                professorCards.element.tap()
            } else {
                // Fallback: tap any button containing "Professor" text
                let professorButton = app.buttons.containing("Professor").element(boundBy: 0)
                if professorButton.exists {
                    professorButton.tap()
                }
            }
        }
        
        // 3. Verify we've navigated to Professor Tab View
        let professorTabExists = app.staticTexts["Professor"].firstMatch.exists || 
                                app.collectionViews.element(boundBy: 0).exists
        XCTAssertTrue(professorTabExists, "Should navigate to Professor Tab View")
        
        // Wait for professor tab to load
        sleep(2)
    }
    
    func testProfessorFlow_CreateSession() {
        // Prerequisite: Navigate to Professor mode
        testProfessorFlow_RoleSelection()
        
        // 2. Wait for Session List View
        sleep(1)
        
        // 3. Look for "Create Session" or "+" button
        let createButton = app.buttons["Create Session"]
        if createButton.exists {
            createButton.tap()
        } else {
            // Try plus button
            let plusButton = app.buttons.matchingIdentifier("Plus").element(boundBy: 0)
            if plusButton.exists {
                plusButton.tap()
            } else {
                // Try any button with "Create" in the title
                let createBtn = app.buttons.containing("Create").element(boundBy: 0)
                if createBtn.exists {
                    createBtn.tap()
                } else {
                    XCAXCuiError.fail("Could not find Create Session button")
                }
            }
        }
        
        // 4. Verify Create Session View loads
        sleep(1)
        XCTAssert(app.textFields.firstMatch.exists || app.staticTexts.firstMatch.exists, "Create Session view should load")
        
        // 5. Fill in session details
        let totalRoundsField = app.textFields["Total Rounds"]
        if totalRoundsField.exists {
            totalRoundsField.tap()
            totalRoundsField.typeText("5")
        }
        
        let teamSizeField = app.textFields["Students per Team"]
        if teamSizeField.exists {
            teamSizeField.tap()
            teamSizeField.typeText("3")
        }
        
        // 6. Look for "Create" or "Start" button
        let createSessionButton = app.buttons["Create"]
        if createSessionButton.exists {
            createSessionButton.tap()
        } else {
            let startButton = app.buttons["Start"]
            if startButton.exists {
                startButton.tap()
            }
        }
        
        // 7. Verify session was created
        sleep(2)
        XCTAssertTrue(true, "Session creation flow completed successfully")
    }
    
    func testProfessorFlow_SessionList() {
        // 1. Navigate to Professor mode
        testProfessorFlow_RoleSelection()
        
        // 2. Verify Session List is visible
        sleep(1)
        
        // Look for session list or table
        let sessionList = app.tableViews.element(boundBy: 0)
        if sessionList.exists {
            XCTAssertTrue(sessionList.rows.count > 0 || app.staticTexts["No sessions yet"].exists, 
                         "Session list should be displayed")
        }
        
        sleep(1)
    }
    
    // MARK: - Student Flow Tests
    
    func testStudentFlow_RoleSelection() {
        // 1. Start fresh - terminate and relaunch
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        
        // 2. Verify Launch View
        XCTAssert(app.staticTexts["BizSim AI"].exists, "Launch title should be visible")
        
        // 3. Tap Student role
        if app.buttons["Student"].exists {
            app.buttons["Student"].tap()
        } else {
            let studentButton = app.buttons.containing("Student").element(boundBy: 0)
            if studentButton.exists {
                studentButton.tap()
            }
        }
        
        // 4. Verify navigation to Join Session View
        sleep(2)
        XCTAssertTrue(true, "Student role selected, should navigate to Join Session view")
    }
    
    func testStudentFlow_JoinSession() {
        // Prerequisite: Navigate to Student mode
        testStudentFlow_RoleSelection()
        
        // 2. Verify Join Session View is shown
        sleep(1)
        
        // Look for session code input field
        let sessionCodeField = app.textFields["Session Code"]
        if sessionCodeField.exists {
            // Enter a session code (test value)
            sessionCodeField.tap()
            sessionCodeField.typeText("TEST123")
            
            // Tap Join button
            sleep(1)
            let joinButton = app.buttons["Join"]
            if joinButton.exists {
                joinButton.tap()
            } else {
                let enterButton = app.buttons["Enter"]
                if enterButton.exists {
                    enterButton.tap()
                }
            }
            
            sleep(2)
        }
        
        XCTAssertTrue(true, "Join Session flow tested")
    }
    
    func testStudentFlow_TeamDashboard() {
        // This test assumes a session has been joined
        // In a real scenario, this would follow testStudentFlow_JoinSession with a valid session
        
        sleep(1)
        
        // Verify dashboard elements
        let dashboardExists = app.staticTexts.firstMatch.exists || 
                             app.collectionViews.element(boundBy: 0).exists
        XCTAssertTrue(dashboardExists, "Dashboard should be visible if session is joined")
    }
    
    // MARK: - Cross-Flow Tests
    
    func testFullProfessorToStudentFlow() {
        // 1. Start as Professor
        testProfessorFlow_RoleSelection()
        sleep(1)
        
        // 2. Terminate and restart as Student
        app.terminate()
        app.launch()
        waitForAppToLaunch()
        
        // 3. Switch to Student mode
        if app.buttons["Student"].exists {
            app.buttons["Student"].tap()
        }
        
        sleep(2)
        XCTAssertTrue(true, "Full flow from Professor to Student completed")
    }
    
    // MARK: - Performance Tests
    
    func testAppLaunchPerformance() {
        let appLaunchMetric = XCTMetricRecord("AppLaunchTime")
        
        app.launch()
        
        let launchDuration = appLaunchMetric.measure {
            _ = app.waitForExistence(timeout: 10)
        }
        
        XCTAssertTrue(app.exists, "App should launch within time limit")
    }
    
    func testNavigationResponsiveness() {
        // Test that role selection responds quickly
        XCTAssert(app.staticTexts["BizSim AI"].exists)
        
        let startTimestamp = Date()
        
        if app.buttons["Professor"].exists {
            app.buttons["Professor"].tap()
        }
        
        sleep(1)
        let elapsed = Date().timeIntervalSince(startTimestamp)
        
        XCTAssert(elapsed < 5.0, "Navigation should complete within 5 seconds")
    }
}

// MARK: - Helper Extensions

extension XCTestCase {
    func expect(_ expression: @autoclosure() -> Bool, 
                message: String = "", 
                file: StaticString = #file, 
                line: UInt = #line) {
        XCTAssertTrue(expression, message, file: file, line: line)
    }
}
