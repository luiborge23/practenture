package com.practenture.android.network

import retrofit2.Response
import retrofit2.http.*

interface PractentureApi {
    @GET("api/health") suspend fun health(): Response<HealthResponse>
    @POST("api/auth/login") suspend fun login(@Body request: LoginRequest): LoginResponse
    @POST("api/auth/refresh") suspend fun refresh(@Body request: RefreshTokenRequest): RefreshTokenResponse
    @POST("api/professor/change-password") suspend fun changePassword(@Body request: ChangePasswordRequest): ChangePasswordResponse
    @POST("api/sessions") suspend fun createSession(
        @Header("Idempotency-Key") idempotencyKey: String,
        @Body request: CreateSessionRequest,
    ): CreateSessionResponse
    @POST("api/sessions/{code}/start") suspend fun startSession(@Path("code") code: String): StartSessionResponse
    @POST("api/sessions/{code}/end") suspend fun endSession(@Path("code") code: String): EndSessionResponse
    @GET("api/dashboard/sessions") suspend fun dashboardSessions(): DashboardSessionsResponse
    @POST("api/sessions/{code}/announcements") suspend fun createAnnouncement(
        @Path("code") code: String,
        @Body request: CreateAnnouncementRequest,
    ): CreateAnnouncementResponse
    @GET("api/sessions/{code}/announcements") suspend fun announcements(@Path("code") code: String): List<Announcement>
    @PUT("api/sessions/{code}/join") suspend fun join(@Path("code") code: String, @Body request: JoinRequest): JoinResponse
    @POST("api/sessions/{code}/submit_decision") suspend fun submitDecision(@Path("code") code: String, @Body request: SubmitDecisionRequest): Response<SubmitDecisionResponse>
    @POST("api/sessions/{code}/process_round") suspend fun processRound(@Path("code") code: String): ProcessRoundResponse
    @GET("api/sessions/{code}/status") suspend fun status(@Path("code") code: String): SessionStatus
    @GET("api/sessions/{code}/results") suspend fun results(@Path("code") code: String): ResultsResponse
    @GET("api/sessions/{code}/leaderboard") suspend fun leaderboard(@Path("code") code: String): LeaderboardResponse
}
