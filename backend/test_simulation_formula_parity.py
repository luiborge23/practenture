"""Deterministic Swift/Python formula parity tests for simulation_engine."""

import pytest

from models import MarketType, PlayerDecision, SessionConfiguration, TeamConfig
from simulation_engine import (
    _compute_amazon_attractiveness,
    _compute_internet_attractiveness,
    _compute_wholesale_attractiveness,
    allocate_private_label,
    compute_awareness_score,
    compute_sq_rating,
    compute_total_market_demand,
    process_round,
)


class ZeroNoise:
    """RNG test double whose noise factor is always exactly 1.0."""

    def uniform(self, lower: float, upper: float) -> float:
        return 0.0


def decision(**overrides) -> PlayerDecision:
    values = {
        "productionQuantity": 10_000,
        "privateLabelMaxUnits": 10_000,
        "advertisingBudget": 0,
        "tiktokBudget": 0,
        "instagramBudget": 0,
        "youtubeBudget": 0,
        "tqmInvestment": 2_000,
    }
    values.update(overrides)
    return PlayerDecision(**values)


def test_total_market_demand_growth_multiplier_cap_and_noise() -> None:
    config = SessionConfiguration(
        baseMarketDemand=1_000,
        marketType=MarketType.aggressive,
    )

    assert compute_total_market_demand(config, 1, ZeroNoise()) == pytest.approx(1_365)
    assert compute_total_market_demand(config, 10, ZeroNoise()) == pytest.approx(1_950)
    assert compute_total_market_demand(config, 20, ZeroNoise()) == pytest.approx(2_600)
    assert compute_total_market_demand(config, 40, ZeroNoise()) == pytest.approx(2_600)


def test_single_team_channel_demand_uses_swift_fixed_shares() -> None:
    config = SessionConfiguration(baseMarketDemand=1_000, plantCapacity=10_000)
    team = TeamConfig(teamName="Solo")

    results, _ = process_round(
        config, [team], {"Solo": decision()}, 1, {}, ZeroNoise()
    )

    assert results[0].demand == {
        "wholesale": 525,
        "internet": 157,
        "amazon": 210,
        "privateLabel": 157,
        "totalSold": 1_049,
    }
    assert results[0].marketShare == round(1_049 / 1_050, 4)


def test_private_label_is_lowest_bid_first_and_integer_truncated() -> None:
    teams = [TeamConfig(teamName="High"), TeamConfig(teamName="Low")]
    decisions = {
        "High": decision(privateLabelBidPrice=50, privateLabelMaxUnits=500),
        "Low": decision(privateLabelBidPrice=40, privateLabelMaxUnits=100),
    }

    assert allocate_private_label(teams, decisions, 250.9) == {
        "Low": 100,
        "High": 150,
    }


def test_lower_prices_increase_attractiveness_in_every_channel() -> None:
    common_wholesale = dict(
        sq=5,
        avg_sq=5,
        effective_price=80,
        avg_effective_price=100,
        advertising_budget=1_000,
        avg_advertising=1_000,
        retail_outlets=0,
        celebrity_endorsement=decision().celebrityEndorsement,
        reputation=0.5,
        delivery_time=decision().deliveryTime,
        social_media_boost=1,
    )
    low_w = _compute_wholesale_attractiveness(**common_wholesale)
    common_wholesale["effective_price"] = 120
    high_w = _compute_wholesale_attractiveness(**common_wholesale)

    common_internet = dict(
        sq=5,
        avg_sq=5,
        avg_price=100,
        advertising_budget=100,
        avg_advertising=100,
        celebrity_endorsement=decision().celebrityEndorsement,
        reputation=0.5,
        free_shipping_threshold=100,
        social_media_boost=1,
    )
    low_i = _compute_internet_attractiveness(price=80, **common_internet)
    high_i = _compute_internet_attractiveness(price=120, **common_internet)

    common_amazon = dict(
        sq=5,
        avg_sq=5,
        avg_price=100,
        amazon_ad_budget=0,
        fulfillment_method=decision().fulfillmentMethod,
        social_media_boost=1,
    )
    low_a = _compute_amazon_attractiveness(price=80, **common_amazon)
    high_a = _compute_amazon_attractiveness(price=120, **common_amazon)

    assert low_w > high_w
    assert low_i > high_i
    assert low_a > high_a


def test_awareness_matches_swift_formula_and_caps_at_one() -> None:
    assert compute_awareness_score(10_000, 2_000, 3_000, 5_000) == pytest.approx(0.8)
    assert compute_awareness_score(20_000, 5_000, 5_000, 5_000) == 1.0


def test_multi_round_state_uses_current_tqm_before_sq_and_rejection() -> None:
    config = SessionConfiguration(baseMarketDemand=1_000)
    team = TeamConfig(teamName="Solo")
    d = decision(tqmInvestment=2_000)

    first_results, states = process_round(
        config, [team], {"Solo": d}, 1, {}, ZeroNoise()
    )
    first_sq = states["Solo"]["sqRating"]
    assert states["Solo"]["cumulativeTQM"] == 2_000

    _, states = process_round(
        config, [team], {"Solo": d}, 2, states, ZeroNoise()
    )
    expected_second_sq = compute_sq_rating(
        d.materialsQuality,
        d.stylingBudget,
        d.modelsOffered,
        4_000,
        d.bestPracticesInvestment,
        d.trainingHours,
        first_sq,
    )

    assert first_results[0].sqRating == round(first_sq, 2)
    assert states["Solo"]["cumulativeTQM"] == 4_000
    assert states["Solo"]["sqRating"] == pytest.approx(expected_second_sq)
    assert states["Solo"]["awarenessScore"] == 0
    assert first_results[0].awarenessScore == 0
    assert "awarenessScore" in first_results[0].model_dump()
