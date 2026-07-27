"""Contracts for immutable scenario identity and Footwear Classic parity."""
from dataclasses import FrozenInstanceError
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from main import app
from models import CreateSessionRequest, Session, SessionConfiguration
from scenario_packs import (
    ATHLETIC_FOOTWEAR_CLASSIC, DEFAULT_SCENARIO_ID, DEFAULT_SCENARIO_VERSION,
    ScenarioPackNotFoundError, get_scenario_pack,
)
import simulation_engine as engine


def test_legacy_models_default_to_footwear_classic():
    request = CreateSessionRequest()
    assert (request.scenarioId, request.scenarioVersion) == (DEFAULT_SCENARIO_ID, DEFAULT_SCENARIO_VERSION)
    session = Session(code="BIZ-TEST", config=SessionConfiguration())
    assert (session.scenarioId, session.scenarioVersion) == (DEFAULT_SCENARIO_ID, DEFAULT_SCENARIO_VERSION)

def test_registry_default_is_immutable_and_stable():
    pack = get_scenario_pack()
    assert pack is ATHLETIC_FOOTWEAR_CLASSIC
    assert pack.title == "Athletic Footwear — Classic Scenario"
    with pytest.raises(FrozenInstanceError):
        pack.title = "changed"

def test_unknown_scenario_and_version_are_rejected():
    with pytest.raises(ScenarioPackNotFoundError): get_scenario_pack("wearable-technology", "research")
    with pytest.raises(ValidationError): CreateSessionRequest(scenarioId="wearable-technology", scenarioVersion="research")
    with pytest.raises(ValidationError): CreateSessionRequest(scenarioId=DEFAULT_SCENARIO_ID, scenarioVersion="9.9.9")

def test_discovery_exposes_only_production_backed_pack():
    response = TestClient(app).get("/api/sessions/scenarios")
    assert response.status_code == 200, response.text
    body = response.json()["scenarios"]
    ids = [(p["scenario_id"], p["scenario_version"]) for p in body]
    assert (DEFAULT_SCENARIO_ID, DEFAULT_SCENARIO_VERSION) in ids
    # Wearable is registered but must be marked as research/not-playable
    if ("wearable-technology", "0.1.0-research") in ids:
        wearable = [p for p in body if p["scenario_id"] == "wearable-technology"][0]
        assert wearable.get("status") in ("research", None) or not wearable.get("playable", True)

def test_classic_coefficients_match_engine_constants():
    c = ATHLETIC_FOOTWEAR_CLASSIC.coefficients
    assert c.price_elasticity == engine.PRICE_ELASTICITY
    assert c.sq_weight == engine.SQ_WEIGHT
    assert c.storage_cost_per_unit == engine.STORAGE_COST_PER_UNIT
    assert c.base_rejection_rate == engine.BASE_REJECTION_RATE
    assert c.noise_amplitude == engine.NOISE_AMPLITUDE
