package com.bizsimai.android.data

import com.bizsimai.android.BuildConfig
import com.bizsimai.android.network.*

class BizSimRepository(private val api: BizSimApi) {
    companion object {
        fun create(token: String? = null, baseUrl: String = BuildConfig.BIZSIMAI_BASE_URL) =
            BizSimRepository(ApiFactory.create(baseUrl, token))
    }

    suspend fun health(): Boolean = api.health().isSuccessful

    suspend fun login(username: String, password: String) =
        api.login(LoginRequest(username = username, password = password))

    suspend fun loginWithGoogle(idToken: String) =
        api.login(LoginRequest(provider = "google", id_token = idToken))

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