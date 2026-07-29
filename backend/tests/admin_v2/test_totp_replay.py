"""Deterministic sequential and multi-connection TOTP replay contracts."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import sqlite3
import uuid

import pytest
from fastapi.testclient import TestClient

import mfa
from admin_v2.repository import AdminSessionRepository
from database import db
from main import app
from security import hash_password

PASSWORD = "AdminV2-TOTP-Replay!"
SECRET = "JBSWY3DPEHPK3PXP"
FIXED_TIME = 1_800_000_000


@pytest.fixture
def owner():
    username = f"totp-replay-{uuid.uuid4().hex}"
    db.create_user(username, hash_password(PASSWORD), "owner", "Replay Owner")
    db.set_mfa_secret(username, SECRET)
    db.enable_mfa(username, [])
    yield username
    with db._lock:
        conn = db._get_conn()
        conn.execute("DELETE FROM admin_sessions WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM admin_mfa_replay_state WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM privileged_login_attempts WHERE identity_key=?", (username,))
        conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (username,))
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()


def _code(timestamp: int) -> str:
    return mfa._hotp(SECRET, timestamp // 30)


def _login(client: TestClient, username: str, code: str):
    return client.post(
        "/api/admin/v2/auth/login",
        json={"username": username, "password": PASSWORD, "mfaCode": code},
    )


def _sessions(username: str) -> list[dict]:
    with db._lock:
        rows = db._get_conn().execute(
            "SELECT * FROM admin_sessions WHERE owner_user_id=? ORDER BY created_at, id",
            (username,),
        ).fetchall()
    return [dict(row) for row in rows]


def _accepted_step(username: str) -> int | None:
    with db._lock:
        row = db._get_conn().execute(
            "SELECT last_accepted_totp_step FROM admin_mfa_replay_state WHERE owner_user_id=?",
            (username,),
        ).fetchone()
    return None if row is None else int(row[0])


def test_counter_resolution_chooses_newest_matching_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    center = FIXED_TIME // 30
    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME)
    monkeypatch.setattr(mfa, "_hotp", lambda _secret, step: "123456" if step in {center, center + 1} else "654321")
    assert mfa.resolve_totp_counter(SECRET, "123456", at_time=FIXED_TIME) == center + 1
    assert mfa.verify_totp(SECRET, "123456") is True


def test_same_code_is_accepted_once_without_replay_rotation_and_next_step_is_accepted(
    owner: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [FIXED_TIME]
    monkeypatch.setattr(mfa.time, "time", lambda: now[0])
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    with TestClient(app, base_url="http://testserver") as client:
        accepted = _login(client, owner, _code(FIXED_TIME))
        assert accepted.status_code == 200, accepted.text
        original = _sessions(owner)
        assert len(original) == 1 and original[0]["revoked_at"] is None

        replay = _login(client, owner, _code(FIXED_TIME))
        assert replay.status_code == 401, replay.text
        assert replay.json()["error"]["code"] == "ADMIN_MFA_REPLAYED"
        assert _sessions(owner) == original

        now[0] += 30
        next_step = _login(client, owner, _code(now[0]))
        assert next_step.status_code == 200, next_step.text

    rows = _sessions(owner)
    assert len(rows) == 2
    assert sum(row["revoked_at"] is None for row in rows) == 1
    assert _accepted_step(owner) == now[0] // 30


def test_concurrent_same_code_across_separate_connections_has_one_winner(
    owner: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME)
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    code = _code(FIXED_TIME)

    def attempt() -> tuple[int, str | None]:
        with TestClient(app, base_url="http://testserver") as client:
            response = _login(client, owner, code)
            error = response.json().get("error", {}).get("code")
            return response.status_code, error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: attempt(), range(2)))

    assert sorted(status for status, _ in results) == [200, 401]
    assert [error for status, error in results if status == 401] == ["ADMIN_MFA_REPLAYED"]
    rows = _sessions(owner)
    assert len(rows) == 1 and rows[0]["revoked_at"] is None
    assert _accepted_step(owner) == FIXED_TIME // 30


def test_failed_session_insert_rolls_back_totp_counter_consumption(
    owner: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME)
    repo = AdminSessionRepository()
    common = dict(
        token_hash="duplicate-replay-token",
        csrf_hash="csrf",
        user_id=owner,
        role="owner",
        created_at=datetime.now(timezone.utc).isoformat(),
        idle_expires_at="2099-01-01T00:15:00+00:00",
        absolute_expires_at="2099-01-01T08:00:00+00:00",
        mfa_code=_code(FIXED_TIME),
        login_identity=owner,
        client_signal="rollback-test",
    )
    assert repo.create_after_mfa(session_id="first", **common) == "created"
    assert _accepted_step(owner) == FIXED_TIME // 30

    monkeypatch.setattr(mfa.time, "time", lambda: FIXED_TIME + 30)
    common["mfa_code"] = _code(FIXED_TIME + 30)
    with pytest.raises(sqlite3.IntegrityError):
        repo.create_after_mfa(session_id="second", **common)

    assert _accepted_step(owner) == FIXED_TIME // 30
    assert len(_sessions(owner)) == 1
