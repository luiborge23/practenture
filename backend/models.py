"""Pydantic models for BizSimAI — mirroring iOS SimulationModels.swift."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ── Enums ──────────────────────────────────────────────────────────────────

class SessionState(str, Enum):
    CREATING = "creating"
    ACTIVE = "active"
    COMPLETED = "completed"
    FINISHED = "finished"


class CelebrityType(str, Enum):
    NONE = "none"
    ATHLETE = "athlete"
    MUSICIAN = "musician"
    ACTOR = "actor"
    SOCIAL_INFLUENCER = "social_influencer"
    CEO = "ceo"


class FulfillmentMethod(str, Enum):
    FBM = "fbm"       # First Merchant/Business Model
    FBA = "fba"       # Amazon Fulfillment
    OWN_STORE = "own_store"


# ── Session Configuration ──────────────────────────────────────────────────

class SessionConfiguration(BaseModel):
    totalRounds: int = Field(default=20, ge=1, le=50)
    numberOfAICompetitors: int = Field(default=3, ge=0, le=20)
    randomSeed: int = Field(default=42)
    startingCash: float = Field(default=500000.0, gt=0)
    initialEquity: float = Field(default=300000.0, gt=0)
    plantCapacity: int = Field(default=10000, ge=100)
    maxOvertimePercent: int = Field(default=25, ge=0, le=50)
    minWage: float = Field(default=12000.0, gt=0)
    maxWage: float = Field(default=40000.0, gt=0)
    minDividend: float = Field(default=0.0, ge=0)
    maxDividend: float = Field(default=5.0, ge=0)


class TeamConfig(BaseModel):
    teamName: str
    isAI: bool = False
    aiStrategy: Optional[str] = None
    studentId: Optional[str] = None


# ── Player Decisions ───────────────────────────────────────────────────────

class SocialMediaBudget(BaseModel):
    tiktok: float = Field(default=0.0, ge=0)
    instagram: float = Field(default=0.0, ge=0)
    youtube: float = Field(default=0.0, ge=0)


class PlayerDecision(BaseModel):
    # Pricing
    wholesalePrice: float = Field(default=28.0, gt=0)
    internetPrice: float = Field(default=30.0, gt=0)
    amazonPrice: float = Field(default=32.0, gt=0)

    # Product decisions
    materialsQuality: float = Field(default=0.5, ge=0, le=1)
    stylingBudget: float = Field(default=100000.0, ge=0)
    numModels: int = Field(default=2, ge=0, le=20)

    # Quality & R&D
    tqmInvestment: float = Field(default=0.0, ge=0)
    rdInvestment: float = Field(default=0.0, ge=0)

    # Marketing & Advertising
    marketingInvestment: float = Field(default=150000.0, ge=0)
    advertisingBudget: float = Field(default=80000.0, ge=0)
    celebrityType: str = "none"
    socialMediaBudget: SocialMediaBudget = Field(default_factory=SocialMediaBudget)

    # HR decisions
    baseWage: float = Field(default=25000.0, gt=0)
    incentivePay: float = Field(default=0.0, ge=0)
    trainingBudget: float = Field(default=0.0, ge=0)

    # Production decisions
    productionQuantity: int = Field(default=8000, ge=0)
    overtimePercent: int = Field(default=0, ge=0, le=50)

    # CSR
    csrInvestment: float = Field(default=0.0, ge=0)

    # Financial decisions
    dividendsPerShare: float = Field(default=0.0, ge=0)
    newLoanAmount: float = Field(default=0.0, ge=0)
    sharesBuyback: int = Field(default=0, ge=0)
    sharesIssued: int = Field(default=0, ge=0)

    # Channel-specific
    retailOutlets: int = Field(default=0, ge=0, le=50)
    fulfillmentMethod: str = "fbm"
    internetPromotion: float = Field(default=0.0, ge=0, le=1)


# ── Simulation Results ─────────────────────────────────────────────────────

class RoundResult(BaseModel):
    teamId: str
    round: int
    revenue: float = 0.0
    costs: float = 0.0
    profit: float = 0.0
    marketShare: float = 0.0
    sqRating: float = 0.0
    reputation: float = 0.0
    cumulativeProfit: float = 0.0
    cash: float = 0.0
    inventory: float = 0.0
    equity: float = 0.0
    debt: float = 0.0
    sharesOutstanding: float = 0.0
    eps: float = 0.0
    roe: float = 0.0
    stockPrice: float = 0.0
    # Scorecard
    epsScore: float = 0.0
    roeScore: float = 0.0
    stockPriceScore: float = 0.0
    imageScore: float = 0.0
    creditScore: float = 0.0
    totalScore: float = 0.0
    # Detailed financials
    productionCost: float = 0.0
    marketingCost: float = 0.0
    unitCost: float = 0.0
    demand: Dict[str, float] = Field(default_factory=dict)  # channel → units


class InvestorScorecard(BaseModel):
    epsScore: float
    roeScore: float
    stockPriceScore: float
    imageScore: float
    creditScore: float
    totalScore: float


# ── Session ────────────────────────────────────────────────────────────────

class Session(BaseModel):
    id: str = ""
    code: str
    config: SessionConfiguration
    teams: List[TeamConfig] = []
    currentRound: int = 0
    state: SessionState = SessionState.CREATING
    results: Dict[int, List[RoundResult]] = {}
    created_by: str = ""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    maxHumanTeams: int = 30


# ── Announcements ──────────────────────────────────────────────────────────

class Announcement(BaseModel):
    id: str
    sessionId: str
    message: str
    authorId: str
    authorName: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# ── Leaderboard ────────────────────────────────────────────────────────────

class LeaderboardEntry(BaseModel):
    teamName: str
    studentName: Optional[str] = None
    totalScore: float = 0.0
    eps: float = 0.0
    roe: float = 0.0
    stockPrice: float = 0.0
    imageRating: float = 0.0
    creditRating: float = 0.0
    cumulativeProfit: float = 0.0
    marketShare: float = 0.0
    rank: int = 0


# ── Request / Response schemas ─────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    config: SessionConfiguration = Field(default_factory=SessionConfiguration)
    teams: List[TeamConfig] = []
    created_by: str = "professor"
    maxHumanTeams: int = 30
    classId: Optional[str] = None


class CreateSessionResponse(BaseModel):
    sessionId: str
    code: str


class JoinSessionRequest(BaseModel):
    teamName: str
    studentId: str


class JoinSessionResponse(BaseModel):
    teamId: str
    teamName: str
    round: int
    state: str


class SubmitDecisionRequest(BaseModel):
    round: int
    teamId: str
    decision: PlayerDecision


class SubmitDecisionResponse(BaseModel):
    status: str = "accepted"
    round: int
    teamId: str


class ProcessRoundResponse(BaseModel):
    round: int
    results: List[RoundResult]


class AdvanceResponse(BaseModel):
    round: int
    status: str
    results: Optional[List[RoundResult]] = None


class EndSessionResponse(BaseModel):
    status: str
    finalResults: Optional[List[RoundResult]] = None


class StatusResponse(BaseModel):
    sessionId: str
    code: str
    state: str
    currentRound: int
    totalRounds: int
    teamsSubmitted: int
    totalTeams: int


class CreateAnnouncementRequest(BaseModel):
    message: str
    authorId: str = "professor"
    authorName: str = "Professor"


class DashboardSessionResponse(BaseModel):
    code: str
    state: str
    currentRound: int = 0
    totalRounds: int = 20
    teamsCount: int = 0
    aiTeamsCount: int = 0
    totalTeams: int = 0
    totalSubmissions: int = 0
    lastRound: int = 0


class ErrorResponse(BaseModel):
    detail: str


# ── Multi-tenant Models ─────────────────────────────────────────────────────

class CreateClassRequest(BaseModel):
    name: str
    description: str = ""


class ClassResponse(BaseModel):
    id: str
    professor_user_id: str
    name: str
    description: str = ""
    join_code: str
    is_active: bool = True


class JoinClassRequest(BaseModel):
    join_code: str


class EnrollStudentResponse(BaseModel):
    status: str = "enrolled"
    class_id: str
    class_name: str
    message: Optional[str] = None


class StudentClassListResponse(BaseModel):
    classes: list[ClassResponse]


class ClassListResponse(BaseModel):
    classes: list[ClassResponse]


class ClassStudentsResponse(BaseModel):
    students: list[dict]


# ── Professor Code Models ──────────────────────────────────────────────────

class ProfessorCodeCreateRequest(BaseModel):
    university_name: str = ""
    notes: str = ""


class ProfessorCodeResponse(BaseModel):
    code: str
    university_name: str = ""
    notes: str = ""
    used: bool = False
    used_by: Optional[str] = None


class ProfessorCodeListResponse(BaseModel):
    codes: list[ProfessorCodeResponse]


class RedeemCodeRequest(BaseModel):
    code: str


class RedeemCodeResponse(BaseModel):
    status: str = "promoted"
    role: str = "professor"
    access_token: str = Field(alias="accessToken")
    token_type: str = Field(default="bearer", alias="tokenType")

    model_config = {"populate_by_name": True}


# ── Password Change Models ─────────────────────────────────────────────────

class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class ChangePasswordResponse(BaseModel):
    status: str = "changed"


# ── Password Reset Models ──────────────────────────────────────────────────

class ForgotPasswordRequest(BaseModel):
    email: str


class ForgotPasswordResponse(BaseModel):
    status: str = "email_sent"
    token: Optional[str] = None


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(alias="newPassword")

    model_config = {"populate_by_name": True}


class ResetPasswordResponse(BaseModel):
    status: str = "password_reset"


# ── Pre-create Professor Models ────────────────────────────────────────────

class PreCreateProfessorRequest(BaseModel):
    username: str
    password: str
    name: str = ""
    email: str = ""
    university_name: str = ""


class PreCreateProfessorResponse(BaseModel):
    status: str = "created"
    username: str
    professor_code: str
    message: str = ""


# ── AI Service Models ────────────────────────────────────────────────────────

class GenerateScenarioRequest(BaseModel):
    industry: str = "consumer_electronics"
    difficulty: str = "medium"  # easy, medium, hard
    round_num: int = 1
    total_rounds: int = 20


class ScenarioResponse(BaseModel):
    scenario: str
    source: str = "ai"  # "ai" or "fallback"


class ProvideFeedbackRequest(BaseModel):
    decision: Dict[str, Any]
    round_result: Dict[str, Any]
    context: str = ""


class FeedbackResponse(BaseModel):
    feedback: str
    source: str = "ai"


class GenerateHintRequest(BaseModel):
    current_state: Dict[str, Any]
    problem: str = ""


class HintResponse(BaseModel):
    hint: str
    source: str = "ai"


class GenerateInsightsRequest(BaseModel):
    session_results: List[Dict[str, Any]] = []
    team_count: int = 1


class InsightsResponse(BaseModel):
    insights: str
    source: str = "ai"


class AIStatusResponse(BaseModel):
    enabled: bool
    model: str
    region: str
