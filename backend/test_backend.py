"""Tests for BizSimAI backend."""

import pytest
from fastapi.testclient import TestClient

from main import app
from database import db

client = TestClient(app)


# ── Auth helper ─────────────────────────────────────────────────────────────

def get_professor_token():
    """Login as the default professor and return Bearer token."""
    response = client.post("/api/auth/login", json={
        "provider": "password",
        "username": "professor",
        "password": "bizsimai2026",
    })
    assert response.status_code == 200, f"Professor login failed: {response.text}"
    return response.json()["accessToken"]


# ── Fixtures ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clean_db():
    """Reset in-memory DB and SQLite before each test."""
    db.sessions.clear()
    db.decisions.clear()
    db.announcements.clear()
    db.results.clear()
    db.team_states.clear()
    # Clear SQLite users table to avoid stale data from previous test runs
    conn = db._get_conn()
    conn.execute("DELETE FROM users")
    conn.execute("DELETE FROM sessions")
    conn.execute("DELETE FROM professor_codes")
    conn.execute("DELETE FROM classes")
    conn.execute("DELETE FROM class_enrollments")
    conn.commit()
    # Re-bootstrap professor after clearing (tests expect it to exist)
    from auth import ensure_professor
    ensure_professor()
    yield


@pytest.fixture
def professor_token():
    """Return a valid professor JWT token."""
    return get_professor_token()


@pytest.fixture
def created_session(professor_token):
    """Create a session and return its code."""
    response = client.post("/api/sessions", json={
        "config": {
            "totalRounds": 5,
            "numberOfAICompetitors": 2,
            "randomSeed": 42,
            "startingCash": 500000.0,
            "initialEquity": 300000.0,
            "plantCapacity": 10000,
            "maxOvertimePercent": 25,
            "minWage": 12000.0,
            "maxWage": 40000.0,
            "minDividend": 0.0,
            "maxDividend": 5.0,
        },
        "teams": [
            {"teamName": "Team Alpha", "isAI": False, "studentId": "student-1"},
            {"teamName": "Team Beta", "isAI": False, "studentId": "student-2"},
            {"teamName": "Team Gamma", "isAI": True, "aiStrategy": "balanced"},
        ],
        "created_by": "professor-1",
    }, headers={"Authorization": f"Bearer {professor_token}"})
    assert response.status_code == 201
    data = response.json()
    assert "sessionId" in data
    assert "code" in data
    assert data["code"].startswith("BIZ-")
    assert len(data["code"]) == 8  # "BIZ-XXXX"
    return data["code"]


# ── Health check ───────────────────────────────────────────────────────────

def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


# ── Session creation ───────────────────────────────────────────────────────

def test_create_session_returns_valid_code(created_session):
    """Test that session creation returns a valid BIZ-XXXXXX code."""
    assert created_session.startswith("BIZ-")
    # Verify the session exists
    response = client.get(f"/api/sessions/{created_session}")
    assert response.status_code == 200
    session = response.json()
    assert session["code"] == created_session
    assert session["state"] == "creating"
    assert len(session["teams"]) == 3


# ── Session get ────────────────────────────────────────────────────────────

def test_get_nonexistent_session():
    response = client.get("/api/sessions/BIZ-999999")
    assert response.status_code == 404


# ── Session join ───────────────────────────────────────────────────────────

def test_join_session(created_session):
    """Test that a student can join a session."""
    # Start the session first
    client.post(f"/api/sessions/{created_session}/start")

    response = client.put(f"/api/sessions/{created_session}/join", json={
        "teamName": "Team Delta",
        "studentId": "student-3",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["teamId"] == "Team Delta"
    assert data["teamName"] == "Team Delta"
    assert data["state"] == "active"


def test_join_duplicate_team_name(created_session):
    """Test that joining with a duplicate team name fails."""
    client.post(f"/api/sessions/{created_session}/start")

    # Join first time — should succeed
    client.put(f"/api/sessions/{created_session}/join", json={
        "teamName": "Team Delta",
        "studentId": "student-3",
    })

    # Join again with same name — should fail
    response = client.put(f"/api/sessions/{created_session}/join", json={
        "teamName": "Team Delta",
        "studentId": "student-4",
    })
    assert response.status_code == 400


# ── Teams listing ──────────────────────────────────────────────────────────

def test_get_teams(created_session):
    """Test listing teams in a session."""
    response = client.get(f"/api/sessions/{created_session}/teams")
    assert response.status_code == 200
    data = response.json()
    assert len(data["teams"]) == 3
    team_names = [t["teamName"] for t in data["teams"]]
    assert "Team Alpha" in team_names
    assert "Team Beta" in team_names
    assert "Team Gamma" in team_names


# ── Decision submission ────────────────────────────────────────────────────

def test_submit_decision(created_session):
    """Test submitting a round decision."""
    client.post(f"/api/sessions/{created_session}/start")

    decision = {
        "wholesalePrice": 30.0,
        "internetPrice": 32.0,
        "amazonPrice": 34.0,
        "materialsQuality": 0.6,
        "stylingBudget": 200000.0,
        "numModels": 5,
        "tqmInvestment": 100000.0,
        "rdInvestment": 100000.0,
        "marketingInvestment": 150000.0,
        "advertisingBudget": 80000.0,
        "celebrityType": "athlete",
        "socialMediaBudget": {"tiktok": 10000, "instagram": 15000, "youtube": 5000},
        "baseWage": 25000.0,
        "incentivePay": 1000.0,
        "trainingBudget": 50000.0,
        "productionQuantity": 8000,
        "overtimePercent": 10,
        "csrInvestment": 20000.0,
        "dividendsPerShare": 0.5,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 5,
        "fulfillmentMethod": "fba",
        "internetPromotion": 0.2,
    }

    # Submit decision for round 1
    response = client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 1,
        "teamId": "Team Alpha",
        "decision": decision,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["round"] == 1

    # Double submission should fail
    response = client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 1,
        "teamId": "Team Alpha",
        "decision": decision,
    })
    assert response.status_code == 409


def test_submit_wrong_round(created_session):
    """Test submitting a decision for the wrong round."""
    client.post(f"/api/sessions/{created_session}/start")

    response = client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 2,  # Current round is 1
        "teamId": "Team Alpha",
        "decision": {
            "wholesalePrice": 30.0,
            "internetPrice": 32.0,
            "amazonPrice": 34.0,
            "materialsQuality": 0.6,
            "stylingBudget": 200000.0,
            "numModels": 5,
            "tqmInvestment": 100000.0,
            "rdInvestment": 100000.0,
            "marketingInvestment": 150000.0,
            "advertisingBudget": 80000.0,
            "celebrityType": "none",
            "socialMediaBudget": {"tiktok": 0, "instagram": 0, "youtube": 0},
            "baseWage": 25000.0,
            "incentivePay": 0.0,
            "trainingBudget": 0.0,
            "productionQuantity": 8000,
            "overtimePercent": 0,
            "csrInvestment": 0.0,
            "dividendsPerShare": 0.0,
            "newLoanAmount": 0.0,
            "sharesBuyback": 0,
            "sharesIssued": 0,
            "retailOutlets": 0,
            "fulfillmentMethod": "fbm",
            "internetPromotion": 0.0,
        },
    })
    assert response.status_code == 400


# ── Decision retrieval ─────────────────────────────────────────────────────

def test_get_decisions(created_session):
    """Test retrieving decisions for a round."""
    client.post(f"/api/sessions/{created_session}/start")

    decision = {
        "wholesalePrice": 30.0,
        "internetPrice": 32.0,
        "amazonPrice": 34.0,
        "materialsQuality": 0.6,
        "stylingBudget": 200000.0,
        "numModels": 5,
        "tqmInvestment": 100000.0,
        "rdInvestment": 100000.0,
        "marketingInvestment": 150000.0,
        "advertisingBudget": 80000.0,
        "celebrityType": "none",
        "socialMediaBudget": {"tiktok": 0, "instagram": 0, "youtube": 0},
        "baseWage": 25000.0,
        "incentivePay": 0.0,
        "trainingBudget": 0.0,
        "productionQuantity": 8000,
        "overtimePercent": 0,
        "csrInvestment": 0.0,
        "dividendsPerShare": 0.0,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 0,
        "fulfillmentMethod": "fbm",
        "internetPromotion": 0.0,
    }

    client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 1,
        "teamId": "Team Alpha",
        "decision": decision,
    })

    response = client.get(f"/api/sessions/{created_session}/decisions/1")
    assert response.status_code == 200
    data = response.json()
    assert "Team Alpha" in data["decisions"]
    assert data["round"] == 1


# ── Round processing ───────────────────────────────────────────────────────

def test_process_round_returns_results(created_session):
    """Test that processing a round returns valid results."""
    client.post(f"/api/sessions/{created_session}/start")

    decision = {
        "wholesalePrice": 30.0,
        "internetPrice": 32.0,
        "amazonPrice": 34.0,
        "materialsQuality": 0.6,
        "stylingBudget": 200000.0,
        "numModels": 5,
        "tqmInvestment": 100000.0,
        "rdInvestment": 100000.0,
        "marketingInvestment": 150000.0,
        "advertisingBudget": 80000.0,
        "celebrityType": "none",
        "socialMediaBudget": {"tiktok": 0, "instagram": 0, "youtube": 0},
        "baseWage": 25000.0,
        "incentivePay": 0.0,
        "trainingBudget": 0.0,
        "productionQuantity": 8000,
        "overtimePercent": 0,
        "csrInvestment": 0.0,
        "dividendsPerShare": 0.0,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 0,
        "fulfillmentMethod": "fbm",
        "internetPromotion": 0.0,
    }

    # Team Alpha submits
    client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })

    # Process round (Team Beta and Gamma are AI, will auto-generate)
    response = client.post(f"/api/sessions/{created_session}/process_round")
    assert response.status_code == 200
    data = response.json()
    assert data["round"] == 1
    # Team Alpha (human) + Team Gamma (AI auto-generated) = 2 results
    assert len(data["results"]) == 2

    # Verify result structure
    for result in data["results"]:
        assert "teamId" in result
        assert "round" in result
        assert "revenue" in result
        assert "profit" in result
        assert "cumulativeProfit" in result
        assert "cash" in result
        assert "equity" in result
        assert "eps" in result
        assert "roe" in result
        assert "stockPrice" in result
        assert "totalScore" in result


def test_process_round_advances_round(created_session):
    """Test that processing advances to the next round."""
    client.post(f"/api/sessions/{created_session}/start")

    decision = {
        "wholesalePrice": 30.0,
        "internetPrice": 32.0,
        "amazonPrice": 34.0,
        "materialsQuality": 0.6,
        "stylingBudget": 200000.0,
        "numModels": 5,
        "tqmInvestment": 100000.0,
        "rdInvestment": 100000.0,
        "marketingInvestment": 150000.0,
        "advertisingBudget": 80000.0,
        "celebrityType": "none",
        "socialMediaBudget": {"tiktok": 0, "instagram": 0, "youtube": 0},
        "baseWage": 25000.0,
        "incentivePay": 0.0,
        "trainingBudget": 0.0,
        "productionQuantity": 8000,
        "overtimePercent": 0,
        "csrInvestment": 0.0,
        "dividendsPerShare": 0.0,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 0,
        "fulfillmentMethod": "fbm",
        "internetPromotion": 0.0,
    }

    client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })

    client.post(f"/api/sessions/{created_session}/process_round")

    # Now we should be in round 2
    response = client.get(f"/api/sessions/{created_session}/status")
    data = response.json()
    assert data["currentRound"] == 2


# ── Results retrieval ──────────────────────────────────────────────────────

def test_get_results(created_session):
    """Test retrieving round results."""
    client.post(f"/api/sessions/{created_session}/start")

    decision = {
        "wholesalePrice": 30.0,
        "internetPrice": 32.0,
        "amazonPrice": 34.0,
        "materialsQuality": 0.6,
        "stylingBudget": 200000.0,
        "numModels": 5,
        "tqmInvestment": 100000.0,
        "rdInvestment": 100000.0,
        "marketingInvestment": 150000.0,
        "advertisingBudget": 80000.0,
        "celebrityType": "none",
        "socialMediaBudget": {"tiktok": 0, "instagram": 0, "youtube": 0},
        "baseWage": 25000.0,
        "incentivePay": 0.0,
        "trainingBudget": 0.0,
        "productionQuantity": 8000,
        "overtimePercent": 0,
        "csrInvestment": 0.0,
        "dividendsPerShare": 0.0,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 0,
        "fulfillmentMethod": "fbm",
        "internetPromotion": 0.0,
    }

    client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })
    client.post(f"/api/sessions/{created_session}/process_round")

    response = client.get(f"/api/sessions/{created_session}/results")
    assert response.status_code == 200
    data = response.json()
    assert "1" in data["results"]  # Round 1 results
    # Team Alpha (human) + Team Gamma (AI auto-generated) = 2 results
    assert len(data["results"]["1"]) == 2


# ── Announcements ──────────────────────────────────────────────────────────

def test_create_announcement(created_session):
    """Test creating an announcement."""
    response = client.post(f"/api/sessions/{created_session}/announcements", json={
        "message": "Round 1 is starting!",
        "authorId": "professor-1",
        "authorName": "Prof. Smith",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "sent"
    assert "announcementId" in data


def test_get_announcements(created_session):
    """Test retrieving announcements."""
    # Create some announcements
    for i in range(3):
        client.post(f"/api/sessions/{created_session}/announcements", json={
            "message": f"Announcement {i+1}",
            "authorId": "professor-1",
            "authorName": "Prof. Smith",
        })

    response = client.get(f"/api/sessions/{created_session}/announcements")
    assert response.status_code == 200
    announcements = response.json()
    assert len(announcements) == 3
    assert announcements[0]["message"] == "Announcement 1"


# ── Leaderboard ────────────────────────────────────────────────────────────

def test_leaderboard_empty(created_session):
    """Test leaderboard with no rounds played."""
    response = client.get(f"/api/sessions/{created_session}/leaderboard")
    assert response.status_code == 200
    data = response.json()
    assert "leaderboard" in data
    assert len(data["leaderboard"]) == 3


def test_leaderboard_ordering(created_session):
    """Test leaderboard is sorted by total score."""
    client.post(f"/api/sessions/{created_session}/start")

    decision = {
        "wholesalePrice": 30.0,
        "internetPrice": 32.0,
        "amazonPrice": 34.0,
        "materialsQuality": 0.6,
        "stylingBudget": 200000.0,
        "numModels": 5,
        "tqmInvestment": 100000.0,
        "rdInvestment": 100000.0,
        "marketingInvestment": 150000.0,
        "advertisingBudget": 80000.0,
        "celebrityType": "none",
        "socialMediaBudget": {"tiktok": 0, "instagram": 0, "youtube": 0},
        "baseWage": 25000.0,
        "incentivePay": 0.0,
        "trainingBudget": 0.0,
        "productionQuantity": 8000,
        "overtimePercent": 0,
        "csrInvestment": 0.0,
        "dividendsPerShare": 0.0,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 0,
        "fulfillmentMethod": "fbm",
        "internetPromotion": 0.0,
    }

    client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })
    client.post(f"/api/sessions/{created_session}/process_round")

    response = client.get(f"/api/sessions/{created_session}/leaderboard")
    assert response.status_code == 200
    data = response.json()
    leaderboard = data["leaderboard"]
    assert len(leaderboard) == 3
    # Check ranking
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[1]["rank"] == 2
    assert leaderboard[2]["rank"] == 3
    # Scores should be descending
    assert leaderboard[0]["totalScore"] >= leaderboard[1]["totalScore"]


# ── Session end ────────────────────────────────────────────────────────────

def test_end_session(created_session):
    """Test ending a session."""
    client.post(f"/api/sessions/{created_session}/start")

    decision = {
        "wholesalePrice": 30.0,
        "internetPrice": 32.0,
        "amazonPrice": 34.0,
        "materialsQuality": 0.6,
        "stylingBudget": 200000.0,
        "numModels": 5,
        "tqmInvestment": 100000.0,
        "rdInvestment": 100000.0,
        "marketingInvestment": 150000.0,
        "advertisingBudget": 80000.0,
        "celebrityType": "none",
        "socialMediaBudget": {"tiktok": 0, "instagram": 0, "youtube": 0},
        "baseWage": 25000.0,
        "incentivePay": 0.0,
        "trainingBudget": 0.0,
        "productionQuantity": 8000,
        "overtimePercent": 0,
        "csrInvestment": 0.0,
        "dividendsPerShare": 0.0,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 0,
        "fulfillmentMethod": "fbm",
        "internetPromotion": 0.0,
    }

    client.post(f"/api/sessions/{created_session}/submit_decision", json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })
    client.post(f"/api/sessions/{created_session}/process_round")

    response = client.post(f"/api/sessions/{created_session}/end")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ended"

    # Verify session state is finished
    session_resp = client.get(f"/api/sessions/{created_session}")
    assert session_resp.json()["state"] == "finished"


# ── Status endpoint ────────────────────────────────────────────────────────

def test_session_status(created_session):
    """Test session status endpoint."""
    # Before starting
    response = client.get(f"/api/sessions/{created_session}/status")
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == created_session
    assert data["state"] == "creating"
    assert data["currentRound"] == 0

    # After starting
    client.post(f"/api/sessions/{created_session}/start")
    response = client.get(f"/api/sessions/{created_session}/status")
    data = response.json()
    assert data["state"] == "active"
    assert data["currentRound"] == 1
