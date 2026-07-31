"""Contracts for the first secure Admin Console V2 vertical slice."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from database import db
from main import app
from security import hash_password
from admin_v2.service import auth_service


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    # Secure may only be disabled explicitly in tests/local HTTP harnesses.
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    with TestClient(app, base_url="http://testserver") as test_client:
        yield test_client


def login(client: TestClient, username: str = "owner", password: str = "practenture2026"):
    return client.post(
        "/api/admin/v2/auth/login",
        json={"username": username, "password": password},
    )


def assert_error(response, status: int, code: str) -> dict:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "requestId", "fieldErrors"}
    assert body["error"]["code"] == code
    assert body["error"]["requestId"]
    assert response.headers["x-request-id"] == body["error"]["requestId"]
    assert body["error"]["fieldErrors"] == []
    return body


def test_v2_api_and_shell_are_mounted_at_canonical_and_compatibility_routes(client: TestClient):
    assert client.get("/admin-v2").status_code == 200
    assert "Admin Console V2" in client.get("/admin-v2").text
    assert client.get("/admin").status_code == 200
    assert "Admin Console V2" in client.get("/admin").text
    assert_error(client.get("/api/admin/v2/auth/session"), 401, "ADMIN_AUTH_REQUIRED")


def test_legacy_owner_api_is_not_mounted(client: TestClient):
    assert client.get("/api/owner/audit-events").status_code == 404
    assert client.post("/api/owner/cleanup-plans", json={"selector": {"sessions": True}}).status_code == 404
    assert client.post("/api/owner/login", json={}).status_code == 404


def test_no_duplicate_method_path_routes():
    seen: set[tuple[str, str]] = set()
    duplicates: list[tuple[str, str]] = []
    for route in app.routes:
        path = getattr(route, "path", None)
        if not path or not path.startswith("/api/admin/v2"):
            continue
        for method in getattr(route, "methods", set()) or set():
            key = (method, path)
            if key in seen:
                duplicates.append(key)
            seen.add(key)
    assert duplicates == []


def test_login_success_rotates_session_and_sets_strict_cookie(client: TestClient):
    client.cookies.set(
        "practenture_admin_v2_session",
        "attacker-fixed-session",
        domain="testserver.local",
        path="/api/admin/v2",
    )
    response = login(client)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"session"}
    assert body["session"]["userId"] == "owner"
    assert body["session"]["role"] == "owner"
    assert body["session"]["csrfToken"]
    cookie = response.headers["set-cookie"]
    assert "practenture_admin_v2_session=" in cookie
    assert "attacker-fixed-session" not in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/api/admin/v2" in cookie
    assert "Max-Age=" in cookie

    first_token = client.cookies.get("practenture_admin_v2_session")
    second_response = login(client)
    second_token = client.cookies.get("practenture_admin_v2_session")
    assert second_response.status_code == 200
    assert second_token != first_token
    with db._get_conn() as conn:
        old = conn.execute(
            "SELECT revoked_at, revocation_reason FROM admin_sessions WHERE token_hash=?",
            (hashlib.sha256(first_token.encode()).hexdigest(),),
        ).fetchone()
    assert old["revoked_at"] is not None
    assert old["revocation_reason"] == "login_rotation"


def test_cookie_is_secure_by_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("PRACTENTURE_ADMIN_COOKIE_SECURE", raising=False)
    with TestClient(app, base_url="https://testserver") as secure_client:
        response = login(secure_client)
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_cookie_insecure_override_is_ignored_without_test_mode(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("PRACTENTURE_TESTING", raising=False)
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    with TestClient(app, base_url="https://testserver") as secure_client:
        response = login(secure_client)
    assert response.status_code == 200
    assert "Secure" in response.headers["set-cookie"]


def test_v2_framework_404_has_stable_error_contract(client: TestClient):
    response = client.get("/api/admin/v2/does-not-exist")
    assert_error(response, 404, "ADMIN_NOT_FOUND")
    assert response.headers["cache-control"] == "no-store"


def test_v2_framework_405_has_stable_error_contract(client: TestClient):
    response = client.get("/api/admin/v2/auth/login")
    assert_error(response, 405, "ADMIN_METHOD_NOT_ALLOWED")
    assert response.headers["cache-control"] == "no-store"


def test_v2_generic_http_exception_has_stable_error_contract(client: TestClient):
    """Exercise the non-404/405 framework HTTPException handler branch."""
    path = "/api/admin/v2/_test/http-exception"

    async def raise_http_exception():
        raise HTTPException(status_code=418, detail="Test-only HTTP exception")

    app.add_api_route(path, raise_http_exception, methods=["GET"])
    added_route = app.router.routes[-1]
    try:
        response = client.get(path)
    finally:
        app.router.routes.remove(added_route)

    body = assert_error(response, 418, "ADMIN_HTTP_ERROR")
    assert body["error"]["message"] == "Test-only HTTP exception"
    assert response.headers["cache-control"] == "no-store"


def test_v2_request_validation_has_stable_error_contract(client: TestClient):
    response = client.post("/api/admin/v2/auth/login", json={"username": "owner"})
    assert_error(response, 400, "ADMIN_VALIDATION_ERROR")
    assert response.headers["cache-control"] == "no-store"


def test_v2_unhandled_500_has_stable_error_contract(
    monkeypatch: pytest.MonkeyPatch,
):
    def explode(*args, **kwargs):
        raise RuntimeError("safely induced admin v2 failure")

    monkeypatch.setattr("admin_v2.routes.auth_service.login", explode)
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    with TestClient(
        app, base_url="http://testserver", raise_server_exceptions=False
    ) as test_client:
        response = login(test_client)
    assert_error(response, 500, "ADMIN_INTERNAL_ERROR")
    assert response.headers["cache-control"] == "no-store"


def test_login_failure_is_stable_and_does_not_leak_secret(client: TestClient):
    secret = "definitely-wrong-secret"
    response = login(client, password=secret)
    body = assert_error(response, 401, "ADMIN_INVALID_CREDENTIALS")
    assert secret not in response.text
    assert "password" not in str(body).lower()


def test_recovery_changes_password_and_revokes_existing_sessions(client: TestClient):
    username = "recovery-owner"
    original_password = "OriginalRecovery123!"
    db.create_user(username, hash_password(original_password), "owner", "Recovery Owner")
    original_session = login(client, username, original_password)
    assert original_session.status_code == 200

    start = client.post(
        "/api/admin/v2/auth/recovery/start",
        json={"identifier": username},
    )
    assert start.status_code == 202, start.text
    recovery_token = start.headers["x-admin-recovery-token"]

    new_password = "RecoveredOwner123!"
    complete = client.post(
        "/api/admin/v2/auth/recovery/complete",
        json={"recoveryToken": recovery_token, "newPassword": new_password},
    )
    assert complete.status_code == 200, complete.text
    assert_error(client.get("/api/admin/v2/auth/session"), 401, "ADMIN_AUTH_REQUIRED")
    assert_error(login(client, username, original_password), 401, "ADMIN_INVALID_CREDENTIALS")
    assert login(client, username, new_password).status_code == 200
    recovered = db.get_user(username)
    assert recovered is not None
    assert recovered["password_changed_at"] is not None


def test_recovery_delivers_an_unlogged_fragment_link_in_production(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    username = "recovery-email-owner"
    email = "administrator@example.edu"
    db.create_user(
        username,
        hash_password("OriginalDelivery123!"),
        "owner",
        "Recovery Email Owner",
        email=email,
    )
    delivered: dict[str, str] = {}

    def capture_delivery(*, recipient: str, token: str) -> str:
        delivered.update(recipient=recipient, token=token)
        return "ses-message-id"

    monkeypatch.delenv("PRACTENTURE_TESTING", raising=False)
    monkeypatch.setattr(
        "password_reset_email.send_admin_recovery_link", capture_delivery
    )
    response = client.post(
        "/api/admin/v2/auth/recovery/start", json={"identifier": username}
    )
    assert response.status_code == 202
    assert "x-admin-recovery-token" not in response.headers
    assert delivered["recipient"] == email
    assert delivered["token"] not in response.text
    with db._get_conn() as conn:
        stored = conn.execute(
            "SELECT token_hash, used FROM password_reset_tokens WHERE user_id=?",
            (username,),
        ).fetchone()
    assert stored is not None
    assert stored["token_hash"] == hashlib.sha256(delivered["token"].encode()).hexdigest()
    assert stored["used"] == 0


def test_recovery_provider_io_is_deferred_until_after_public_response_work(
    monkeypatch: pytest.MonkeyPatch,
):
    username = "deferred-recovery-owner"
    email = "deferred@example.edu"
    db.create_user(
        username,
        hash_password("OriginalDeferred123!"),
        "owner",
        "Deferred Recovery Owner",
        email=email,
    )
    delivered: list[str] = []
    scheduled: list[tuple[Callable[..., None], tuple[object, ...]]] = []

    monkeypatch.delenv("PRACTENTURE_TESTING", raising=False)
    monkeypatch.setattr(
        "password_reset_email.send_admin_recovery_link",
        lambda *, recipient, token: delivered.append(recipient),
    )

    result = auth_service.start_recovery(
        username,
        "req-deferred-recovery",
        "198.51.100.1",
        lambda function, *args: scheduled.append((function, args)),
    )

    assert result is None
    assert delivered == []
    assert len(scheduled) == 1
    function, args = scheduled[0]
    function(*args)
    assert delivered == [email]


def test_failed_later_recovery_delivery_does_not_revoke_an_accepted_link(
    monkeypatch: pytest.MonkeyPatch,
):
    username = "recovery-delivery-race-owner"
    email = "recovery-race@example.edu"
    db.create_user(
        username,
        hash_password("OriginalRecoveryRace123!"),
        "owner",
        "Recovery Delivery Race Owner",
        email=email,
    )
    scheduled: list[tuple[Callable[..., None], tuple[object, ...]]] = []
    calls = 0

    def scheduler(function: Callable[..., None], *args: object) -> None:
        scheduled.append((function, args))

    def provider(*, recipient: str, token: str) -> str:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("provider rejected replacement")
        return "accepted-message-id"

    monkeypatch.delenv("PRACTENTURE_TESTING", raising=False)
    monkeypatch.setattr("password_reset_email.send_admin_recovery_link", provider)
    auth_service.start_recovery(username, "recovery-race-1", "198.51.100.20", scheduler)
    auth_service.start_recovery(username, "recovery-race-2", "198.51.100.21", scheduler)
    assert len(scheduled) == 2

    first, first_args = scheduled[0]
    second, second_args = scheduled[1]
    first(*first_args)
    second(*second_args)
    first_hash = str(first_args[2])
    second_hash = str(second_args[2])
    with db._get_conn() as conn:
        first_row = conn.execute(
            "SELECT used FROM password_reset_tokens WHERE token_hash=?", (first_hash,)
        ).fetchone()
        second_row = conn.execute(
            "SELECT used FROM password_reset_tokens WHERE token_hash=?", (second_hash,)
        ).fetchone()
    assert first_row is not None and first_row["used"] == 0
    assert second_row is not None and second_row["used"] == 1


def test_recovery_is_rate_limited_by_identity_and_client(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(auth_service, "recovery_threshold", 2)
    monkeypatch.setattr(auth_service, "recovery_window_seconds", 3600)
    payload = {"identifier": "rate-limited-recovery-owner"}
    assert client.post("/api/admin/v2/auth/recovery/start", json=payload).status_code == 202
    assert client.post("/api/admin/v2/auth/recovery/start", json=payload).status_code == 202
    blocked = client.post("/api/admin/v2/auth/recovery/start", json=payload)
    assert_error(blocked, 429, "ADMIN_RECOVERY_THROTTLED")
    assert int(blocked.headers["retry-after"]) > 0


def test_recovery_rate_limit_normalizes_identifier_before_budgeting(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(auth_service, "recovery_threshold", 1)
    monkeypatch.setattr(auth_service, "recovery_window_seconds", 3600)

    accepted = client.post(
        "/api/admin/v2/auth/recovery/start",
        json={"identifier": "  missing-owner@example.edu"},
    )
    blocked = client.post(
        "/api/admin/v2/auth/recovery/start",
        json={"identifier": "MISSING-OWNER@example.edu  "},
    )

    assert accepted.status_code == 202
    assert_error(blocked, 429, "ADMIN_RECOVERY_THROTTLED")


def test_authenticated_password_change_uses_revocation_boundary(client: TestClient):
    username = "password-change-owner"
    original_password = "OriginalChange123!"
    db.create_user(username, hash_password(original_password), "owner", "Password Change Owner")
    logged_in = login(client, username, original_password)
    csrf = logged_in.json()["session"]["csrfToken"]
    new_password = "ChangedOwner123!"

    reauthenticated = client.post(
        "/api/admin/v2/auth/reauthenticate",
        headers={"X-CSRF-Token": csrf},
        json={"password": original_password},
    )
    assert reauthenticated.status_code == 200, reauthenticated.text

    changed = client.post(
        "/api/admin/v2/auth/password/change",
        headers={"X-CSRF-Token": csrf},
        json={
            "currentPassword": original_password,
            "newPassword": new_password,
        },
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["session"]["userId"] == username
    assert login(client, username, new_password).status_code == 200
    changed_user = db.get_user(username)
    assert changed_user is not None
    assert changed_user["password_changed_at"] is not None


def test_wrong_role_is_explicit_403(client: TestClient):
    db.create_user("prof-v2", hash_password("Professor123!"), "professor", "Professor V2")
    response = login(client, "prof-v2", "Professor123!")
    assert_error(response, 403, "ADMIN_OWNER_REQUIRED")


def test_session_endpoint_returns_typed_camel_case_session(client: TestClient):
    login_response = login(client)
    login_csrf = login_response.json()["session"]["csrfToken"]
    response = client.get("/api/admin/v2/auth/session")
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    # Refresh is non-destructive: concurrent tabs keep the same derived CSRF token.
    assert session["csrfToken"]
    assert session["csrfToken"] == login_csrf
    assert set(session) == {
        "userId", "role", "csrfToken", "createdAt", "lastSeenAt",
        "idleExpiresAt", "absoluteExpiresAt",
    }
    assert "user_id" not in response.text


def test_csrf_denial_success_and_logout_revocation(client: TestClient):
    csrf = login(client).json()["session"]["csrfToken"]
    assert_error(client.post("/api/admin/v2/auth/logout"), 403, "ADMIN_CSRF_INVALID")

    response = client.post(
        "/api/admin/v2/auth/logout", headers={"X-CSRF-Token": csrf}
    )
    assert response.status_code == 204, response.text
    assert "Max-Age=0" in response.headers["set-cookie"]
    assert_error(client.get("/api/admin/v2/auth/session"), 401, "ADMIN_AUTH_REQUIRED")


def test_idle_and_absolute_expiry_are_enforced(client: TestClient):
    login(client)
    token = client.cookies.get("practenture_admin_v2_session")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()

    with db._get_conn() as conn:
        conn.execute(
            "UPDATE admin_sessions SET idle_expires_at=? WHERE token_hash=?",
            (expired, token_hash),
        )
        conn.commit()
    assert_error(client.get("/api/admin/v2/auth/session"), 401, "ADMIN_SESSION_EXPIRED")

    login(client)
    token = client.cookies.get("practenture_admin_v2_session")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db._get_conn() as conn:
        conn.execute(
            "UPDATE admin_sessions SET absolute_expires_at=? WHERE token_hash=?",
            (expired, token_hash),
        )
        conn.commit()
    assert_error(client.get("/api/admin/v2/auth/session"), 401, "ADMIN_SESSION_EXPIRED")


def test_only_hashes_are_persisted_and_secrets_absent_from_errors(client: TestClient):
    password = "practenture2026"
    response = login(client, password=password)
    session = response.json()["session"]
    token = client.cookies.get("practenture_admin_v2_session")
    csrf = session["csrfToken"]

    with db._get_conn() as conn:
        row = conn.execute(
            "SELECT token_hash, csrf_token_hash FROM admin_sessions WHERE revoked_at IS NULL"
        ).fetchone()
    assert row["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert row["csrf_token_hash"] == hashlib.sha256(csrf.encode()).hexdigest()
    persisted = f"{row['token_hash']} {row['csrf_token_hash']}"
    assert token not in persisted
    assert csrf not in persisted
    assert password not in persisted

    denied = client.post(
        "/api/admin/v2/auth/logout", headers={"X-CSRF-Token": "secret-csrf-bad"}
    )
    assert "secret-csrf-bad" not in denied.text
    assert token not in denied.text
