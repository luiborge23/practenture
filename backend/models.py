"""Pydantic models for BizSimAI — mirroring iOS SimulationModels.swift."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, model_validator


# ── Enums ──────────────────────────────────────────────────────────────────

class SessionState(str, Enum):
    CREATING = "creating"
    ACTIVE = "active"
    COMPLETED = "completed"
    FINISHED = "finished"


# ── Configuration Enums ───────────────────────────────────────────────────

class MarketType(str, Enum):
    conservative = "conservative"
    moderate = "moderate"
    aggressive = "aggressive"

    @property
    def demand_multiplier(self) -> float:
        return {"conservative": 0.8, "moderate": 1.0, "aggressive": 1.3}[self.value]

    @property
    def volatility(self) -> float:
        return {"conservative": 0.05, "moderate": 0.10, "aggressive": 0.20}[self.value]


class AIDifficulty(str, Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class ScoringMetric(str, Enum):
    investorScore = "investor_score"
    cumulativeProfit = "cumulative_profit"
    revenue = "revenue"
    composite = "composite"


# ── Materials Quality ─────────────────────────────────────────────────────

class MaterialsQuality(str, Enum):
    standard = "standard"
    superior = "superior"

    @property
    def cost_multiplier(self) -> float:
        return {"standard": 1.0, "superior": 1.4}[self.value]

    @property
    def sq_bonus(self) -> float:
        return {"standard": 0.0, "superior": 2.0}[self.value]


# ── Celebrity Endorsement ────────────────────────────────────────────────

class CelebrityEndorsement(str, Enum):
    none = "none"
    local = "local"
    national = "national"
    global_ = "global"  # renamed from 'global' to avoid Python keyword

    @property
    def annual_cost(self) -> float:
        return {"none": 0, "local": 5_000, "national": 15_000, "global": 35_000}[self.value]

    @property
    def demand_boost(self) -> float:
        return {"none": 1.0, "local": 1.08, "national": 1.18, "global": 1.30}[self.value]

    @property
    def image_boost(self) -> float:
        return {"none": 0, "local": 3, "national": 8, "global": 15}[self.value]


# ── Delivery Time ────────────────────────────────────────────────────────

class DeliveryTime(str, Enum):
    standard = "standard"
    rush = "rush"

    @property
    def cost_per_unit(self) -> float:
        return {"standard": 0, "rush": 2.0}[self.value]

    @property
    def demand_boost(self) -> float:
        return {"standard": 1.0, "rush": 1.06}[self.value]


# ── Influencer Tier ──────────────────────────────────────────────────────

class InfluencerTier(str, Enum):
    none = "none"
    nano = "nano"       # 1K-10K followers, highest engagement
    micro = "micro"     # 10K-100K followers
    macro = "macro"     # 100K-1M followers
    mega = "mega"       # 1M+ followers, lowest engagement but max reach

    @property
    def cost_per_influencer(self) -> float:
        return {"none": 0, "nano": 300, "micro": 2_500, "macro": 15_000, "mega": 50_000}[self.value]

    @property
    def engagement_rate(self) -> float:
        return {"none": 0, "nano": 0.065, "micro": 0.04, "macro": 0.02, "mega": 0.01}[self.value]

    @property
    def reach_multiplier(self) -> float:
        return {"none": 0, "nano": 1.0, "micro": 5.0, "macro": 25.0, "mega": 100.0}[self.value]

    @property
    def image_boost(self) -> float:
        return {"none": 0, "nano": 1, "micro": 3, "macro": 6, "mega": 10}[self.value]


# ── Fulfillment Method ───────────────────────────────────────────────────

class FulfillmentMethod(str, Enum):
    fba = "fba"       # Fulfilled by Amazon — higher fees, higher Buy Box win rate
    fbm = "fbm"       # Fulfilled by Merchant — lower fees, lower visibility

    @property
    def fee_per_unit(self) -> float:
        return {"fba": 4.50, "fbm": 1.50}[self.value]

    @property
    def buy_box_multiplier(self) -> float:
        return {"fba": 1.25, "fbm": 0.85}[self.value]

    @property
    def trust_multiplier(self) -> float:
        return {"fba": 1.15, "fbm": 1.0}[self.value]


# ── Credit Rating ────────────────────────────────────────────────────────

class CreditRating(str, Enum):
    a_plus = "A+"
    a = "A"
    a_minus = "A-"
    b_plus = "B+"
    b = "B"
    b_minus = "B-"
    c_plus = "C+"
    c = "C"
    c_minus = "C-"

    @property
    def investor_score(self) -> float:
        return {
            "A+": 20, "A": 18, "A-": 16,
            "B+": 13, "B": 10, "B-": 7,
            "C+": 4, "C": 2, "C-": 0,
        }[self.value]

    @property
    def interest_rate_multiplier(self) -> float:
        return {
            "A+": 0.8, "A": 0.9, "A-": 1.0,
            "B+": 1.15, "B": 1.3, "B-": 1.5,
            "C+": 1.8, "C": 2.2, "C-": 3.0,
        }[self.value]

    @classmethod
    def from_financials(cls, debt_to_equity: float, interest_coverage: float, cash_ratio: float) -> "CreditRating":
        """Compute credit rating from financial ratios (iOS lines 427-431)."""
        # Exact Swift additive 100-point financial-health table.
        if debt_to_equity < 0.3:
            score = 40.0
        elif debt_to_equity < 0.5:
            score = 35.0
        elif debt_to_equity < 0.8:
            score = 25.0
        elif debt_to_equity < 1.2:
            score = 15.0
        else:
            score = 5.0

        if interest_coverage > 8:
            score += 35.0
        elif interest_coverage > 5:
            score += 30.0
        elif interest_coverage > 3:
            score += 20.0
        elif interest_coverage > 1.5:
            score += 10.0

        if cash_ratio > 0.5:
            score += 25.0
        elif cash_ratio > 0.3:
            score += 20.0
        elif cash_ratio > 0.15:
            score += 10.0

        if score >= 90:
            return cls.a_plus
        if score >= 80:
            return cls.a
        if score >= 70:
            return cls.a_minus
        if score >= 60:
            return cls.b_plus
        if score >= 50:
            return cls.b
        if score >= 40:
            return cls.b_minus
        if score >= 30:
            return cls.c_plus
        if score >= 15:
            return cls.c
        return cls.c_minus


# ── Session Configuration ─────────────────────────────────────────────────

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

    # iOS-mapped fields
    marketType: MarketType = Field(default=MarketType.moderate)
    aiDifficulty: AIDifficulty = Field(default=AIDifficulty.medium)
    scoringMetric: ScoringMetric = Field(default=ScoringMetric.investorScore)
    fixedCostsPerRound: float = Field(default=5000.0, gt=0)
    baseCostPerUnit: float = Field(default=30.0, gt=0)
    baseMarketDemand: int = Field(default=10000, ge=100)
    sharesOutstanding: int = Field(default=10000, ge=1)
    baseInterestRate: float = Field(default=0.06, gt=0)


# ── Team Config ───────────────────────────────────────────────────────────

class TeamConfig(BaseModel):
    teamName: str
    isAI: bool = False
    aiStrategy: Optional[str] = None
    studentId: Optional[str] = None


# ── Player Decisions ─────────────────────────────────────────────────────

class SocialMediaBudget(BaseModel):
    tiktok: float = Field(default=0.0, ge=0)
    instagram: float = Field(default=0.0, ge=0)
    youtube: float = Field(default=0.0, ge=0)

    @property
    def total(self) -> float:
        return self.tiktok + self.instagram + self.youtube


class PlayerDecision(BaseModel):
    @model_validator(mode="before")
    @classmethod
    def translate_legacy_payload(cls, value: Any) -> Any:
        """Translate the production iOS decision contract to modern fields."""
        if not isinstance(value, dict):
            return value

        data = dict(value)

        # The legacy client encoded quality on a 0...1 scale.  Its Swift
        # decoder used > 0.75 for superior and standard otherwise.
        quality = data.get("materialsQuality")
        if isinstance(quality, (int, float)) and not isinstance(quality, bool):
            data["materialsQuality"] = (
                MaterialsQuality.superior.value
                if quality > 0.75
                else MaterialsQuality.standard.value
            )

        # Modern values always win when a transition payload contains both.
        if "modelsOffered" not in data and "numModels" in data:
            # The legacy Swift decoder clamped the old count to at least one.
            data["modelsOffered"] = max(1, data["numModels"])

        if "celebrityEndorsement" not in data and "celebrityType" in data:
            # These are the exact mappings used by NetworkService.swift.
            celebrity_map = {
                "none": CelebrityEndorsement.none.value,
                "athlete": CelebrityEndorsement.local.value,
                "musician": CelebrityEndorsement.national.value,
                "actor": CelebrityEndorsement.global_.value,
            }
            legacy_celebrity = data["celebrityType"]
            if legacy_celebrity in celebrity_map:
                data["celebrityEndorsement"] = celebrity_map[legacy_celebrity]

        if "trainingHours" not in data and "trainingBudget" in data:
            # Legacy conversion used $50 per training hour.
            data["trainingHours"] = max(0.0, data["trainingBudget"] / 50.0)

        social = data.get("socialMediaBudget")
        if isinstance(social, SocialMediaBudget):
            social = social.model_dump()
        if isinstance(social, dict):
            for legacy_key, modern_key in (
                ("tiktok", "tiktokBudget"),
                ("instagram", "instagramBudget"),
                ("youtube", "youtubeBudget"),
            ):
                if modern_key not in data and legacy_key in social:
                    data[modern_key] = social[legacy_key]
        elif "socialMediaBudget" not in data:
            # Keep the compatibility object useful when modern flat budgets
            # are provided and the model is serialized back to JSON.
            data["socialMediaBudget"] = {
                "tiktok": data.get("tiktokBudget", 0.0),
                "instagram": data.get("instagramBudget", 0.0),
                "youtube": data.get("youtubeBudget", 0.0),
            }

        return data

    # ── Pricing (PricingDecision) ───────────────────────────────────────
    wholesalePrice: float = Field(default=80.0, gt=0)
    internetPrice: float = Field(default=90.0, gt=0)
    amazonPrice: float = Field(default=85.0, gt=0)
    privateLabelBidPrice: float = Field(default=45.0, ge=0)
    privateLabelMaxUnits: int = Field(default=50, ge=0)
    amazonAdBudget: float = Field(default=0.0, ge=0)

    # ── Product (ProductDecision) ───────────────────────────────────────
    materialsQuality: MaterialsQuality = Field(default=MaterialsQuality.standard)
    stylingBudget: float = Field(default=3000.0, ge=0)
    modelsOffered: int = Field(default=3, ge=1)  # renamed from numModels
    tqmInvestment: float = Field(default=2000.0, ge=0)

    # ── Marketing (MarketingDecision) ───────────────────────────────────
    advertisingBudget: float = Field(default=8000.0, ge=0)
    celebrityEndorsement: CelebrityEndorsement = Field(default=CelebrityEndorsement.none)
    retailOutlets: int = Field(default=20, ge=0)
    mailInRebate: float = Field(default=0.0, ge=0)
    deliveryTime: DeliveryTime = Field(default=DeliveryTime.standard)
    freeShippingThreshold: float = Field(default=100.0, ge=0)
    tiktokBudget: float = Field(default=0.0, ge=0)
    instagramBudget: float = Field(default=0.0, ge=0)
    youtubeBudget: float = Field(default=0.0, ge=0)
    influencerTier: InfluencerTier = Field(default=InfluencerTier.none)

    # ── Workforce (WorkforceDecision) ───────────────────────────────────
    baseWage: float = Field(default=25000.0, ge=0)
    incentivePay: float = Field(default=0.50, ge=0)  # per-unit incentive
    trainingHours: float = Field(default=20.0, ge=0)  # hours per worker
    bestPracticesInvestment: float = Field(default=1000.0, ge=0)

    # ── Production (ProductionDecision) ─────────────────────────────────
    productionQuantity: int = Field(default=200, ge=0)
    overtimePercent: float = Field(default=0.0, ge=0, le=20)

    # ── Finance (FinanceDecision) ───────────────────────────────────────
    csrInvestment: float = Field(default=2000.0, ge=0)
    dividendsPerShare: float = Field(default=0.50, ge=0)
    newLoanAmount: float = Field(default=0.0, ge=0)
    sharesBuyback: int = Field(default=0, ge=0)
    sharesIssued: int = Field(default=0, ge=0)

    # ── Legacy compatibility (keep for old iOS clients) ─────────────────
    numModels: int = Field(default=3, ge=0, le=20)  # deprecated → modelsOffered
    rdInvestment: float = Field(default=0.0, ge=0)  # not used in iOS engine
    marketingInvestment: float = Field(default=150000.0, ge=0)  # not used in iOS engine
    socialMediaBudget: SocialMediaBudget = Field(default_factory=SocialMediaBudget)  # legacy
    fulfillmentMethod: FulfillmentMethod = Field(default=FulfillmentMethod.fbm)  # Amazon channel
    internetPromotion: float = Field(default=0.0, ge=0, le=1)  # not used in iOS engine

    model_config = {"populate_by_name": True}


# ── Simulation Results ─────────────────────────────────────────────────────

class RoundResult(BaseModel):
    teamId: str
    round: int
    # Aggregate (unchanged)
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
    awarenessScore: float = 0.0
    creditScore: float = 0.0
    totalScore: float = 0.0
    # Detailed financials (existing)
    productionCost: float = 0.0
    marketingCost: float = 0.0
    unitCost: float = 0.0
    demand: Dict[str, float] = Field(default_factory=dict)  # channel → units
    # Per-channel revenue breakdown
    wholesaleRevenue: float = 0.0
    internetRevenue: float = 0.0
    amazonRevenue: float = 0.0
    privateLabelRevenue: float = 0.0
    # Per-channel units sold
    wholesaleUnitsSold: int = 0
    internetUnitsSold: int = 0
    amazonUnitsSold: int = 0
    privateLabelUnitsSold: int = 0
    # Detailed cost breakdown
    workforceCosts: float = 0.0
    csrCosts: float = 0.0
    endorsementCosts: float = 0.0
    rebateCosts: float = 0.0
    deliveryCosts: float = 0.0
    storageCosts: float = 0.0
    interestExpense: float = 0.0
    dividendsPaid: float = 0.0
    socialMediaCosts: float = 0.0
    amazonFees: float = 0.0
    # Display metrics (not previously in model)
    imageRating: float = 0.0
    creditRating: str = "A"
    customerSatisfaction: float = 0.0
    rejectionRate: float = 0.0


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

class TeamsResponse(BaseModel):
    sessionId: str
    teams: List[TeamConfig]


class SessionResultsResponse(BaseModel):
    sessionId: str
    results: Dict[str, List[RoundResult]]


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


class HealthConfigResponse(BaseModel):
    host: str
    port: int
    cors_origins: List[str]
    jwt_secret_configured: bool
    jwt_expiry_hours: str


class HealthResponse(BaseModel):
    status: str
    service: str
    config: HealthConfigResponse


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
    humanTeams: int = 0


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
