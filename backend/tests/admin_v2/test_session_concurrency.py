"""Deterministic adversarial session/CSRF concurrency contracts for Admin V2."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import threading
import uuid

import pytest
from fastapi.testclient import TestClient

from admin_v2.errors import AdminError
from admin_v2.repository import AdminSessionRepository
from admin_v2.service import IDLE_TIMEOUT, auth_service
from database import Database, db
from main import app
from security import hash_password

PASSWORD = "AdminV2-Concurrency-Test!"
SESSION_PATH = "/api/admin/v2/auth/session"
LOGOUT_PATH = "/api/admin/v2/auth/logout"
COOKIE = "practenture_admin_v2_session"
TIMEOUT = 5


def _result(future: Future):
    return future.result(timeout=TIMEOUT)


def _assert_error(response, allowed: set[tuple[int, str]]) -> None:
    assert response.status_code != 500, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "requestId", "fieldErrors"}
    assert (response.status_code, body["error"]["code"]) in allowed
    assert body["error"]["requestId"]
    assert response.headers["x-request-id"] == body["error"]["requestId"]
    assert body["error"]["fieldErrors"] == []


@pytest.fixture
def owner(monkeypatch: pytest.MonkeyPatch):
    username = f"session-race-{uuid.uuid4().hex}"
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    db.create_user(username, hash_password(PASSWORD), "owner", "Session Race Owner")
    yield username
    with db._lock:
        conn = db._get_conn()
        conn.execute("DELETE FROM admin_sessions WHERE owner_user_id=?", (username,))
        conn.execute("DELETE FROM privileged_login_attempts WHERE identity_key=?", (username,))
        conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (username,))
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()


def _login(owner: str) -> tuple[str, str]:
    _, token, csrf = auth_service.login(
        owner, PASSWORD, mfa_code=None, client_signal=f"race-{owner}"
    )
    return token, csrf


def _client_for(token: str) -> TestClient:
    client = TestClient(app, base_url="http://testserver", raise_server_exceptions=False)
    client.cookies.set(COOKIE, token, domain="testserver.local", path="/api/admin/v2")
    return client


def test_two_concurrent_session_gets_share_a_still_usable_nonrotating_csrf(owner):
    token, original_csrf = _login(owner)
    barrier = threading.Barrier(2, timeout=TIMEOUT)

    def get_session():
        with _client_for(token) as client:
            barrier.wait()
            return client.get(SESSION_PATH)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(get_session) for _ in range(2)]
        responses = [_result(future) for future in futures]

    assert [response.status_code for response in responses] == [200, 200]
    tokens = [response.json()["session"]["csrfToken"] for response in responses]
    assert tokens == [original_csrf, original_csrf]
    # A later request with the same cookie proves neither GET destructively rotated state.
    with _client_for(token) as client:
        later = client.get(SESSION_PATH)
    assert later.status_code == 200, later.text
    assert later.json()["session"]["csrfToken"] == original_csrf


def test_concurrent_authenticate_and_logout_have_only_controlled_outcomes(owner):
    token, csrf = _login(owner)
    barrier = threading.Barrier(2, timeout=TIMEOUT)

    def authenticate():
        with _client_for(token) as client:
            barrier.wait()
            return client.get(SESSION_PATH)

    def logout():
        with _client_for(token) as client:
            barrier.wait()
            return client.post(LOGOUT_PATH, headers={"X-CSRF-Token": csrf})

    with ThreadPoolExecutor(max_workers=2) as pool:
        auth_response, logout_response = map(
            _result, (pool.submit(authenticate), pool.submit(logout))
        )

    for response in (auth_response, logout_response):
        assert response.status_code in {200, 204, 401, 403}, response.text
        if response.status_code in {401, 403}:
            _assert_error(
                response,
                {
                    (401, "ADMIN_AUTH_REQUIRED"),
                    (401, "ADMIN_SESSION_EXPIRED"),
                    (403, "ADMIN_CSRF_INVALID"),
                },
            )
    if auth_response.status_code == 200:
        assert auth_response.json()["session"]["userId"] == owner
        assert auth_response.json()["session"]["csrfToken"] == csrf
    assert logout_response.status_code == 204, logout_response.text
    with _client_for(token) as client:
        _assert_error(client.get(SESSION_PATH), {(401, "ADMIN_AUTH_REQUIRED")})


def test_two_concurrent_logout_attempts_yield_one_success_and_one_auth_required(owner):
    token, csrf = _login(owner)
    barrier = threading.Barrier(2, timeout=TIMEOUT)

    def logout():
        with _client_for(token) as client:
            barrier.wait()
            return client.post(LOGOUT_PATH, headers={"X-CSRF-Token": csrf})

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(logout) for _ in range(2)]
        responses = [_result(future) for future in futures]

    assert sorted(response.status_code for response in responses) == [204, 401]
    denied = next(response for response in responses if response.status_code == 401)
    _assert_error(denied, {(401, "ADMIN_AUTH_REQUIRED")})


def test_touch_active_is_atomic_across_independent_database_connections(owner):
    token, _ = _login(owner)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    databases = [Database(), Database()]
    repositories = [AdminSessionRepository(database) for database in databases]
    barrier = threading.Barrier(2, timeout=TIMEOUT)
    now = datetime.now(timezone.utc)

    def touch(repo: AdminSessionRepository, offset: int):
        barrier.wait()
        instant = now + timedelta(milliseconds=offset)
        return repo.touch_active(
            token_hash,
            now=instant,
            idle_expires_at=(instant + IDLE_TIMEOUT).isoformat(),
        )

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(touch, repo, index)
                for index, repo in enumerate(repositories)
            ]
            results = [_result(future) for future in futures]
        assert all(state == "active" and record is not None for record, state in results)
        with db._lock:
            persisted = db._get_conn().execute(
                "SELECT * FROM admin_sessions WHERE token_hash=?", (token_hash,)
            ).fetchone()
        assert persisted["revoked_at"] is None
        assert persisted["last_seen_at"] == max(record.last_seen_at for record, _ in results)
    finally:
        for database in databases:
            database._get_conn().close()


def test_expired_and_revoked_rows_never_return_active_and_only_idle_expiry_slides(owner):
    token, csrf = _login(owner)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    repository = AdminSessionRepository()
    before, state = repository.touch_active(
        token_hash,
        now=datetime.now(timezone.utc),
        idle_expires_at=(datetime.now(timezone.utc) + IDLE_TIMEOUT).isoformat(),
    )
    assert state == "active" and before is not None

    later = datetime.now(timezone.utc) + timedelta(seconds=2)
    after, state = repository.touch_active(
        token_hash, now=later, idle_expires_at=(later + IDLE_TIMEOUT).isoformat()
    )
    assert state == "active" and after is not None
    assert after.absolute_expires_at == before.absolute_expires_at
    assert after.idle_expires_at > before.idle_expires_at
    assert after.csrf_token_hash == hashlib.sha256(csrf.encode()).hexdigest()

    assert repository.revoke(token_hash, later.isoformat(), "test_revoke")
    record, state = repository.touch_active(
        token_hash, now=later, idle_expires_at=(later + IDLE_TIMEOUT).isoformat()
    )
    assert record is None and state == "missing"

    expired_token, _ = _login(owner)
    expired_hash = hashlib.sha256(expired_token.encode()).hexdigest()
    expired = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    with db._lock:
        conn = db._get_conn()
        conn.execute(
            "UPDATE admin_sessions SET idle_expires_at=? WHERE token_hash=?",
            (expired, expired_hash),
        )
        conn.commit()
    record, state = repository.touch_active(
        expired_hash,
        now=datetime.now(timezone.utc),
        idle_expires_at=(datetime.now(timezone.utc) + IDLE_TIMEOUT).isoformat(),
    )
    assert record is None and state == "expired"
