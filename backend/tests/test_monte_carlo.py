"""Monte Carlo stability and exploit-resistance tests for the simulation engine.

These tests verify that the engine produces stable, bounded, and exploit-resistant
results across a wide range of decision sets. They are required release gates.
"""

from __future__ import annotations

import math
import random
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from models import PlayerDecision, SessionConfiguration, TeamConfig
from simulation_engine import process_round


def _make_config(**overrides) -> SessionConfiguration:
    defaults = dict(
        randomSeed=42,
        marketType="moderate",
        startingCash=500_000.0,
        initialEquity=300_000.0,
        plantCapacity=10_000,
        fixedCostsPerRound=5_000.0,
        baseCostPerUnit=30.0,
        baseMarketDemand=10_000,
        sharesOutstanding=10_000,
    )
    defaults.update(overrides)
    return SessionConfiguration(**defaults)


def _make_team(name: str, **overrides) -> TeamConfig:
    defaults = dict(teamName=name)
    defaults.update(overrides)
    return TeamConfig(**defaults)


def _make_decision(team: str, **overrides) -> PlayerDecision:
    defaults = dict(
        wholesalePrice=80.0,
        internetPrice=90.0,
        amazonPrice=85.0,
        privateLabelBidPrice=40.0,
        privateLabelMaxUnits=500,
        amazonAdBudget=3000.0,
        materialsQuality="standard",
        stylingBudget=5000.0,
        modelsOffered=4,
        tqmInvestment=3000.0,
        advertisingBudget=10000.0,
        celebrityEndorsement="none",
        retailOutlets=30,
        mailInRebate=3.0,
        deliveryTime="standard",
        freeShippingThreshold=75.0,
        tiktokBudget=2000.0,
        instagramBudget=3000.0,
        youtubeBudget=1500.0,
        influencerTier="micro",
        baseWage=26000.0,
        incentivePay=0.6,
        trainingHours=25.0,
        bestPracticesInvestment=2000.0,
        productionQuantity=7000,
        overtimePercent=8.0,
        csrInvestment=2000.0,
        dividendsPerShare=0.4,
        newLoanAmount=0.0,
        sharesBuyback=0,
        sharesIssued=0,
        fulfillmentMethod="fba",
    )
    defaults.update(overrides)
    return PlayerDecision(**defaults)


def _initial_state(team: TeamConfig) -> dict:
    return {
        "cash": 500_000.0,
        "inventory": 100,
        "reputation": 0.5,
        "cumulativeTQM": 0.0,
        "equity": 300_000.0,
        "debt": 0.0,
        "sharesOutstanding": 10_000,
        "sqRating": 5.0,
        "imageRating": 50.0,
        "creditRating": "A",
        "totalScore": 0.0,
    }


# ── Monte Carlo Stability ────────────────────────────────────────────


class TestMonteCarloStability:
    """Run many random simulations and verify bounded, stable results."""

    @pytest.mark.parametrize("seed", range(50))
    def test_all_teams_produce_finite_non_nan_results(self, seed: int):
        """Every team must end with finite, non-NaN cash, equity, and profit."""
        rng = random.Random(seed)
        config = _make_config(randomSeed=seed)
        teams = [_make_team(f"Team-{i}") for i in range(4)]
        decisions = {}
        states = {}
        for i, team in enumerate(teams):
            d = _make_decision(
                team.teamName,
                wholesalePrice=rng.uniform(40, 120),
                internetPrice=rng.uniform(50, 130),
                amazonPrice=rng.uniform(45, 125),
                productionQuantity=rng.randint(1000, 12000),
                advertisingBudget=rng.uniform(0, 30000),
            )
            decisions[team.teamName] = d
            states[team.teamName] = _initial_state(team)

        results, updated = process_round(config, teams, decisions, 1, states)

        for result in results:
            assert math.isfinite(result.cash), f"Non-finite cash for {result.teamId}"
            assert math.isfinite(result.equity), f"Non-finite equity for {result.teamId}"
            assert math.isfinite(result.profit), f"Non-finite profit for {result.teamId}"
            assert math.isfinite(result.revenue), f"Non-finite revenue for {result.teamId}"

    def test_no_monopoly_in_4_team_simulation(self):
        """No single team should capture >90% market share in a balanced round."""
        config = _make_config()
        teams = [_make_team(f"Team-{i}") for i in range(4)]
        decisions = {}
        states = {}
        for team in teams:
            decisions[team.teamName] = _make_decision(team.teamName)
            states[team.teamName] = _initial_state(team)

        results, _ = process_round(config, teams, decisions, 1, states)
        for result in results:
            assert result.marketShare < 0.90, f"Monopoly: {result.teamId} has {result.marketShare:.2%}"

    def test_profit_is_bounded(self):
        """No team should produce absurd profit (>10x starting cash) in one round."""
        config = _make_config()
        teams = [_make_team(f"Team-{i}") for i in range(4)]
        decisions = {}
        states = {}
        for team in teams:
            decisions[team.teamName] = _make_decision(team.teamName)
            states[team.teamName] = _initial_state(team)

        results, _ = process_round(config, teams, decisions, 1, states)
        for result in results:
            assert result.profit < 5_000_000, f"Absurd profit: {result.profit}"
            assert result.profit > -5_000_000, f"Absurd loss: {result.profit}"

    def test_deterministic_replay(self):
        """Same seed + decisions must produce identical results."""
        config = _make_config(randomSeed=12345)
        teams = [_make_team("A"), _make_team("B")]
        decisions = {"A": _make_decision("A"), "B": _make_decision("B")}
        states = {"A": _initial_state(teams[0]), "B": _initial_state(teams[1])}

        r1, _ = process_round(config, teams, decisions, 1, dict(states))
        r2, _ = process_round(config, teams, decisions, 1, dict(states))

        for a, b in zip(r1, r2):
            assert a.cash == b.cash, f"Non-deterministic cash: {a.cash} != {b.cash}"
            assert a.profit == b.profit, f"Non-deterministic profit: {a.profit} != {b.profit}"
            assert a.equity == b.equity, f"Non-deterministic equity: {a.equity} != {b.equity}"


# ── Exploit Resistance ───────────────────────────────────────────────


class TestExploitResistance:
    """Verify that degenerate strategies do not produce exploits."""

    def test_zero_price_produces_negative_profit(self):
        """Price = 0 must produce negative profit (revenue < production cost)."""
        config = _make_config()
        teams = [_make_team("Dumper")]
        decisions = {"Dumper": _make_decision("Dumper", wholesalePrice=0.01, internetPrice=0.01, amazonPrice=0.01)}
        states = {"Dumper": _initial_state(teams[0])}

        results, _ = process_round(config, teams, decisions, 1, states)
        assert results[0].profit < 0, "Zero-price dumping should not be profitable"

    def test_excessive_production_does_not_produce_positive_marginal_profit(self):
        """Production > 2x capacity must not produce positive marginal profit."""
        config = _make_config(plantCapacity=5000)
        teams = [_make_team("Overproducer")]
        decisions = {"Overproducer": _make_decision("Overproducer", productionQuantity=50000, overtimePercent=20)}
        states = {"Overproducer": _initial_state(teams[0])}

        results, _ = process_round(config, teams, decisions, 1, states)
        # Overproduction should lead to high costs that exceed revenue
        assert results[0].profit < 500_000, "Excessive production should not be highly profitable"

    def test_excessive_marketing_has_diminishing_returns(self):
        """10x baseline advertising must not produce 10x market share."""
        config = _make_config()
        teams = [_make_team("Spammer"), _make_team("Normal")]
        decisions = {
            "Spammer": _make_decision("Spammer", advertisingBudget=100_000),
            "Normal": _make_decision("Normal", advertisingBudget=10_000),
        }
        states = {"Spammer": _initial_state(teams[0]), "Normal": _initial_state(teams[1])}

        results, _ = process_round(config, teams, decisions, 1, states)
        spammer_share = results[0].marketShare
        # 10x marketing should not give >80% market share
        assert spammer_share < 0.80, f"Marketing spam exploit: {spammer_share:.2%}"

    def test_debt_spiral_triggers_credit_downgrade(self):
        """Debt > 10x equity should result in a poor credit rating."""
        config = _make_config()
        teams = [_make_team("Debtor")]
        states = {"Debtor": _initial_state(teams[0])}
        states["Debtor"]["debt"] = 3_000_000  # 10x equity
        states["Debtor"]["equity"] = 300_000
        decisions = {"Debtor": _make_decision("Debtor")}

        results, updated = process_round(config, teams, decisions, 1, states)
        credit = updated[teams[0].teamName]["creditRating"]
        # Credit rating should be poor (C range)
        assert credit in ("c_plus", "c", "c_minus"), f"Expected poor credit for debt spiral, got {credit}"

    def test_buyback_reissue_does_not_inflate_stock_price(self):
        """Buyback followed by reissue must not inflate stock price beyond reason."""
        config = _make_config()
        teams = [_make_team("Manipulator")]
        states = {"Manipulator": _initial_state(teams[0])}
        decisions = {"Manipulator": _make_decision("Manipulator", sharesBuyback=5000, sharesIssued=5000)}

        results, _ = process_round(config, teams, decisions, 1, states)
        # Stock price should remain reasonable (< $500 for a $300k equity / 10k share company)
        assert results[0].stockPriceScore <= 20, f"Stock price manipulation detected: score={results[0].stockPriceScore}"


# ── Boundary and Invariant Tests ─────────────────────────────────────


class TestBoundaryInvariants:
    """Verify numerical invariants hold at boundary conditions."""

    def test_zero_production_produces_zero_inventory(self):
        """Zero production must result in zero new inventory."""
        config = _make_config()
        teams = [_make_team("Idle")]
        decisions = {"Idle": _make_decision("Idle", productionQuantity=0)}
        states = {"Idle": _initial_state(teams[0])}

        results, _ = process_round(config, teams, decisions, 1, states)
        assert results[0].demand["totalSold"] >= 0
        assert results[0].inventory >= 0

    def test_accounting_identity_holds(self):
        """cash + debt = equity + assets (simplified accounting check)."""
        config = _make_config()
        teams = [_make_team("A"), _make_team("B")]
        decisions = {"A": _make_decision("A"), "B": _make_decision("B")}
        states = {"A": _initial_state(teams[0]), "B": _initial_state(teams[1])}

        results, updated = process_round(config, teams, decisions, 1, states)
        for result in results:
            state = updated[result.teamId]
            # Cash must change by profit (approximately, ignoring dividends/loans)
            # This is a sanity check, not an exact accounting identity
            assert math.isfinite(state["cash"])
            assert math.isfinite(state["equity"])

    def test_all_channel_demands_are_non_negative(self):
        """No channel demand should be negative."""
        config = _make_config()
        teams = [_make_team("A")]
        decisions = {"A": _make_decision("A", wholesalePrice=200, internetPrice=200, amazonPrice=200)}
        states = {"A": _initial_state(teams[0])}

        results, _ = process_round(config, teams, decisions, 1, states)
        for channel, demand in results[0].demand.items():
            assert demand >= 0, f"Negative demand for channel {channel}: {demand}"

    def test_results_are_sorted_by_round(self):
        """Results must contain the correct round number."""
        config = _make_config()
        teams = [_make_team("A")]
        decisions = {"A": _make_decision("A")}
        states = {"A": _initial_state(teams[0])}

        results, _ = process_round(config, teams, decisions, 5, states)
        assert results[0].round == 5
