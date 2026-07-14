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

            // Backend uses team name as teamId (not a UUID). Store the raw teamId
            // string on TeamConfig so submit_decision can send it back correctly.
            let rawTeamId = result.teamId
            joinedTeam = TeamConfig(
                id: UUID(),  // local UUID for SwiftData
                name: result.teamName,
                isAI: false,
                studentId: studentId,
                backendTeamId: rawTeamId
            )

            // Fetch real session data from backend (config, teams, announcements)
            do {
                let session = try await NetworkService.shared.getSession(byCode: sessionCode)
                loadedSession = session
            } catch {
                loadedSession = nil
            }
            
            do {
                let teams = try await NetworkService.shared.getTeams(code: sessionCode)
                loadedTeams = teams
            } catch {
                loadedTeams = []
            }
            
            do {
                let announcements = try await SyncService.shared.syncAnnouncements(sessionCode: sessionCode)
                loadedAnnouncements = announcements
            } catch {
                loadedAnnouncements = []
            }

        } catch {
            errorMessage = error.localizedDescription
            // Local fallback: just mark as joined
            joinedTeam = TeamConfig(id: UUID(), name: teamName, isAI: false, studentId: studentId)
            availableTeams = 1
            loadedAnnouncements = []
        }

        isLoading = false
    }

    var loadedSession: SessionBackend?
    var loadedTeams: [TeamConfigBackend] = []
    var loadedAnnouncements: [AnnouncementBackend] = []

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
