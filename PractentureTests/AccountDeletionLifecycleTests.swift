import XCTest
@testable import Practenture

@MainActor
final class AccountDeletionLifecycleTests: XCTestCase {
    func testResetToLaunchClearsProfessorAndGameplayState() {
        let state = AppState()
        let session = SimulationSession(config: SessionConfiguration())
        state.selectMode(.professor)
        state.activeSession = session
        state.gameController = GameController(session: session)
        state.professorSessions = [session]
        state.professorSelectedTab = "monitor"

        state.resetToLaunch()

        XCTAssertNil(state.currentMode)
        XCTAssertNil(state.activeSession)
        XCTAssertNil(state.gameController)
        XCTAssertTrue(state.professorSessions.isEmpty)
        XCTAssertEqual(state.professorSelectedTab, "sessions")
    }

    func testKeychainDeletionIsVerified() throws {
        let keychain = KeychainWrapper(service: "com.luisborges.practenture.tests.\(UUID().uuidString)")
        let key = "account-deletion-token"
        guard keychain.set("sensitive-token", forKey: key) else {
            throw XCTSkip("Unsigned XCTest host has no Keychain entitlement; verify on a signed device")
        }
        XCTAssertEqual(keychain.string(forKey: key), "sensitive-token")

        XCTAssertTrue(keychain.delete(forKey: key))
        XCTAssertNil(keychain.string(forKey: key))
        XCTAssertTrue(keychain.delete(forKey: key), "Deleting an already absent item is idempotent")
    }
}
