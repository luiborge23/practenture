"""Security and transaction contracts for Admin Console V2 MFA login."""

from __future__ import annotations

import hashlib
import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

import mfa
from admin_v2.service import auth_service
from database import db
from main import app
from security import hash_password

PASSWORD = "AdminV2-MFA-Test-Password!"
TOTP_SECRET = "JBSWY3DPEHPK3PXP"
FIXED_TIME = 1_800_000_000
BACKUP_CODE = "A1B2C3D4"


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    with TestClient(app, base_url="http://testserver") as test_client:
        yield test_client


@pytest.fixture
def owner(request: pytest.FixtureRequest):
    """Create a unique owner and remove every related row after the test."""
    username = f"mfa-{request.node.name.replace('_', '-')[:80]}"
    db.create_user(username, hash_password(PASSWORD), "owner", "MFA Security Owner")
    yield username
    with db._lock:
        conn = db._get_conn()
        conn.execute("DELETE FROM admin_sessions WHERE owner_user_id=?", (username,))
        conn.execute(
            "DELETE FROM privileged_login_attempts WHERE identity_key=?",
            (username.casefold(),),
        )
        conn.execute("DELETE FROM admin_mfa_replay_state WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM admin_mfa_challenges WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (username,))
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()


def enable_mfa(username: str, backup_codes: list[str] | None = None) -> None:
    db.set_mfa_secret(username, TOTP_SECRET)
    db.enable_mfa(username, backup_codes or [BACKUP_CODE])


def login(client: TestClient, username: str, mfa_code: str | None = None):
    payload = {"username": username, "password": PASSWORD}
    if mfa_code is not None:
        payload["mfaCode"] = mfa_code
    return client.post("/api/admin/v2/auth/login", json=payload)


def assert_error(response, code: str) -> None:
    assert response.status_code == 401, response.text
    assert response.json()["error"]["code"] == code


def session_rows(username: str) -> list[dict]:
    with db._lock:
        rows = db._get_conn().execute(
            "SELECT * FROM admin_sessions WHERE owner_user_id=? ORDER BY created_at",
            (username,),
        ).fetchall()
    return [dict(row) for row in rows]


def backup_codes(username: str) -> list[str]:
    row = db.get_mfa_secret(username)
    assert row is not None
    return json.loads(row["backup_codes"])


def current_totp() -> str:
    return mfa._hotp(TOTP_SECRET, FIXED_TIME // 30)


def test_mfa_enabled_password_only_requires_mfa_without_creating_session(
    client: TestClient, owner: str,
) -> None:
    enable_mfa(owner)

    response = login(client, owner)

    assert_error(response, "ADMIN_MFA_REQUIRED")
    assert session_rows(owner) == []
    assert backup_codes(owner) == [mfa.hash_backup_code(BACKUP_CODE)]


def test_invalid_totp_is_rejected_without_creating_session(
    client: TestClient, owner: str,
) -> None:
    enable_mfa(owner)

    response = login(client, owner, "000000")

    assert_error(response, "ADMIN_INVALID_MFA")
    assert session_rows(owner) == []
    assert backup_codes(owner) == [mfa.hash_backup_code(BACKUP_CODE)]


def test_invalid_backup_preserves_code_and_existing_active_session(
    client: TestClient, owner: str,
) -> None:
    assert login(client, owner).status_code == 200
    original = session_rows(owner)
    assert len(original) == 1 and original[0]["revoked_at"] is None
    enable_mfa(owner)

    response = login(client, owner, "NOT-A-BACKUP")

    assert_error(response, "ADMIN_INVALID_MFA")
    assert backup_codes(owner) == [mfa.hash_backup_code(BACKUP_CODE)]
    assert session_rows(owner) == original


def test_valid_current_totp_creates_exactly_one_active_session(
    client: TestClient, owner: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    enable_mfa(owner)
    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME)

    response = login(client, owner, current_totp())

    assert response.status_code == 200, response.text
    assert response.json()["session"]["userId"] == owner
    rows = session_rows(owner)
    assert len(rows) == 1
    assert rows[0]["revoked_at"] is None
    assert backup_codes(owner) == [mfa.hash_backup_code(BACKUP_CODE)]


def test_valid_backup_is_consumed_once_and_reuse_cannot_rotate_session(
    client: TestClient, owner: str,
) -> None:
    enable_mfa(owner, [BACKUP_CODE, "E5F6A7B8"])

    accepted = login(client, owner, BACKUP_CODE)
    assert accepted.status_code == 200, accepted.text
    assert backup_codes(owner) == [mfa.hash_backup_code("E5F6A7B8")]
    original = session_rows(owner)
    assert len(original) == 1 and original[0]["revoked_at"] is None

    rejected = login(client, owner, BACKUP_CODE)

    assert_error(rejected, "ADMIN_INVALID_MFA")
    assert backup_codes(owner) == [mfa.hash_backup_code("E5F6A7B8")]
    assert session_rows(owner) == original


def test_mfa_disabled_owner_can_login_without_code(
    client: TestClient, owner: str,
) -> None:
    response = login(client, owner)

    assert response.status_code == 200, response.text
    rows = session_rows(owner)
    assert len(rows) == 1
    assert rows[0]["revoked_at"] is None


def test_backup_consumption_and_rotation_roll_back_if_session_insert_fails(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """MFA consumption, rotation, and insert are one atomic transaction."""
    assert login(client, owner).status_code == 200
    original = session_rows(owner)
    existing_id_suffix = original[0]["id"].removeprefix("adm_")
    enable_mfa(owner)
    generated = iter(("fresh-token-that-does-not-collide", existing_id_suffix))
    monkeypatch.setattr("admin_v2.service.secrets.token_urlsafe", lambda _n: next(generated))

    with pytest.raises(sqlite3.IntegrityError):
        auth_service.login(
            owner,
            PASSWORD,
            mfa_code=BACKUP_CODE,
            client_signal="transaction-test",
        )

    assert backup_codes(owner) == [mfa.hash_backup_code(BACKUP_CODE)]
    assert session_rows(owner) == original
    assert hashlib.sha256(b"fresh-token-that-does-not-collide").hexdigest() not in {
        row["token_hash"] for row in session_rows(owner)
    }
