"""Regression contracts for suspended users at every legacy auth boundary."""

from __future__ import annotations

import uuid

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

import auth
import auth_enrollment
from database import db
from main import app
from security import hash_password


PASSWORD = "Suspended123!"


def _create_user(role: str, *, status: str | None = "active") -> str:
    username = f"suspended-boundary-{role}-{uuid.uuid4().hex}"
    assert db.create_user(
        username=username,
        password_hash=hash_password(PASSWORD),
        role=role,
        # Legacy student password login resolves by student ID when the display
        # name differs from the submitted identifier.
        name=username if role == "student" else f"Boundary {role.title()}",
        student_id=username if role == "student" else None,
    )
    with db._get_conn() as conn:
        conn.execute("UPDATE users SET status=? WHERE username=?", (status, username))
        conn.commit()
    return username


def _password_login(client: TestClient, username: str):
    return client.post(
        "/api/auth/login",
        json={"provider": "password", "username": username, "password": PASSWORD},
    )


def test_new_admin_v2_domain_routers_are_mounted_once_under_canonical_prefix():
    route_pairs = [
        (method, route.path)
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods or set()
    ]
    required = {
        ("GET", "/api/admin/v2/invitations"),
        ("GET", "/api/admin/v2/users"),
        ("GET", "/api/admin/v2/sessions"),
    }
    assert all(route_pairs.count(route) == 1 for route in required)
    assert not any("/api/admin/v2/api/admin/v2" in path for _, path in route_pairs)


@pytest.mark.parametrize("role", ["owner", "professor", "student"])
def test_explicitly_suspended_password_login_is_denied_for_every_role(
    monkeypatch: pytest.MonkeyPatch, role: str
):
    username = _create_user(role, status="suspended")
    if role == "owner":
        monkeypatch.setenv("PRACTENTURE_OWNER_USERNAME", username)

    with TestClient(app) as client:
        response = _password_login(client, username)

    assert response.status_code == 403
    assert response.json() == {"detail": "Account is suspended"}


@pytest.mark.parametrize("stored_status", ["active", None])
def test_active_and_legacy_null_status_password_logins_remain_compatible(stored_status):
    username = _create_user("professor", status=stored_status)

    with TestClient(app) as client:
        response = _password_login(client, username)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["userId"] == username
        assert body["role"] == "professor"
        assert client.post(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {body['accessToken']}"},
        ).status_code == 200


def test_existing_social_user_is_denied_after_mocked_provider_verification(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(
        auth,
        "verify_google_id_token",
        lambda token, audience: {
            "sub": "provider-subject",
            "email": "suspended@example.test",
            "name": "Suspended Social",
        },
    )
    monkeypatch.setattr(
        auth_enrollment,
        "find_social_user",
        lambda provider, subject: {
            "username": "suspended-social",
            "role": "professor",
            "status": "suspended",
            "email": "suspended@example.test",
        },
    )

    with TestClient(app) as client:
        response = client.post(
            "/api/auth/login",
            json={"provider": "google", "id_token": "mock-provider-token"},
        )

    assert response.status_code == 403
    assert response.json() == {"detail": "Account is suspended"}


def test_bearer_verification_denies_token_after_explicit_suspension():
    username = _create_user("professor")
    with TestClient(app) as client:
        login = _password_login(client, username)
        assert login.status_code == 200, login.text
        access_token = login.json()["accessToken"]

        with db._get_conn() as conn:
            conn.execute(
                "UPDATE users SET status='suspended' WHERE username=?", (username,)
            )
            conn.commit()

        response = client.post(
            "/api/auth/verify",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid or expired token"
    assert response.headers["www-authenticate"] == "Bearer"


def test_suspended_refresh_is_denied_before_rotation_and_mints_nothing():
    username = _create_user("professor")
    with TestClient(app) as client:
        login = _password_login(client, username)
        assert login.status_code == 200, login.text
        refresh_token = login.json()["refreshToken"]
        token_hash = auth._hash_token(refresh_token)

        with db._get_conn() as conn:
            before_count = conn.execute(
                "SELECT COUNT(*) FROM refresh_tokens WHERE user_id=?", (username,)
            ).fetchone()[0]
            conn.execute(
                "UPDATE users SET status='suspended' WHERE username=?", (username,)
            )
            conn.commit()

        response = client.post(
            "/api/auth/refresh", json={"refreshToken": refresh_token}
        )

        with db._get_conn() as conn:
            presented = conn.execute(
                "SELECT revoked FROM refresh_tokens WHERE token_hash=?", (token_hash,)
            ).fetchone()
            after_count = conn.execute(
                "SELECT COUNT(*) FROM refresh_tokens WHERE user_id=?", (username,)
            ).fetchone()[0]

    assert response.status_code == 403
    assert response.json() == {"detail": "Account is suspended"}
    assert presented["revoked"] == 0
    assert after_count == before_count
