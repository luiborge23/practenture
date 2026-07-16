import XCTest
@testable import BizSimAI

/// Explicitly opt-in smoke coverage for a deliberately provisioned backend.
/// Normal simulator/unit-test runs skip this class and remain hermetic.
@MainActor
final class LiveBackendDeviceTests: XCTestCase {
    private var environment: [String: String] { ProcessInfo.processInfo.environment }

    private func requireLiveBackend() throws -> (code: String, teamName: String) {
        try XCTSkipUnless(
            environment["RUN_LIVE_BACKEND_DEVICE_TESTS"] == "1",
            "Set RUN_LIVE_BACKEND_DEVICE_TESTS=1 with LIVE_BACKEND_SESSION_CODE and LIVE_BACKEND_TEAM_NAME to run live smoke tests."
        )
        guard let code = environment["LIVE_BACKEND_SESSION_CODE"], !code.isEmpty,
              let teamName = environment["LIVE_BACKEND_TEAM_NAME"], !teamName.isEmpty else {
            throw XCTSkip("Live backend session/team fixtures were not supplied.")
        }
        return (code, teamName)
    }

    func testJoinSubmitAndStatusAgainstProvisionedBackend() async throws {
        let fixture = try requireLiveBackend()
        let service = NetworkService.shared
        let studentID = environment["LIVE_BACKEND_STUDENT_ID"] ?? "xctest-live-device"

        let join = try await service.joinSession(
            code: fixture.code,
            teamName: fixture.teamName,
            studentId: studentID
        )
        XCTAssertFalse(join.teamId.isEmpty)

        let decision = PlayerDecision(teamId: UUID(), round: 1)
        XCTAssertTrue(decision.isValid, decision.validationErrors.joined(separator: ", "))
        try await service.submitDecision(
            code: fixture.code,
            round: 1,
            decision: decision,
            backendTeamId: join.teamId
        )

        let status = try await service.getSessionStatus(code: fixture.code)
        XCTAssertEqual(status.code, fixture.code)
    }
}
