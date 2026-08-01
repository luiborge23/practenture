package com.practenture.android.data

import com.practenture.android.BuildConfig
import com.practenture.android.network.*
import com.practenture.android.security.TokenStore

class PractentureRepository(private val api: PractentureApi) {
    companion object {
        fun create(token: String? = null, baseUrl: String = BuildConfig.PRACTENTURE_BASE_URL) =
            PractentureRepository(ApiFactory.create(baseUrl, token))

        fun create(tokenStore: TokenStore, baseUrl: String = BuildConfig.PRACTENTURE_BASE_URL) =
            PractentureRepository(ApiFactory.createAuthenticated(baseUrl, tokenStore))
    }

    suspend fun health(): Boolean = api.health().isSuccessful

    suspend fun login(username: String, password: String, mfaCode: String? = null) =
        api.login(LoginRequest(username = username, password = password, mfa_code = mfaCode))

    suspend fun loginWithGoogle(idToken: String, professorCode: String? = null) =
        api.login(LoginRequest(provider = "google", id_token = idToken, professor_code = professorCode))

    suspend fun changePassword(oldPassword: String, newPassword: String) =
        api.changePassword(ChangePasswordRequest(oldPassword, newPassword))

    suspend fun createSession(
        name: String,
        rounds: Int,
        aiCompetitors: Int,
        maxHumanTeams: Int,
        idempotencyKey: String,
    ) = api.createSession(
        idempotencyKey,
        CreateSessionRequest(
            SessionConfigurationRequest(name, rounds, aiCompetitors),
            maxHumanTeams = maxHumanTeams,
        ),
    )

    suspend fun dashboardSessions() = api.dashboardSessions()

    suspend fun startSession(code: String) = api.startSession(code.uppercase())

    suspend fun endSession(code: String) = api.endSession(code.uppercase())

    suspend fun announce(code: String, message: String, authorName: String) =
        api.createAnnouncement(code.uppercase(), CreateAnnouncementRequest(message, authorName))

    suspend fun announcements(code: String) = api.announcements(code.uppercase())

    suspend fun join(code: String, teamName: String, studentId: String) =
        api.join(code.uppercase(), JoinRequest(teamName, studentId))

    suspend fun submit(code: String, round: Int, backendTeamId: String, decision: PlayerDecision) =
        api.submitDecision(code.uppercase(), SubmitDecisionRequest(round, backendTeamId, decision))

    suspend fun status(code: String) = api.status(code.uppercase())

    suspend fun results(code: String) = api.results(code.uppercase())

    suspend fun leaderboard(code: String) = api.leaderboard(code.uppercase())

    suspend fun processRoundAsProfessor(code: String) = api.processRound(code.uppercase())
    // No client-side simulation and no advance endpoint: process_round computes and advances atomically.
}