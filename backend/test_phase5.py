"""Tests for Phase 5 features: Auth, WebSocket, Grade Export."""

import os
import pytest
from fastapi.testclient import TestClient

from main import app
from database import db
from starlette.websockets import WebSocketDisconnect

client = TestClient(app)


def auth_headers(token):
    """Build an Authorization header for an access token."""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def clean_phase5_auth_state(monkeypatch):
    """Give each auth-contract test a known professor and isolated users."""
    monkeypatch.setenv("PRACTENTURE_PROFESSOR_PASSWORD", "practenture2026")
    conn = db._get_conn()
    conn.execute("DELETE FROM memberships")
    conn.execute("DELETE FROM organizations")
    conn.execute("DELETE FROM class_enrollments")
    conn.execute("DELETE FROM classes")
    conn.execute("DELETE FROM professor_codes")
    conn.execute("DELETE FROM users")
    conn.commit()
    from auth import ensure_professor
    ensure_professor()
    organization = db.get_or_create_organization("Legacy Phase 5 Tests")
    assert db.add_membership("professor", organization["id"], "professor")
    yield


# ── Authentication Tests ──────────────────────────────────────────────────


def test_login_professor():
    """Professor can log in with password."""
    resp = client.post("/api/auth/login", json={
        "provider": "password",
        "username": "professor",
        "password": "practenture2026",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["role"] == "professor"
    assert "accessToken" in data


def test_login_student_not_registered():
    """Unregistered student cannot log in."""
    resp = client.post("/api/auth/login", json={
        "provider": "password",
        "username": "nonexistent",
        "password": "wrong",
    })
    assert resp.status_code == 401


def test_login_wrong_password():
    """Wrong password returns 401."""
    resp = client.post("/api/auth/login", json={
        "provider": "password",
        "username": "professor",
        "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_register_student():
    """New student can register."""
    resp = client.post("/api/auth/register", json={
        "student_id": "S12345",
        "name": "Test Student",
        "password": "TestPass123!",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["student_id"] == "S12345"
    assert data["name"] == "Test Student"


def test_register_duplicate():
    """Duplicate registration returns 409."""
    # Register first
    client.post("/api/auth/register", json={
        "student_id": "S67890",
        "name": "Duplicate Student",
        "password": "TestPass456!",
    })
    # Try again
    resp = client.post("/api/auth/register", json={
        "student_id": "S67890",
        "name": "Duplicate Student",
        "password": "TestPass456!",
    })
    assert resp.status_code == 409


def test_login_registered_student():
    """Registered student can log in."""
    # Register first
    client.post("/api/auth/register", json={
        "student_id": "S99999",
        "name": "Login Test Student",
        "password": "LoginPass123!",
    })
    # Login (use student_id as username)
    resp = client.post("/api/auth/login", json={
        "provider": "password",
        "username": "S99999",
        "password": "LoginPass123!",
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "student"


def test_verify_token():
    """Valid token returns user info."""
    # Login
    resp = client.post("/api/auth/login", json={
        "provider": "password",
        "username": "professor",
        "password": "practenture2026",
    })
    token = resp.json()["accessToken"]

    # Verify
    resp = client.post("/api/auth/verify", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["valid"] is True
    assert resp.json()["role"] == "professor"


def test_verify_invalid_token():
    """Invalid token returns 401."""
    resp = client.post("/api/auth/verify", headers={"Authorization": "Bearer invalidtoken123"})
    assert resp.status_code == 401


def test_professor_only_endpoint():
    """Professor can access professor-only endpoint."""
    resp = client.post("/api/auth/login", json={
        "provider": "password",
        "username": "professor",
        "password": "practenture2026",
    })
    token = resp.json()["accessToken"]

    resp = client.post("/api/auth/professor-only", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


# ── WebSocket Tests ──────────────────────────────────────────────────────


def test_websocket_connect_no_session():
    """Connecting to non-existent session closes connection."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/BIZ-XXXXXX?token=fake") as ws:
            pass


def test_websocket_connect_no_token():
    """Connecting without token closes with auth error."""
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/ws/BIZ-XXXXXX") as ws:
            pass


@pytest.mark.skipif(
    os.environ.get("CI") or not os.environ.get("APPLE_AUDIENCE"),
    reason="Requires Apple JWKS network access and APPLE_AUDIENCE configured",
)
def test_websocket_student_login_provider():
    """Apple/Google login provider works with valid-structure token."""
    import base64, json, hmac, hashlib

    # Create a fake JWT with valid structure (unsigned, for testing)
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    payload = base64.urlsafe_b64encode(json.dumps({"sub": "apple_user_123", "email": "test@apple.com"}).encode()).rstrip(b"=").decode()
    signing_input = f"{header}.{payload}"
    signature = hmac.new(b"test-secret-for-validation", signing_input.encode(), hashlib.sha256).digest()
    signature_b = base64.urlsafe_b64encode(signature).rstrip(b"=").decode()
    fake_token = f"{signing_input}.{signature_b}"

    resp = client.post("/api/auth/login", json={
        "provider": "apple",
        "id_token": fake_token,
    })
    assert resp.status_code == 200
    assert resp.json()["role"] == "student"
    assert "accessToken" in resp.json()


# ── Grade Export Test ────────────────────────────────────────────────────


def test_end_session_returns_results():
    """Ending a session returns final results for grade export."""
    # Login as professor
    resp = client.post("/api/auth/login", json={
        "provider": "password", "username": "professor", "password": "practenture2026",
    })
    token = resp.json()["accessToken"]

    # Create session
    resp = client.post("/api/sessions", json={
        "config": {"totalRounds": 3, "numberOfAICompetitors": 1},
        "teams": [
            {"teamName": "Alpha", "studentId": "S001"},
            {"teamName": "Beta", "studentId": "S002"},
        ],
        "created_by": "professor",
    }, headers=auth_headers(token))
    code = resp.json()["code"]

    # Start session
    client.post(f"/api/sessions/{code}/start", headers=auth_headers(token))

    # End session (no rounds played yet, but should work)
    resp = client.post(f"/api/sessions/{code}/end", headers=auth_headers(token))
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ended"
    # Results may be empty since no rounds were played
    assert "finalResults" in data
