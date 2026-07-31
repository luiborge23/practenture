"""End-to-end contracts for the Administrator MFA management lifecycle."""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

import admin_v2.service as service_module
from admin_v2.errors import AdminError
from admin_v2.repository import AdminSessionRepository
from admin_v2.service import AdminAuthService, auth_service
from database import db
from main import app
import mfa
from security import hash_password

PASSWORD = "AdminMfaLifecycle123!"
FIXED_TIME = 2_200_000_000


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    with TestClient(app, base_url="http://testserver") as value:
        yield value


@pytest.fixture
def owner() -> Iterator[str]:
    username = f"admin-mfa-{uuid.uuid4().hex}"
    db.create_user(username, hash_password(PASSWORD), "owner", "Administrator MFA Owner")
    yield username
    with db._lock:
        conn = db._get_conn()
        conn.execute("DELETE FROM admin_recent_auth WHERE session_id IN (SELECT id FROM admin_sessions WHERE owner_user_id=?)", (username,))
        conn.execute("DELETE FROM admin_sessions WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM admin_mfa_replay_state WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM admin_mfa_challenges WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (username,))
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()


def login(client: TestClient, owner: str):
    return client.post(
        "/api/admin/v2/auth/login",
        json={"username": owner, "password": PASSWORD},
    )


def authenticated(client: TestClient, owner: str) -> dict[str, str]:
    response = login(client, owner)
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["session"]["csrfToken"]}


def setup(client: TestClient, headers: dict[str, str]) -> dict:
    response = client.post(
        "/api/admin/v2/auth/mfa/setup",
        headers=headers,
        json={"password": PASSWORD},
    )
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    return response.json()


def confirm(client: TestClient, headers: dict[str, str], secret: str):
    return client.post(
        "/api/admin/v2/auth/mfa/confirm",
        headers=headers,
        json={"code": mfa._hotp(secret, int(mfa.time.time()) // 30)},
    )


def stored_recovery_codes(owner: str) -> list[str]:
    record = db.get_mfa_secret(owner)
    assert record is not None
    return json.loads(record["backup_codes"])


def test_admin_mfa_enrollment_reuses_professor_security_contract(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME)
    assert client.get("/api/admin/v2/auth/mfa/status").status_code == 401
    headers = authenticated(client, owner)
    assert client.get("/api/admin/v2/auth/mfa/status").json() == {
        "enabled": False,
        "recoveryCodesRemaining": 0,
    }
    assert client.post(
        "/api/admin/v2/auth/mfa/setup", json={"password": PASSWORD}
    ).status_code == 403
    wrong_password = client.post(
        "/api/admin/v2/auth/mfa/setup",
        headers=headers,
        json={"password": "wrong-password"},
    )
    assert wrong_password.status_code == 401
    assert wrong_password.json()["error"]["code"] == "ADMIN_REAUTH_FAILED"

    enrollment = setup(client, headers)
    assert enrollment["otpauthUri"].startswith("otpauth://totp/Practenture:")
    assert enrollment["qrCodeDataUri"].startswith("data:image/svg+xml;base64,")
    secret = enrollment["secret"]
    record = db.get_mfa_secret(owner)
    assert record is not None
    assert record["secret"].startswith("enc-v1$")
    assert record["secret"] != secret
    assert int(record["enabled"]) == 0

    invalid = client.post(
        "/api/admin/v2/auth/mfa/confirm",
        headers=headers,
        json={"code": "000000"},
    )
    assert invalid.status_code == 400
    assert not db.is_mfa_enabled(owner)

    enabled = confirm(client, headers, secret)
    assert enabled.status_code == 200, enabled.text
    recovery_codes = enabled.json()["recoveryCodes"]
    assert len(recovery_codes) == 10
    assert all(re.fullmatch(r"[0-9A-F]{4}(?:-[0-9A-F]{4}){2}", code) for code in recovery_codes)
    persisted = stored_recovery_codes(owner)
    assert len(persisted) == 10
    assert all(value.startswith("sha256$") for value in persisted)
    assert not set(recovery_codes) & set(persisted)
    assert client.get("/api/admin/v2/auth/mfa/status").json() == {
        "enabled": True,
        "recoveryCodesRemaining": 10,
    }

    repeated = confirm(client, headers, secret)
    assert repeated.status_code == 409
    assert stored_recovery_codes(owner) == persisted

    challenge = login(client, owner)
    assert challenge.status_code == 401
    assert challenge.json()["error"]["code"] == "ADMIN_MFA_REQUIRED"
    replay = client.post(
        "/api/admin/v2/auth/mfa/verify",
        json={
            "challengeToken": challenge.headers["X-Admin-MFA-Challenge"],
            "mfaCode": mfa._hotp(secret, FIXED_TIME // 30),
        },
    )
    assert replay.status_code == 401
    assert replay.json()["error"]["code"] == "ADMIN_MFA_REPLAYED"


def test_admin_mfa_regeneration_and_disable_require_password_csrf_and_current_factor(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [FIXED_TIME]
    monkeypatch.setattr(mfa.time, "time", lambda: now[0])
    headers = authenticated(client, owner)
    enrollment = setup(client, headers)
    secret = enrollment["secret"]
    first_codes = confirm(client, headers, secret).json()["recoveryCodes"]
    old_persisted = stored_recovery_codes(owner)

    no_csrf = client.post(
        "/api/admin/v2/auth/mfa/recovery-codes",
        json={"password": PASSWORD, "code": first_codes[0]},
    )
    assert no_csrf.status_code == 403
    wrong_password = client.post(
        "/api/admin/v2/auth/mfa/recovery-codes",
        headers=headers,
        json={"password": "wrong-password", "code": first_codes[0]},
    )
    assert wrong_password.status_code == 401
    assert stored_recovery_codes(owner) == old_persisted

    regenerated = client.post(
        "/api/admin/v2/auth/mfa/recovery-codes",
        headers=headers,
        json={"password": PASSWORD, "code": first_codes[0]},
    )
    assert regenerated.status_code == 200, regenerated.text
    second_codes = regenerated.json()["recoveryCodes"]
    assert len(second_codes) == 10
    assert set(second_codes).isdisjoint(first_codes)
    assert stored_recovery_codes(owner) != old_persisted

    rejected = client.post(
        "/api/admin/v2/auth/mfa/disable",
        headers=headers,
        json={"password": PASSWORD, "code": "invalid-code"},
    )
    assert rejected.status_code == 401
    assert db.is_mfa_enabled(owner)

    now[0] += 30
    disabled = client.post(
        "/api/admin/v2/auth/mfa/disable",
        headers=headers,
        json={"password": PASSWORD, "code": mfa._hotp(secret, now[0] // 30)},
    )
    assert disabled.status_code == 200, disabled.text
    assert disabled.json() == {"status": "disabled"}
    assert disabled.headers["cache-control"] == "no-store"
    assert not db.is_mfa_enabled(owner)
    assert client.get("/api/admin/v2/auth/mfa/status").json() == {
        "enabled": False,
        "recoveryCodesRemaining": 0,
    }

    with db._lock:
        rows = db._get_conn().execute(
            "SELECT action FROM admin_audit_events WHERE actor_json LIKE ? ORDER BY occurred_at",
            (f"%{owner}%",),
        ).fetchall()
    actions = [str(row[0]) for row in rows]
    assert "admin.auth.mfa_enrollment_started" in actions
    assert "admin.auth.mfa_enabled" in actions
    assert "admin.auth.mfa_recovery_codes_regenerated" in actions
    assert "admin.auth.mfa_disabled" in actions


def test_admin_mfa_enrollment_verification_is_account_wide_throttled(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME)
    monkeypatch.setattr(auth_service, "mfa_owner_threshold", 2)
    headers = authenticated(client, owner)
    enrollment = setup(client, headers)

    for _ in range(2):
        response = client.post(
            "/api/admin/v2/auth/mfa/confirm",
            headers=headers,
            json={"code": "000000"},
        )
        assert response.status_code == 400

    throttled = confirm(client, headers, enrollment["secret"])
    assert throttled.status_code == 429
    assert throttled.json()["error"]["code"] == "ADMIN_MFA_THROTTLED"
    assert int(throttled.headers["Retry-After"]) > 0
    assert not db.is_mfa_enabled(owner)


def test_concurrent_admin_mfa_confirmation_has_exactly_one_winner(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME)
    headers = authenticated(client, owner)
    enrollment = setup(client, headers)
    code = mfa._hotp(enrollment["secret"], FIXED_TIME // 30)

    def attempt_confirmation():
        return client.post(
            "/api/admin/v2/auth/mfa/confirm",
            headers=headers,
            json={"code": code},
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(lambda _: attempt_confirmation(), range(2)))

    assert sorted(response.status_code for response in responses) == [200, 409]
    winner = next(response for response in responses if response.status_code == 200)
    recovery_codes = winner.json()["recoveryCodes"]
    assert stored_recovery_codes(owner) == [mfa.hash_backup_code(value) for value in recovery_codes]
    with db._lock:
        enabled_events = db._get_conn().execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE action='admin.auth.mfa_enabled' AND actor_json LIKE ?",
            (f"%{owner}%",),
        ).fetchone()[0]
    assert enabled_events == 1


def test_repeated_admin_mfa_setup_resumes_the_same_pending_secret(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME)
    authenticated(client, owner)
    token = client.cookies.get("practenture_admin_v2_session")
    assert token
    session, _ = auth_service.authenticate(token)

    secret, uri, qr_code = auth_service.start_mfa_enrollment(
        session,
        PASSWORD,
        "req_admin_mfa_setup_resume_contract_one",
        "127.0.0.1",
        lambda value: f"qr:{value}",
    )
    resumed_secret, resumed_uri, resumed_qr_code = auth_service.start_mfa_enrollment(
        session,
        PASSWORD,
        "req_admin_mfa_setup_resume_contract_two",
        "127.0.0.1",
        lambda value: f"qr:{value}",
    )

    assert resumed_secret == secret
    assert resumed_uri == uri
    assert qr_code == f"qr:{uri}"
    assert resumed_qr_code == qr_code
    code = mfa._hotp(secret, FIXED_TIME // 30)
    issued = auth_service.confirm_mfa_enrollment(
        session,
        code,
        "req_admin_mfa_confirm_resume_contract",
        "test-client",
    )
    assert stored_recovery_codes(owner) == [mfa.hash_backup_code(value) for value in issued]


def test_mfa_management_password_throttle_survives_clients_and_repository_instances(
    client: TestClient,
    owner: str,
) -> None:
    authenticated(client, owner)
    token = client.cookies.get("practenture_admin_v2_session")
    assert token
    session, _ = auth_service.authenticate(token)

    for index, client_signal in enumerate(("client-a", "client-b")):
        service = AdminAuthService(AdminSessionRepository())
        service.login_threshold = 2
        service.login_identity_threshold = 2
        with pytest.raises(AdminError) as failure:
            service.start_mfa_enrollment(
                session,
                "wrong-password",
                f"req_admin_mfa_wrong_password_{index}",
                client_signal,
                lambda value: f"qr:{value}",
            )
        assert failure.value.status_code == 401

    restarted_service = AdminAuthService(AdminSessionRepository())
    restarted_service.login_threshold = 2
    restarted_service.login_identity_threshold = 2
    with pytest.raises(AdminError) as throttled:
        restarted_service.start_mfa_enrollment(
            session,
            PASSWORD,
            "req_admin_mfa_throttled_after_restart",
            "client-c",
            lambda value: f"qr:{value}",
        )
    assert throttled.value.status_code == 429
    assert throttled.value.code == "ADMIN_REAUTH_THROTTLED"
    assert int(throttled.value.headers["Retry-After"]) > 0


def test_successful_mfa_management_does_not_accumulate_toward_lockout(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(auth_service, "login_threshold", 2)
    monkeypatch.setattr(auth_service, "login_identity_threshold", 2)
    headers = authenticated(client, owner)

    responses = [
        client.post(
            "/api/admin/v2/auth/mfa/setup",
            headers=headers,
            json={"password": PASSWORD},
        )
        for _ in range(3)
    ]
    assert [response.status_code for response in responses] == [200, 200, 200]
    assert len({response.json()["secret"] for response in responses}) == 1


def test_qr_generation_failure_rolls_back_pending_secret_and_success_audit(
    client: TestClient,
    owner: str,
) -> None:
    authenticated(client, owner)
    token = client.cookies.get("practenture_admin_v2_session")
    assert token
    session, _ = auth_service.authenticate(token)

    def unavailable(_: str) -> str:
        raise AdminError(
            503,
            "ADMIN_MFA_SETUP_UNAVAILABLE",
            "MFA enrollment is temporarily unavailable",
        )

    with pytest.raises(AdminError) as failure:
        auth_service.start_mfa_enrollment(
            session,
            PASSWORD,
            "req_admin_mfa_qr_failure",
            "test-client",
            unavailable,
        )
    assert failure.value.code == "ADMIN_MFA_SETUP_UNAVAILABLE"
    assert db.get_mfa_secret(owner) is None
    with db._lock:
        count = db._get_conn().execute(
            """SELECT COUNT(*) FROM admin_audit_events
               WHERE action='admin.auth.mfa_enrollment_started'
                 AND actor_json LIKE ?""",
            (f"%{owner}%",),
        ).fetchone()[0]
    assert count == 0


def test_revoked_session_cannot_win_race_into_mfa_setup_mutation(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticated(client, owner)
    token = client.cookies.get("practenture_admin_v2_session")
    assert token
    session, _ = auth_service.authenticate(token)
    execute = auth_service.mutations.execute

    def revoke_before_mutation(**kwargs):
        with db._lock:
            conn = db._get_conn()
            conn.execute(
                """UPDATE admin_sessions SET revoked_at=?, revocation_reason='race_test'
                   WHERE id=?""",
                ("2099-01-01T00:00:00+00:00", session.record.id),
            )
            conn.commit()
        return execute(**kwargs)

    monkeypatch.setattr(auth_service.mutations, "execute", revoke_before_mutation)
    with pytest.raises(AdminError) as failure:
        auth_service.start_mfa_enrollment(
            session,
            PASSWORD,
            "req_admin_mfa_revocation_race",
            "test-client",
            lambda value: f"qr:{value}",
        )
    assert failure.value.code == "ADMIN_AUTH_REQUIRED"
    assert db.get_mfa_secret(owner) is None
    with db._lock:
        count = db._get_conn().execute(
            """SELECT COUNT(*) FROM admin_audit_events
               WHERE action='admin.auth.mfa_enrollment_started'
                 AND actor_json LIKE ?""",
            (f"%{owner}%",),
        ).fetchone()[0]
    assert count == 0


def test_successful_login_mfa_verification_resets_owner_throttle(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [FIXED_TIME]
    monkeypatch.setattr(mfa.time, "time", lambda: now[0])
    monkeypatch.setattr(auth_service, "mfa_owner_threshold", 2)
    headers = authenticated(client, owner)
    enrollment = setup(client, headers)
    secret = enrollment["secret"]
    assert confirm(client, headers, secret).status_code == 200

    for _ in range(3):
        now[0] += 30
        challenge = login(client, owner)
        assert challenge.status_code == 401
        verified = client.post(
            "/api/admin/v2/auth/mfa/verify",
            json={
                "challengeToken": challenge.headers["X-Admin-MFA-Challenge"],
                "mfaCode": mfa._hotp(secret, now[0] // 30),
            },
        )
        assert verified.status_code == 200, verified.text


def test_mfa_management_equalizes_incorrect_legacy_password_work(
    client: TestClient,
    owner: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    authenticated(client, owner)
    token = client.cookies.get("practenture_admin_v2_session")
    assert token
    session, _ = auth_service.authenticate(token)
    legacy_hash = hashlib.sha256(PASSWORD.encode()).hexdigest()
    with db._lock:
        conn = db._get_conn()
        conn.execute(
            "UPDATE users SET password_hash=? WHERE username=?",
            (legacy_hash, owner),
        )
        conn.commit()

    verified_hashes: list[str] = []
    verify_password = service_module.verify_password

    def tracked_verify_password(password: str, password_hash: str) -> bool:
        verified_hashes.append(password_hash)
        return verify_password(password, password_hash)

    monkeypatch.setattr(service_module, "verify_password", tracked_verify_password)
    with pytest.raises(AdminError) as failure:
        auth_service.start_mfa_enrollment(
            session,
            "wrong-password",
            "req_admin_mfa_legacy_password_failure",
            "test-client",
            lambda value: f"qr:{value}",
        )
    assert failure.value.code == "ADMIN_REAUTH_FAILED"
    assert verified_hashes == [legacy_hash, service_module._DUMMY_PASSWORD_HASH]
