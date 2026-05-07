// JoinSessionViewModel.swift
// BizSimAI
//
// ViewModel for the student join-session flow.
// Supports both cloud backend and local fallback.

import SwiftUI

@MainActor
@Observable
final class JoinSessionViewModel {

    var sessionCode: String = ""
    var teamName: String = ""
    var studentId: String = ""
    var isLoading: Bool = false
    var errorMessage: String?
    var joinedTeam: TeamConfig?
    var joinedTeamId: UUID? { joinedTeam?.id }
    var availableTeams: Int = 0

    var isValid: Bool {
        !sessionCode.isEmpty && sessionCode.count >= 4 &&
        !teamName.trimmingCharacters(in: .whitespaces).isEmpty
    }

    // MARK: - Join Session

    func join() async {
        guard isValid else {
            errorMessage = "Please enter a valid session code and team name."
            return
        }

        isLoading = true
        errorMessage = nil

        do {
            // Try backend join first
            let result = try await SyncService.shared.syncSessionJoin(
                sessionCode: sessionCode,
                teamName: teamName,
                studentId: studentId
            )

            joinedTeam = TeamConfig(
                id: UUID(uuidString: result.teamId) ?? UUID(),
                name: result.teamName,
                isAI: false,
                studentId: studentId
            )
            availableTeams = 1 // Will be updated by session monitor

        } catch {
            errorMessage = error.localizedDescription
            // Local fallback: just mark as joined
            joinedTeam = TeamConfig(id: UUID(), name: teamName, isAI: false, studentId: studentId)
            availableTeams = 1
        }

        isLoading = false
    }

    // MARK: - Verify Session Code

    func verifySessionCode() async {
        guard !sessionCode.isEmpty && sessionCode.count >= 4 else {
            availableTeams = 0
            return
        }

        do {
            let status = try await NetworkService.shared.getSessionStatus(code: sessionCode)
            availableTeams = status.totalTeams
        } catch {
            availableTeams = 0
        }
    }
}
