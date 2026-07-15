"""
BizSimAI Simulation Engine

Pure Python simulation engine — deterministic, mirrors the Swift implementation.
All random noise uses a seeded RNG for reproducibility.
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

from models import (
    PlayerDecision,
    RoundResult,
    SessionConfiguration,
    SocialMediaBudget,
    TeamConfig,
)

# ── Constants ──────────────────────────────────────────────────────────────

PRICE_ELASTICITY = 1.5
SQ_WEIGHT = 1.2
STORAGE_COST_PER_UNIT = 1.50
BASE_REJECTION_RATE = 0.12        # 12% base defect rate
BASE_WAGE_BASELINE = 25000.0
NOISE_AMPLITUDE = 0.05            # 5% noise
BASE_STOCK_TARGET = 25.0
TARGET_GROWTH_RATE = 0.06         # 6% ratchet per round
OUTLETS_WEIGHT = 0.3
MARKETING_DIVISOR = 2000.0
MARKETING_MULTIPLIER = 5.0
FBA_FEE_RATE = 0.15              # Amazon FBA fee as % of price
FBM_FEE_RATE = 0.10              # FBM (own store) fee as % of price
INITIAL_STOCK_PRICE = 50.0       # Starting stock price

# Celebrity effect multipliers
CELEBRITY_MULTIPLIERS = {
    "none": 1.0,
    "athlete": 1.15,
    "musician": 1.12,
    "actor": 1.10,
    "social_influencer": 1.18,
    "ceo": 1.05,
}

# Social media multipliers (each channel contributes partially)
SOCIAL_MEDIA_CONTRIBUTION = 0.3  # Each channel contributes 30% of budget impact


def _add_noise(rng: random.Random, value: float) -> float:
    """Add deterministic noise to a value."""
    noise_factor = 1.0 + rng.uniform(-NOISE_AMPLITUDE, NOISE_AMPLITUDE)
    return value * noise_factor


def _clamp(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def _compute_rejection_rate(tqm: float, training: float) -> float:
    """Compute rejection rate based on TQM and training investments."""
    # TQM reduces rejection: each $100K of TQM reduces by ~1.1%
    tqm_reduction = min(tqm / 100000.0 * 0.011, 0.09)  # max 9% reduction from TQM
    # Training reduces rejection: each $50K of training reduces by ~0.9%
    training_reduction = min(training / 50000.0 * 0.009, 0.05)  # max 5% from training
    return max(BASE_REJECTION_RATE - tqm_reduction - training_reduction, 0.01)


def _compute_sq_rating(materials_quality: float, num_models: int, styling_budget: float) -> float:
    """Compute S/Q rating from 0.0 to 10.0."""
    base = materials_quality * 5.0  # 0-5 from materials
    models_bonus = min(num_models / 10.0 * 2.0, 2.0)  # up to 2 extra from models
    style_bonus = min(styling_budget / 500000.0 * 3.0, 3.0)  # up to 3 extra from styling
    sq = base + models_bonus + style_bonus
    return _clamp(sq, 0.0, 10.0)


def _compute_reputation(sq: float, tqm: float, csr: float, marketing: float) -> float:
    """Compute reputation from 0.0 to 10.0."""
    base = (sq / 10.0) * 4.0  # up to 4 from S/Q
    tqm_impact = min(tqm / 200000.0 * 2.0, 2.0)
    csr_impact = min(csr / 100000.0 * 2.0, 2.0)
    marketing_impact = min(marketing / 300000.0 * 2.0, 2.0)
    return _clamp(base + tqm_impact + csr_impact + marketing_impact, 0.0, 10.0)


def _compute_attractiveness(
    own_value: float,
    competitor_avg: float,
    elasticity: float,
    noise_rng: random.Random | None = None,
) -> float:
    """Compute attractiveness score: (own / competitor)^elasticity with optional noise."""
    if competitor_avg <= 0:
        competitor_avg = 1.0
    ratio = own_value / competitor_avg
    attractiveness = ratio ** elasticity
    if noise_rng is not None:
        attractiveness = _add_noise(noise_rng, attractiveness)
    return attractiveness


# ── Demand Computation ─────────────────────────────────────────────────────

def compute_wholesale_demand(
    base_cost: float,
    price: float,
    sq_rating: float,
    competitor_avg_price: float,
    competitor_avg_sq: float,
    marketing_budget: float,
    social_budget: SocialMediaBudget,
    retail_outlets: int,
    rng: random.Random | None = None,
) -> float:
    """
    Compute wholesale channel demand using elasticity model.
    Base demand ~10000 units.
    """
    base_demand = 10000.0

    price_attr = _compute_attractiveness(price, competitor_avg_price, PRICE_ELASTICITY, rng)
    sq_attr = _compute_attractiveness(sq_rating, competitor_avg_sq, SQ_WEIGHT, rng)

    marketing_influence = (marketing_budget / MARKETING_DIVISOR) * MARKETING_MULTIPLIER
    total_social = social_budget.tiktok + social_budget.instagram + social_budget.youtube
    social_influence = total_social * SOCIAL_MEDIA_CONTRIBUTION / MARKETING_DIVISOR * MARKETING_MULTIPLIER
    outlet_influence = retail_outlets * OUTLETS_WEIGHT / 10.0

    attractiveness = price_attr * sq_attr * (1.0 + marketing_influence + social_influence + outlet_influence)
    demand = base_demand * attractiveness
    demand = max(demand, 0.0)

    if rng is not None:
        demand = _add_noise(rng, demand)

    return demand


def compute_internet_demand(
    base_cost: float,
    price: float,
    sq_rating: float,
    competitor_avg_price: float,
    competitor_avg_sq: float,
    marketing_budget: float,
    social_budget: SocialMediaBudget,
    promotion_factor: float,
    rng: random.Random | None = None,
) -> float:
    """Compute internet channel demand with promotion multiplier."""
    base_demand = 5000.0

    price_attr = _compute_attractiveness(price, competitor_avg_price, PRICE_ELASTICITY, rng)
    sq_attr = _compute_attractiveness(sq_rating, competitor_avg_sq, SQ_WEIGHT, rng)

    marketing_influence = (marketing_budget / MARKETING_DIVISOR) * MARKETING_MULTIPLIER * 0.5
    total_social = social_budget.tiktok + social_budget.instagram + social_budget.youtube
    social_influence = total_social * SOCIAL_MEDIA_CONTRIBUTION / MARKETING_DIVISOR * MARKETING_MULTIPLIER

    promotion_multiplier = 1.0 + promotion_factor * 0.3

    attractiveness = price_attr * sq_attr * (1.0 + marketing_influence + social_influence) * promotion_multiplier
    demand = base_demand * attractiveness
    demand = max(demand, 0.0)

    if rng is not None:
        demand = _add_noise(rng, demand)

    return demand


def compute_amazon_demand(
    base_cost: float,
    price: float,
    sq_rating: float,
    competitor_avg_price: float,
    competitor_avg_sq: float,
    marketing_budget: float,
    social_budget: SocialMediaBudget,
    fulfillment: str,
    rng: random.Random | None = None,
) -> float:
    """Compute Amazon channel demand (FBA vs FBM fee differences)."""
    base_demand = 5000.0

    price_attr = _compute_attractiveness(price, competitor_avg_price, PRICE_ELASTICITY, rng)
    sq_attr = _compute_attractiveness(sq_rating, competitor_avg_sq, SQ_WEIGHT, rng)

    marketing_influence = (marketing_budget / MARKETING_DIVISOR) * MARKETING_MULTIPLIER * 0.3
    total_social = social_budget.tiktok + social_budget.instagram + social_budget.youtube
    social_influence = total_social * SOCIAL_MEDIA_CONTRIBUTION / MARKETING_DIVISOR * MARKETING_MULTIPLIER * 0.3

    # FBA provides slightly more visibility
    channel_bonus = 1.0 if fulfillment == "fba" else 1.0

    attractiveness = price_attr * sq_attr * (1.0 + marketing_influence + social_influence) * channel_bonus
    demand = base_demand * attractiveness
    demand = max(demand, 0.0)

    if rng is not None:
        demand = _add_noise(rng, demand)

    return demand


def compute_private_label_demand(
    base_cost: float,
    price: float,
    sq_rating: float,
    competitor_avg_price: float,
    competitor_avg_sq: float,
    rng: random.Random | None = None,
) -> float:
    """Compute private label demand (allocate remaining unsold inventory)."""
    base_demand = 2000.0

    price_attr = _compute_attractiveness(price, competitor_avg_price, PRICE_ELASTICITY, rng)
    sq_attr = _compute_attractiveness(sq_rating, competitor_avg_sq, SQ_WEIGHT, rng)

    attractiveness = price_attr * sq_attr
    demand = base_demand * attractiveness
    demand = max(demand, 0.0)

    if rng is not None:
        demand = _add_noise(rng, demand)

    return demand


# ── Production Cost ────────────────────────────────────────────────────────

def compute_production_cost(
    quantity: int,
    materials_quality: float,
    base_wage: float,
    incentive_pay: float,
    training_budget: float,
    overtime_percent: int,
    max_overtime: int,
    base_wage_baseline: float = BASE_WAGE_BASELINE,
) -> Tuple[float, float]:
    """
    Compute production cost and unit cost.
    Returns (total_production_cost, unit_cost).
    """
    # Labor cost per worker scales with wage relative to baseline
    wage_factor = base_wage / base_wage_baseline
    labor_cost_per_unit = 8.0 * wage_factor  # Base $8 labor per unit

    # Material cost scales with quality (0.0 to 1.0)
    material_cost_per_unit = 3.0 + materials_quality * 7.0

    # Overtime premium
    allowed_overtime = min(overtime_percent, max_overtime)
    overtime_factor = 1.0 + (allowed_overtime / 100.0) * 0.5

    # Training reduces unit cost slightly
    training_reduction = min(training_budget / 500000.0 * 0.15, 0.15)

    unit_cost = (material_cost_per_unit + labor_cost_per_unit) * overtime_factor * (1.0 - training_reduction)
    total_cost = unit_cost * quantity

    return total_cost, max(unit_cost, 0.01)


# ── Marketing & Advertising Cost ───────────────────────────────────────────

def compute_marketing_cost(
    marketing_investment: float,
    advertising_budget: float,
    celebrity_type: str,
    social_budget: SocialMediaBudget,
) -> float:
    """Total marketing spend."""
    celebrity_mult = CELEBRITY_MULTIPLIERS.get(celebrity_type, 1.0)
    social_total = social_budget.tiktok + social_budget.instagram + social_budget.youtube
    return marketing_investment + advertising_budget * celebrity_mult + social_total


# ── Financial Calculations ─────────────────────────────────────────────────

def compute_creditscore(
    debt: float,
    equity: float,
    interest_expense: float,
    cash: float,
) -> float:
    """
    Compute credit rating score (0-100).
    Based on D/E ratio, interest coverage, and cash ratio.
    """
    if equity <= 0:
        equity = 1.0
    if interest_expense <= 0:
        interest_expense = 1.0

    # Debt-to-equity ratio (lower is better)
    de_ratio = debt / equity
    de_score = max(0.0, 20.0 - de_ratio * 10.0)  # 0 D/E = 20 pts

    # Interest coverage (higher is better)
    interest_coverage = max(0.0, interest_expense * 5.0)  # Simplified
    ic_score = min(interest_coverage * 5.0, 20.0)

    # Cash ratio
    cash_ratio = cash / max(debt, 1.0)
    cash_score = min(cash_ratio * 10.0, 20.0)

    return _clamp(de_score + ic_score + cash_score, 0.0, 60.0)


def compute_investor_scorecard(
    eps: float,
    roe: float,
    stock_price: float,
    reputation: float,
    credit_rating: float,
    prev_eps: float,
    prev_roe: float,
    prev_stock_price: float,
    round_num: int,
) -> Dict[str, float]:
    """
    Compute investor scorecard. Each component worth 20 points (total 100).
    Targets ratchet by TARGET_GROWTH_RATE each round.
    """
    # EPS score: based on actual vs target
    target_eps = BASE_WAGE_BASELINE * (1 + TARGET_GROWTH_RATE) ** round_num * 0.001
    if prev_eps != 0:
        target_eps = abs(prev_eps) * (1 + TARGET_GROWTH_RATE)
    if target_eps <= 0:
        target_eps = 1.0
    # For negative EPS, score based on how close to zero (less negative = better)
    if eps < 0:
        eps_ratio = max(0, 1.0 + eps / max(abs(target_eps), 1.0))  # 0 to 1 for negative EPS
    else:
        eps_ratio = eps / target_eps if target_eps > 0 else 0
    eps_score = min(eps_ratio * 20.0, 20.0)

    # ROE score
    prev_roe = max(abs(prev_roe), 0.01)
    target_roe = prev_roe * (1 + TARGET_GROWTH_RATE)
    if roe < 0:
        roe_ratio = max(0, 1.0 + roe / max(abs(target_roe), 0.01))
    else:
        roe_ratio = max(abs(roe), 0) / target_roe if target_roe > 0 else 0
    roe_score = min(roe_ratio * 20.0, 20.0)

    # Stock price score
    prev_sp = max(abs(prev_stock_price), 1.0)
    target_sp = prev_sp * (1 + TARGET_GROWTH_RATE)
    sp_ratio = abs(stock_price) / target_sp if target_sp > 0 else 0
    sp_score = min(sp_ratio * 20.0, 20.0)

    # Image (reputation) score
    target_rep = 5.0 * (1 + TARGET_GROWTH_RATE) ** (round_num * 0.5)
    image_score = min((reputation / max(target_rep, 1.0)) * 20.0, 20.0)

    # Credit score
    credit_score = min((credit_rating / 100.0) * 20.0, 20.0)

    total = eps_score + roe_score + sp_score + image_score + credit_score

    return {
        "epsScore": round(eps_score, 2),
        "roeScore": round(roe_score, 2),
        "stockPriceScore": round(sp_score, 2),
        "imageScore": round(image_score, 2),
        "creditScore": round(credit_score, 2),
        "totalScore": round(_clamp(total, 0.0, 100.0), 2),
    }


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
        materials_quality = 0.3 + rng.uniform(0, 0.2)
        marketing_investment = 250000 + rng.uniform(0, 100000)
        advertising_budget = 150000 + rng.uniform(0, 100000)
        production_qty = 12000 + int(rng.uniform(0, 3000))
        tqm = rng.uniform(50000, 150000)
        rd = rng.uniform(80000, 150000)
        base_wage = 22000 + rng.uniform(0, 3000)
    elif strategy == "quality":
        wholesale_price = 32.0 + rng.uniform(0, 5)
        internet_price = 35.0 + rng.uniform(0, 5)
        amazon_price = 38.0 + rng.uniform(0, 5)
        materials_quality = 0.7 + rng.uniform(0, 0.3)
        marketing_investment = 150000 + rng.uniform(0, 50000)
        advertising_budget = 100000 + rng.uniform(0, 50000)
        production_qty = 8000 + int(rng.uniform(0, 2000))
        tqm = rng.uniform(150000, 250000)
        rd = rng.uniform(150000, 200000)
        styling_budget = 300000 + rng.uniform(0, 200000)
        num_models = 8 + int(rng.uniform(0, 5))
        base_wage = 28000 + rng.uniform(0, 3000)
    elif strategy == "lowcost":
        wholesale_price = 18.0 + rng.uniform(0, 3)
        internet_price = 20.0 + rng.uniform(0, 3)
        amazon_price = 22.0 + rng.uniform(0, 3)
        materials_quality = 0.2 + rng.uniform(0, 0.2)
        marketing_investment = 80000 + rng.uniform(0, 50000)
        advertising_budget = 50000 + rng.uniform(0, 50000)
        production_qty = 10000 + int(rng.uniform(0, 3000))
        tqm = rng.uniform(20000, 80000)
        rd = rng.uniform(30000, 80000)
        base_wage = 18000 + rng.uniform(0, 3000)
    elif strategy == "premium":
        wholesale_price = 45.0 + rng.uniform(0, 5)
        internet_price = 50.0 + rng.uniform(0, 5)
        amazon_price = 55.0 + rng.uniform(0, 5)
        materials_quality = 0.9 + rng.uniform(0, 0.1)
        marketing_investment = 200000 + rng.uniform(0, 50000)
        advertising_budget = 120000 + rng.uniform(0, 50000)
        production_qty = 6000 + int(rng.uniform(0, 2000))
        tqm = rng.uniform(100000, 200000)
        rd = rng.uniform(120000, 180000)
        base_wage = 30000 + rng.uniform(0, 4000)
    else:  # balanced
        wholesale_price = 28.0 + rng.uniform(0, 4)
        internet_price = 30.0 + rng.uniform(0, 4)
        amazon_price = 32.0 + rng.uniform(0, 4)
        materials_quality = 0.5 + rng.uniform(0, 0.2)
        marketing_investment = 150000 + rng.uniform(0, 50000)
        advertising_budget = 80000 + rng.uniform(0, 50000)
        production_qty = 8000 + int(rng.uniform(0, 2000))
        tqm = rng.uniform(80000, 150000)
        rd = rng.uniform(80000, 120000)
        base_wage = 25000 + rng.uniform(0, 2000)

    social_budget = SocialMediaBudget(
        tiktok=rng.uniform(0, 20000),
        instagram=rng.uniform(0, 20000),
        youtube=rng.uniform(0, 15000),
    )

    return PlayerDecision(
        wholesalePrice=round(wholesale_price, 2),
        internetPrice=round(internet_price, 2),
        amazonPrice=round(amazon_price, 2),
        materialsQuality=round(_clamp(materials_quality, 0, 1), 3),
        stylingBudget=round(300000 + rng.uniform(0, 200000), 2),
        numModels=4 + int(rng.uniform(0, 4)),
        tqmInvestment=round(tqm, 2),
        rdInvestment=round(rd, 2),
        marketingInvestment=round(marketing_investment, 2),
        advertisingBudget=round(advertising_budget, 2),
        celebrityType=rng.choice(["none", "athlete", "musician", "social_influencer"]),
        socialMediaBudget=social_budget,
        baseWage=round(base_wage, 2),
        incentivePay=round(rng.uniform(0, 2000), 2),
        trainingBudget=round(rng.uniform(0, 80000), 2),
        productionQuantity=max(production_qty, 0),
        overtimePercent=int(rng.uniform(0, 25)),
        csrInvestment=round(rng.uniform(0, 50000), 2),
        dividendsPerShare=round(rng.uniform(0, 2.0), 2),
        newLoanAmount=round(rng.uniform(0, 100000), 2),
        sharesBuyback=int(rng.uniform(0, 1000)),
        sharesIssued=int(rng.uniform(0, 500)),
        retailOutlets=int(rng.uniform(0, 15)),
        fulfillmentMethod=rng.choice(["fbm", "fba"]),
        internetPromotion=round(rng.uniform(0, 0.5), 3),
    )


# ── Main Round Processing ──────────────────────────────────────────────────

def process_round(
    config: SessionConfiguration,
    teams: List[TeamConfig],
    decisions: Dict[str, PlayerDecision],
    round_num: int,
    team_states: Dict[str, Dict[str, Any]],
    rng: random.Random | None = None,
) -> Tuple[List[RoundResult], Dict[str, Dict[str, Any]]]:
    """
    Process one round of the simulation for all teams.
    
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
        rng = random.Random(config.randomSeed + round_num * 1000)

    # Step 1: Generate AI decisions for teams without human decisions
    all_decisions = {}
    for team in teams:
        tid = team.teamName  # Use team name as teamId
        if tid in decisions:
            all_decisions[tid] = decisions[tid]
        elif team.isAI:
            strategy = team.aiStrategy or "balanced"
            all_decisions[tid] = generate_ai_decision(
                tid, round_num, config.randomSeed, strategy
            )
        # Teams without decisions are skipped (no round participation)

    # Step 2: Compute team-level stats for attractiveness calculations
    team_sq = {}
    team_costs = {}
    team_prices = {}
    team_demands = {}  # Channel → demand

    for team in teams:
        tid = team.teamName
        if tid not in all_decisions:
            continue

        d = all_decisions[tid]
        sq = _compute_sq_rating(d.materialsQuality, d.numModels, d.stylingBudget)
        team_sq[tid] = sq

        unit_cost, total_prod_cost = compute_production_cost(
            d.productionQuantity,
            d.materialsQuality,
            d.baseWage,
            d.incentivePay,
            d.trainingBudget,
            d.overtimePercent,
            config.maxOvertimePercent,
        )
        team_costs[tid] = {
            "unitCost": unit_cost,
            "productionCost": total_prod_cost,
        }

        team_prices[tid] = {
            "wholesale": d.wholesalePrice,
            "internet": d.internetPrice,
            "amazon": d.amazonPrice,
        }

    # Step 3: Compute competitor averages for each channel
    valid_teams = [t for t in teams if t.teamName in all_decisions]
    n = len(valid_teams)
    if n == 0:
        return [], team_states

    # Wholesale averages
    w_prices = [all_decisions[t.teamName].wholesalePrice for t in valid_teams]
    w_sq = [team_sq[t.teamName] for t in valid_teams]
    avg_w_price = sum(w_prices) / n if n > 0 else 25.0
    avg_w_sq = sum(w_sq) / n if n > 0 else 5.0

    # Internet averages
    i_prices = [all_decisions[t.teamName].internetPrice for t in valid_teams]
    avg_i_price = sum(i_prices) / n if n > 0 else 30.0

    # Amazon averages
    a_prices = [all_decisions[t.teamName].amazonPrice for t in valid_teams]
    avg_a_price = sum(a_prices) / n if n > 0 else 32.0

    # Step 4: Compute demand for each team in each channel
    for team in teams:
        tid = team.teamName
        if tid not in all_decisions:
            continue

        d = all_decisions[tid]
        cost_info = team_costs.get(tid, {"unitCost": 15.0, "productionCost": 0})
        unit_cost = cost_info["unitCost"]

        # Wholesale demand
        d_wholesale = compute_wholesale_demand(
            base_cost=unit_cost,
            price=d.wholesalePrice,
            sq_rating=team_sq[tid],
            competitor_avg_price=avg_w_price,
            competitor_avg_sq=avg_w_sq,
            marketing_budget=d.marketingInvestment,
            social_budget=d.socialMediaBudget,
            retail_outlets=d.retailOutlets,
            rng=rng,
        )

        # Internet demand
        d_internet = compute_internet_demand(
            base_cost=unit_cost,
            price=d.internetPrice,
            sq_rating=team_sq[tid],
            competitor_avg_price=avg_i_price,
            competitor_avg_sq=avg_w_sq,
            marketing_budget=d.marketingInvestment,
            social_budget=d.socialMediaBudget,
            promotion_factor=d.internetPromotion,
            rng=rng,
        )

        # Amazon demand
        d_amazon = compute_amazon_demand(
            base_cost=unit_cost,
            price=d.amazonPrice,
            sq_rating=team_sq[tid],
            competitor_avg_price=avg_a_price,
            competitor_avg_sq=avg_w_sq,
            marketing_budget=d.marketingInvestment,
            social_budget=d.socialMediaBudget,
            fulfillment=d.fulfillmentMethod,
            rng=rng,
        )

        # Total target demand
        total_demand = d_wholesale + d_internet + d_amazon

        # Available inventory = production + previous inventory
        prev_inv = team_states.get(tid, {}).get("inventory", 0.0)
        total_available = d.productionQuantity + prev_inv
        total_available = max(total_available, 0)

        # If production < demand, adjust production based on base stock target
        if total_available < total_demand:
            # Adjust production: target = baseStockTarget * totalDemand / average demand
            # But we already set productionQuantity in the decision, so let's use a buffer
            pass  # Use the decision's production quantity as-is

        # Allocate demand proportionally across channels based on availability
        if total_available > 0 and total_demand > 0:
            allocation_ratio = min(total_available / total_demand, 1.0)
            d_wholesale = d_wholesale * allocation_ratio
            d_internet = d_internet * allocation_ratio
            d_amazon = d_amazon * allocation_ratio

        # Actual units sold = min(demand, available)
        wholesale_sold = min(d_wholesale, d.productionQuantity)  # Wholesale gets first pick
        internet_sold = min(d_internet, max(0, total_available - wholesale_sold))
        amazon_sold = min(d_amazon, max(0, total_available - wholesale_sold - internet_sold))

        total_sold = wholesale_sold + internet_sold + amazon_sold
        ending_inventory = max(0, total_available - total_sold)

        team_demands[tid] = {
            "wholesale": wholesale_sold,
            "internet": internet_sold,
            "amazon": amazon_sold,
            "total_sold": total_sold,
            "ending_inventory": ending_inventory,
        }

    # Step 5: Calculate financials for each team
    results = []
    for team in teams:
        tid = team.teamName
        if tid not in all_decisions:
            continue

        d = all_decisions[tid]
        cost_info = team_costs[tid]
        unit_cost = cost_info["unitCost"]
        production_cost = cost_info["productionCost"]
        demands = team_demands[tid]

        # Revenue
        wholesale_rev = demands["wholesale"] * d.wholesalePrice
        internet_rev = demands["internet"] * d.internetPrice
        amazon_rev = demands["amazon"] * d.amazonPrice
        # FBA/FBM fees on Amazon revenue
        if d.fulfillmentMethod == "fba":
            amazon_rev *= (1.0 - FBA_FEE_RATE)
        else:
            amazon_rev *= (1.0 - FBM_FEE_RATE)
        total_revenue = wholesale_rev + internet_rev + amazon_rev

        # Marketing & advertising cost
        marketing_cost = compute_marketing_cost(
            d.marketingInvestment,
            d.advertisingBudget,
            d.celebrityType,
            d.socialMediaBudget,
        )

        # Storage cost
        storage_cost = demands["ending_inventory"] * STORAGE_COST_PER_UNIT

        # Dividend cost
        dividend_cost = d.dividendsPerShare * max(team_states.get(tid, {}).get("sharesOutstanding", 10000), 1)

        # Buyback cost
        buyback_cost = d.sharesBuyback * 50.0  # Assume $50/share

        # Share issuance proceeds
        share_proceeds = d.sharesIssued * 50.0

        # Interest on existing debt (10% annual / 20 rounds = 0.5% per round)
        prev_state = team_states.get(tid, {})
        debt = prev_state.get("debt", 0.0)
        loan_interest_rate = 0.005  # per round
        interest_expense = debt * loan_interest_rate

        # New loan proceeds
        new_loan = d.newLoanAmount

        # Total costs
        total_costs = (
            production_cost
            + marketing_cost
            + storage_cost
            + dividend_cost
            + buyback_cost
            + interest_expense
            - share_proceeds
        )

        # Profit
        profit = total_revenue - total_costs

        # Update financial state
        cash = prev_state.get("cash", config.startingCash)
        equity = prev_state.get("equity", config.initialEquity)
        shares_outstanding = prev_state.get("sharesOutstanding", 10000.0)

        new_equity = equity + profit
        new_cash = cash + total_revenue - production_cost - marketing_cost - storage_cost + new_loan - buyback_cost - dividend_cost + share_proceeds
        new_debt = debt + new_loan
        new_shares = shares_outstanding - d.sharesBuyback + d.sharesIssued
        new_shares = max(new_shares, 1.0)

        # Market share
        total_market_demand = sum(team_demands.get(t.teamName, {}).get("total_sold", 0) for t in valid_teams)
        market_share = demands["total_sold"] / total_market_demand if total_market_demand > 0 else 0.0

        # Reputation
        reputation = _compute_reputation(
            team_sq[tid], d.tqmInvestment, d.csrInvestment, d.marketingInvestment
        )

        # Cumulative profit
        cumulative_profit = prev_state.get("cumulativeProfit", 0.0) + profit

        # EPS
        eps = profit / new_shares

        # ROE
        roe = profit / new_equity if new_equity > 0 else 0.0

        # Stock price calculation — weighted average of EPS and ROE trends
        prev_sp = prev_state.get("stockPrice", INITIAL_STOCK_PRICE)
        prev_eps_val = prev_state.get("eps", 0.0)
        prev_roe_val = prev_state.get("roe", 0.0)

        eps_change = eps - prev_eps_val
        roe_change = roe - prev_roe_val
        # Blend: 50% EPS change + 30% ROE change + 20% mean reversion to $50
        stock_price = prev_sp * (1 + eps_change * 0.5 + roe_change * 0.3) * 0.8 + 50.0 * 0.2
        stock_price = max(stock_price, 1.0)

        # Credit rating
        credit_rating = compute_creditscore(new_debt, new_equity, interest_expense, new_cash)

        # Investor scorecard
        scorecard = compute_investor_scorecard(
            eps=eps,
            roe=roe,
            stock_price=stock_price,
            reputation=reputation,
            credit_rating=credit_rating,
            prev_eps=prev_eps_val,
            prev_roe=prev_roe_val,
            prev_stock_price=prev_sp,
            round_num=round_num,
        )

        # Build result
        result = RoundResult(
            teamId=tid,
            round=round_num,
            revenue=round(total_revenue, 2),
            costs=round(total_costs, 2),
            profit=round(profit, 2),
            marketShare=round(market_share, 4),
            sqRating=round(team_sq[tid], 2),
            reputation=round(reputation, 2),
            cumulativeProfit=round(cumulative_profit, 2),
            cash=round(new_cash, 2),
            inventory=round(demands["ending_inventory"], 2),
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
            creditScore=scorecard["creditScore"],
            totalScore=scorecard["totalScore"],
            productionCost=round(production_cost, 2),
            marketingCost=round(marketing_cost, 2),
            unitCost=round(unit_cost, 2),
            demand={
                "wholesale": round(demands["wholesale"], 2),
                "internet": round(demands["internet"], 2),
                "amazon": round(demands["amazon"], 2),
                "totalSold": round(demands["total_sold"], 2),
            },
        )
        results.append(result)

        # Update team state
        team_states[tid] = {
            "cash": new_cash,
            "equity": new_equity,
            "debt": new_debt,
            "sharesOutstanding": new_shares,
            "cumulativeProfit": cumulative_profit,
            "inventory": demands["ending_inventory"],
            "stockPrice": stock_price,
            "eps": eps,
            "roe": roe,
            "reputation": reputation,
            "creditRating": credit_rating,
            "totalScore": scorecard["totalScore"],
        }

    return results, team_states
