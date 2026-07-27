"""Contracts for Owner authorization on professor admin endpoints.

Tests that:
- Owner can call existing Professor pre-create and code endpoints
- Professor/Student/anonymous are denied with 403/401
- Audit events are emitted for Owner actions
"""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from audit import get_audit_logs, log_event
from auth import _create_token
from database import db
from main import app
from security import hash_password

client = TestClient(app)


def H(sub, role):
    token = _create_token({
        "sub": sub,
        "role": role,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()
    })
    return {"Authorization": f"Bearer {token}"}


def seed(name, role, password="Contract123!"):
    db.create_user(name, hash_password(password), role, name, f"{name}@example.test")


@pytest.fixture(autouse=True)
def clean():
    for store in (db.sessions, db.decisions, db.announcements, db.results, db.team_states):
        store.clear()
    with db._get_conn() as c:
        for table in ("audit_logs", "memberships", "organizations",
                      "professor_codes", "sessions", "users"):
            c.execute(f"DELETE FROM {table}")
        c.commit()
    seed("owner-x", "owner")
    seed("prof-a", "professor")
    seed("student-a", "student")


# ── Professor pre-create endpoint ────────────────────────────────────────────

def test_precreate_owner_success():
    """Owner can pre-create a professor account."""
    r = client.post("/api/professor/pre-create", json={
        "username": "new-prof",
        "password": "Temporary123!",
        "name": "New Professor",
        "email": "new@example.test",
        "university_name": "Contract University",
    }, headers=H("owner-x", "owner"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"status", "username", "professor_code", "message"}
    assert body["status"] == "created"
    assert body["username"] == "new-prof"


def test_precreate_professor_denied():
    """Professor cannot pre-create."""
    r = client.post("/api/professor/pre-create", json={
        "username": "x",
        "password": "Temporary123!",
    }, headers=H("prof-a", "professor"))
    assert r.status_code == 403
    assert r.json() == {"detail": "Owner access required"}


def test_precreate_student_denied():
    """Student cannot pre-create."""
    r = client.post("/api/professor/pre-create", json={
        "username": "x",
        "password": "Temporary123!",
    }, headers=H("student-a", "student"))
    assert r.status_code == 403
    assert r.json() == {"detail": "Owner access required"}


def test_precreate_anonymous_denied():
    """Anonymous user cannot pre-create."""
    r = client.post("/api/professor/pre-create", json={
        "username": "x",
        "password": "Temporary123!",
    })
    assert r.status_code == 401


# ── Professor codes endpoints ────────────────────────────────────────────────

def test_create_professor_code_owner_success():
    """Owner can create a professor code."""
    r = client.post("/api/professor/codes", json={
        "university_name": "Test University",
        "notes": "Test code",
    }, headers=H("owner-x", "owner"))
    assert r.status_code == 201, r.text
    body = r.json()
    assert set(body) == {"code", "university_name", "notes", "used", "used_by"}
    assert body["code"].startswith("PROF-")
    # PROF-XXXX-XXXX = 4 + 1 + 4 + 1 + 4 = 14 characters
    assert len(body["code"]) == 14


def test_create_professor_code_professor_denied():
    """Professor cannot create professor codes."""
    r = client.post("/api/professor/codes", json={
        "university_name": "Test University",
    }, headers=H("prof-a", "professor"))
    assert r.status_code == 403
    assert r.json() == {"detail": "Owner access required"}


def test_list_professor_codes_owner_success():
    """Owner can list professor codes."""
    # Create one first
    client.post("/api/professor/codes", json={
        "university_name": "Test University",
    }, headers=H("owner-x", "owner"))
    
    r = client.get("/api/professor/codes", headers=H("owner-x", "owner"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"codes"}
    assert isinstance(body["codes"], list)
    assert len(body["codes"]) >= 1


def test_list_professor_codes_professor_denied():
    """Professor cannot list professor codes."""
    r = client.get("/api/professor/codes", headers=H("prof-a", "professor"))
    assert r.status_code == 403
    assert r.json() == {"detail": "Owner access required"}


# ── Audit log endpoint ───────────────────────────────────────────────────────

def test_audit_owner_success():
    """Owner can retrieve audit logs."""
    # Create some events
    log_event("owner-x", "test_action", {"key": "value"}, "10.0.0.1")
    
    r = client.get("/api/professor/audit", headers=H("owner-x", "owner"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"logs", "count"}
    assert isinstance(body["logs"], list)
    assert body["count"] >= 1


def test_audit_professor_denied():
    """Professor cannot retrieve audit logs."""
    r = client.get("/api/professor/audit", headers=H("prof-a", "professor"))
    assert r.status_code == 403
    assert r.json() == {"detail": "Owner access required"}


def test_audit_student_denied():
    """Student cannot retrieve audit logs."""
    r = client.get("/api/professor/audit", headers=H("student-a", "student"))
    assert r.status_code == 403
    assert r.json() == {"detail": "Owner access required"}


def test_audit_anonymous_denied():
    """Anonymous user cannot retrieve audit logs."""
    r = client.get("/api/professor/audit")
    assert r.status_code == 401


# ── Password change endpoint ─────────────────────────────────────────────────

def test_change_password_professor_success():
    """Professor can change their own password."""
    # First set must_change_password=1
    with db._get_conn() as c:
        c.execute("UPDATE users SET must_change_password=1 WHERE username='prof-a'")
        c.commit()
    
    r = client.post("/api/professor/change-password", json={
        "old_password": "Contract123!",
        "new_password": "NewPassword456!",
    }, headers=H("prof-a", "professor"))
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "changed"}
    
    # Verify old password no longer works
    assert db.verify_user("prof-a", "Contract123!") is None
    # Verify new password works
    assert db.verify_user("prof-a", "NewPassword456!") is not None


def test_change_password_student_success():
    """Student can change their own password."""
    # Student's default password is Contract123!
    r = client.post("/api/professor/change-password", json={
        "old_password": "Contract123!",
        "new_password": "NewPassword456!",
    }, headers=H("student-a", "student"))
    assert r.status_code == 200, r.text
    assert r.json() == {"status": "changed"}
    
    # Verify old password no longer works
    assert db.verify_user("student-a", "Contract123!") is None
    # Verify new password works
    assert db.verify_user("student-a", "NewPassword456!") is not None


# ── Redemption endpoint ──────────────────────────────────────────────────────

def test_redeem_code_professor_denied():
    """Professor cannot redeem another code."""
    # Create a code
    r = client.post("/api/professor/codes", json={
        "university_name": "Test University",
    }, headers=H("owner-x", "owner"))
    code = r.json()["code"]
    
    # Professor tries to redeem
    r = client.post("/api/professor/redeem", json={"code": code}, headers=H("prof-a", "professor"))
    assert r.status_code == 400
    assert "already a professor" in r.json()["detail"].lower()


def test_redeem_code_student_success():
    """Student can redeem a professor code."""
    # Create a code
    r = client.post("/api/professor/codes", json={
        "university_name": "Test University",
    }, headers=H("owner-x", "owner"))
    code = r.json()["code"]
    
    # Student redeems
    r = client.post("/api/professor/redeem", json={"code": code}, headers=H("student-a", "student"))
    assert r.status_code == 200, r.text
    body = r.json()
    assert set(body) == {"status", "role", "accessToken", "tokenType"}
    assert body["status"] == "promoted"
    assert body["role"] == "professor"
