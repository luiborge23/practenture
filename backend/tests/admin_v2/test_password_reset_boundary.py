"""Atomicity contracts for the legacy password-reset/Admin V2 boundary."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import threading
import time
import uuid

import pytest
from fastapi.testclient import TestClient

from database import Database, db
from main import app
from security import hash_password, verify_password


@pytest.fixture
def identities():
    created: list[str] = []
    yield created
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


def _create_user(identities: list[str], role: str, password: str = "Original123!") -> str:
    username = f"reset-{role}-{uuid.uuid4().hex}"
    assert db.create_user(username, hash_password(password), role, f"Reset {role.title()}")
    identities.append(username)
    return username


def _create_token(username: str, raw_token: str, *, expires_at: float | None = None) -> str:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    if expires_at is None:
        db.create_reset_token(username, token_hash)
    else:
        with db._lock:
            db._get_conn().execute(
                """INSERT INTO password_reset_tokens
                       (token_hash, user_id, expires_at, used)
                   VALUES (?, ?, ?, 0)""",
                (token_hash, username, expires_at),
            )
            db._get_conn().commit()
    return token_hash


def _store_refresh(username: str, token_hash: str) -> None:
    now = time.time()
    db.store_refresh_token(token_hash, username, now, now + 3600)


def _login_owner(username: str, password: str = "Original123!") -> TestClient:
    client = TestClient(app, base_url="http://testserver")
    response = client.post(
        "/api/admin/v2/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    return client


def _reset(client: TestClient, token: str, password: str):
    return client.post(
        "/api/auth/reset-password",
        json={"token": token, "newPassword": password},
    )


def test_owner_reset_revokes_admin_cookie_and_refresh_tokens(
    identities, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    owner = _create_user(identities, "owner")
    client = _login_owner(owner)
    assert client.get("/api/admin/v2/auth/session").status_code == 200

    raw_token = f"owner-token-{uuid.uuid4().hex}"
    token_hash = _create_token(owner, raw_token)
    _store_refresh(owner, "owner-refresh")

    response = _reset(client, raw_token, "Replacement123!")
    assert response.status_code == 200
    assert response.json() == {"status": "password_reset"}
    assert client.get("/api/admin/v2/auth/session").status_code == 401

    with db._lock:
        conn = db._get_conn()
        user = conn.execute("SELECT password_hash FROM users WHERE username=?", (owner,)).fetchone()
        reset = conn.execute(
            "SELECT used FROM password_reset_tokens WHERE token_hash=?", (token_hash,)
        ).fetchone()
        refresh = conn.execute(
            "SELECT revoked FROM refresh_tokens WHERE token_hash='owner-refresh'"
        ).fetchone()
        sessions = conn.execute(
            "SELECT revoked_at, revocation_reason FROM admin_sessions WHERE owner_user_id=?",
            (owner,),
        ).fetchall()

    assert verify_password("Replacement123!", user["password_hash"])
    assert reset["used"] == 1
    assert refresh["revoked"] == 1
    assert sessions and all(row["revoked_at"] is not None for row in sessions)
    assert {row["revocation_reason"] for row in sessions} == {"password_reset"}


def test_concurrent_completion_has_one_winner_and_winner_password(
    identities, monkeypatch: pytest.MonkeyPatch
):
    professor = _create_user(identities, "professor")
    raw_token = f"race-token-{uuid.uuid4().hex}"
    token_hash = _create_token(professor, raw_token)
    _store_refresh(professor, "race-refresh")
    passwords = ("ConcurrentOne123!", "ConcurrentTwo123!")
    barrier = threading.Barrier(2)

    def synchronized_hash(password: str) -> str:
        barrier.wait(timeout=5)
        return f"test-hash::{password}"

    monkeypatch.setattr("security.hash_password", synchronized_hash)

    def complete(password: str):
        with TestClient(app, base_url="http://testserver") as client:
            return password, _reset(client, raw_token, password)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(complete, passwords))

    assert sorted(response.status_code for _, response in results) == [200, 400]
    winner = next(password for password, response in results if response.status_code == 200)
    loser_response = next(response for _, response in results if response.status_code == 400)
    assert loser_response.json() == {"detail": "Invalid or expired reset token"}

    with db._lock:
        conn = db._get_conn()
        password_hash = conn.execute(
            "SELECT password_hash FROM users WHERE username=?", (professor,)
        ).fetchone()[0]
        reset = conn.execute(
            "SELECT used FROM password_reset_tokens WHERE token_hash=?", (token_hash,)
        ).fetchone()
        refresh = conn.execute(
            "SELECT revoked FROM refresh_tokens WHERE token_hash='race-refresh'"
        ).fetchone()

    assert password_hash == f"test-hash::{winner}"
    assert reset["used"] == 1
    assert refresh["revoked"] == 1


def test_downstream_session_failure_rolls_back_every_reset_mutation(identities):
    owner = _create_user(identities, "owner")
    raw_token = f"rollback-token-{uuid.uuid4().hex}"
    token_hash = _create_token(owner, raw_token)
    _store_refresh(owner, "rollback-refresh")
    now = datetime.now(timezone.utc)
    session_id = f"rollback-{uuid.uuid4().hex}"
    old_hash = db.get_user(owner)["password_hash"]

    with db._lock:
        conn = db._get_conn()
        conn.execute(
            """INSERT INTO admin_sessions
                   (id, token_hash, csrf_token_hash, owner_user_id, role,
                    created_at, last_seen_at, idle_expires_at, absolute_expires_at)
               VALUES (?, ?, ?, ?, 'owner', ?, ?, ?, ?)""",
            (
                session_id,
                f"session-hash-{uuid.uuid4().hex}",
                f"csrf-hash-{uuid.uuid4().hex}",
                owner,
                now.isoformat(),
                now.isoformat(),
                (now + timedelta(minutes=15)).isoformat(),
                (now + timedelta(hours=8)).isoformat(),
            ),
        )
        conn.execute(
            """CREATE TRIGGER fail_password_reset_session_revoke
               BEFORE UPDATE OF revoked_at ON admin_sessions
               WHEN NEW.revocation_reason='password_reset'
               BEGIN SELECT RAISE(ABORT, 'forced password reset failure'); END"""
        )
        conn.commit()

    try:
        with pytest.raises(Exception, match="forced password reset failure"):
            db.complete_password_reset(raw_token, "replacement-hash-must-rollback")
    finally:
        with db._lock:
            db._get_conn().execute("DROP TRIGGER IF EXISTS fail_password_reset_session_revoke")
            db._get_conn().commit()

    with db._lock:
        conn = db._get_conn()
        user_hash = conn.execute(
            "SELECT password_hash FROM users WHERE username=?", (owner,)
        ).fetchone()[0]
        reset_used = conn.execute(
            "SELECT used FROM password_reset_tokens WHERE token_hash=?", (token_hash,)
        ).fetchone()[0]
        refresh_revoked = conn.execute(
            "SELECT revoked FROM refresh_tokens WHERE token_hash='rollback-refresh'"
        ).fetchone()[0]
        session = conn.execute(
            "SELECT revoked_at, revocation_reason FROM admin_sessions WHERE id=?", (session_id,)
        ).fetchone()

    assert user_hash == old_hash
    assert reset_used == 0
    assert refresh_revoked == 0
    assert session["revoked_at"] is None
    assert session["revocation_reason"] is None


def test_professor_reset_does_not_revoke_owner_sessions(
    identities, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    owner = _create_user(identities, "owner")
    professor = _create_user(identities, "professor")
    client = _login_owner(owner)
    raw_token = f"professor-token-{uuid.uuid4().hex}"
    _create_token(professor, raw_token)
    _store_refresh(professor, "professor-refresh")

    assert _reset(client, raw_token, "ProfessorNew123!").status_code == 200
    assert client.get("/api/admin/v2/auth/session").status_code == 200

    with db._lock:
        conn = db._get_conn()
        active_owner_sessions = conn.execute(
            """SELECT COUNT(*) FROM admin_sessions
               WHERE owner_user_id=? AND revoked_at IS NULL""",
            (owner,),
        ).fetchone()[0]
        professor_refresh = conn.execute(
            "SELECT revoked FROM refresh_tokens WHERE token_hash='professor-refresh'"
        ).fetchone()[0]
    assert active_owner_sessions == 1
    assert professor_refresh == 1


def test_invalid_and_expired_tokens_change_nothing(
    identities, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    owner = _create_user(identities, "owner")
    client = _login_owner(owner)
    old_hash = db.get_user(owner)["password_hash"]
    expired_raw = f"expired-token-{uuid.uuid4().hex}"
    expired_hash = _create_token(owner, expired_raw, expires_at=time.time() - 1)
    _store_refresh(owner, "untouched-refresh")

    invalid = _reset(client, f"invalid-{uuid.uuid4().hex}", "InvalidAttempt123!")
    expired = _reset(client, expired_raw, "ExpiredAttempt123!")
    assert invalid.status_code == expired.status_code == 400
    assert invalid.json() == expired.json() == {"detail": "Invalid or expired reset token"}

    with db._lock:
        conn = db._get_conn()
        current_hash = conn.execute(
            "SELECT password_hash FROM users WHERE username=?", (owner,)
        ).fetchone()[0]
        expired_used = conn.execute(
            "SELECT used FROM password_reset_tokens WHERE token_hash=?", (expired_hash,)
        ).fetchone()[0]
        refresh_revoked = conn.execute(
            "SELECT revoked FROM refresh_tokens WHERE token_hash='untouched-refresh'"
        ).fetchone()[0]
        active_sessions = conn.execute(
            """SELECT COUNT(*) FROM admin_sessions
               WHERE owner_user_id=? AND revoked_at IS NULL""",
            (owner,),
        ).fetchone()[0]

    assert current_hash == old_hash
    assert expired_used == 0
    assert refresh_revoked == 0
    assert active_sessions == 1
    assert client.get("/api/admin/v2/auth/session").status_code == 200


def test_legacy_database_without_admin_sessions_still_resets_owner(
    tmp_path, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("PRACTENTURE_DB_PATH", str(tmp_path / "legacy.sqlite3"))
    legacy_db = Database()
    owner = f"legacy-owner-{uuid.uuid4().hex}"
    assert legacy_db.create_user(owner, "old-hash", "owner", "Legacy Owner")
    raw_token = f"legacy-token-{uuid.uuid4().hex}"
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    legacy_db.create_reset_token(owner, token_hash)
    legacy_db.store_refresh_token("legacy-refresh", owner, time.time(), time.time() + 3600)

    assert legacy_db.complete_password_reset(raw_token, "new-hash")
    conn = legacy_db.connect()
    try:
        assert conn.execute(
            "SELECT password_hash FROM users WHERE username=?", (owner,)
        ).fetchone()[0] == "new-hash"
        assert conn.execute(
            "SELECT used FROM password_reset_tokens WHERE token_hash=?", (token_hash,)
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT revoked FROM refresh_tokens WHERE token_hash='legacy-refresh'"
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='admin_sessions'"
        ).fetchone() is None
    finally:
        conn.close()
