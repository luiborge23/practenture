"""Account-deletion contracts: reauthentication, atomicity, and anonymization."""

from __future__ import annotations

import json
import hashlib
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from collections.abc import Iterator
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient
import pytest

import account_deletion
import auth
import database as database_module
from auth import _create_access_token
from database import Database
from main import app
from mfa import _hotp, generate_totp_secret
from models import SessionConfiguration, TeamConfig
from security import hash_password


@pytest.fixture
def isolated_db(tmp_path, monkeypatch) -> Iterator[Database]:
    monkeypatch.setenv("PRACTENTURE_DB_PATH", str(tmp_path / "account-deletion.db"))
    monkeypatch.setenv(
        "PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY",
        "account-deletion-test-provider-key-at-least-32-bytes",
    )
    test_db = Database()
    monkeypatch.setattr(database_module, "db", test_db)
    monkeypatch.setattr(auth.db_module, "db", test_db)
    yield test_db
    if test_db._conn is not None:
        test_db._conn.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def _create_user(
    db: Database,
    *,
    username: str,
    role: str = "student",
    password: str = "DeleteMe123!",
    provider: str = "password",
    provider_uid: str | None = None,
) -> None:
    conn = db._get_conn()
    conn.execute(
        """INSERT OR REPLACE INTO users
           (username, password_hash, role, name, student_id, email, provider,
            provider_uid, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
        (
            username,
            hash_password(password),
            role,
            "Deletion Test User",
            username if role == "student" else None,
            f"{username}@example.test",
            provider,
            provider_uid,
        ),
    )
    conn.commit()


def _access_token(username: str, role: str = "student") -> str:
    return _create_access_token(
        {
            "sub": username,
            "role": role,
            "tenantId": "",
            "exp": (datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp(),
        }
    )


def _headers(username: str, role: str = "student") -> dict[str, str]:
    return {"Authorization": f"Bearer {_access_token(username, role)}"}


def _deletion_proof(client: TestClient, headers: dict[str, str]) -> dict[str, str]:
    requirements = client.get(
        "/api/auth/account/deletion-requirements", headers=headers
    )
    assert requirements.status_code == 200
    payload = requirements.json()
    return {
        "challengeId": payload["challengeId"],
        "operationToken": payload["operationToken"],
    }


def test_password_account_requires_confirmation_and_current_password(
    isolated_db: Database, client: TestClient
) -> None:
    _create_user(isolated_db, username="delete-password")
    headers = _headers("delete-password")
    proof = _deletion_proof(client, headers)

    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "delete", "password": "DeleteMe123!", **proof},
    )
    assert response.status_code == 409
    assert isolated_db.get_user("delete-password") is not None

    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": "wrong", **proof},
    )
    assert response.status_code == 403
    assert isolated_db.get_user("delete-password") is not None


def test_student_deletion_revokes_access_and_anonymizes_gameplay(
    isolated_db: Database, client: TestClient
) -> None:
    username = "delete-student"
    _create_user(isolated_db, username=username)
    conn = isolated_db._get_conn()
    conn.execute(
        "INSERT INTO organizations (id, name) VALUES ('org-delete', 'Deletion Org')"
    )
    conn.execute(
        "INSERT INTO memberships (id, user_id, org_id, role) "
        "VALUES ('membership-delete', ?, 'org-delete', 'student')",
        (username,),
    )
    conn.execute(
        """INSERT INTO classes
           (id, professor_user_id, organization_id, name, join_code)
           VALUES ('class-delete', 'professor', 'org-delete', 'Class', 'DEL-CLASS')"""
    )
    conn.execute(
        "INSERT INTO class_enrollments (id, class_id, student_user_id) "
        "VALUES ('enrollment-delete', 'class-delete', ?)",
        (username,),
    )
    conn.execute(
        """INSERT INTO refresh_tokens
           (token_hash, user_id, issued_at, expires_at, revoked)
           VALUES ('refresh-delete', ?, 1, 9999999999, 0)""",
        (username,),
    )
    conn.execute(
        """INSERT INTO mfa_secrets (user_id, secret, enabled, backup_codes)
           VALUES (?, 'encrypted-secret', 0, '[]')""",
        (username,),
    )
    conn.execute(
        """INSERT INTO auth_identities
           (id, provider, provider_subject, user_id, created_at)
           VALUES ('identity-delete', 'password', 'subject-delete', ?, 1)""",
        (username,),
    )
    conn.commit()

    code = isolated_db.create_session(
        SessionConfiguration(),
        [TeamConfig(teamName="Personal Team Name", studentId=username)],
        created_by="professor",
        professor_user_id="professor",
        class_id="class-delete",
        organization_id="org-delete",
    )
    isolated_db.transition_session_owned(
        code=code,
        professor_user_id="professor",
        allowed_states=("creating",),
        new_state="finished",
    )
    conn = isolated_db._get_conn()
    conn.execute(
        "INSERT INTO decisions VALUES (?, 1, 'Personal Team Name', ?)",
        (code, json.dumps({"teamId": "Personal Team Name", "studentId": username})),
    )
    conn.execute(
        "INSERT INTO results VALUES (?, 1, 'Personal Team Name', ?)",
        (code, json.dumps({"teamId": "Personal Team Name"})),
    )
    conn.commit()

    old_token = _access_token(username)
    headers = {"Authorization": f"Bearer {old_token}"}
    proof = _deletion_proof(client, headers)
    pending_receipt = client.post(
        "/api/auth/account/deletion-status",
        json={"operationToken": proof["operationToken"]},
    )
    assert pending_receipt.status_code == 200
    assert pending_receipt.json() == {"status": "pending"}
    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": "DeleteMe123!", **proof},
    )
    assert response.status_code == 204
    assert response.content == b""
    assert isolated_db.get_user(username) is None
    receipt = client.post(
        "/api/auth/account/deletion-status",
        json={"operationToken": proof["operationToken"]},
    )
    assert receipt.status_code == 200
    assert receipt.json() == {"status": "completed"}
    assert client.post(
        "/api/auth/account/deletion-status",
        json={"operationToken": "unknown-opaque-token-that-is-long-enough"},
    ).status_code == 404

    conn = isolated_db._get_conn()
    assert conn.execute(
        "SELECT 1 FROM refresh_tokens WHERE user_id=?", (username,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT 1 FROM mfa_secrets WHERE user_id=?", (username,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT 1 FROM auth_identities WHERE user_id=?", (username,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT 1 FROM memberships WHERE user_id=?", (username,)
    ).fetchone() is None
    assert conn.execute(
        "SELECT 1 FROM class_enrollments WHERE student_user_id=?", (username,)
    ).fetchone() is None

    session_row = conn.execute(
        "SELECT teams_json FROM sessions WHERE code=?", (code,)
    ).fetchone()
    teams = json.loads(session_row["teams_json"])
    assert teams[0]["studentId"] is None
    assert teams[0]["teamName"].startswith("Deleted Team ")
    assert "Personal Team Name" not in session_row["teams_json"]
    assert username not in session_row["teams_json"]
    new_team_id = teams[0]["teamName"]
    assert conn.execute(
        "SELECT 1 FROM decisions WHERE session_code=? AND team_id=?",
        (code, new_team_id),
    ).fetchone() is not None
    assert conn.execute(
        "SELECT 1 FROM results WHERE session_code=? AND team_id=?",
        (code, new_team_id),
    ).fetchone() is not None

    verify = client.post(
        "/api/auth/verify", headers={"Authorization": f"Bearer {old_token}"}
    )
    assert verify.status_code == 401


def test_deletion_challenge_is_atomic_and_one_use(
    isolated_db: Database,
) -> None:
    from account_deletion_security import (
        DeletionSecurityError,
        consume_deletion_challenge,
        create_deletion_challenge,
    )

    username = "delete-one-use"
    _create_user(isolated_db, username=username)
    challenge = create_deletion_challenge(
        isolated_db, user_id=username, provider="password"
    )
    conn = isolated_db.connect(check_same_thread=False)
    try:
        conn.execute("BEGIN IMMEDIATE")
        consume_deletion_challenge(
            conn,
            challenge_id=challenge["challengeId"],
            user_id=username,
            provider="password",
            operation_token=challenge["operationToken"],
            provider_nonce=None,
            provider_issued_at=None,
        )
        conn.commit()
        conn.execute("BEGIN IMMEDIATE")
        with pytest.raises(DeletionSecurityError):
            consume_deletion_challenge(
                conn,
                challenge_id=challenge["challengeId"],
                user_id=username,
                provider="password",
                operation_token=challenge["operationToken"],
                provider_nonce=None,
                provider_issued_at=None,
            )
        conn.rollback()
    finally:
        conn.close()


def test_student_deletion_detaches_active_classroom_participation(
    isolated_db: Database, client: TestClient
) -> None:
    username = "delete-active-student"
    _create_user(isolated_db, username=username)
    code = isolated_db.create_session(
        SessionConfiguration(),
        [TeamConfig(teamName="Active Team", studentId=username)],
        created_by="professor",
        professor_user_id="professor",
    )
    headers = _headers(username)
    proof = _deletion_proof(client, headers)

    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": "DeleteMe123!", **proof},
    )
    assert response.status_code == 204
    assert isolated_db.get_user(username) is None
    session = isolated_db.get_session(code)
    assert session is not None
    assert session.teams[0].studentId is None
    assert session.teams[0].teamName.startswith("Deleted Team ")


def test_professor_deletion_requires_finished_sessions_and_preserves_pseudonymous_history(
    isolated_db: Database, client: TestClient
) -> None:
    username = "delete-professor"
    _create_user(isolated_db, username=username, role="professor")
    conn = isolated_db._get_conn()
    conn.execute(
        "INSERT INTO organizations (id, name, created_by) VALUES ('org-prof-delete', 'Org', ?)",
        (username,),
    )
    conn.execute(
        """INSERT INTO classes
           (id, professor_user_id, organization_id, name, join_code)
           VALUES ('class-prof-delete', ?, 'org-prof-delete', 'Class', 'PROF-DEL')""",
        (username,),
    )
    conn.commit()
    code = isolated_db.create_session(
        SessionConfiguration(),
        [],
        created_by=username,
        professor_user_id=username,
        class_id="class-prof-delete",
        organization_id="org-prof-delete",
    )
    isolated_db.transition_session_owned(
        code=code,
        professor_user_id=username,
        allowed_states=("creating",),
        new_state="active",
    )
    headers = _headers(username, "professor")
    proof = _deletion_proof(client, headers)

    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": "DeleteMe123!", **proof},
    )
    assert response.status_code == 409
    assert "active classroom session" in response.json()["detail"]["message"]
    assert isolated_db.get_user(username) is not None

    isolated_db.transition_session_owned(
        code=code,
        professor_user_id=username,
        allowed_states=("active",),
        new_state="finished",
    )
    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": "DeleteMe123!", **proof},
    )
    assert response.status_code == 204

    conn = isolated_db._get_conn()
    session = conn.execute(
        "SELECT state, professor_user_id, created_by FROM sessions WHERE code=?", (code,)
    ).fetchone()
    assert session["state"] == "finished"
    assert session["professor_user_id"].startswith("deleted-")
    assert session["created_by"] == session["professor_user_id"]
    class_row = conn.execute(
        "SELECT professor_user_id, is_active FROM classes WHERE id='class-prof-delete'"
    ).fetchone()
    assert class_row["professor_user_id"] == session["professor_user_id"]
    assert class_row["is_active"] == 0
    tombstone = conn.execute(
        "SELECT * FROM users WHERE username=?", (session["professor_user_id"],)
    ).fetchone()
    assert tombstone["status"] == "deleted"
    assert tombstone["email"] is None
    assert tombstone["provider_uid"] is None


def test_mfa_enabled_account_requires_and_consumes_second_factor(
    isolated_db: Database, client: TestClient
) -> None:
    username = "delete-mfa"
    _create_user(isolated_db, username=username)
    secret = generate_totp_secret()
    isolated_db.set_mfa_secret(username, secret)
    isolated_db.enable_mfa(username, ["ABCD-EFGH-IJKL"])
    headers = _headers(username)

    requirements = client.get(
        "/api/auth/account/deletion-requirements", headers=headers
    )
    assert requirements.status_code == 200
    requirements_payload = requirements.json()
    assert requirements_payload["mfaRequired"] is True
    proof = {
        "challengeId": requirements_payload["challengeId"],
        "operationToken": requirements_payload["operationToken"],
    }

    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": "DeleteMe123!", **proof},
    )
    assert response.status_code == 403
    assert isolated_db.get_user(username) is not None

    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={
            "confirmation": "DELETE",
            "password": "DeleteMe123!",
            "mfaCode": "000000",
            **proof,
        },
    )
    assert response.status_code == 403
    assert isolated_db.get_user(username) is not None

    current_code = _hotp(secret, int(time.time()) // 30)
    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={
            "confirmation": "DELETE",
            "password": "DeleteMe123!",
            "mfaCode": current_code,
            **proof,
        },
    )
    assert response.status_code == 204
    assert isolated_db.get_user(username) is None


def test_social_account_requires_matching_provider_subject(
    isolated_db: Database, client: TestClient, monkeypatch
) -> None:
    username = "delete-apple"
    _create_user(
        isolated_db,
        username=username,
        role="professor",
        provider="apple",
        provider_uid="apple-subject",
    )
    headers = _headers(username, "professor")
    requirements = client.get(
        "/api/auth/account/deletion-requirements", headers=headers
    ).json()
    provider_nonce = hashlib.sha256(
        requirements["challenge"].encode("utf-8")
    ).hexdigest()
    monkeypatch.setattr(
        "routers.auth.verify_apple_id_token",
        lambda token, audience: {
            "sub": "other-subject",
            "nonce": provider_nonce,
            "iat": time.time(),
        },
    )
    monkeypatch.setattr(
        "apple_token_revocation.exchange_apple_authorization_code",
        lambda code: {
            "refresh_token": "refresh-token",
            "id_token": "exchanged-id-token",
        },
    )
    monkeypatch.setattr("apple_token_revocation.revoke_apple_tokens", lambda tokens: None)
    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={
            "confirmation": "DELETE",
            "providerToken": "provider-token",
            "providerNonce": provider_nonce,
            "providerAuthorizationCode": "authorization-code",
            "challengeId": requirements["challengeId"],
            "operationToken": requirements["operationToken"],
        },
    )
    assert response.status_code == 403
    assert isolated_db.get_user(username) is not None

    monkeypatch.setattr(
        "routers.auth.verify_apple_id_token",
        lambda token, audience: {
            "sub": "apple-subject",
            "nonce": provider_nonce,
            "iat": time.time(),
        },
    )
    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={
            "confirmation": "DELETE",
            "providerToken": "provider-token",
            "providerNonce": provider_nonce,
            "providerAuthorizationCode": "authorization-code",
            "challengeId": requirements["challengeId"],
            "operationToken": requirements["operationToken"],
        },
    )
    assert response.status_code == 204
    assert isolated_db.get_user(username) is None


def test_owner_cannot_self_delete_without_transfer(
    isolated_db: Database, client: TestClient
) -> None:
    _create_user(isolated_db, username="delete-owner", role="owner")
    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=_headers("delete-owner", "owner"),
        json={"confirmation": "DELETE", "password": "DeleteMe123!"},
    )
    assert response.status_code == 403
    assert "transferred" in response.json()["detail"]["message"].lower()
    assert isolated_db.get_user("delete-owner") is not None


def test_apple_revocation_outbox_survives_provider_failure(
    isolated_db: Database, client: TestClient, monkeypatch
) -> None:
    from account_deletion_security import process_provider_revocation_job

    username = "delete-apple-outbox"
    _create_user(
        isolated_db,
        username=username,
        provider="apple",
        provider_uid="apple-outbox-subject",
    )
    headers = _headers(username)
    requirements = client.get(
        "/api/auth/account/deletion-requirements", headers=headers
    ).json()
    nonce = hashlib.sha256(requirements["challenge"].encode("utf-8")).hexdigest()
    monkeypatch.setattr(
        "routers.auth.verify_apple_id_token",
        lambda token, audience: {
            "sub": "apple-outbox-subject",
            "nonce": nonce,
            "iat": time.time(),
        },
    )
    monkeypatch.setattr(
        "apple_token_revocation.exchange_apple_authorization_code",
        lambda code: {
            "refresh_token": "durable-refresh-token",
            "id_token": "exchange-id-token",
        },
    )

    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={
            "confirmation": "DELETE",
            "providerToken": "provider-id-token",
            "providerNonce": nonce,
            "providerAuthorizationCode": "authorization-code",
            "challengeId": requirements["challengeId"],
            "operationToken": requirements["operationToken"],
        },
    )
    assert response.status_code == 204
    assert isolated_db.get_user(username) is None

    job = isolated_db._get_conn().execute(
        "SELECT * FROM provider_revocation_jobs"
    ).fetchone()
    assert job is not None
    assert job["status"] == "pending"
    assert "durable-refresh-token" not in job["payload_ciphertext"]

    def fail_revocation(tokens):
        raise RuntimeError("provider unavailable")

    monkeypatch.setattr("apple_token_revocation.revoke_apple_tokens", fail_revocation)
    assert process_provider_revocation_job(isolated_db, job["id"]) is False
    failed = isolated_db._get_conn().execute(
        "SELECT * FROM provider_revocation_jobs WHERE id=?", (job["id"],)
    ).fetchone()
    assert failed["status"] == "pending"
    assert failed["attempts"] == 1
    assert isolated_db.get_user(username) is None

    isolated_db._get_conn().execute(
        "UPDATE provider_revocation_jobs SET next_attempt_at=0 WHERE id=?", (job["id"],)
    )
    isolated_db._get_conn().commit()
    monkeypatch.setattr("apple_token_revocation.revoke_apple_tokens", lambda tokens: None)
    assert process_provider_revocation_job(isolated_db, job["id"]) is True
    completed = isolated_db._get_conn().execute(
        "SELECT * FROM provider_revocation_jobs WHERE id=?", (job["id"],)
    ).fetchone()
    assert completed["status"] == "completed"
    assert completed["payload_ciphertext"] == ""


def test_apple_exchange_identity_must_match_reauthentication_token(
    isolated_db: Database, client: TestClient, monkeypatch
) -> None:
    username = "delete-apple-exchange-mismatch"
    _create_user(
        isolated_db,
        username=username,
        provider="apple",
        provider_uid="linked-apple-subject",
    )
    headers = _headers(username)
    requirements = client.get(
        "/api/auth/account/deletion-requirements", headers=headers
    ).json()
    nonce = hashlib.sha256(requirements["challenge"].encode("utf-8")).hexdigest()

    def verify_token(token: str, audience: str | None):
        return {
            "sub": (
                "different-apple-subject"
                if token == "exchanged-id-token"
                else "linked-apple-subject"
            ),
            "nonce": nonce,
            "iat": time.time(),
        }

    monkeypatch.setattr("routers.auth.verify_apple_id_token", verify_token)
    monkeypatch.setattr(
        "apple_token_revocation.exchange_apple_authorization_code",
        lambda code: {
            "refresh_token": "refresh-token",
            "id_token": "exchanged-id-token",
        },
    )
    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={
            "confirmation": "DELETE",
            "providerToken": "provider-id-token",
            "providerNonce": nonce,
            "providerAuthorizationCode": "authorization-code",
            "challengeId": requirements["challengeId"],
            "operationToken": requirements["operationToken"],
        },
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "apple_authorization_code_mismatch"
    assert isolated_db.get_user(username) is not None
    assert isolated_db._get_conn().execute(
        "SELECT 1 FROM provider_revocation_jobs"
    ).fetchone() is None


def test_stale_revocation_worker_cannot_overwrite_completed_job(
    isolated_db: Database, monkeypatch
) -> None:
    from account_deletion_security import (
        enqueue_provider_revocation,
        process_provider_revocation_job,
    )

    conn = isolated_db._get_conn()
    job_id = enqueue_provider_revocation(
        conn,
        provider="apple",
        payload={"tokens": ["lease-safe-token"]},
    )
    conn.commit()
    first_worker_entered = threading.Event()
    release_first_worker = threading.Event()
    call_lock = threading.Lock()
    call_count = 0

    def revoke(tokens):
        nonlocal call_count
        with call_lock:
            call_count += 1
            current_call = call_count
        if current_call == 1:
            first_worker_entered.set()
            assert release_first_worker.wait(timeout=5)
            raise RuntimeError("stale worker failed after its lease expired")

    monkeypatch.setattr("apple_token_revocation.revoke_apple_tokens", revoke)
    with ThreadPoolExecutor(max_workers=1) as pool:
        stale_future = pool.submit(
            process_provider_revocation_job, isolated_db, job_id
        )
        assert first_worker_entered.wait(timeout=5)
        conn.execute(
            "UPDATE provider_revocation_jobs SET next_attempt_at=0 WHERE id=?",
            (job_id,),
        )
        conn.commit()
        assert process_provider_revocation_job(isolated_db, job_id) is True
        release_first_worker.set()
        assert stale_future.result(timeout=5) is False

    completed = conn.execute(
        "SELECT * FROM provider_revocation_jobs WHERE id=?", (job_id,)
    ).fetchone()
    assert completed["status"] == "completed"
    assert completed["payload_ciphertext"] == ""
    assert completed["lease_token"] is None


def test_pending_revocation_survives_jwt_secret_rotation(
    isolated_db: Database, monkeypatch
) -> None:
    from account_deletion_security import (
        enqueue_provider_revocation,
        process_provider_revocation_job,
    )

    conn = isolated_db._get_conn()
    job_id = enqueue_provider_revocation(
        conn,
        provider="apple",
        payload={"refresh_token": "rotation-safe-token"},
    )
    conn.commit()
    monkeypatch.setenv("PRACTENTURE_JWT_SECRET", "x" * 32)
    revoked = []
    monkeypatch.setattr(
        "apple_token_revocation.revoke_apple_tokens", lambda payload: revoked.append(payload)
    )

    assert process_provider_revocation_job(isolated_db, job_id) is True
    assert revoked == [{"refresh_token": "rotation-safe-token"}]


def test_provider_revocation_key_never_falls_back_to_authentication_secrets(
    monkeypatch,
) -> None:
    from account_deletion_security import validate_provider_security_configuration

    monkeypatch.delenv("PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY", raising=False)
    monkeypatch.setenv("PRACTENTURE_MFA_ENCRYPTION_KEY", "mfa-secret-at-least-32-characters")
    monkeypatch.setenv("PRACTENTURE_JWT_SECRET", "jwt-secret-at-least-32-characters")
    monkeypatch.setenv("SECRET_KEY", "legacy-secret-at-least-32-characters")

    with pytest.raises(RuntimeError, match="PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY"):
        validate_provider_security_configuration()


def test_google_deletion_requires_token_fresher_than_challenge(
    isolated_db: Database, client: TestClient, monkeypatch
) -> None:
    username = "delete-google-freshness"
    _create_user(
        isolated_db,
        username=username,
        provider="google",
        provider_uid="google-subject",
    )
    headers = _headers(username)
    requirements = client.get(
        "/api/auth/account/deletion-requirements", headers=headers
    ).json()
    monkeypatch.setattr(
        "routers.auth.verify_google_id_token",
        lambda token, audience: {
            "sub": "google-subject",
            "iat": requirements["challengeExpiresAt"] - 600,
        },
    )
    body = {
        "confirmation": "DELETE",
        "providerToken": "google-id-token",
        "challengeId": requirements["challengeId"],
        "operationToken": requirements["operationToken"],
    }
    response = client.request(
        "DELETE", "/api/auth/account", headers=headers, json=body
    )
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "provider_token_not_fresh"
    assert isolated_db.get_user(username) is not None

    monkeypatch.setattr(
        "routers.auth.verify_google_id_token",
        lambda token, audience: {"sub": "google-subject", "iat": time.time()},
    )
    response = client.request(
        "DELETE", "/api/auth/account", headers=headers, json=body
    )
    assert response.status_code == 204
    assert isolated_db.get_user(username) is None


def test_account_deletion_factor_failures_are_throttled(
    isolated_db: Database, client: TestClient
) -> None:
    username = "delete-throttled"
    _create_user(isolated_db, username=username)
    headers = _headers(username)
    body = {"confirmation": "DELETE", "password": "wrong-password"}

    for _ in range(5):
        response = client.request(
            "DELETE", "/api/auth/account", headers=headers, json=body
        )
        assert response.status_code == 403

    response = client.request(
        "DELETE", "/api/auth/account", headers=headers, json=body
    )
    assert response.status_code == 429
    assert response.json()["detail"]["code"] == "deletion_rate_limited"
    assert isolated_db.get_user(username) is not None


def test_deletion_attempt_reservation_is_atomic_under_concurrency(
    isolated_db: Database,
) -> None:
    from account_deletion_security import (
        DeletionSecurityError,
        reserve_deletion_attempt,
    )

    def reserve(_: int) -> bool:
        try:
            reserve_deletion_attempt(
                isolated_db,
                user_id="parallel-delete-user",
                client_signal="parallel-client",
            )
            return True
        except DeletionSecurityError:
            return False

    with ThreadPoolExecutor(max_workers=20) as pool:
        outcomes = list(pool.map(reserve, range(20)))
    assert outcomes.count(True) == 5
    assert outcomes.count(False) == 15


def test_deleted_bootstrap_professor_is_not_recreated(
    isolated_db: Database, client: TestClient, monkeypatch
) -> None:
    username = "bootstrap-professor-delete"
    password = "BootstrapDelete123!"
    monkeypatch.setenv("PRACTENTURE_PROFESSOR_USERNAME", username)
    monkeypatch.setenv("PRACTENTURE_PROFESSOR_PASSWORD", password)
    _create_user(
        isolated_db,
        username=username,
        role="professor",
        password=password,
    )
    headers = _headers(username, "professor")
    proof = _deletion_proof(client, headers)
    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": password, **proof},
    )
    assert response.status_code == 204
    monkeypatch.setenv(
        "PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY", "rotated-after-deletion-key"
    )

    auth.ensure_professor()

    assert isolated_db.get_user(username) is None
    assert isolated_db._get_conn().execute(
        "SELECT COUNT(*) AS count FROM account_deletion_markers"
    ).fetchone()["count"] == 2


def test_retained_invitation_and_audit_data_is_pseudonymized(
    isolated_db: Database, client: TestClient
) -> None:
    username = "delete-retained-pii"
    email = f"{username}@example.test"
    _create_user(isolated_db, username=username)
    conn = isolated_db._get_conn()
    conn.execute(
        """INSERT INTO professor_invitations
           (id, secret_hash, masked_code, organization_id, intended_email, expires_at)
           VALUES ('pii-invite', 'hash', '****', 'org', ?, '2099-01-01')""",
        (email,),
    )
    conn.execute(
        """INSERT INTO invitation_email_deliveries
           (id, invitation_id, recipient_email, owner_id, idempotency_key_hash,
            request_fingerprint, state, created_at, updated_at)
           VALUES ('pii-delivery', 'pii-invite', ?, 'owner', 'idem', 'fingerprint',
                   'accepted', '2026-01-01', '2026-01-01')""",
        (email,),
    )
    conn.execute(
        """INSERT INTO audit_events
           (id, occurred_at, actor_user_id, actor_role, action, target_type,
            target_id, request_id, source_ip, user_agent, before_json,
            after_json, metadata_json)
           VALUES ('pii-audit', '2026-01-01', ?, 'student', 'update', 'user', ?,
                   'request', '203.0.113.1', 'Personal Agent', ?, ?, ?)""",
        (
            username,
            username,
            json.dumps({"email": email, "username": username}),
            json.dumps({"name": "Deletion Test User"}),
            json.dumps({"description": f"Changed {email}"}),
        ),
    )
    conn.commit()
    headers = _headers(username)
    proof = _deletion_proof(client, headers)

    response = client.request(
        "DELETE",
        "/api/auth/account",
        headers=headers,
        json={"confirmation": "DELETE", "password": "DeleteMe123!", **proof},
    )

    assert response.status_code == 204
    retained = "\n".join(
        str(value)
        for row in conn.execute(
            """SELECT intended_email FROM professor_invitations
               UNION ALL SELECT recipient_email FROM invitation_email_deliveries
               UNION ALL SELECT before_json FROM audit_events
               UNION ALL SELECT after_json FROM audit_events
               UNION ALL SELECT metadata_json FROM audit_events"""
        ).fetchall()
        for value in row
    )
    assert username not in retained
    assert email not in retained
    audit = conn.execute("SELECT * FROM audit_events WHERE id='pii-audit'").fetchone()
    assert audit["source_ip"] is None
    assert audit["user_agent"] is None


def test_deletion_rolls_back_every_change_on_failure(
    isolated_db: Database, monkeypatch
) -> None:
    username = "delete-rollback"
    _create_user(isolated_db, username=username)
    conn = isolated_db._get_conn()
    conn.execute(
        """INSERT INTO refresh_tokens
           (token_hash, user_id, issued_at, expires_at, revoked)
           VALUES ('refresh-rollback', ?, 1, 9999999999, 0)""",
        (username,),
    )
    conn.commit()

    def fail_after_transaction_started(*args, **kwargs):
        raise RuntimeError("injected failure")

    monkeypatch.setattr(account_deletion, "_anonymize_session_teams", fail_after_transaction_started)
    from account_deletion_security import create_deletion_challenge

    challenge = create_deletion_challenge(
        isolated_db, user_id=username, provider="password"
    )
    with pytest.raises(RuntimeError, match="injected failure"):
        account_deletion.delete_account(
            isolated_db,
            user_id=username,
            confirmation="DELETE",
            password="DeleteMe123!",
            challenge_id=challenge["challengeId"],
            operation_token=challenge["operationToken"],
        )

    assert isolated_db.get_user(username) is not None
    assert isolated_db._get_conn().execute(
        "SELECT 1 FROM refresh_tokens WHERE user_id=?", (username,)
    ).fetchone() is not None
    assert isolated_db._get_conn().execute(
        "SELECT 1 FROM users WHERE username LIKE 'deleted-%'"
    ).fetchone() is None
