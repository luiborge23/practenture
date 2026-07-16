"""
BizSimAI Simulation Engine

Pure Python simulation engine — deterministic, mirrors the Swift implementation.
All random noise uses a seeded RNG for reproducibility.

This version matches iOS SimulationEngine.swift formulas EXACTLY:
- S/Q rating with ratcheting (0.4*prev + 0.6*new)
- Competitive attractiveness demand model (share allocation)
- Tiered credit rating interest rates
- 10-component image rating scorecard
- Ratcheting investor targets (base * 1.06^round)
- Per-channel social media factors
- Private label allocation (lowest bid wins)
- Market-based buyback/issuance pricing
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

from models import (
    CelebrityEndorsement,
    CreditRating,
    DeliveryTime,
    FulfillmentMethod,
    InfluencerTier,
    MaterialsQuality,
    PlayerDecision,
    RoundResult,
    SessionConfiguration,
    SocialMediaBudget,
    TeamConfig,
)

# ── Constants (must match iOS exactly) ──────────────────────────────────────

PRICE_ELASTICITY = 1.5
SQ_WEIGHT = 1.2
STORAGE_COST_PER_UNIT = 1.50
BASE_REJECTION_RATE = 0.12
BASE_WAGE_BASELINE = 25000.0
NOISE_AMPLITUDE = 0.05
BASE_STOCK_TARGET = 25.0
TARGET_RATCHET_RATE = 0.06
BASE_EPSTARGET = 2.0
BASE_ROETARGET = 0.15
BASE_IMAGE_TARGET = 50.0
BASE_INTEREST_RATE = 0.06
OVERTIME_COST_PREMIUM = 1.5
OUTLETS_WEIGHT = 0.3
ADVERTISING_WEIGHT = 0.6

# Channel share weights (for total demand calculation)
WHOLESALE_SHARE = 0.50
AMAZON_SHARE = 0.20
INTERNET_SHARE = 0.15
PRIVATE_LABEL_SHARE = 0.15

# ── Helper Functions ────────────────────────────────────────────────────────


class SwiftSeededRandomGenerator:
    """Python port of SimulationEngine.swift's wrapping 64-bit LCG."""

    _MASK = (1 << 64) - 1

    def __init__(self, seed: int):
        self.state = seed & self._MASK

    def next(self) -> int:
        self.state = (
            self.state * 6364136223846793005 + 1442695040888963407
        ) & self._MASK
        return self.state

    def next_double(self) -> float:
        return (self.next() >> 11) / float(1 << 53)

    def uniform(self, lower: float, upper: float) -> float:
        return lower + (upper - lower) * self.next_double()


def _add_noise(rng: Any, value: float, amplitude: float = NOISE_AMPLITUDE) -> float:
    """Add deterministic noise to a value."""
    if rng is None:
        return value
    noise_factor = 1.0 + rng.uniform(-amplitude, amplitude)
    return value * noise_factor


def compute_total_market_demand(
    config: SessionConfiguration, round_num: int, rng: Any
) -> float:
    """Exact Swift total-demand formula, including growth cap and market noise."""
    demand_growth = min(2.0, 1.0 + 0.05 * round_num)
    base_demand = (
        config.baseMarketDemand
        * config.marketType.demand_multiplier
        * demand_growth
    )
    return _add_noise(rng, base_demand, config.marketType.volatility)


def compute_awareness_score(
    advertising_budget: float,
    tiktok_budget: float,
    instagram_budget: float,
    youtube_budget: float,
) -> float:
    """Exact Swift awareness formula on its 0...1 scale."""
    social_media_budget = tiktok_budget + instagram_budget + youtube_budget
    return min(1.0, (advertising_budget + social_media_budget) / 25000.0)


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _safe_div(numerator: float, denominator: float, default: float = 1.0) -> float:
    """Safe division that returns default if denominator is zero."""
    return numerator / max(denominator, 1e-10) if denominator != 0 else default


# ── S/Q Rating (iOS lines 951-968) ─────────────────────────────────────────

def compute_sq_rating(
    materials_quality: MaterialsQuality,
    styling_budget: float,
    models_offered: int,
    cumulative_tqm: float,
    best_practices: float,
    training_hours: float,
    previous_sq: float,
) -> float:
    """
    Compute S/Q rating with ratcheting.
    iOS: 0.4 * previousSQ + 0.6 * newSQ
    where newSQ = 3.0 + materials.sqBonus + styling + models + TQM + bestPractices + training
    """
    new_sq = 3.0 + materials_quality.sq_bonus
    new_sq += _clamp(math.log(1 + styling_budget / 3000) / math.log(5), 0, 2.0)
    new_sq += _clamp(models_offered * 0.3, 0, 1.5)
    new_sq += _clamp(math.log(1 + cumulative_tqm / 5000) / math.log(10), 0, 1.5)
    new_sq += _clamp(best_practices / 5000, 0, 0.5)
    new_sq += _clamp(training_hours / 80.0, 0, 0.5)

    blended = 0.4 * previous_sq + 0.6 * new_sq
    return _clamp(blended, 1.0, 10.0)


# ── Rejection Rate (iOS lines 973-986) ─────────────────────────────────────

def compute_rejection_rate(
    cumulative_tqm: float,
    training_hours: float,
    incentive_pay: float,
    best_practices: float,
) -> float:
    """
    Compute rejection rate based on TQM, training, incentive pay, best practices.
    iOS: base 12%, reduced by each factor with specific caps.
    """
    rate = 0.12
    rate -= _clamp(cumulative_tqm / 200000, 0, 0.04)
    rate -= _clamp(training_hours / 100.0 * 0.03, 0, 0.03)
    rate -= _clamp(incentive_pay / 2.0 * 0.02, 0, 0.02)
    rate -= _clamp(best_practices / 5000 * 0.02, 0, 0.02)
    return _clamp(rate, 0.01, 0.50)


# ── Demand Model (iOS lines 145-213) ───────────────────────────────────────

def _compute_social_media_demand_boost(
    tiktok_budget: float,
    instagram_budget: float,
    youtube_budget: float,
    influencer_tier: InfluencerTier,
) -> float:
    """
    Compute social media demand boost factor.
    iOS lines 148-170: per-channel factors * influencer factor.
    """
    tiktok_factor = 1.0 + _clamp(tiktok_budget / 15000 * 0.08, 0, 0.08)
    instagram_factor = 1.0 + _clamp(instagram_budget / 15000 * 0.06, 0, 0.06)
    youtube_factor = 1.0 + _clamp(youtube_budget / 15000 * 0.05, 0, 0.05)

    # Influencer count estimate
    total_smb = tiktok_budget + instagram_budget + youtube_budget
    if total_smb <= 0:
        est_influencer_count = 0
    else:
        if influencer_tier == InfluencerTier.none:
            est_influencer_count = 0
        elif influencer_tier == InfluencerTier.nano:
            est_influencer_count = max(1, int(total_smb / 1000))
        elif influencer_tier == InfluencerTier.micro:
            est_influencer_count = max(1, int(total_smb / 5000))
        elif influencer_tier == InfluencerTier.macro:
            est_influencer_count = max(1, int(total_smb / 20000))
        elif influencer_tier == InfluencerTier.mega:
            est_influencer_count = max(1, int(total_smb / 60000))
        else:
            est_influencer_count = 0

    # Diminishing returns: sqrt(count)
    influencer_count_factor = max(1, math.sqrt(est_influencer_count))
    influencer_factor = (
        1.0 + influencer_tier.engagement_rate * influencer_tier.reach_multiplier * 0.1 * influencer_count_factor
    )

    return tiktok_factor * instagram_factor * youtube_factor * influencer_factor


def _compute_wholesale_attractiveness(
    sq: float,
    avg_sq: float,
    effective_price: float,
    avg_effective_price: float,
    advertising_budget: float,
    avg_advertising: float,
    retail_outlets: int,
    celebrity_endorsement: CelebrityEndorsement,
    reputation: float,
    delivery_time: DeliveryTime,
    social_media_boost: float,
    rng: random.Random | None = None,
) -> float:
    """Compute wholesale channel attractiveness (iOS lines 172-186)."""
    # Match Swift: rebates may exceed price, but elasticity must never receive
    # a negative base (which would produce a complex number in Python).
    price_attract = _safe_div(max(avg_effective_price, 1.0), max(effective_price, 1.0)) ** PRICE_ELASTICITY
    sq_attract = _safe_div(sq, max(avg_sq, 1.0)) ** SQ_WEIGHT
    ad_attract = _safe_div(max(advertising_budget, 100), max(avg_advertising, 100)) ** ADVERTISING_WEIGHT
    outlet_factor = 1.0 + retail_outlets / 100.0 * OUTLETS_WEIGHT
    endorse_factor = celebrity_endorsement.demand_boost
    reputation_factor = 0.7 + 0.6 * reputation
    delivery_factor = delivery_time.demand_boost

    attractiveness = (
        price_attract * sq_attract * ad_attract
        * outlet_factor * endorse_factor * reputation_factor * delivery_factor
        * social_media_boost
    )

    if rng is not None:
        attractiveness = _add_noise(rng, attractiveness)

    return attractiveness


def _compute_internet_attractiveness(
    sq: float,
    avg_sq: float,
    price: float,
    avg_price: float,
    advertising_budget: float,
    avg_advertising: float,
    celebrity_endorsement: CelebrityEndorsement,
    reputation: float,
    free_shipping_threshold: float,
    social_media_boost: float,
    rng: random.Random | None = None,
) -> float:
    """Compute internet channel attractiveness (iOS lines 188-197)."""
    price_attract = _safe_div(max(avg_price, 1.0), max(price, 1.0)) ** (PRICE_ELASTICITY * 0.9)
    sq_attract = _safe_div(sq, max(avg_sq, 1.0)) ** (SQ_WEIGHT * 1.1)
    ad_attract = _safe_div(max(advertising_budget, 100), max(avg_advertising, 100)) ** ADVERTISING_WEIGHT
    endorse_factor = celebrity_endorsement.demand_boost
    reputation_factor = 0.7 + 0.6 * reputation

    # Free shipping boost: lower threshold = more attractive (baseline $100)
    free_ship_boost = 1.0 + _clamp((100 - free_shipping_threshold) / 200.0, 0, 1.0)

    attractiveness = (
        price_attract * sq_attract * ad_attract
        * endorse_factor * reputation_factor * free_ship_boost
        * social_media_boost
    )

    if rng is not None:
        attractiveness = _add_noise(rng, attractiveness)

    return attractiveness


def _compute_amazon_attractiveness(
    sq: float,
    avg_sq: float,
    price: float,
    avg_price: float,
    amazon_ad_budget: float,
    fulfillment_method: FulfillmentMethod,
    social_media_boost: float,
    rng: random.Random | None = None,
) -> float:
    """Compute Amazon channel attractiveness (iOS lines 199-213)."""
    amazon_referral_rate = 0.15
    effective_price = price * (1.0 - amazon_referral_rate)
    avg_effective_price = avg_price * (1.0 - amazon_referral_rate)

    price_attract = _safe_div(max(avg_effective_price, 1.0), max(effective_price, 1.0)) ** (PRICE_ELASTICITY * 0.8)
    review_proxy = _safe_div(sq, max(avg_sq, 1.0)) ** (SQ_WEIGHT * 1.2)
    ad_boost = 1.0 + _clamp(amazon_ad_budget / 10000 * 0.15, 0, 0.15)
    buy_box = fulfillment_method.buy_box_multiplier
    trust = fulfillment_method.trust_multiplier

    attractiveness = price_attract * review_proxy * ad_boost * buy_box * trust * social_media_boost

    if rng is not None:
        attractiveness = _add_noise(rng, attractiveness)

    return attractiveness


# ── Production Cost (iOS lines 294-338) ────────────────────────────────────

def compute_production_cost(
    quantity: int,
    materials_quality: MaterialsQuality,
    base_cost_per_unit: float,
    base_capacity: int,
    base_wage: float,
    incentive_pay: float,
    training_hours: float,
) -> Tuple[float, float, int]:
    """
    Compute production cost and unit cost.
    Returns (total_production_cost, unit_cost, workers_needed).

    iOS lines 294-338:
    - materialsCost = baseCostPerUnit * costMultiplier
    - regularUnits = min(grossProduction, baseCapacity)
    - overtimeUnits = max(0, grossProduction - baseCapacity)
    - workersNeeded = max(1, grossProduction / 10)
    """
    materials_cost_per_unit = base_cost_per_unit * materials_quality.cost_multiplier

    regular_units = min(quantity, base_capacity)
    overtime_units = max(0, quantity - base_capacity)

    regular_prod_cost = materials_cost_per_unit * regular_units
    overtime_prod_cost = materials_cost_per_unit * OVERTIME_COST_PREMIUM * overtime_units

    total_prod_cost = regular_prod_cost + overtime_prod_cost
    unit_cost = _safe_div(total_prod_cost, quantity) if quantity > 0 else materials_cost_per_unit

    # Workforce costs
    workers_needed = max(1, quantity // 10)
    wage_cost = base_wage * workers_needed / 1000.0
    incentive_cost = incentive_pay * quantity
    training_cost = training_hours * 50.0 * workers_needed / 1000.0
    workforce_cost = wage_cost + incentive_cost + training_cost

    return total_prod_cost, unit_cost, workers_needed


# ── Private Label Allocation (iOS lines 219-228) ───────────────────────────

def allocate_private_label(
    teams: List[TeamConfig],
    decisions: Dict[str, PlayerDecision],
    private_label_demand: float,
) -> Dict[str, int]:
    """
    Allocate private label demand to lowest bidders.
    iOS lines 219-228: sorted by bid price ascending, lowest wins.
    """
    team_contexts = [(t, decisions[t.teamName]) for t in teams if t.teamName in decisions]
    private_label_bids = sorted(team_contexts, key=lambda x: x[1].privateLabelBidPrice)

    allocations: Dict[str, int] = {}
    remaining_pl = int(private_label_demand)

    for team, decision in private_label_bids:
        if remaining_pl <= 0:
            break
        allocation = min(decision.privateLabelMaxUnits, remaining_pl)
        allocations[team.teamName] = allocation
        remaining_pl -= allocation

    return allocations


# ── Image Rating (iOS lines 433-447) ───────────────────────────────────────

def compute_image_rating(
    sq: float,
    advertising_budget: float,
    csr_investment: float,
    celebrity_endorsement: CelebrityEndorsement,
    models_offered: int,
    training_hours: float,
    instagram_budget: float,
    tiktok_budget: float,
    youtube_budget: float,
    influencer_tier: InfluencerTier,
) -> float:
    """
    Compute 10-component image rating (iOS lines 433-447).
    """
    sq_contrib = sq * 5.0
    ad_contrib = _clamp(advertising_budget / 2000.0 * 5, 0, 15)
    csr_contrib = _clamp(csr_investment / 2000.0 * 5, 0, 15)
    endorse_contrib = celebrity_endorsement.image_boost
    models_contrib = _clamp(models_offered * 2, 0, 10)
    workforce_contrib = _clamp(training_hours / 40.0 * 5, 0, 5)
    instagram_contrib = _clamp(instagram_budget / 10000 * 8, 0, 8)
    tiktok_contrib = _clamp(tiktok_budget / 10000 * 4, 0, 4)
    youtube_contrib = _clamp(youtube_budget / 10000 * 5, 0, 5)
    influencer_contrib = influencer_tier.image_boost

    return _clamp(
        sq_contrib + ad_contrib + csr_contrib + endorse_contrib
        + models_contrib + workforce_contrib
        + instagram_contrib + tiktok_contrib + youtube_contrib + influencer_contrib,
        0,
        100,
    )


# ── Credit Rating (iOS lines 427-431) ──────────────────────────────────────

def compute_credit_rating(
    debt_to_equity: float,
    interest_coverage: float,
    cash_ratio: float,
) -> CreditRating:
    """Compute credit rating from financials (iOS lines 427-431)."""
    return CreditRating.from_financials(debt_to_equity, interest_coverage, cash_ratio)


# ── Stock Price (iOS lines 450-464) ────────────────────────────────────────

def compute_stock_price(
    eps: float,
    roe: float,
    dividends_per_share: float,
    credit_rating: CreditRating,
    shares_issued: int,
    shares_outstanding: float,
    previous_stock_price: float,
    round_num: int,
    rng: random.Random | None = None,
) -> float:
    """
    Compute stock price using iOS formula (lines 450-464).
    epsGrowthFactor * roeFactor * (1 + dividendYield) * creditFactor * dilutionPenalty
    Then blend 40% previous + 60% new (for round > 1).
    """
    eps_growth_factor = max(0.5, 1.0 + eps / max(abs(BASE_EPSTARGET), 0.01))
    roe_factor = max(0.5, 1.0 + roe)

    # Dividend yield based on previous stock price
    dividend_yield = dividends_per_share / max(1, previous_stock_price)

    credit_factor = credit_rating.investor_score / 20.0

    # Dilution penalty
    if shares_issued > 0:
        dilution_penalty = max(0.85, 1.0 - shares_issued / max(1, shares_outstanding) * 0.5)
    else:
        dilution_penalty = 1.0

    # Raw stock price with noise
    raw_stock_price = max(
        1,
        BASE_STOCK_TARGET * eps_growth_factor * roe_factor
        * (1 + dividend_yield) * credit_factor * dilution_penalty
        * (1.0 + (rng.uniform(-0.03, 0.03) if rng else 0)),
    )

    # Blend with previous price to dampen volatility (40% previous, 60% new)
    if round_num > 1:
        stock_price = 0.4 * previous_stock_price + 0.6 * raw_stock_price
    else:
        stock_price = raw_stock_price

    return _clamp(stock_price, 1.0, 500.0)


# ── Investor Scorecard (iOS lines 467-479) ─────────────────────────────────

def compute_investor_scorecard(
    eps: float,
    roe: float,
    stock_price: float,
    image_rating: float,
    credit_rating: CreditRating,
    round_num: int,
) -> Dict[str, float]:
    """
    Compute investor scorecard with ratcheting targets (iOS lines 467-479).
    Each component worth 0-20 points (total 100).
    Targets ratchet: base * 1.06^round.
    """
    ratchet_multiplier = (1.0 + TARGET_RATCHET_RATE) ** round_num

    eps_target = BASE_EPSTARGET * ratchet_multiplier
    roe_target = BASE_ROETARGET * ratchet_multiplier
    stock_target = BASE_STOCK_TARGET * ratchet_multiplier
    image_target = _clamp(BASE_IMAGE_TARGET * (1.0 + 0.03 * round_num), 0, 90)

    eps_score = _clamp(20 * eps / max(eps_target, 0.01), 0, 20)
    roe_score = _clamp(20 * roe / max(roe_target, 0.001), 0, 20)
    stock_price_score = _clamp(20 * stock_price / max(stock_target, 1), 0, 20)
    image_score = _clamp(20 * image_rating / max(image_target, 1), 0, 20)
    credit_score = credit_rating.investor_score

    total = eps_score + roe_score + stock_price_score + image_score + credit_score

    return {
        "epsScore": round(eps_score, 2),
        "roeScore": round(roe_score, 2),
        "stockPriceScore": round(stock_price_score, 2),
        "imageScore": round(image_score, 2),
        "creditScore": round(credit_score, 2),
        "totalScore": round(_clamp(total, 0.0, 100.0), 2),
    }


# ── Customer Satisfaction (iOS lines 413-416) ──────────────────────────────

def compute_customer_satisfaction(
    sq: float,
    wholesale_price: float,
    avg_wholesale_price: float,
    total_sold: float,
    total_demand_for_team: float,
    reputation: float,
) -> float:
    """Compute customer satisfaction (iOS lines 413-416)."""
    price_fairness = _clamp(_safe_div(avg_wholesale_price, max(wholesale_price, 1)), 0, 1.0)
    supply_adequacy = _clamp(_safe_div(total_sold, max(total_demand_for_team, 1)), 0, 1.0)

    return _clamp(
        0.35 * (sq / 10.0)
        + 0.3 * price_fairness
        + 0.2 * supply_adequacy
        + 0.15 * reputation,
        0,
        1.0,
    )


# ── AI Team Decision Generator ─────────────────────────────────────────────

def generate_ai_decision(
    team_id: str,
    round_num: int,
    seed: int,
    strategy: str = "balanced",
) -> PlayerDecision:
    """Generate a deterministic AI team decision based on strategy."""
    rng = random.Random(seed + round_num * 1000 + hash(team_id) % 10000)

    if strategy == "aggressive":
        wholesale_price = 22.0 + rng.uniform(0, 3)
        internet_price = 24.0 + rng.uniform(0, 3)
        amazon_price = 26.0 + rng.uniform(0, 3)
        materials_quality = MaterialsQuality.standard
        styling_budget = 100000 + rng.uniform(0, 50000)
        models_offered = 4 + int(rng.uniform(0, 3))
        tqm_investment = 50000 + rng.uniform(0, 100000)
        best_practices_investment = rng.uniform(0, 2000)
        training_hours = rng.uniform(0, 20)
        base_wage = 22000 + rng.uniform(0, 3000)
        advertising_budget = 150000 + rng.uniform(0, 100000)
        retail_outlets = int(rng.uniform(0, 10))
        celebrity_endorsement = CelebrityEndorsement.local
        delivery_time = DeliveryTime.standard
        influencer_tier = InfluencerTier.micro
        social_media_budget = rng.uniform(0, 30000)
        tiktok_budget = rng.uniform(0, 15000)
        instagram_budget = rng.uniform(0, 15000)
        youtube_budget = rng.uniform(0, 10000)
        amazon_ad_budget = rng.uniform(0, 5000)
        private_label_bid_price = 12.0 + rng.uniform(0, 3)
        private_label_max_units = int(rng.uniform(500, 2000))
        free_shipping_threshold = rng.uniform(75, 125)
    elif strategy == "quality":
        wholesale_price = 32.0 + rng.uniform(0, 5)
        internet_price = 35.0 + rng.uniform(0, 5)
        amazon_price = 38.0 + rng.uniform(0, 5)
        materials_quality = MaterialsQuality.superior
        styling_budget = 300000 + rng.uniform(0, 200000)
        models_offered = 8 + int(rng.uniform(0, 5))
        tqm_investment = 150000 + rng.uniform(0, 100000)
        best_practices_investment = rng.uniform(2000, 5000)
        training_hours = rng.uniform(30, 80)
        base_wage = 28000 + rng.uniform(0, 3000)
        advertising_budget = 100000 + rng.uniform(0, 50000)
        retail_outlets = int(rng.uniform(5, 15))
        celebrity_endorsement = CelebrityEndorsement.national
        delivery_time = DeliveryTime.rush
        influencer_tier = InfluencerTier.macro
        social_media_budget = rng.uniform(20000, 50000)
        tiktok_budget = rng.uniform(5000, 20000)
        instagram_budget = rng.uniform(10000, 30000)
        youtube_budget = rng.uniform(5000, 20000)
        amazon_ad_budget = rng.uniform(5000, 15000)
        private_label_bid_price = 18.0 + rng.uniform(0, 4)
        private_label_max_units = int(rng.uniform(1000, 3000))
        free_shipping_threshold = rng.uniform(50, 100)
    elif strategy == "lowcost":
        wholesale_price = 18.0 + rng.uniform(0, 3)
        internet_price = 20.0 + rng.uniform(0, 3)
        amazon_price = 22.0 + rng.uniform(0, 3)
        materials_quality = MaterialsQuality.standard
        styling_budget = rng.uniform(0, 50000)
        models_offered = int(rng.uniform(2, 5))
        tqm_investment = rng.uniform(0, 80000)
        best_practices_investment = rng.uniform(0, 1000)
        training_hours = rng.uniform(0, 15)
        base_wage = 18000 + rng.uniform(0, 3000)
        advertising_budget = 50000 + rng.uniform(0, 50000)
        retail_outlets = int(rng.uniform(0, 8))
        celebrity_endorsement = CelebrityEndorsement.none
        delivery_time = DeliveryTime.standard
        influencer_tier = InfluencerTier.none
        social_media_budget = rng.uniform(0, 15000)
        tiktok_budget = rng.uniform(0, 8000)
        instagram_budget = rng.uniform(0, 5000)
        youtube_budget = rng.uniform(0, 3000)
        amazon_ad_budget = rng.uniform(0, 2000)
        private_label_bid_price = 10.0 + rng.uniform(0, 2)
        private_label_max_units = int(rng.uniform(1000, 3000))
        free_shipping_threshold = rng.uniform(100, 150)
    elif strategy == "premium":
        wholesale_price = 45.0 + rng.uniform(0, 5)
        internet_price = 50.0 + rng.uniform(0, 5)
        amazon_price = 55.0 + rng.uniform(0, 5)
        materials_quality = MaterialsQuality.superior
        styling_budget = 400000 + rng.uniform(0, 200000)
        models_offered = 10 + int(rng.uniform(0, 5))
        tqm_investment = 200000 + rng.uniform(0, 100000)
        best_practices_investment = rng.uniform(3000, 6000)
        training_hours = rng.uniform(50, 100)
        base_wage = 30000 + rng.uniform(0, 4000)
        advertising_budget = 120000 + rng.uniform(0, 50000)
        retail_outlets = int(rng.uniform(8, 20))
        celebrity_endorsement = CelebrityEndorsement.global_
        delivery_time = DeliveryTime.rush
        influencer_tier = InfluencerTier.mega
        social_media_budget = rng.uniform(30000, 60000)
        tiktok_budget = rng.uniform(10000, 25000)
        instagram_budget = rng.uniform(15000, 35000)
        youtube_budget = rng.uniform(10000, 25000)
        amazon_ad_budget = rng.uniform(10000, 25000)
        private_label_bid_price = 20.0 + rng.uniform(0, 5)
        private_label_max_units = int(rng.uniform(500, 2000))
        free_shipping_threshold = rng.uniform(30, 80)
    else:  # balanced
        wholesale_price = 28.0 + rng.uniform(0, 4)
        internet_price = 30.0 + rng.uniform(0, 4)
        amazon_price = 32.0 + rng.uniform(0, 4)
        materials_quality = MaterialsQuality.standard
        styling_budget = 200000 + rng.uniform(0, 150000)
        models_offered = 6 + int(rng.uniform(0, 4))
        tqm_investment = 80000 + rng.uniform(0, 70000)
        best_practices_investment = rng.uniform(1000, 3000)
        training_hours = rng.uniform(15, 50)
        base_wage = 25000 + rng.uniform(0, 2000)
        advertising_budget = 80000 + rng.uniform(0, 50000)
        retail_outlets = int(rng.uniform(3, 12))
        celebrity_endorsement = rng.choice([
            CelebrityEndorsement.none,
            CelebrityEndorsement.local,
            CelebrityEndorsement.national,
        ])
        delivery_time = rng.choice([DeliveryTime.standard, DeliveryTime.rush])
        influencer_tier = rng.choice([
            InfluencerTier.none,
            InfluencerTier.nano,
            InfluencerTier.micro,
        ])
        social_media_budget = rng.uniform(5000, 30000)
        tiktok_budget = rng.uniform(0, 15000)
        instagram_budget = rng.uniform(0, 15000)
        youtube_budget = rng.uniform(0, 12000)
        amazon_ad_budget = rng.uniform(0, 8000)
        private_label_bid_price = 15.0 + rng.uniform(0, 4)
        private_label_max_units = int(rng.uniform(800, 2500))
        free_shipping_threshold = rng.uniform(60, 120)

    incentive_pay = rng.uniform(0, 2000)
    training_budget = rng.uniform(0, 80000)
    production_quantity = int(rng.uniform(5000, 15000))
    overtime_percent = int(rng.uniform(0, 25))
    csr_investment = rng.uniform(0, 50000)
    dividends_per_share = rng.uniform(0, 2.0)
    new_loan_amount = rng.uniform(0, 100000)
    shares_buyback = int(rng.uniform(0, 1000))
    shares_issued = int(rng.uniform(0, 500))
    mail_in_rebate = rng.uniform(0, 3)

    return PlayerDecision(
        wholesalePrice=round(wholesale_price, 2),
        internetPrice=round(internet_price, 2),
        amazonPrice=round(amazon_price, 2),
        materialsQuality=materials_quality,
        stylingBudget=round(styling_budget, 2),
        modelsOffered=models_offered,
        tqmInvestment=round(tqm_investment, 2),
        bestPracticesInvestment=round(best_practices_investment, 2),
        trainingHours=round(training_hours, 2),
        baseWage=round(base_wage, 2),
        incentivePay=round(incentive_pay, 2),
        advertisingBudget=round(advertising_budget, 2),
        retailOutlets=retail_outlets,
        celebrityEndorsement=celebrity_endorsement,
        deliveryTime=delivery_time,
        mailInRebate=round(mail_in_rebate, 2),
        tiktokBudget=round(tiktok_budget, 2),
        instagramBudget=round(instagram_budget, 2),
        youtubeBudget=round(youtube_budget, 2),
        socialMediaBudget=SocialMediaBudget(tiktok=tiktok_budget, instagram=instagram_budget, youtube=youtube_budget),
        influencerTier=influencer_tier,
        privateLabelBidPrice=round(private_label_bid_price, 2),
        privateLabelMaxUnits=private_label_max_units,
        freeShippingThreshold=round(free_shipping_threshold, 2),
        amazonAdBudget=round(amazon_ad_budget, 2),
        fulfillmentMethod=rng.choice([FulfillmentMethod.fba, FulfillmentMethod.fbm]),
        sharesBuyback=shares_buyback,
        sharesIssued=shares_issued,
        dividendsPerShare=round(dividends_per_share, 2),
        newLoanAmount=round(new_loan_amount, 2),
        csrInvestment=round(csr_investment, 2),
    )


# ── Main Round Processing (iOS processRound structure) ─────────────────────

def process_round(
    config: SessionConfiguration,
    teams: List[TeamConfig],
    decisions: Dict[str, PlayerDecision],
    round_num: int,
    team_states: Dict[str, Dict[str, Any]],
    rng: Any = None,
) -> Tuple[List[RoundResult], Dict[str, Dict[str, Any]]]:
    """
    Process one round of the simulation for all teams.

    Matches iOS processRound structure:
    1. Generate AI decisions for teams without human decisions
    2. Compute S/Q ratings with ratcheting
    3. Compute rejection rates
    4. Compute social media demand boosts
    5. Compute competitive attractiveness for each channel
    6. Allocate private label demand (lowest bid wins)
    7. Compute results for each team (revenue, costs, financials)
    8. Update team states

    Args:
        config: Session configuration
        teams: List of team configurations
        decisions: Dict of team_id -> PlayerDecision
        round_num: Current round number (1-based)
        team_states: Dict of team_id -> cumulative state tracking
        rng: Random instance for noise (for determinism)

    Returns:
        (list of RoundResult, updated team_states)
    """
    if rng is None:
        # Swift seeds each round with randomSeed &+ round.
        rng = SwiftSeededRandomGenerator(config.randomSeed + round_num)

    # Step 1: Require every human decision and generate missing AI decisions.
    # The API exposes this as a 409; this invariant also protects direct engine
    # callers from silently dropping a human team from competition.
    missing_human_teams = sorted(
        team.teamName
        for team in teams
        if not team.isAI and team.teamName not in decisions
    )
    if missing_human_teams:
        raise ValueError(
            f"Missing decisions from teams: {', '.join(missing_human_teams)}"
        )

    all_decisions: Dict[str, PlayerDecision] = {}
    for team in teams:
        tid = team.teamName  # Use team name as teamId
        if tid in decisions:
            all_decisions[tid] = decisions[tid]
        elif team.isAI:
            strategy = team.aiStrategy or "balanced"
            all_decisions[tid] = generate_ai_decision(
                tid, round_num, config.randomSeed, strategy
            )

    valid_teams = [t for t in teams if t.teamName in all_decisions]
    n = len(valid_teams)
    if n == 0:
        return [], team_states

    # Step 2: Compute S/Q ratings with ratcheting (iOS lines 951-968)
    team_sq: Dict[str, float] = {}
    for team in valid_teams:
        tid = team.teamName
        d = all_decisions[tid]
        prev_state = team_states.get(tid, {})
        previous_sq = prev_state.get("sqRating", 5.0)

        cumulative_tqm = prev_state.get("cumulativeTQM", 0.0) + d.tqmInvestment
        sq = compute_sq_rating(
            materials_quality=d.materialsQuality,
            styling_budget=d.stylingBudget,
            models_offered=d.modelsOffered,
            cumulative_tqm=cumulative_tqm,
            best_practices=d.bestPracticesInvestment,
            training_hours=d.trainingHours,
            previous_sq=previous_sq,
        )
        team_sq[tid] = sq

    # Step 3: Compute rejection rates (iOS lines 973-986)
    team_rejection_rates: Dict[str, float] = {}
    for team in valid_teams:
        tid = team.teamName
        d = all_decisions[tid]
        prev_state = team_states.get(tid, {})
        cumulative_tqm = prev_state.get("cumulativeTQM", 0.0) + d.tqmInvestment

        rate = compute_rejection_rate(
            cumulative_tqm=cumulative_tqm,
            training_hours=d.trainingHours,
            incentive_pay=d.incentivePay,
            best_practices=d.bestPracticesInvestment,
        )
        team_rejection_rates[tid] = rate

    # Swift draws market-demand noise before any per-team attractiveness noise.
    total_market_demand = compute_total_market_demand(config, round_num, rng)

    # Step 4: Compute social media demand boosts (iOS lines 148-170)
    team_social_boosts: Dict[str, float] = {}
    for team in valid_teams:
        tid = team.teamName
        d = all_decisions[tid]
        boost = _compute_social_media_demand_boost(
            tiktok_budget=d.tiktokBudget,
            instagram_budget=d.instagramBudget,
            youtube_budget=d.youtubeBudget,
            influencer_tier=d.influencerTier,
        )
        team_social_boosts[tid] = boost

    # Step 5: Compute competitor averages for each channel
    avg_w_price = sum(all_decisions[t.teamName].wholesalePrice for t in valid_teams) / n
    avg_i_price = sum(all_decisions[t.teamName].internetPrice for t in valid_teams) / n
    avg_a_price = sum(all_decisions[t.teamName].amazonPrice for t in valid_teams) / n
    avg_sq = sum(team_sq[t.teamName] for t in valid_teams) / n
    avg_advertising = sum(all_decisions[t.teamName].advertisingBudget for t in valid_teams) / n
    avg_rebate = sum(all_decisions[t.teamName].mailInRebate for t in valid_teams) / n

    # Step 6: Compute attractiveness for each team in each channel
    wholesale_attractivities: Dict[str, float] = {}
    internet_attractivities: Dict[str, float] = {}
    amazon_attractivities: Dict[str, float] = {}

    for team in valid_teams:
        tid = team.teamName
        d = all_decisions[tid]
        sq = team_sq[tid]
        boost = team_social_boosts[tid]

        # Wholesale attractiveness (iOS lines 172-186)
        effective_price = d.wholesalePrice - d.mailInRebate * 0.6
        avg_effective_price = avg_w_price - avg_rebate * 0.6
        wholesale_attractivities[tid] = _compute_wholesale_attractiveness(
            sq=sq,
            avg_sq=avg_sq,
            effective_price=effective_price,
            avg_effective_price=avg_effective_price,
            advertising_budget=d.advertisingBudget,
            avg_advertising=avg_advertising,
            retail_outlets=d.retailOutlets,
            celebrity_endorsement=d.celebrityEndorsement,
            reputation=team_states.get(tid, {}).get("reputation", 0.5),
            delivery_time=d.deliveryTime,
            social_media_boost=boost,
            rng=rng,
        )

        # Internet attractiveness (iOS lines 188-197)
        internet_attractivities[tid] = _compute_internet_attractiveness(
            sq=sq,
            avg_sq=avg_sq,
            price=d.internetPrice,
            avg_price=avg_i_price,
            advertising_budget=d.advertisingBudget,
            avg_advertising=avg_advertising,
            celebrity_endorsement=d.celebrityEndorsement,
            reputation=team_states.get(tid, {}).get("reputation", 0.5),
            free_shipping_threshold=d.freeShippingThreshold,
            social_media_boost=boost,
            rng=rng,
        )

        # Amazon attractiveness (iOS lines 199-213)
        amazon_attractivities[tid] = _compute_amazon_attractiveness(
            sq=sq,
            avg_sq=avg_sq,
            price=d.amazonPrice,
            avg_price=avg_a_price,
            amazon_ad_budget=d.amazonAdBudget,
            fulfillment_method=d.fulfillmentMethod,
            social_media_boost=boost,
            rng=rng,
        )

    # Step 7: Total attractiveness per channel
    total_wholesale_attract = sum(wholesale_attractivities.values())
    total_internet_attract = sum(internet_attractivities.values())
    total_amazon_attract = sum(amazon_attractivities.values())

    # Step 8: Private label allocation (iOS lines 219-228). Competitive
    # attractiveness allocates each channel; it does not scale total demand.
    private_label_demand = total_market_demand * PRIVATE_LABEL_SHARE
    pl_allocations = allocate_private_label(teams, all_decisions, private_label_demand)

    # Step 9: Compute results for each team
    results: List[RoundResult] = []

    for team in valid_teams:
        tid = team.teamName
        d = all_decisions[tid]
        sq = team_sq[tid]
        rejection_rate = team_rejection_rates[tid]

        # Demand allocation by share of attractiveness (iOS lines 239-278)
        w_share = _safe_div(wholesale_attractivities.get(tid, 0), max(total_wholesale_attract, 0.001))
        i_share = _safe_div(internet_attractivities.get(tid, 0), max(total_internet_attract, 0.001))
        a_share = _safe_div(amazon_attractivities.get(tid, 0), max(total_amazon_attract, 0.001))

        # Total market demand per channel
        w_total_demand = total_market_demand * WHOLESALE_SHARE
        i_total_demand = total_market_demand * INTERNET_SHARE
        a_total_demand = total_market_demand * AMAZON_SHARE

        # Demand for this team per channel (Swift truncates to Int).
        w_demand = int(w_total_demand * w_share)
        i_demand = int(i_total_demand * i_share)
        a_demand = int(a_total_demand * a_share)

        # Private label allocation
        pl_demand = pl_allocations.get(tid, 0)

        # Production with rejection waste, capped by plant + overtime capacity.
        overtime_capacity = int(config.plantCapacity * d.overtimePercent / 100.0)
        total_capacity = config.plantCapacity + overtime_capacity
        gross_production = min(d.productionQuantity, total_capacity)
        rejected_units = int(gross_production * rejection_rate)
        net_production = gross_production - rejected_units

        # Total available inventory
        prev_inv = team_states.get(tid, {}).get("inventory", 0.0)
        total_available = net_production + prev_inv

        # Total demand for this team (for satisfaction calc)
        total_demand_for_team = w_demand + i_demand + a_demand + pl_demand

        # Match Swift's integer sequential allocation: wholesale, Amazon,
        # internet, then private label.
        if total_available > 0 and total_demand_for_team > 0:
            cap_for_sale = min(total_demand_for_team, int(total_available))
            w_sold = min(w_demand, int(cap_for_sale * w_demand / total_demand_for_team))
            after_w = cap_for_sale - w_sold
            remaining_demand_3 = a_demand + i_demand + pl_demand
            a_sold = min(a_demand, int(after_w * a_demand / remaining_demand_3)) if remaining_demand_3 > 0 else 0
            after_wa = after_w - a_sold
            remaining_demand_2 = i_demand + pl_demand
            i_sold = min(i_demand, int(after_wa * i_demand / remaining_demand_2)) if remaining_demand_2 > 0 else 0
            pl_sold = min(pl_demand, cap_for_sale - w_sold - a_sold - i_sold)
        else:
            w_sold = 0
            i_sold = 0
            a_sold = 0
            pl_sold = 0

        total_sold = w_sold + i_sold + a_sold + pl_sold
        ending_inventory = max(0, total_available - total_sold)

        # ── COSTS (iOS lines 291-379) ──────────────────────────────────

        # Production costs
        base_capacity = config.plantCapacity or 10000
        total_prod_cost, unit_cost, workers_needed = compute_production_cost(
            quantity=gross_production,
            materials_quality=d.materialsQuality,
            base_cost_per_unit=config.baseCostPerUnit,
            base_capacity=base_capacity,
            base_wage=d.baseWage,
            incentive_pay=d.incentivePay,
            training_hours=d.trainingHours,
        )

        # Add fixed costs, styling, TQM, best practices to production cost
        total_prod_cost += config.fixedCostsPerRound + d.stylingBudget + d.tqmInvestment + d.bestPracticesInvestment

        # Workforce costs (iOS lines 334-338)
        wage_cost = d.baseWage * workers_needed / 1000.0
        incentive_cost = d.incentivePay * gross_production
        training_cost = d.trainingHours * 50.0 * workers_needed / 1000.0
        workforce_costs = wage_cost + incentive_cost + training_cost

        # Marketing costs (iOS line 341)
        marketing_cost = d.advertisingBudget + d.retailOutlets * 50

        # CSR cost
        csr_cost = d.csrInvestment

        # Endorsement cost (iOS line 343)
        endorse_cost = d.celebrityEndorsement.annual_cost

        # Social media & influencer costs (iOS lines 346-359)
        if d.socialMediaBudget.total <= 0:
            influencer_count = 0
        else:
            if d.influencerTier == InfluencerTier.none:
                influencer_count = 0
            elif d.influencerTier == InfluencerTier.nano:
                influencer_count = max(1, int(d.socialMediaBudget.total / 1000))
            elif d.influencerTier == InfluencerTier.micro:
                influencer_count = max(1, int(d.socialMediaBudget.total / 5000))
            elif d.influencerTier == InfluencerTier.macro:
                influencer_count = max(1, int(d.socialMediaBudget.total / 20000))
            elif d.influencerTier == InfluencerTier.mega:
                influencer_count = max(1, int(d.socialMediaBudget.total / 60000))
            else:
                influencer_count = 0

        influencer_cost = influencer_count * d.influencerTier.cost_per_influencer
        social_media_total_cost = d.socialMediaBudget.total + influencer_cost

        # Amazon fees (iOS lines 362-365)
        amazon_rev = a_sold * d.amazonPrice
        amazon_referral_fee = amazon_rev * 0.15
        amazon_fulfillment_fee = d.fulfillmentMethod.fee_per_unit * a_sold
        amazon_ad_cost = d.amazonAdBudget
        total_amazon_fees = amazon_referral_fee + amazon_fulfillment_fee + amazon_ad_cost

        # Rebate costs (iOS line 369)
        rebate_redemption_rate = 0.6
        rebate_costs = d.mailInRebate * rebate_redemption_rate * w_sold

        # Delivery costs (iOS line 372)
        delivery_costs = d.deliveryTime.cost_per_unit * w_sold

        # Internet shipping cost (iOS line 375)
        free_ship_rate = _clamp((100 - d.freeShippingThreshold) / 100.0, 0, 1.0)
        internet_shipping_cost = i_sold * 5.0 * free_ship_rate

        # Storage costs (iOS line 379)
        storage_costs = STORAGE_COST_PER_UNIT * ending_inventory

        # ── Financial costs (iOS lines 381-407) ────────────────────────

        # Interest with tiered credit rating (iOS line 382-383)
        prev_state = team_states.get(tid, {})
        debt = prev_state.get("debt", 0.0)

        # Swift charges interest using the rating entering the round.
        equity = prev_state.get("equity", config.initialEquity)
        cash = prev_state.get("cash", config.startingCash)
        previous_credit = prev_state.get("creditRating", CreditRating.a)
        if not isinstance(previous_credit, CreditRating):
            try:
                previous_credit = CreditRating(previous_credit)
            except ValueError:
                previous_credit = CreditRating[previous_credit]

        interest_rate = BASE_INTEREST_RATE * previous_credit.interest_rate_multiplier
        interest_expense = debt * interest_rate

        # Share changes (iOS lines 386-392)
        shares_outstanding = prev_state.get("sharesOutstanding", 10000.0)
        safe_buyback = min(d.sharesBuyback, max(0, shares_outstanding - 1))
        new_shares = max(1, shares_outstanding - safe_buyback + d.sharesIssued)

        # Dividends
        dividends_paid = d.dividendsPerShare * new_shares

        # Stock issuance proceeds (iOS line 391)
        cumulative_investor_score = prev_state.get("totalScore", 0)
        issuance_price = max(5, cumulative_investor_score / 2 if cumulative_investor_score > 0 else 15)
        issuance_proceeds = d.sharesIssued * issuance_price

        # Revenue (iOS line 394)
        wholesale_rev = w_sold * d.wholesalePrice
        internet_rev = i_sold * d.internetPrice
        private_label_rev = pl_sold * d.privateLabelBidPrice

        total_revenue = wholesale_rev + internet_rev + amazon_rev + private_label_rev

        # Total costs (iOS lines 395-397)
        total_costs = (
            total_prod_cost + workforce_costs + marketing_cost + csr_cost
            + endorse_cost + rebate_costs + delivery_costs + internet_shipping_cost
            + storage_costs + interest_expense + dividends_paid
            + social_media_total_cost + total_amazon_fees
        )

        # Profit (iOS line 399)
        profit = total_revenue - total_costs

        # Buyback cost (iOS line 403)
        prev_stock_for_buyback = prev_state.get("stockPrice", BASE_STOCK_TARGET)
        buyback_cost = safe_buyback * max(5, prev_stock_for_buyback)

        # Cash change (iOS line 404)
        cash_change = profit - buyback_cost + d.newLoanAmount + issuance_proceeds
        new_cash = cash + cash_change

        # Debt and equity (iOS lines 406-407)
        new_debt = max(0, debt + d.newLoanAmount)
        new_equity = max(1, equity + profit)

        # Swift derives the ending rating from post-profit financials.
        debt_to_equity = new_debt / new_equity if new_equity > 0 else 10
        interest_coverage = max(0, profit + interest_expense) / interest_expense if interest_expense > 0 else 20
        cash_ratio = new_cash / new_debt if new_debt > 0 else 5
        credit_rating = compute_credit_rating(debt_to_equity, interest_coverage, cash_ratio)

        # Market share (Swift: team units sold / total market demand).
        market_share = _safe_div(total_sold, max(total_market_demand, 1))

        # Customer satisfaction (iOS lines 413-416)
        prev_reputation = prev_state.get("reputation", 0.5)
        satisfaction = compute_customer_satisfaction(
            sq=sq,
            wholesale_price=d.wholesalePrice,
            avg_wholesale_price=avg_w_price,
            total_sold=total_sold,
            total_demand_for_team=total_demand_for_team,
            reputation=prev_reputation,
        )

        # Reputation EMA (iOS line 418)
        new_reputation = 0.7 * prev_reputation + 0.3 * satisfaction

        # Image rating (iOS lines 433-447)
        image_rating = compute_image_rating(
            sq=sq,
            advertising_budget=d.advertisingBudget,
            csr_investment=d.csrInvestment,
            celebrity_endorsement=d.celebrityEndorsement,
            models_offered=d.modelsOffered,
            training_hours=d.trainingHours,
            instagram_budget=d.instagramBudget,
            tiktok_budget=d.tiktokBudget,
            youtube_budget=d.youtubeBudget,
            influencer_tier=d.influencerTier,
        )
        awareness_score = compute_awareness_score(
            advertising_budget=d.advertisingBudget,
            tiktok_budget=d.tiktokBudget,
            instagram_budget=d.instagramBudget,
            youtube_budget=d.youtubeBudget,
        )

        # EPS and ROE (iOS lines 421-422)
        eps = profit / new_shares
        roe = profit / new_equity

        # Stock price (iOS lines 450-464)
        stock_price = compute_stock_price(
            eps=eps,
            roe=roe,
            dividends_per_share=d.dividendsPerShare,
            credit_rating=credit_rating,
            shares_issued=d.sharesIssued,
            shares_outstanding=shares_outstanding,
            previous_stock_price=prev_state.get("stockPrice", BASE_STOCK_TARGET),
            round_num=round_num,
            rng=rng,
        )

        # Investor scorecard (iOS lines 467-479)
        scorecard = compute_investor_scorecard(
            eps=eps,
            roe=roe,
            stock_price=stock_price,
            image_rating=image_rating,
            credit_rating=credit_rating,
            round_num=round_num,
        )

        # Cumulative profit
        cumulative_profit = prev_state.get("cumulativeProfit", 0.0) + profit

        # Cumulative TQM for ratcheting
        cumulative_tqm = prev_state.get("cumulativeTQM", 0.0) + d.tqmInvestment

        # Build result
        result = RoundResult(
            teamId=tid,
            round=round_num,
            revenue=round(total_revenue, 2),
            costs=round(total_costs, 2),
            profit=round(profit, 2),
            marketShare=round(market_share, 4),
            sqRating=round(sq, 2),
            reputation=round(new_reputation, 2),
            cumulativeProfit=round(cumulative_profit, 2),
            cash=round(new_cash, 2),
            inventory=round(ending_inventory, 2),
            equity=round(new_equity, 2),
            debt=round(new_debt, 2),
            sharesOutstanding=round(new_shares, 2),
            eps=round(eps, 4),
            roe=round(roe, 4),
            stockPrice=round(stock_price, 2),
            epsScore=scorecard["epsScore"],
            roeScore=scorecard["roeScore"],
            stockPriceScore=scorecard["stockPriceScore"],
            imageScore=scorecard["imageScore"],
            awarenessScore=round(awareness_score, 4),
            creditScore=scorecard["creditScore"],
            totalScore=scorecard["totalScore"],
            productionCost=round(total_prod_cost, 2),
            marketingCost=round(marketing_cost, 2),
            unitCost=round(unit_cost, 2),
            demand={
                "wholesale": round(w_sold, 2),
                "internet": round(i_sold, 2),
                "amazon": round(a_sold, 2),
                "privateLabel": round(pl_sold, 2),
                "totalSold": round(total_sold, 2),
            },
            # Per-channel revenue breakdown
            wholesaleRevenue=round(wholesale_rev, 2),
            internetRevenue=round(internet_rev, 2),
            amazonRevenue=round(amazon_rev, 2),
            privateLabelRevenue=round(private_label_rev, 2),
            # Per-channel units sold
            wholesaleUnitsSold=int(w_sold),
            internetUnitsSold=int(i_sold),
            amazonUnitsSold=int(a_sold),
            privateLabelUnitsSold=int(pl_sold),
            # Detailed cost breakdown
            workforceCosts=round(workforce_costs, 2),
            csrCosts=round(csr_cost, 2),
            endorsementCosts=round(endorse_cost, 2),
            rebateCosts=round(rebate_costs, 2),
            deliveryCosts=round(delivery_costs, 2),
            storageCosts=round(storage_costs, 2),
            interestExpense=round(interest_expense, 2),
            dividendsPaid=round(dividends_paid, 2),
            socialMediaCosts=round(social_media_total_cost, 2),
            amazonFees=round(total_amazon_fees, 2),
            # Display metrics
            imageRating=round(image_rating, 2),
            creditRating=credit_rating.value,
            customerSatisfaction=round(satisfaction, 4),
            rejectionRate=round(rejection_rate, 4),
        )
        results.append(result)

        # Update team state (iOS lines 405-407, plus new fields)
        team_states[tid] = {
            "cash": new_cash,
            "equity": new_equity,
            "debt": new_debt,
            "sharesOutstanding": new_shares,
            "cumulativeProfit": cumulative_profit,
            "inventory": ending_inventory,
            "stockPrice": stock_price,
            "eps": eps,
            "roe": roe,
            "reputation": new_reputation,
            "creditRating": credit_rating.name,
            "totalScore": scorecard["totalScore"],
            "sqRating": sq,
            "imageRating": image_rating,
            "awarenessScore": awareness_score,
            "cumulativeTQM": cumulative_tqm,
            "totalSold": total_sold,
        }

    return results, team_states
