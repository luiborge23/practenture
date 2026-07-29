"""Focused contracts for the standalone Admin V2 users vertical slice."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import sqlite3

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from admin_v2.dependencies import require_admin_session, require_recent_auth_session
from admin_v2.errors import AdminError, error_envelope
from admin_v2.users_routes import router
from admin_v2.users_schemas import UserActionRequest
from admin_v2.users_service import user_service
from database import db
from security import verify_password
from auth import _create_access_token, _verify_token


@pytest.fixture(autouse=True)
def clean_users_lane():
    conn = db.connect()
    try:
        conn.execute("DELETE FROM admin_idempotency_records")
        conn.execute("DELETE FROM admin_audit_events")
        conn.execute("DELETE FROM admin_sessions WHERE owner_user_id LIKE 'auv2_%'")
        conn.execute("DELETE FROM refresh_tokens WHERE user_id LIKE 'auv2_%'")
        conn.execute("DELETE FROM memberships WHERE user_id LIKE 'auv2_%'")
        conn.execute("DELETE FROM users WHERE username LIKE 'auv2_%'")
        conn.execute("DELETE FROM organizations WHERE id LIKE 'auv2_%'")
        conn.commit()
    finally:
        conn.close()
    yield


@pytest.fixture
def owner_session():
    return SimpleNamespace(record=SimpleNamespace(owner_user_id="owner", role="owner"), user={"username": "owner", "role": "owner", "status": "active"})


@pytest.fixture
def app() -> FastAPI:
    isolated = FastAPI()

    @isolated.middleware("http")
    async def context(request: Request, call_next):
        request.state.request_id = "req-users-test"
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        return response

    @isolated.exception_handler(AdminError)
    async def admin_error(request: Request, exc: AdminError):
        return JSONResponse(status_code=exc.status_code, content=error_envelope(exc.code, exc.message, request.state.request_id), headers=exc.headers)

    isolated.include_router(router, prefix="/api/admin/v2")
    return isolated


@pytest.fixture
def owner_client(app: FastAPI, owner_session):
    app.dependency_overrides[require_admin_session] = lambda: owner_session
    app.dependency_overrides[require_recent_auth_session] = lambda: owner_session
    with TestClient(app) as client:
        yield client


def insert_user(username: str, *, role: str = "professor", status: str = "active", created_at: str = "2026-07-28T10:00:00+00:00", password_hash: str = "unused"):
    conn = db.connect()
    try:
        conn.execute("""INSERT INTO users
            (username,password_hash,role,name,email,provider,must_change_password,status,created_at)
            VALUES (?,?,?,?,?,'password',0,?,?)""",
            (username, password_hash, role, username.replace("auv2_", "").title(), f"{username}@example.test", status, created_at))
        conn.commit()
    finally:
        conn.close()


def insert_org_and_membership(username: str):
    conn = db.connect()
    try:
        conn.execute("INSERT INTO organizations (id,name,slug,status) VALUES ('auv2_org','Admin Users Org','auv2-org','active')")
        conn.execute("INSERT INTO memberships (id,user_id,org_id,role) VALUES (?,?, 'auv2_org','professor')", (f"m-{username}", username))
        conn.commit()
    finally:
        conn.close()


def assert_error(response, status_code: int, code: str):
    assert response.status_code == status_code, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["requestId"] == "req-users-test"


def test_routes_use_owner_reads_and_recent_auth_for_every_mutation(app: FastAPI):
    routes = {(next(iter(route.methods)), route.path): route for route in app.routes if isinstance(route, APIRoute) and route.path.startswith("/api/admin/v2/users")}
    for key in (("GET", "/api/admin/v2/users"), ("GET", "/api/admin/v2/users/{userId}")):
        assert require_admin_session in [d.call for d in routes[key].dependant.dependencies]
    for path in ("/api/admin/v2/users/precreate", "/api/admin/v2/users/{userId}/suspend", "/api/admin/v2/users/{userId}/reactivate", "/api/admin/v2/users/{userId}/require-password-reset", "/api/admin/v2/users/{userId}/revoke-sessions"):
        assert require_recent_auth_session in [d.call for d in routes[("POST", path)].dependant.dependencies]


def test_anonymous_read_is_denied_by_owner_cookie_boundary(app: FastAPI):
    with TestClient(app) as client:
        response = client.get("/api/admin/v2/users")
    assert_error(response, 401, "ADMIN_AUTH_REQUIRED")


def test_list_filters_sorts_and_uses_query_bound_opaque_cursor(owner_client: TestClient):
    insert_user("auv2_alpha", created_at="2026-07-28T10:00:00+00:00")
    insert_user("auv2_beta", created_at="2026-07-28T11:00:00+00:00")
    insert_user("auv2_student", role="student")
    insert_org_and_membership("auv2_alpha")
    first = owner_client.get("/api/admin/v2/users", params={"search": "auv2_", "role": "professor", "status": "active", "sort": "-createdAt", "limit": 1})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["totalCount"] == 2
    assert body["users"][0]["id"] == "auv2_beta"
    assert body["pageInfo"]["hasNextPage"] is True
    cursor = body["pageInfo"]["nextCursor"]
    second = owner_client.get("/api/admin/v2/users", params={"search": "auv2_", "role": "professor", "status": "active", "sort": "-createdAt", "limit": 1, "cursor": cursor})
    assert [item["id"] for item in second.json()["users"]] == ["auv2_alpha"]
    mismatched = owner_client.get("/api/admin/v2/users", params={"search": "auv2_", "role": "student", "cursor": cursor})
    assert_error(mismatched, 400, "ADMIN_CURSOR_INVALID")
    org = owner_client.get("/api/admin/v2/users", params={"organizationId": "auv2_org"})
    assert org.json()["users"][0]["organizationIds"] == ["auv2_org"]


def test_precreate_returns_password_once_but_persists_only_hash_and_redacted_audit(owner_client: TestClient):
    response = owner_client.post("/api/admin/v2/users/precreate", json={"username": "auv2_new", "role": "professor", "name": "New Professor", "email": "NEW@example.test"})
    assert response.status_code == 201, response.text
    body = response.json()
    temporary = body["temporaryPassword"]
    assert body["user"]["mustChangePassword"] is True
    assert body["user"]["email"] == "new@example.test"
    conn = db.connect()
    try:
        row = conn.execute("SELECT password_hash FROM users WHERE username='auv2_new'").fetchone()
        assert row[0] != temporary and verify_password(temporary, row[0])
        persisted = "\n".join(str(tuple(row)) for row in conn.execute("SELECT actor_json,target_json,metadata_json FROM admin_audit_events"))
        assert temporary not in persisted
        assert conn.execute("SELECT COUNT(*) FROM admin_idempotency_records").fetchone()[0] == 0
    finally:
        conn.close()
    detail = owner_client.get("/api/admin/v2/users/auv2_new")
    assert "temporaryPassword" not in detail.text
    duplicate = owner_client.post("/api/admin/v2/users/precreate", json={"username": "auv2_new", "role": "professor", "name": "Other", "email": "other@example.test"})
    assert_error(duplicate, 409, "ADMIN_USER_CONFLICT")


def test_detail_has_stable_not_found_error(owner_client: TestClient):
    assert_error(owner_client.get("/api/admin/v2/users/auv2_missing"), 404, "ADMIN_USER_NOT_FOUND")


def test_suspend_atomically_changes_status_and_revokes_all_persisted_auth_state(owner_client: TestClient):
    insert_user("auv2_target")
    conn = db.connect()
    try:
        conn.execute("INSERT INTO refresh_tokens(token_hash,user_id,issued_at,expires_at,revoked) VALUES ('auv2_rt','auv2_target',1,9999999999,0)")
        conn.execute("""INSERT INTO admin_sessions
            (id,token_hash,csrf_token_hash,owner_user_id,role,created_at,last_seen_at,idle_expires_at,absolute_expires_at)
            VALUES ('auv2_session','auv2_th','auv2_csrf','auv2_target','owner','2026-01-01','2026-01-01','2099-01-01','2099-01-01')""")
        conn.commit()
    finally:
        conn.close()
    response = owner_client.post("/api/admin/v2/users/auv2_target/suspend", headers={"Idempotency-Key": "suspend-target"}, json={"reason": "security review"})
    assert response.status_code == 200, response.text
    assert response.json()["user"]["status"] == "suspended"
    assert response.json()["sessionsRevoked"] is True
    conn = db.connect()
    try:
        user = conn.execute("SELECT status,password_changed_at,disable_reason FROM users WHERE username='auv2_target'").fetchone()
        assert tuple(user)[0] == "suspended" and user[1] and user[2] == "security review"
        assert conn.execute("SELECT revoked FROM refresh_tokens WHERE token_hash='auv2_rt'").fetchone()[0] == 1
        assert conn.execute("SELECT revoked_at FROM admin_sessions WHERE id='auv2_session'").fetchone()[0]
    finally:
        conn.close()


def test_suspend_rolls_back_status_when_session_revocation_fails(owner_session, monkeypatch):
    insert_user("auv2_atomic")
    original = user_service.repository.revoke_sessions
    monkeypatch.setattr(user_service.repository, "revoke_sessions", lambda *args, **kwargs: (_ for _ in ()).throw(sqlite3.OperationalError("forced")))
    with pytest.raises(sqlite3.OperationalError, match="forced"):
        user_service.action(session=owner_session, user_id="auv2_atomic", action="suspend", payload=UserActionRequest(reason="test"), idempotency_key="atomic-fail", request_id="req-atomic")
    monkeypatch.setattr(user_service.repository, "revoke_sessions", original)
    user = db.get_user("auv2_atomic")
    assert user is not None and user["status"] == "active"


def test_reactivate_password_reset_and_revoke_sessions_are_idempotent(owner_client: TestClient):
    insert_user("auv2_lifecycle", status="suspended")
    reactivate = owner_client.post("/api/admin/v2/users/auv2_lifecycle/reactivate", headers={"Idempotency-Key": "reactivate"}, json={"reason": "review complete"})
    assert reactivate.status_code == 200 and reactivate.json()["user"]["status"] == "active"
    reset = owner_client.post("/api/admin/v2/users/auv2_lifecycle/require-password-reset", headers={"Idempotency-Key": "reset"}, json={})
    assert reset.status_code == 200 and reset.json()["user"]["mustChangePassword"] is True
    revoke = owner_client.post("/api/admin/v2/users/auv2_lifecycle/revoke-sessions", headers={"Idempotency-Key": "revoke"}, json={"reason": "operator request"})
    replay = owner_client.post("/api/admin/v2/users/auv2_lifecycle/revoke-sessions", headers={"Idempotency-Key": "revoke"}, json={"reason": "operator request"})
    assert revoke.status_code == replay.status_code == 200
    assert revoke.json() == replay.json()
    conn = db.connect()
    try:
        actions = [row[0] for row in conn.execute("SELECT action FROM admin_audit_events WHERE target_json LIKE '%auv2_lifecycle%' ORDER BY occurred_at")]
        assert actions == ["user.reactivate", "user.require_password_reset", "user.revoke_sessions"]
    finally:
        conn.close()


def test_revoke_sessions_invalidates_already_issued_access_tokens(owner_client: TestClient):
    insert_user("auv2_token_boundary")
    issued_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    token = _create_access_token(
        {"sub": "auv2_token_boundary", "role": "professor", "exp": (issued_at + timedelta(hours=1)).timestamp()},
        issued_at=issued_at,
    )
    assert _verify_token(token) is not None
    response = owner_client.post(
        "/api/admin/v2/users/auv2_token_boundary/revoke-sessions",
        headers={"Idempotency-Key": "token-boundary"},
        json={},
    )
    assert response.status_code == 200, response.text
    assert _verify_token(token) is None


def test_action_requires_idempotency_key_and_self_suspend_is_forbidden(owner_client: TestClient):
    insert_user("auv2_no_key")
    missing = owner_client.post("/api/admin/v2/users/auv2_no_key/suspend", json={})
    assert_error(missing, 400, "ADMIN_IDEMPOTENCY_KEY_INVALID")
    self_suspend = owner_client.post("/api/admin/v2/users/owner/suspend", headers={"Idempotency-Key": "self"}, json={})
    assert_error(self_suspend, 409, "ADMIN_USER_SELF_SUSPEND_FORBIDDEN")
