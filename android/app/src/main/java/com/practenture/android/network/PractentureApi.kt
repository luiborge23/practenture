package com.practenture.android.network

import retrofit2.Response
import retrofit2.http.*

interface PractentureApi {
    @GET("api/health") suspend fun health(): Response<HealthResponse>
    @POST("api/auth/login") suspend fun login(@Body request: LoginRequest): LoginResponse
    @PUT("api/sessions/{code}/join") suspend fun join(@Path("code") code: String, @Body request: JoinRequest): JoinResponse
    @POST("api/sessions/{code}/submit_decision") suspend fun submitDecision(@Path("code") code: String, @Body request: SubmitDecisionRequest): Response<SubmitDecisionResponse>
    @POST("api/sessions/{code}/process_round") suspend fun processRound(@Path("code") code: String): ProcessRoundResponse
    @GET("api/sessions/{code}/status") suspend fun status(@Path("code") code: String): SessionStatus
    @GET("api/sessions/{code}/results") suspend fun results(@Path("code") code: String): ResultsResponse
    @GET("api/sessions/{code}/leaderboard") suspend fun leaderboard(@Path("code") code: String): LeaderboardResponse
}
