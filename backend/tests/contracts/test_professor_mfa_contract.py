"""Professor Portal MFA enrollment, login, recovery, and hardening contracts."""
from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timedelta, timezone
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

import mfa
from auth import _create_access_token
from database import db
from main import app
from security import hash_password

PASSWORD = "ProfessorMfa123!"
ORIGIN = "https://practenture.com"


@pytest.fixture
def professor() -> Iterator[str]:
    username = f"prof-mfa-{uuid.uuid4().hex}"
    db.create_user(username, hash_password(PASSWORD), "professor", "MFA Professor", f"{username}@example.edu")
    yield username
    with db._lock:
        conn = db._get_conn()
        conn.execute("DELETE FROM admin_mfa_replay_state WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (username,))
        conn.execute("DELETE FROM refresh_tokens WHERE user_id=?", (username,))
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()


def authenticated_client(username: str) -> tuple[TestClient, dict[str, str]]:
    client = TestClient(app, base_url=ORIGIN)
    token = _create_access_token({
        "sub": username,
        "role": "professor",
        "name": "MFA Professor",
        "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
    })
    csrf = f"csrf-{uuid.uuid4().hex}"
    client.cookies.set("practenture_professor_session", token)
    client.cookies.set("practenture_professor_csrf", csrf)
    return client, {"X-CSRF-Token": csrf}


def enroll(client: TestClient, headers: dict[str, str], username: str) -> tuple[str, list[str]]:
    setup = client.post(
        "/api/professor-portal/mfa/setup",
        headers=headers,
        json={"password": PASSWORD},
    )
    assert setup.status_code == 200, setup.text
    payload = setup.json()
    assert payload["otpauthUri"].startswith("otpauth://totp/Practenture:")
    assert payload["qrCodeDataUri"].startswith("data:image/svg+xml;base64,")
    secret = payload["secret"]
    code = mfa._hotp(secret, int(time.time()) // 30)
    confirmed = client.post(
        "/api/professor-portal/mfa/confirm",
        headers=headers,
        json={"code": code},
    )
    assert confirmed.status_code == 200, confirmed.text
    recovery = confirmed.json()["recoveryCodes"]
    assert len(recovery) == 10
    assert all(re.fullmatch(r"[0-9A-F]{4}(?:-[0-9A-F]{4}){2}", item) for item in recovery)
    return secret, recovery


def portal_login(username: str, *, code: str | None = None) -> TestClient:
    client = TestClient(app, base_url=ORIGIN)
    body: dict[str, str] = {"provider": "password", "username": username, "password": PASSWORD}
    if code is not None:
        body["mfa_code"] = code
    response = client.post(
        "/api/professor-portal/login",
        headers={"Origin": ORIGIN},
        json=body,
    )
    client.last_response = response  # type: ignore[attr-defined]
    return client


def test_enrollment_requires_csrf_and_password_and_stores_only_hashed_recovery_codes(professor: str) -> None:
    client, headers = authenticated_client(professor)
    assert client.get("/api/professor-portal/mfa/status").json() == {
        "enabled": False,
        "recoveryCodesRemaining": 0,
    }
    assert client.post(
        "/api/professor-portal/mfa/setup", json={"password": PASSWORD}
    ).status_code == 403
    wrong = client.post(
        "/api/professor-portal/mfa/setup", headers=headers, json={"password": "wrong"}
    )
    assert wrong.status_code == 401

    secret, recovery = enroll(client, headers, professor)
    status = client.get("/api/professor-portal/mfa/status")
    assert status.json() == {"enabled": True, "recoveryCodesRemaining": 10}
    stored = db.get_mfa_secret(professor)
    assert stored is not None
    assert stored["secret"].startswith("enc-v1$")
    assert stored["secret"] != secret
    persisted = json.loads(stored["backup_codes"])
    assert all(value.startswith("sha256$") for value in persisted)
    assert not set(recovery) & set(persisted)

    overwrite = client.post(
        "/api/professor-portal/mfa/setup", headers=headers, json={"password": PASSWORD}
    )
    assert overwrite.status_code == 409
    client.close()


def test_login_requires_second_factor_rejects_totp_replay_and_consumes_recovery_once(
    professor: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = 2_000_000_000
    monkeypatch.setattr(mfa.time, "time", lambda: fixed)
    client, headers = authenticated_client(professor)
    secret, recovery = enroll(client, headers, professor)
    client.close()

    missing = portal_login(professor)
    assert missing.last_response.status_code == 409  # type: ignore[attr-defined]
    assert missing.last_response.json() == {"detail": "Enter the MFA code to continue"}  # type: ignore[attr-defined]
    missing.close()

    current = mfa._hotp(secret, fixed // 30)
    accepted = portal_login(professor, code=current)
    assert accepted.last_response.status_code == 200  # type: ignore[attr-defined]
    accepted.close()
    replay = portal_login(professor, code=current)
    assert replay.last_response.status_code == 401  # type: ignore[attr-defined]
    replay.close()

    backup = portal_login(professor, code=recovery[0].lower().replace("-", " "))
    assert backup.last_response.status_code == 200  # type: ignore[attr-defined]
    backup.close()
    reused = portal_login(professor, code=recovery[0])
    assert reused.last_response.status_code == 401  # type: ignore[attr-defined]
    reused.close()
    record = db.get_mfa_secret(professor)
    assert record is not None
    assert len(json.loads(record["backup_codes"])) == 9


def test_recovery_regeneration_and_disable_require_password_and_current_mfa(
    professor: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [2_100_000_000]
    monkeypatch.setattr(mfa.time, "time", lambda: now[0])
    client, headers = authenticated_client(professor)
    secret, old_codes = enroll(client, headers, professor)

    denied = client.post(
        "/api/professor-portal/mfa/recovery-codes",
        headers=headers,
        json={"password": "wrong", "code": old_codes[0]},
    )
    assert denied.status_code == 401
    regenerated = client.post(
        "/api/professor-portal/mfa/recovery-codes",
        headers=headers,
        json={"password": PASSWORD, "code": old_codes[0]},
    )
    assert regenerated.status_code == 200, regenerated.text
    new_codes = regenerated.json()["recoveryCodes"]
    assert set(new_codes).isdisjoint(old_codes)

    no_factor = client.post(
        "/api/professor-portal/mfa/disable",
        headers=headers,
        json={"password": PASSWORD, "code": "invalid"},
    )
    assert no_factor.status_code == 401
    now[0] += 30
    current = mfa._hotp(secret, now[0] // 30)
    disabled = client.post(
        "/api/professor-portal/mfa/disable",
        headers=headers,
        json={"password": PASSWORD, "code": current},
    )
    assert disabled.status_code == 204, disabled.text
    assert client.get("/api/professor-portal/mfa/status").json()["enabled"] is False
    client.close()


def test_shared_disable_endpoint_no_longer_accepts_empty_body(professor: str) -> None:
    client, headers = authenticated_client(professor)
    enroll(client, headers, professor)
    token = client.cookies.get("practenture_professor_session")
    api = TestClient(app, base_url=ORIGIN, headers={"Authorization": f"Bearer {token}"})
    response = api.post("/api/auth/mfa/disable", json={})
    assert response.status_code == 401
    assert db.is_mfa_enabled(professor)
    api.close()
    client.close()
