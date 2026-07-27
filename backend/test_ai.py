"""Tests for AI Service — Bedrock integration (mocked).

Covers:
- Scenario generation (AI + fallback)
- Feedback generation (AI + fallback)
- Hint generation (AI + fallback)
- Insights generation (AI + fallback)
- Status endpoint
- Auth enforcement (professor-only)
"""

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

from main import app
from database import db
from ai_service import BEDROCK_ENABLED, BEDROCK_MODEL, BEDROCK_REGION

client = TestClient(app)


# ── DB cleanup fixture (mirrors test_backend.py) ───────────────────────────

@pytest.fixture(autouse=True)
def clean_db():
    """Reset in-memory DB and SQLite before each test."""
    db.sessions.clear()
    db.decisions.clear()
    db.announcements.clear()
    db.results.clear()
    db.team_states.clear()
    conn = db._get_conn()
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM sessions")
    conn.execute("DELETE FROM professor_codes")
    conn.execute("DELETE FROM classes")
    conn.execute("DELETE FROM class_enrollments")
    conn.commit()
    from auth import ensure_professor
    ensure_professor()
    yield


# ── Auth helper ─────────────────────────────────────────────────────────────

def _get_professor_token():
    """Login as professor and return access token."""
    resp = client.post("/api/auth/login", json={
        "provider": "password",
        "username": "professor",
        "password": "practenture2026",
    })
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    return resp.json()["accessToken"]


def _get_student_token():
    """Register + login as student and return access token."""
    import time
    uid = int(time.time() * 1000) % 10000
    sid = f"S{uid}"
    client.post("/api/auth/register", json={
        "student_id": sid,
        "name": f"Test Student AI {uid}",
        "password": "TestPass789!",
    })
    # Login uses student_id as username (not lowercase)
    resp = client.post("/api/auth/login", json={
        "provider": "password",
        "username": sid,
        "password": "TestPass789!",
    })
    assert resp.status_code == 200, f"Login failed: {resp.json()}"
    return resp.json()["accessToken"]


# ── Status Endpoint ────────────────────────────────────────────────────────

def test_ai_status():
    """AI status endpoint returns configuration."""
    resp = client.get("/api/ai/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "enabled" in data
    assert "model" in data
    assert "region" in data


# ── Auth Enforcement ───────────────────────────────────────────────────────

def test_scenario_requires_professor():
    """Unauthenticated request to /ai/scenario returns 401."""
    resp = client.post("/api/ai/scenario", json={})
    assert resp.status_code == 401


def test_student_cannot_access_ai():
    """Student role cannot access AI endpoints."""
    token = _get_student_token()
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.post("/api/ai/scenario", json={}, headers=headers)
    assert resp.status_code == 403

    resp = client.post("/api/ai/feedback", json={}, headers=headers)
    assert resp.status_code == 403

    resp = client.post("/api/ai/hint", json={}, headers=headers)
    assert resp.status_code == 403

    resp = client.post("/api/ai/insights", json={}, headers=headers)
    assert resp.status_code == 403


# ── Scenario Generation ───────────────────────────────────────────────────

def test_scenario_fallback_when_bedrock_disabled():
    """Scenario returns fallback text when Bedrock is disabled."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("routers.ai.BEDROCK_ENABLED", False):
        resp = client.post("/api/ai/scenario", json={
            "industry": "retail",
            "difficulty": "hard",
            "round_num": 5,
            "total_rounds": 20,
        }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "scenario" in data
    assert data["source"] == "fallback"


def test_scenario_with_mocked_bedrock():
    """Scenario calls Bedrock and returns AI-generated text."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    mock_response = {
        "content": [{"text": "Market demand has increased 15% this round due to seasonal trends."}]
    }

    mock_body = MagicMock()
    mock_body.read.return_value = __import__("json").dumps(mock_response)

    mock_client = MagicMock()
    mock_client.invoke_model.return_value = mock_body

    with patch("ai_service._get_bedrock_client", return_value=mock_client):
        with patch("routers.ai.BEDROCK_ENABLED", True):
            resp = client.post("/api/ai/scenario", json={
                "industry": "consumer_electronics",
                "difficulty": "medium",
            }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "scenario" in data
    assert data["source"] == "ai"


# ── Feedback Generation ───────────────────────────────────────────────────

def test_feedback_fallback_when_bedrock_disabled():
    """Feedback returns fallback text when Bedrock is disabled."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("routers.ai.BEDROCK_ENABLED", False):
        resp = client.post("/api/ai/feedback", json={
            "decision": {
                "wholesalePrice": 28.0,
                "internetPrice": 30.0,
                "amazonPrice": 32.0,
                "materialsQuality": 0.5,
                "marketingInvestment": 150000,
                "advertisingBudget": 80000,
                "productionQuantity": 8000,
            },
            "round_result": {
                "profit": 125000.0,
                "revenue": 500000.0,
                "marketShare": 18.5,
            },
        }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "feedback" in data
    assert data["source"] == "fallback"


def test_feedback_with_mocked_bedrock():
    """Feedback calls Bedrock and returns AI-generated text."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    mock_response = {
        "content": [{"text": "Good pricing strategy. Consider increasing TQM investment."}]
    }

    mock_body = MagicMock()
    mock_body.read.return_value = __import__("json").dumps(mock_response)

    mock_client = MagicMock()
    mock_client.invoke_model.return_value = mock_body

    with patch("ai_service._get_bedrock_client", return_value=mock_client):
        with patch("routers.ai.BEDROCK_ENABLED", True):
            resp = client.post("/api/ai/feedback", json={
                "decision": {"wholesalePrice": 28.0, "productionQuantity": 8000},
                "round_result": {"profit": 125000.0, "marketShare": 18.5},
            }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "feedback" in data
    assert data["source"] == "ai"


# ── Hint Generation ───────────────────────────────────────────────────────

def test_hint_fallback_when_bedrock_disabled():
    """Hint returns fallback text when Bedrock is disabled."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("routers.ai.BEDROCK_ENABLED", False):
        resp = client.post("/api/ai/hint", json={
            "current_state": {
                "cash": 45000.0,
                "stockPrice": 42.5,
                "marketShare": 12.0,
            },
            "problem": "low market share",
        }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "hint" in data
    assert data["source"] == "fallback"


def test_hint_with_mocked_bedrock():
    """Hint calls Bedrock and returns AI-generated text."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    mock_response = {
        "content": [{"text": "Increase marketing spend by 20% to capture market share."}]
    }

    mock_body = MagicMock()
    mock_body.read.return_value = __import__("json").dumps(mock_response)

    mock_client = MagicMock()
    mock_client.invoke_model.return_value = mock_body

    with patch("ai_service._get_bedrock_client", return_value=mock_client):
        with patch("routers.ai.BEDROCK_ENABLED", True):
            resp = client.post("/api/ai/hint", json={
                "current_state": {"cash": 100000.0, "marketShare": 8.0},
            }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "hint" in data
    assert data["source"] == "ai"


# ── Insights Generation ───────────────────────────────────────────────────

def test_insights_fallback_when_bedrock_disabled():
    """Insights returns fallback text when Bedrock is disabled."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    with patch("routers.ai.BEDROCK_ENABLED", False):
        resp = client.post("/api/ai/insights", json={
            "session_results": [
                {"round": 1, "avg_revenue": 450000, "avg_profit": 80000, "avg_market_share": 15.0},
                {"round": 2, "avg_revenue": 480000, "avg_profit": 95000, "avg_market_share": 16.2},
            ],
            "team_count": 8,
        }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "insights" in data
    assert data["source"] == "fallback"


def test_insights_with_mocked_bedrock():
    """Insights calls Bedrock and returns AI-generated text."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    mock_response = {
        "content": [{"text": "Class performance improving. Top students are investing heavily in quality."}]
    }

    mock_body = MagicMock()
    mock_body.read.return_value = __import__("json").dumps(mock_response)

    mock_client = MagicMock()
    mock_client.invoke_model.return_value = mock_body

    with patch("ai_service._get_bedrock_client", return_value=mock_client):
        with patch("routers.ai.BEDROCK_ENABLED", True):
            resp = client.post("/api/ai/insights", json={
                "session_results": [{"round": 1, "avg_revenue": 450000}],
                "team_count": 8,
            }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "insights" in data
    assert data["source"] == "ai"


# ── Bedrock Error Handling ────────────────────────────────────────────────

def test_scenario_fallback_on_bedrock_error():
    """Scenario falls back gracefully when Bedrock raises an error."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    # Create a mock that raises an error
    mock_client = MagicMock()
    mock_client.invoke_model.side_effect = Exception("Simulated Bedrock failure")

    with patch("ai_service._get_bedrock_client", return_value=mock_client):
        with patch("routers.ai.BEDROCK_ENABLED", True):
            resp = client.post("/api/ai/scenario", json={}, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    # Should fall back to local text, not 500
    assert "scenario" in data


def test_feedback_fallback_on_bedrock_error():
    """Feedback falls back gracefully when Bedrock raises an error."""
    token = _get_professor_token()
    headers = {"Authorization": f"Bearer {token}"}

    mock_client = MagicMock()
    mock_client.invoke_model.side_effect = Exception("Simulated Bedrock failure")

    with patch("ai_service._get_bedrock_client", return_value=mock_client):
        with patch("routers.ai.BEDROCK_ENABLED", True):
            resp = client.post("/api/ai/feedback", json={
                "decision": {"wholesalePrice": 28.0},
                "round_result": {"profit": 10000.0},
            }, headers=headers)

    assert resp.status_code == 200
    data = resp.json()
    assert "feedback" in data
