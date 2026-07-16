"""Broad deterministic business-rule and conservation tests for the simulation engine."""
import math
import random

import pytest

from models import (
    CelebrityEndorsement, CreditRating, DeliveryTime, FulfillmentMethod,
    InfluencerTier, MaterialsQuality, PlayerDecision, SessionConfiguration,
    TeamConfig,
)
from simulation_engine import (
    _compute_amazon_attractiveness, _compute_internet_attractiveness,
    _compute_social_media_demand_boost, _compute_wholesale_attractiveness,
    compute_credit_rating, compute_image_rating, compute_investor_scorecard,
    compute_production_cost, compute_rejection_rate, compute_sq_rating,
    compute_stock_price, generate_ai_decision, process_round,
)


class ZeroNoise:
    def uniform(self, _lower, _upper):
        return 0.0


def _decision(**overrides):
    values = dict(
        wholesalePrice=80, internetPrice=90, amazonPrice=85,
        privateLabelBidPrice=45, privateLabelMaxUnits=100,
        amazonAdBudget=1000, materialsQuality=MaterialsQuality.standard,
        stylingBudget=3000, modelsOffered=3, tqmInvestment=2000,
        advertisingBudget=8000, celebrityEndorsement=CelebrityEndorsement.none,
        retailOutlets=20, mailInRebate=0, deliveryTime=DeliveryTime.standard,
        freeShippingThreshold=100, tiktokBudget=0, instagramBudget=0,
        youtubeBudget=0, influencerTier=InfluencerTier.none, baseWage=25000,
        incentivePay=0.5, trainingHours=20, bestPracticesInvestment=1000,
        productionQuantity=10000, overtimePercent=0, csrInvestment=2000,
        dividendsPerShare=0, newLoanAmount=0, sharesBuyback=0,
        sharesIssued=0, fulfillmentMethod=FulfillmentMethod.fbm,
    )
    values.update(overrides)
    return PlayerDecision(**values)


def _assert_round_invariants(result, state, config, decision, previous_inventory=0):
    numeric = result.model_dump(exclude={"teamId", "demand"}).values()
    assert all(math.isfinite(float(value)) for value in numeric)
    assert result.profit == pytest.approx(result.revenue - result.costs, abs=0.02)
    assert result.demand["totalSold"] == pytest.approx(
        sum(result.demand[channel] for channel in ("wholesale", "internet", "amazon", "privateLabel"))
    )
    capacity = config.plantCapacity * (1 + decision.overtimePercent / 100)
    assert result.demand["totalSold"] + result.inventory <= capacity + previous_inventory + 1e-6
    assert result.inventory >= 0
    assert result.sharesOutstanding >= 1
    assert 0 <= result.marketShare <= 1
    assert 1 <= result.sqRating <= 10
    assert 0 <= result.reputation <= 1
    assert 1 <= result.stockPrice <= 500
    assert 0 <= result.awarenessScore <= 1
    assert 0 <= result.totalScore <= 100
    for component in (result.epsScore, result.roeScore, result.stockPriceScore,
                      result.imageScore, result.creditScore):
        assert 0 <= component <= 20
    assert result.totalScore == pytest.approx(
        result.epsScore + result.roeScore + result.stockPriceScore
        + result.imageScore + result.creditScore, abs=0.03
    )
    assert state["inventory"] == pytest.approx(result.inventory, abs=0.01)
    assert state["cash"] == pytest.approx(result.cash, abs=0.01)
    assert state["equity"] == pytest.approx(result.equity, abs=0.01)
    assert state["debt"] == pytest.approx(result.debt, abs=0.01)


def test_round_accounting_capacity_scores_and_state_conservation():
    config = SessionConfiguration(baseMarketDemand=50000, plantCapacity=10000)
    d = _decision(productionQuantity=12000, overtimePercent=20)
    result, states = process_round(config, [TeamConfig(teamName="T")], {"T": d}, 1, {}, ZeroNoise())
    _assert_round_invariants(result[0], states["T"], config, d)
    assert result[0].cash == pytest.approx(config.startingCash + result[0].profit, abs=0.02)
    assert result[0].equity == pytest.approx(max(1, config.initialEquity + result[0].profit), abs=0.02)


def test_sq_inputs_are_monotonic_and_rating_is_bounded():
    base = compute_sq_rating(MaterialsQuality.standard, 0, 1, 0, 0, 0, 5)
    improvements = [
        compute_sq_rating(MaterialsQuality.superior, 0, 1, 0, 0, 0, 5),
        compute_sq_rating(MaterialsQuality.standard, 12000, 1, 0, 0, 0, 5),
        compute_sq_rating(MaterialsQuality.standard, 0, 5, 0, 0, 0, 5),
        compute_sq_rating(MaterialsQuality.standard, 0, 1, 50000, 0, 0, 5),
        compute_sq_rating(MaterialsQuality.standard, 0, 1, 0, 5000, 0, 5),
        compute_sq_rating(MaterialsQuality.standard, 0, 1, 0, 0, 80, 5),
    ]
    assert all(value > base for value in improvements)
    assert 1 <= compute_sq_rating(MaterialsQuality.superior, 1e12, 100, 1e12, 1e12, 1e12, 100) <= 10


def test_quality_workforce_and_tqm_reduce_rejections_with_one_percent_floor():
    baseline = compute_rejection_rate(0, 0, 0, 0)
    assert compute_rejection_rate(200000, 0, 0, 0) < baseline
    assert compute_rejection_rate(0, 100, 0, 0) < baseline
    assert compute_rejection_rate(0, 0, 2, 0) < baseline
    assert compute_rejection_rate(0, 0, 0, 5000) < baseline
    assert compute_rejection_rate(1e12, 1e12, 1e12, 1e12) == pytest.approx(0.01)


def test_production_cost_zero_quantity_quality_and_overtime_boundaries():
    zero_total, zero_unit, workers = compute_production_cost(0, MaterialsQuality.standard, 20, 100, 25000, 0, 0)
    assert zero_total == 0 and zero_unit == 20 and workers == 1
    standard = compute_production_cost(100, MaterialsQuality.standard, 20, 100, 25000, 0, 0)
    superior = compute_production_cost(100, MaterialsQuality.superior, 20, 100, 25000, 0, 0)
    overtime = compute_production_cost(120, MaterialsQuality.standard, 20, 100, 25000, 0, 0)
    assert superior[0] > standard[0]
    assert overtime[0] > 1.2 * standard[0]
    assert overtime[1] > standard[1]


def test_every_marketing_and_channel_control_moves_intended_attractiveness():
    common_w = dict(sq=5, avg_sq=5, effective_price=80, avg_effective_price=80,
                    advertising_budget=1000, avg_advertising=1000, retail_outlets=0,
                    celebrity_endorsement=CelebrityEndorsement.none, reputation=.5,
                    delivery_time=DeliveryTime.standard, social_media_boost=1)
    base_w = _compute_wholesale_attractiveness(**common_w)
    for change in (
        {"effective_price": 70}, {"advertising_budget": 2000}, {"retail_outlets": 100},
        {"celebrity_endorsement": CelebrityEndorsement.global_},
        {"delivery_time": DeliveryTime.rush}, {"social_media_boost": 1.1},
    ):
        assert _compute_wholesale_attractiveness(**(common_w | change)) > base_w

    common_i = dict(sq=5, avg_sq=5, price=90, avg_price=90, advertising_budget=1000,
                    avg_advertising=1000, celebrity_endorsement=CelebrityEndorsement.none,
                    reputation=.5, free_shipping_threshold=100, social_media_boost=1)
    assert _compute_internet_attractiveness(**(common_i | {"free_shipping_threshold": 0})) > _compute_internet_attractiveness(**common_i)

    common_a = dict(sq=5, avg_sq=5, price=85, avg_price=85, amazon_ad_budget=0,
                    fulfillment_method=FulfillmentMethod.fbm, social_media_boost=1)
    assert _compute_amazon_attractiveness(**(common_a | {"amazon_ad_budget": 10000})) > _compute_amazon_attractiveness(**common_a)
    assert _compute_amazon_attractiveness(**(common_a | {"fulfillment_method": FulfillmentMethod.fba})) > _compute_amazon_attractiveness(**common_a)
    assert _compute_social_media_demand_boost(15000, 15000, 15000, InfluencerTier.micro) > 1


def test_image_scorecard_credit_and_stock_are_monotonic_and_bounded():
    base_image = compute_image_rating(3, 0, 0, CelebrityEndorsement.none, 1, 0, 0, 0, 0, InfluencerTier.none)
    strong_image = compute_image_rating(8, 10000, 10000, CelebrityEndorsement.global_, 5, 80, 10000, 10000, 10000, InfluencerTier.mega)
    assert strong_image > base_image
    assert 0 <= strong_image <= 100
    good_credit = compute_credit_rating(0.1, 20, 5)
    bad_credit = compute_credit_rating(10, 0, -1)
    assert good_credit.investor_score > bad_credit.investor_score
    score = compute_investor_scorecard(100, 10, 1000, 100, good_credit, 50)
    assert all(0 <= value <= 100 for value in score.values())
    no_dilution = compute_stock_price(2, .2, 1, good_credit, 0, 10000, 50, 1, ZeroNoise())
    diluted = compute_stock_price(2, .2, 1, good_credit, 5000, 10000, 50, 1, ZeroNoise())
    assert 1 <= diluted <= no_dilution <= 500


def test_all_supported_ai_strategies_are_seed_deterministic_valid_and_distinct():
    decisions = {}
    supported = ("balanced", "aggressive", "quality", "lowcost", "premium")
    for strategy in supported:
        first = generate_ai_decision("AI", 4, 12345, strategy)
        second = generate_ai_decision("AI", 4, 12345, strategy)
        assert first == second
        assert isinstance(first, PlayerDecision)
        decisions[strategy] = first.model_dump()
    assert len({str(decisions[strategy]) for strategy in supported}) == len(supported)


def test_unknown_ai_strategy_falls_back_to_balanced():
    assert generate_ai_decision("AI", 4, 12345, "unknown") == generate_ai_decision(
        "AI", 4, 12345, "balanced"
    )


def test_rebate_above_price_is_clamped_and_never_creates_complex_demand():
    baseline = _compute_wholesale_attractiveness(
        5, 5, 1, 1, 1000, 1000, 0, CelebrityEndorsement.none, .5,
        DeliveryTime.standard, 1
    )
    rebated = _compute_wholesale_attractiveness(
        5, 5, -100, -100, 1000, 1000, 0, CelebrityEndorsement.none, .5,
        DeliveryTime.standard, 1
    )
    assert isinstance(rebated, float)
    assert math.isfinite(rebated)
    assert rebated == pytest.approx(baseline)


def test_100_seeded_full_field_rounds_preserve_all_invariants():
    rng = random.Random(20260716)
    config = SessionConfiguration(baseMarketDemand=20000, plantCapacity=10000)
    qualities = list(MaterialsQuality)
    celebrities = list(CelebrityEndorsement)
    deliveries = list(DeliveryTime)
    influencers = list(InfluencerTier)
    fulfillment = list(FulfillmentMethod)
    for index in range(100):
        d = _decision(
            wholesalePrice=rng.uniform(1, 200), internetPrice=rng.uniform(1, 200),
            amazonPrice=rng.uniform(1, 200), privateLabelBidPrice=rng.uniform(0, 100),
            privateLabelMaxUnits=rng.randint(0, 20000), amazonAdBudget=rng.uniform(0, 30000),
            materialsQuality=rng.choice(qualities), stylingBudget=rng.uniform(0, 50000),
            modelsOffered=rng.randint(1, 20), tqmInvestment=rng.uniform(0, 200000),
            advertisingBudget=rng.uniform(0, 100000), celebrityEndorsement=rng.choice(celebrities),
            retailOutlets=rng.randint(0, 100), mailInRebate=rng.uniform(0, 20),
            deliveryTime=rng.choice(deliveries), freeShippingThreshold=rng.uniform(0, 200),
            tiktokBudget=rng.uniform(0, 50000), instagramBudget=rng.uniform(0, 50000),
            youtubeBudget=rng.uniform(0, 50000), influencerTier=rng.choice(influencers),
            baseWage=rng.uniform(0, 100000), incentivePay=rng.uniform(0, 5),
            trainingHours=rng.uniform(0, 200), bestPracticesInvestment=rng.uniform(0, 50000),
            productionQuantity=rng.randint(0, 20000), overtimePercent=rng.uniform(0, 20),
            csrInvestment=rng.uniform(0, 100000), dividendsPerShare=rng.uniform(0, 10),
            newLoanAmount=rng.uniform(0, 1_000_000), sharesBuyback=rng.randint(0, 20000),
            sharesIssued=rng.randint(0, 20000), fulfillmentMethod=rng.choice(fulfillment),
        )
        team = f"T{index}"
        results, states = process_round(config, [TeamConfig(teamName=team)], {team: d}, 1, {}, ZeroNoise())
        _assert_round_invariants(results[0], states[team], config, d)
