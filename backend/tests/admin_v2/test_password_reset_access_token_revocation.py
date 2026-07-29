"""Access-token revocation contracts for successful password resets."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from auth import _create_access_token, _create_token, _verify_token
from database import db
from main import app
from security import hash_password


ORIGINAL_PASSWORD = "Original123!"
NEW_PASSWORD = "Replacement123!"


@pytest.fixture
def identity():
    created: list[str] = []

    def create(role: str) -> str:
        username = f"access-reset-{role}-{uuid.uuid4().hex}"
        assert db.create_user(
            username, hash_password(ORIGINAL_PASSWORD), role, f"Access Reset {role.title()}"
        )
        created.append(username)
        return username

    yield create

    with db._lock:
        conn = db._get_conn()
        for username in created:
            conn.execute("DELETE FROM admin_sessions WHERE owner_user_id=?", (username,))
            conn.execute("DELETE FROM admin_mfa_replay_state WHERE owner_user_id=?", (username,))
            conn.execute("DELETE FROM privileged_login_attempts WHERE identity_key=?", (username.casefold(),))
            conn.execute("DELETE FROM privileged_login_buckets WHERE scope_key=?", (username.casefold(),))
            conn.execute("DELETE FROM password_reset_tokens WHERE user_id=?", (username,))
            conn.execute("DELETE FROM refresh_tokens WHERE user_id=?", (username,))
            conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (username,))
            conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()


def _login(client: TestClient, username: str, password: str) -> dict:
    response = client.post(
        "/api/auth/login",
        json={"provider": "password", "username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _create_reset_token(username: str) -> str:
    raw = f"reset-{uuid.uuid4().hex}"
    db.create_reset_token(username, hashlib.sha256(raw.encode()).hexdigest())
    return raw


def _verify(client: TestClient, access_token: str):
    return client.post(
        "/api/auth/verify", headers={"Authorization": f"Bearer {access_token}"}
    )


@pytest.mark.parametrize("role", ["owner", "professor"])
def test_reset_rejects_old_access_token_and_accepts_new_login_token(
    identity, monkeypatch: pytest.MonkeyPatch, role: str
):
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    username = identity(role)
    if role == "owner":
        monkeypatch.setenv("PRACTENTURE_OWNER_USERNAME", username)

    with TestClient(app, base_url="http://testserver") as client:
        login = _login(client, username, ORIGINAL_PASSWORD)
        old_access = login["accessToken"]
        old_refresh = login["refreshToken"]
        assert _verify(client, old_access).status_code == 200

        admin_client = None
        if role == "owner":
            admin_client = TestClient(app, base_url="http://testserver")
            admin_login = admin_client.post(
                "/api/admin/v2/auth/login",
                json={"username": username, "password": ORIGINAL_PASSWORD},
            )
            assert admin_login.status_code == 200, admin_login.text
            assert admin_client.get("/api/admin/v2/auth/session").status_code == 200

        reset = client.post(
            "/api/auth/reset-password",
            json={"token": _create_reset_token(username), "newPassword": NEW_PASSWORD},
        )
        assert reset.status_code == 200, reset.text
        assert reset.json() == {"status": "password_reset"}

        assert _verify(client, old_access).status_code == 401
        refresh = client.post(
            "/api/auth/refresh", json={"refreshToken": old_refresh}
        )
        assert refresh.status_code == 401
        if admin_client is not None:
            assert admin_client.get("/api/admin/v2/auth/session").status_code == 401
            admin_client.close()

        new_login = _login(client, username, NEW_PASSWORD)
        assert _verify(client, new_login["accessToken"]).status_code == 200


def test_failed_reset_does_not_invalidate_access_token(identity):
    username = identity("professor")
    with TestClient(app, base_url="http://testserver") as client:
        access_token = _login(client, username, ORIGINAL_PASSWORD)["accessToken"]
        before = db.get_user(username)["password_changed_at"]

        failed = client.post(
            "/api/auth/reset-password",
            json={"token": f"invalid-{uuid.uuid4().hex}", "newPassword": NEW_PASSWORD},
        )

        assert failed.status_code == 400
        assert db.get_user(username)["password_changed_at"] == before
        assert _verify(client, access_token).status_code == 200


def test_password_change_boundary_equality_and_legacy_iat_compatibility(identity):
    username = identity("professor")
    boundary = datetime.now(timezone.utc) + timedelta(minutes=1)
    expires_at = (boundary + timedelta(hours=1)).timestamp()

    with db._get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_changed_at=? WHERE username=?",
            (boundary.isoformat().replace("+00:00", "Z"), username),
        )

    before = _create_access_token(
        {"sub": username, "role": "professor", "exp": expires_at},
        issued_at=boundary - timedelta(microseconds=1),
    )
    equal = _create_access_token(
        {"sub": username, "role": "professor", "exp": expires_at},
        issued_at=boundary,
    )
    legacy_without_iat = _create_token(
        {"sub": username, "role": "professor", "exp": expires_at}
    )

    assert _verify_token(before) is None
    assert _verify_token(equal)["sub"] == username
    assert _verify_token(legacy_without_iat) is None

    with db._get_conn() as conn:
        conn.execute(
            "UPDATE users SET password_changed_at=NULL WHERE username=?", (username,)
        )
    assert _verify_token(legacy_without_iat)["sub"] == username
