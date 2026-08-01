package com.practenture.android.network

import com.google.gson.JsonElement

data class HealthResponse(val status: String? = null)
data class LoginRequest(
    val provider: String = "password", val username: String? = null, val password: String? = null,
    val id_token: String? = null, val professor_code: String? = null, val mfa_code: String? = null
)
data class LoginResponse(
    val accessToken: String, val refreshToken: String? = null, val tokenType: String = "bearer",
    val role: String, val userId: String, val mfaRequired: Boolean = false,
    val mustChangePassword: Boolean = false, val professorCodeRequired: Boolean = false
)
data class RefreshTokenRequest(val refreshToken: String)
data class RefreshTokenResponse(val accessToken: String, val refreshToken: String)
data class ChangePasswordRequest(val old_password: String, val new_password: String)
data class ChangePasswordResponse(val status: String)
data class SocialMediaBudget(val tiktok: Double = 0.0, val instagram: Double = 0.0, val youtube: Double = 0.0)
data class PlayerDecision(
    val wholesalePrice: Double = 80.0, val internetPrice: Double = 90.0, val amazonPrice: Double = 85.0,
    val privateLabelBidPrice: Double = 45.0, val privateLabelMaxUnits: Int = 50, val amazonAdBudget: Double = 0.0,
    val materialsQuality: String = "standard", val stylingBudget: Double = 3000.0, val modelsOffered: Int = 3,
    val tqmInvestment: Double = 2000.0, val advertisingBudget: Double = 8000.0,
    val celebrityEndorsement: String = "none", val retailOutlets: Int = 20, val mailInRebate: Double = 0.0,
    val deliveryTime: String = "standard", val freeShippingThreshold: Double = 100.0,
    val tiktokBudget: Double = 0.0, val instagramBudget: Double = 0.0, val youtubeBudget: Double = 0.0,
    val influencerTier: String = "none", val baseWage: Double = 25000.0, val incentivePay: Double = 0.5,
    val trainingHours: Double = 20.0, val bestPracticesInvestment: Double = 1000.0,
    val productionQuantity: Int = 200, val overtimePercent: Double = 0.0, val csrInvestment: Double = 2000.0,
    val dividendsPerShare: Double = 0.5, val newLoanAmount: Double = 0.0, val sharesBuyback: Int = 0,
    val sharesIssued: Int = 0, val fulfillmentMethod: String = "fbm"
)
data class SubmitDecisionRequest(val round: Int, val teamId: String, val decision: PlayerDecision)
data class SubmitDecisionResponse(val status: String = "accepted", val round: Int, val teamId: String)
data class JoinRequest(val teamName: String, val studentId: String)
data class JoinResponse(val teamId: String, val teamName: String, val round: Int, val state: String)
data class SessionConfigurationRequest(
    val name: String,
    val totalRounds: Int,
    val numberOfAICompetitors: Int,
)
data class CreateSessionRequest(
    val config: SessionConfigurationRequest,
    val teams: List<Any> = emptyList(),
    val maxHumanTeams: Int,
    val scenarioId: String = "athletic-footwear-classic",
    val scenarioVersion: String = "1.0.0",
)
data class CreateSessionResponse(val sessionId: String, val code: String)
data class StartSessionResponse(val status: String, val sessionId: String, val code: String)
data class EndSessionResponse(val status: String)
data class DashboardSession(
    val code: String,
    val name: String,
    val state: String,
    val currentRound: Int,
    val totalRounds: Int,
)
data class DashboardSessionsResponse(val sessions: List<DashboardSession>)
data class CreateAnnouncementRequest(val message: String, val authorName: String)
data class CreateAnnouncementResponse(val status: String, val announcementId: String)
data class Announcement(
    val id: String,
    val sessionId: String,
    val message: String,
    val authorId: String,
    val authorName: String,
    val timestamp: String,
)
data class SessionStatus(
    val sessionId: String, val code: String, val state: String, val currentRound: Int,
    val totalRounds: Int, val teamsSubmitted: Int, val totalTeams: Int, val humanTeams: Int
)
data class RoundResult(
    val teamId: String, val round: Int, val revenue: Double = 0.0, val costs: Double = 0.0,
    val profit: Double = 0.0, val marketShare: Double = 0.0, val sqRating: Double = 0.0,
    val reputation: Double = 0.0, val awarenessScore: Double = 0.0, val cash: Double = 0.0,
    val inventory: Double = 0.0, val equity: Double = 0.0, val debt: Double = 0.0,
    val eps: Double = 0.0, val roe: Double = 0.0, val stockPrice: Double = 0.0,
    val totalScore: Double = 0.0, val demand: Map<String, Double> = emptyMap()
)
data class ProcessRoundResponse(val round: Int, val results: List<RoundResult>)
data class LeaderboardEntry(
    val rank: Int? = null, val teamId: String? = null, val teamName: String = "",
    val totalScore: Double = 0.0, val eps: Double = 0.0, val roe: Double = 0.0,
    val stockPrice: Double = 0.0, val imageRating: Double = 0.0, val marketShare: Double = 0.0
)
data class LeaderboardResponse(val sessionId: String, val round: Int, val leaderboard: List<LeaderboardEntry>)
typealias ResultsResponse = JsonElement
