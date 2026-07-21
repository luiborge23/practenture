"""Tests for BizSimAI backend."""

import time

import pytest
from fastapi.testclient import TestClient

from main import app
from database import db
from auth import _create_token

client = TestClient(app)


# ── Auth helper ─────────────────────────────────────────────────────────────

def get_professor_token():
    """Issue a professor token for the fixture session owner."""
    return _create_token({
        "sub": "professor",
        "role": "professor",
        "tenantId": "",
        "exp": time.time() + 3600,
    })


def auth_headers(token):
    """Build an Authorization header for an access token."""
    return {"Authorization": f"Bearer {token}"}


def register_student_token(student_id):
    """Issue a student token whose subject is the fixture student ID."""
    return _create_token({
        "sub": student_id,
        "role": "student",
        "name": f"Test {student_id}",
        "tenantId": "",
        "exp": time.time() + 3600,
    })


def get_student_token(student_id):
    """Issue a token for a student already bound to a fixture team."""
    return register_student_token(student_id)


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
def student_tokens():
    """Tokens bound to the human students preconfigured in created_session."""
    return {
        student_id: register_student_token(student_id)
        for student_id in ("student-1", "student-2", "student-3", "student-4")
    }


@pytest.fixture
def created_session(professor_token, student_tokens):
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
    }, headers=auth_headers(professor_token))
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
    # Verify the session exists (public endpoint for tests)
    response = client.get(f"/api/sessions/{created_session}/public")
    assert response.status_code == 200
    session = response.json()
    assert session["code"] == created_session
    assert session["state"] == "creating"
    # Three configured teams plus two auto-created AI competitors.
    assert len(session["teams"]) == 5
    assert sum(team["isAI"] for team in session["teams"]) == 3


# ── Session get ────────────────────────────────────────────────────────────

def test_get_nonexistent_session():
    response = client.get("/api/sessions/BIZ-999999/public")
    assert response.status_code == 404


# ── Session join ───────────────────────────────────────────────────────────

def test_join_session(created_session, student_tokens):
    """Test that a student can join a session."""
    # Start the session first
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

    response = client.put(
        f"/api/sessions/{created_session}/join",
        headers=auth_headers(student_tokens["student-3"]),
        json={
        "teamName": "Team Delta",
        "studentId": "student-3",
    })
    assert response.status_code == 200
    data = response.json()
    assert data["teamId"] == "Team Delta"
    assert data["teamName"] == "Team Delta"
    assert data["state"] == "active"


def test_join_duplicate_team_name(created_session, student_tokens):
    """Test that joining with a duplicate team name fails."""
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

    # Join first time — should succeed
    client.put(
        f"/api/sessions/{created_session}/join",
        headers=auth_headers(student_tokens["student-3"]),
        json={
        "teamName": "Team Delta",
        "studentId": "student-3",
    })

    # Join again with same name — should fail
    response = client.put(
        f"/api/sessions/{created_session}/join",
        headers=auth_headers(student_tokens["student-4"]),
        json={
        "teamName": "Team Delta",
        "studentId": "student-4",
    })
    assert response.status_code == 409


# ── Teams listing ──────────────────────────────────────────────────────────

def test_get_teams(created_session):
    """Test listing teams in a session."""
    response = client.get(
        f"/api/sessions/{created_session}/teams",
        headers=auth_headers(get_professor_token()),
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["teams"]) == 5
    assert sum(team["isAI"] for team in data["teams"]) == 3
    team_names = [t["teamName"] for t in data["teams"]]
    assert "Team Alpha" in team_names
    assert "Team Beta" in team_names
    assert "Team Gamma" in team_names


# ── Decision submission ────────────────────────────────────────────────────

def test_submit_decision(created_session):
    """Test submitting a round decision."""
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

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
    response = client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
        "round": 1,
        "teamId": "Team Alpha",
        "decision": decision,
    })
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "accepted"
    assert data["round"] == 1

    # Double submission should fail
    response = client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
        "round": 1,
        "teamId": "Team Alpha",
        "decision": decision,
    })
    assert response.status_code == 409


def test_submit_wrong_round(created_session):
    """Test submitting a decision for the wrong round."""
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

    response = client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
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
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

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

    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
        "round": 1,
        "teamId": "Team Alpha",
        "decision": decision,
    })

    response = client.get(
        f"/api/sessions/{created_session}/decisions/1",
        headers=auth_headers(get_professor_token()),
    )
    assert response.status_code == 200
    data = response.json()
    assert "Team Alpha" in data["decisions"]
    assert data["round"] == 1


# ── Round processing ───────────────────────────────────────────────────────

def test_process_round_returns_results(created_session):
    """Test that processing a round returns valid results."""
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

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
    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })
    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-2")),
        json={
        "round": 1, "teamId": "Team Beta", "decision": decision,
    })

    # Process after both human teams submit; AI teams auto-generate.
    response = client.post(
        f"/api/sessions/{created_session}/process_round",
        headers=auth_headers(get_professor_token()),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["round"] == 1
    assert len(data["results"]) == 5

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
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

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

    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })

    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-2")),
        json={
        "round": 1, "teamId": "Team Beta", "decision": decision,
    })

    client.post(
        f"/api/sessions/{created_session}/process_round",
        headers=auth_headers(get_professor_token()),
    )

    # Now we should be in round 2
    token = get_professor_token()
    response = client.get(
        f"/api/sessions/{created_session}/status",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["currentRound"] == 2


# ── Results retrieval ──────────────────────────────────────────────────────

def test_get_results(created_session):
    """Test retrieving round results."""
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

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

    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })
    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-2")),
        json={
        "round": 1, "teamId": "Team Beta", "decision": decision,
    })
    client.post(
        f"/api/sessions/{created_session}/process_round",
        headers=auth_headers(get_professor_token()),
    )

    response = client.get(
        f"/api/sessions/{created_session}/results",
        headers=auth_headers(get_professor_token()),
    )
    assert response.status_code == 200
    data = response.json()
    assert "1" in data["results"]  # Round 1 results
    assert len(data["results"]["1"]) == 5


# ── Announcements ──────────────────────────────────────────────────────────

def test_create_announcement(created_session):
    """Test creating an announcement."""
    response = client.post(
        f"/api/sessions/{created_session}/announcements",
        headers=auth_headers(get_professor_token()),
        json={
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
        client.post(
        f"/api/sessions/{created_session}/announcements",
        headers=auth_headers(get_professor_token()),
        json={
            "message": f"Announcement {i+1}",
            "authorId": "professor-1",
            "authorName": "Prof. Smith",
        })

    response = client.get(
        f"/api/sessions/{created_session}/announcements",
        headers=auth_headers(get_professor_token()),
    )
    assert response.status_code == 200
    announcements = response.json()
    assert len(announcements) == 3
    assert announcements[0]["message"] == "Announcement 1"


# ── Leaderboard ────────────────────────────────────────────────────────────

def test_leaderboard_empty(created_session):
    """Test leaderboard with no rounds played."""
    response = client.get(
        f"/api/sessions/{created_session}/leaderboard",
        headers=auth_headers(get_professor_token()),
    )
    assert response.status_code == 200
    data = response.json()
    assert "leaderboard" in data
    assert len(data["leaderboard"]) == 5


def test_leaderboard_ordering(created_session):
    """Test leaderboard is sorted by total score."""
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

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

    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })
    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-2")),
        json={
        "round": 1, "teamId": "Team Beta", "decision": decision,
    })
    client.post(
        f"/api/sessions/{created_session}/process_round",
        headers=auth_headers(get_professor_token()),
    )

    response = client.get(
        f"/api/sessions/{created_session}/leaderboard",
        headers=auth_headers(get_professor_token()),
    )
    assert response.status_code == 200
    data = response.json()
    leaderboard = data["leaderboard"]
    assert len(leaderboard) == 5
    assert [entry["rank"] for entry in leaderboard] == [1, 2, 3, 4, 5]
    scores = [entry["totalScore"] for entry in leaderboard]
    assert scores == sorted(scores, reverse=True)


# ── Session end ────────────────────────────────────────────────────────────

def test_end_session(created_session):
    """Test ending a session."""
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )

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

    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-1")),
        json={
        "round": 1, "teamId": "Team Alpha", "decision": decision,
    })
    client.post(
        f"/api/sessions/{created_session}/submit_decision",
        headers=auth_headers(get_student_token("student-2")),
        json={
        "round": 1, "teamId": "Team Beta", "decision": decision,
    })
    client.post(
        f"/api/sessions/{created_session}/process_round",
        headers=auth_headers(get_professor_token()),
    )

    response = client.post(
        f"/api/sessions/{created_session}/end",
        headers=auth_headers(get_professor_token()),
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ended"

    # Verify session state is finished
    session_resp = client.get(f"/api/sessions/{created_session}/public")
    assert session_resp.json()["state"] == "finished"


# ── Status endpoint ────────────────────────────────────────────────────────

def test_session_status(created_session, professor_token):
    """Test authenticated session status endpoint."""
    headers = {"Authorization": f"Bearer {professor_token}"}
    # Before starting
    response = client.get(f"/api/sessions/{created_session}/status", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["code"] == created_session
    assert data["state"] == "creating"
    assert data["currentRound"] == 0

    # After starting
    client.post(
        f"/api/sessions/{created_session}/start",
        headers=auth_headers(get_professor_token()),
    )
    response = client.get(f"/api/sessions/{created_session}/status", headers=headers)
    data = response.json()
    assert data["state"] == "active"
    assert data["currentRound"] == 1


def _cohort_decision(student_index: int, round_num: int) -> dict:
    """Full modern PlayerDecision payload with deterministic strategy variation."""
    strategy = student_index % 5
    return {
        "wholesalePrice": 22.0 + strategy * 4 + round_num * 0.15,
        "internetPrice": 24.0 + strategy * 4 + round_num * 0.15,
        "amazonPrice": 25.0 + strategy * 4 + round_num * 0.15,
        "materialsQuality": 0.25 + strategy * 0.15,
        "stylingBudget": 40000.0 + strategy * 15000,
        "numModels": 3 + strategy,
        "tqmInvestment": 25000.0 + strategy * 10000,
        "rdInvestment": 30000.0 + strategy * 12000,
        "marketingInvestment": 45000.0 + strategy * 15000,
        "advertisingBudget": 30000.0 + strategy * 10000,
        "celebrityType": ["none", "local", "local", "national", "national"][strategy],
        "socialMediaBudget": {
            "tiktok": 5000.0 + strategy * 1500,
            "instagram": 6000.0 + strategy * 1700,
            "youtube": 4000.0 + strategy * 1200,
        },
        "baseWage": 18000.0 + strategy * 1500,
        "incentivePay": 500.0 + strategy * 250,
        "trainingBudget": 12000.0 + strategy * 4000,
        "productionQuantity": 6500 + strategy * 600,
        "overtimePercent": min(20, strategy * 4),
        "csrInvestment": 5000.0 + strategy * 3000,
        "dividendsPerShare": strategy * 0.1,
        "newLoanAmount": 0.0,
        "sharesBuyback": 0,
        "sharesIssued": 0,
        "retailOutlets": 4 + strategy,
        "fulfillmentMethod": "fba" if strategy >= 2 else "fbm",
        "internetPromotion": 0.10 + strategy * 0.05,
    }


def test_authoritative_20_students_complete_8_rounds(professor_token):
    """API E2E: 20 unique teams submit 160 decisions; backend processes exactly once/round."""
    headers = {"Authorization": f"Bearer {professor_token}"}
    create = client.post("/api/sessions", json={
        "config": {
            "totalRounds": 8,
            "numberOfAICompetitors": 3,
            "randomSeed": 20260716,
            "startingCash": 500000.0,
            "initialEquity": 300000.0,
            "plantCapacity": 12000,
            "baseMarketDemand": 50000,
        },
        "teams": [],
        "created_by": "qa-professor",
        "maxHumanTeams": 30,
    }, headers=headers)
    assert create.status_code == 201, create.text
    code = create.json()["code"]

    team_ids = []
    cohort_tokens = {}
    for index in range(1, 21):
        student_id = f"STU{index:03d}"
        cohort_tokens[student_id] = register_student_token(student_id)
        team_name = f"Team-STU{index:03d}"
        joined = client.put(
            f"/api/sessions/{code}/join",
            headers=auth_headers(cohort_tokens[student_id]),
            json={
            "teamName": team_name,
            "studentId": student_id,
        })
        assert joined.status_code == 200, joined.text
        assert joined.json()["teamId"] == team_name
        team_ids.append(team_name)

    process_calls = 0
    for round_num in range(1, 9):
        for index, team_id in enumerate(team_ids, start=1):
            student_id = f"STU{index:03d}"
            submitted = client.post(
                f"/api/sessions/{code}/submit_decision",
                headers=auth_headers(cohort_tokens[student_id]),
                json={
                "round": round_num,
                "teamId": team_id,
                "decision": _cohort_decision(index, round_num),
            })
            assert submitted.status_code == 200, submitted.text
            assert submitted.json()["teamId"] == team_id

        before = client.get(f"/api/sessions/{code}/status", headers=headers)
        assert before.status_code == 200, before.text
        assert before.json()["currentRound"] == round_num
        assert before.json()["teamsSubmitted"] == 20

        processed = client.post(
            f"/api/sessions/{code}/process_round",
            headers=headers,
        )
        process_calls += 1
        assert processed.status_code == 200, processed.text
        body = processed.json()
        assert body["round"] == round_num
        assert len(body["results"]) == 23  # 20 humans + 3 AI
        assert len({result["teamId"] for result in body["results"]}) == 23

        after = client.get(f"/api/sessions/{code}/status", headers=headers)
        assert after.status_code == 200, after.text
        expected_round = round_num + 1 if round_num < 8 else 8
        assert after.json()["currentRound"] == expected_round
        assert after.json()["state"] == ("active" if round_num < 8 else "finished")

    assert process_calls == 8
    results = client.get(f"/api/sessions/{code}/results", headers=headers)
    assert results.status_code == 200
    assert set(results.json()["results"]) == {str(n) for n in range(1, 9)}
    assert all(len(entries) == 23 for entries in results.json()["results"].values())

    leaderboard = client.get(f"/api/sessions/{code}/leaderboard", headers=headers)
    assert leaderboard.status_code == 200
    entries = leaderboard.json()["leaderboard"]
    assert len(entries) == 23
    assert [entry["rank"] for entry in entries] == list(range(1, 24))
    scores = [entry["totalScore"] for entry in entries]
    assert scores == sorted(scores, reverse=True)
