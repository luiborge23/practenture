"""Deterministic multi-session contracts for Admin V2 login rotation."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import threading
import uuid

import pytest
from fastapi.testclient import TestClient

from admin_v2.service import COOKIE_NAME, COOKIE_PATH, auth_service
from database import db
from main import app
from security import hash_password


PASSWORD = "ConcurrentOwner123!"
TIMEOUT = 5


@pytest.fixture
def owner(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    username = f"concurrent-owner-{uuid.uuid4().hex}"
    assert db.create_user(username, hash_password(PASSWORD), "owner", "Concurrent Owner")
    # The accepted pre-cutover contract permits MFA-disabled unique owners in
    # this race slice, keeping TOTP replay coupling out of session rotation.
    yield username
    with db._lock:
        conn = db._get_conn()
        conn.execute("DELETE FROM admin_sessions WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM privileged_login_attempts WHERE identity_key=?", (username.casefold(),))
        conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (username,))
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()


def _login(client: TestClient, username: str):
    return client.post(
        "/api/admin/v2/auth/login",
        json={"username": username, "password": PASSWORD},
    )


def _token(response) -> str:
    token = response.cookies.get(COOKIE_NAME)
    assert token
    return token


def _set_token(client: TestClient, token: str) -> None:
    client.cookies.set(
        COOKIE_NAME,
        token,
        domain="testserver.local",
        path=COOKIE_PATH,
    )


def _barrier_session_creation(monkeypatch: pytest.MonkeyPatch) -> None:
    """Force both requests past credential verification before either insert."""
    barrier = threading.Barrier(2, timeout=TIMEOUT)
    original = auth_service.repository.create_after_mfa

    def synchronized_create(**kwargs):
        barrier.wait()
        return original(**kwargs)

    monkeypatch.setattr(auth_service.repository, "create_after_mfa", synchronized_create)


def test_concurrent_independent_logins_return_two_still_valid_sessions(
    owner: str, monkeypatch: pytest.MonkeyPatch
):
    _barrier_session_creation(monkeypatch)
    with (
        TestClient(app, base_url="http://testserver") as first,
        TestClient(app, base_url="http://testserver") as second,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        futures = [pool.submit(_login, client, owner) for client in (first, second)]
        responses = [future.result(timeout=TIMEOUT) for future in futures]
        assert [response.status_code for response in responses] == [200, 200]
        tokens = [_token(response) for response in responses]
        assert tokens[0] != tokens[1]
        _set_token(first, tokens[0])
        _set_token(second, tokens[1])
        assert first.get("/api/admin/v2/auth/session").status_code == 200
        assert second.get("/api/admin/v2/auth/session").status_code == 200


def test_concurrent_rotation_of_one_old_cookie_keeps_both_fresh_sessions_valid(
    owner: str, monkeypatch: pytest.MonkeyPatch
):
    with TestClient(app, base_url="http://testserver") as seed:
        old_response = _login(seed, owner)
        assert old_response.status_code == 200
        old_token = _token(old_response)

    _barrier_session_creation(monkeypatch)
    with (
        TestClient(app, base_url="http://testserver") as first,
        TestClient(app, base_url="http://testserver") as second,
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        _set_token(first, old_token)
        _set_token(second, old_token)
        responses = [
            future.result(timeout=TIMEOUT)
            for future in [pool.submit(_login, first, owner), pool.submit(_login, second, owner)]
        ]
        assert [response.status_code for response in responses] == [200, 200]
        fresh = [_token(response) for response in responses]
        assert len(set(fresh)) == 2
        _set_token(first, fresh[0])
        _set_token(second, fresh[1])
        assert first.get("/api/admin/v2/auth/session").status_code == 200
        assert second.get("/api/admin/v2/auth/session").status_code == 200

    with TestClient(app, base_url="http://testserver") as old_client:
        _set_token(old_client, old_token)
        assert old_client.get("/api/admin/v2/auth/session").status_code == 401


def test_sequential_same_client_rotation_revokes_only_its_old_token(owner: str):
    with TestClient(app, base_url="http://testserver") as client:
        first = _login(client, owner)
        old_token = _token(first)
        second = _login(client, owner)
        fresh_token = _token(second)
        assert first.status_code == second.status_code == 200
        assert fresh_token != old_token
        assert client.get("/api/admin/v2/auth/session").status_code == 200

    with TestClient(app, base_url="http://testserver") as old_client:
        _set_token(old_client, old_token)
        assert old_client.get("/api/admin/v2/auth/session").status_code == 401


def test_fixed_or_foreign_cookie_is_never_adopted_or_used_to_revoke(owner: str):
    other = f"unrelated-owner-{uuid.uuid4().hex}"
    assert db.create_user(other, hash_password(PASSWORD), "owner", "Unrelated Owner")
    try:
        with TestClient(app, base_url="http://testserver") as unrelated:
            unrelated_response = _login(unrelated, other)
            unrelated_token = _token(unrelated_response)

        with TestClient(app, base_url="http://testserver") as client:
            _set_token(client, "attacker-fixed-unrecognized-cookie")
            fixed_response = _login(client, owner)
            assert fixed_response.status_code == 200
            assert _token(fixed_response) != "attacker-fixed-unrecognized-cookie"

        with TestClient(app, base_url="http://testserver") as client:
            _set_token(client, unrelated_token)
            foreign_response = _login(client, owner)
            assert foreign_response.status_code == 200
            assert _token(foreign_response) != unrelated_token

        with TestClient(app, base_url="http://testserver") as unrelated:
            _set_token(unrelated, unrelated_token)
            assert unrelated.get("/api/admin/v2/auth/session").status_code == 200

        fixed_hash = hashlib.sha256(b"attacker-fixed-unrecognized-cookie").hexdigest()
        observer = db.connect()
        try:
            assert observer.execute(
                "SELECT 1 FROM admin_sessions WHERE token_hash=?", (fixed_hash,)
            ).fetchone() is None
        finally:
            observer.close()
    finally:
        with db._lock:
            conn = db._get_conn()
            conn.execute("DELETE FROM admin_sessions WHERE owner_user_id=?", (other,))
            conn.execute("DELETE FROM privileged_login_attempts WHERE identity_key=?", (other.casefold(),))
            conn.execute("DELETE FROM users WHERE username=?", (other,))
            conn.commit()