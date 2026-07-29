"""Versioned scenario-pack registry for simulation terminology and coefficients.

The registry deliberately contains only the production Athletic Footwear classic
pack today.  New industries must register a new immutable pack and implement
formula support before sessions can select it.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from types import MappingProxyType
from typing import Iterable, Mapping


DEFAULT_SCENARIO_ID = "athletic-footwear-classic"
DEFAULT_SCENARIO_VERSION = "1.0.0"


class ScenarioPackNotFoundError(ValueError):
    """Raised when a session requests an unregistered scenario pack."""


@dataclass(frozen=True)
class ScenarioCoefficients:
    """Classic engine coefficients, named independently of engine code."""

    price_elasticity: float = 1.5
    sq_weight: float = 1.2
    storage_cost_per_unit: float = 1.50
    base_rejection_rate: float = 0.12
    base_wage_baseline: float = 25_000.0
    noise_amplitude: float = 0.05
    base_stock_target: float = 25.0
    target_ratchet_rate: float = 0.06
    base_eps_target: float = 2.0
    base_roe_target: float = 0.15
    base_image_target: float = 50.0
    base_interest_rate: float = 0.06
    overtime_cost_premium: float = 1.5
    outlets_weight: float = 0.3
    advertising_weight: float = 0.6
    wholesale_share: float = 0.50
    amazon_share: float = 0.20
    internet_share: float = 0.15
    private_label_share: float = 0.15
    amazon_referral_rate: float = 0.15
    rebate_redemption_rate: float = 0.6
    internet_shipping_cost_per_unit: float = 5.0


@dataclass(frozen=True)
class ScenarioTerminology:
    """Display terminology supplied by a scenario without changing API keys."""

    industry: str
    product_singular: str
    product_plural: str
    quality_metric: str
    wholesale_channel: str
    internet_channel: str
    marketplace_channel: str
    private_label_channel: str


@dataclass(frozen=True)
class ScenarioPack:
    scenario_id: str
    scenario_version: str
    title: str
    terminology: ScenarioTerminology
    coefficients: ScenarioCoefficients

    def to_dict(self) -> dict:
        """Return a stable, JSON-compatible registry representation."""
        return {
            "scenario_id": self.scenario_id,
            "scenario_version": self.scenario_version,
            "title": self.title,
            "terminology": asdict(self.terminology),
            "coefficients": asdict(self.coefficients),
        }


class ScenarioPackRegistry:
    """Registry keyed by stable ``(scenario_id, scenario_version)`` identity."""

    def __init__(self, packs: Iterable[ScenarioPack] = ()) -> None:
        registered: dict[tuple[str, str], ScenarioPack] = {}
        for pack in packs:
            key = (pack.scenario_id, pack.scenario_version)
            if key in registered:
                raise ValueError(f"Duplicate scenario pack: {key[0]}@{key[1]}")
            registered[key] = pack
        self._packs: Mapping[tuple[str, str], ScenarioPack] = MappingProxyType(registered)

    def get(self, scenario_id: str, scenario_version: str) -> ScenarioPack:
        try:
            return self._packs[(scenario_id, scenario_version)]
        except KeyError as exc:
            raise ScenarioPackNotFoundError(
                f"Unknown scenario pack: {scenario_id}@{scenario_version}"
            ) from exc

    def list(self) -> tuple[ScenarioPack, ...]:
        return tuple(self._packs[key] for key in sorted(self._packs))


ATHLETIC_FOOTWEAR_CLASSIC = ScenarioPack(
    scenario_id=DEFAULT_SCENARIO_ID,
    scenario_version=DEFAULT_SCENARIO_VERSION,
    title="Athletic Footwear — Classic Scenario",
    terminology=ScenarioTerminology(
        industry="Athletic Footwear",
        product_singular="athletic shoe",
        product_plural="athletic shoes",
        quality_metric="S/Q Rating",
        wholesale_channel="Wholesale",
        internet_channel="Internet",
        marketplace_channel="Amazon",
        private_label_channel="Private Label",
    ),
    coefficients=ScenarioCoefficients(),
)



# ── Wearable Technology (production) ──────────────────────────────────────

WEARABLE_TECHNOLOGY = ScenarioPack(
    scenario_id="wearable-technology",
    scenario_version="1.0.0",
    title="Wearable Technology — Future Scenario",
    terminology=ScenarioTerminology(
        industry="Wearable Technology",
        product_singular="wearable device",
        product_plural="wearable devices",
        quality_metric="Reliability Index",
        wholesale_channel="Retail Distribution",
        internet_channel="Direct-to-Consumer",
        marketplace_channel="Online Marketplace",
        private_label_channel="White-Label OEM",
    ),
    coefficients=ScenarioCoefficients(
        price_elasticity=1.8,
        sq_weight=1.5,
        storage_cost_per_unit=2.00,
        base_rejection_rate=0.08,
        base_wage_baseline=28_000.0,
        noise_amplitude=0.04,
        base_stock_target=25.0,
        target_ratchet_rate=0.06,
        base_eps_target=1.8,
        base_roe_target=0.14,
        base_image_target=55.0,
        base_interest_rate=0.07,
        overtime_cost_premium=1.5,
        outlets_weight=0.2,
        advertising_weight=0.7,
        wholesale_share=0.45,
        amazon_share=0.20,
        internet_share=0.25,
        private_label_share=0.10,
        amazon_referral_rate=0.15,
        rebate_redemption_rate=0.6,
        internet_shipping_cost_per_unit=5.0,
    ),
)

SCENARIO_PACKS = ScenarioPackRegistry([ATHLETIC_FOOTWEAR_CLASSIC, WEARABLE_TECHNOLOGY])


def get_scenario_pack(
    scenario_id: str | None = None,
    scenario_version: str | None = None,
) -> ScenarioPack:
    """Resolve identity, defaulting missing legacy fields to the classic pack."""
    return SCENARIO_PACKS.get(
        scenario_id or DEFAULT_SCENARIO_ID,
        scenario_version or DEFAULT_SCENARIO_VERSION,
    )


# Scenarios explicitly registered as playable. Only these IDs can create sessions.
PLAYABLE_SCENARIOS: frozenset[str] = frozenset(["athletic-footwear-classic", "wearable-technology"])


def is_scenario_playable(scenario_id: str) -> bool:
    """Return True if sessions can be created with this scenario."""
    return scenario_id in PLAYABLE_SCENARIOS
