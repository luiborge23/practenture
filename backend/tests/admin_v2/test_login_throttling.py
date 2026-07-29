"""Adversarial durability and boundary contracts for Admin V2 login throttling."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import sqlite3
import uuid
from typing import Any

import pytest
from fastapi.testclient import TestClient

from admin_v2.repository import AdminSessionRepository
from admin_v2.errors import AdminError
from admin_v2.service import auth_service
from database import Database, db
from main import app
from security import hash_password

PASSWORD = "AdminV2-Throttle-Test!"


@pytest.fixture
def identity():
    value = f"throttle-{uuid.uuid4().hex}"
    yield value
    with db._lock:
        conn = db._get_conn()
        conn.execute("DELETE FROM admin_sessions WHERE owner_user_id=?", (value,))
        conn.execute("DELETE FROM privileged_login_attempts WHERE identity_key=?", (value.casefold(),))
        identity_key = AdminSessionRepository.normalize_identity(value)
        conn.execute(
            """DELETE FROM privileged_login_buckets
               WHERE (scope_type='identity' AND scope_key=?)
                  OR scope_type='pair'""",
            (identity_key,),
        )
        conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (value,))
        conn.execute("DELETE FROM users WHERE username=?", (value,))
        conn.commit()


def row(identity: str, client: str):
    identity_key = AdminSessionRepository.normalize_identity(identity)
    client_key = AdminSessionRepository.normalize_client_signal(client)
    with db._lock:
        return db._get_conn().execute(
            """SELECT attempt_count, window_started_at, locked_until
               FROM privileged_login_buckets
               WHERE scope_type='pair' AND scope_key=?""",
            (AdminSessionRepository.pair_scope_key(identity_key, client_key),),
        ).fetchone()


def reserve(repo, identity, client, now, threshold=3, window=60):
    return repo.reserve_login_attempt(
        identity, client, now=now, threshold=threshold, window_seconds=window
    )


def test_normalized_identity_and_client_share_one_counter(identity):
    repo = AdminSessionRepository()
    assert reserve(repo, f"  {identity.upper()}  ", " 2001:0DB8:0:0::1 ", 100).allowed
    assert reserve(repo, identity, "2001:db8::1", 101).allowed
    assert row(identity, "2001:db8::1")["attempt_count"] == 2


def test_pairwise_client_signal_prevents_global_username_lock_and_window_expires(identity):
    repo = AdminSessionRepository()
    for now in (100, 101, 102):
        assert reserve(repo, identity, "192.0.2.10", now).allowed
    blocked = reserve(repo, identity, "192.0.2.10", 102.1)
    assert not blocked.allowed and blocked.retry_after == 60

    # The same identity from a distinct peer is not globally locked.
    assert reserve(repo, identity, "192.0.2.11", 103).allowed
    # The original pair decays after its fixed window/lock period.
    assert reserve(repo, identity, "192.0.2.10", 162).allowed
    refreshed = row(identity, "192.0.2.10")
    assert refreshed["attempt_count"] == 1
    assert refreshed["window_started_at"] == 162


def test_threshold_attempt_is_reserved_and_next_attempt_gets_integer_retry_after(identity):
    repo = AdminSessionRepository()
    assert reserve(repo, identity, "198.51.100.7", 10).allowed
    assert reserve(repo, identity, "198.51.100.7", 11).allowed
    assert reserve(repo, identity, "198.51.100.7", 12).allowed
    decision = reserve(repo, identity, "198.51.100.7", 12.25)
    assert decision.allowed is False
    assert decision.retry_after == 60
    assert isinstance(decision.retry_after, int)


def test_forwarding_headers_cannot_split_route_counter(identity, monkeypatch):
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    old_threshold, old_window = auth_service.login_threshold, auth_service.login_window_seconds
    auth_service.login_threshold, auth_service.login_window_seconds = 3, 60
    try:
        with TestClient(app, base_url="http://testserver") as client:
            responses = [
                client.post(
                    "/api/admin/v2/auth/login",
                    json={"username": identity, "password": "wrong"},
                    headers={
                        "X-Forwarded-For": f"203.0.113.{index}",
                        "Forwarded": f"for=203.0.113.{index}",
                    },
                )
                for index in range(1, 5)
            ]
    finally:
        auth_service.login_threshold, auth_service.login_window_seconds = old_threshold, old_window

    assert [response.status_code for response in responses] == [401, 401, 401, 429]
    assert responses[-1].json()["error"]["code"] == "ADMIN_LOGIN_THROTTLED"
    retry_after = responses[-1].headers["Retry-After"]
    assert retry_after.isdecimal() and int(retry_after) >= 1
    with db._lock:
        rows = db._get_conn().execute(
            """SELECT scope_key, attempt_count FROM privileged_login_buckets
               WHERE scope_type='client' AND scope_key=?""",
            ("testclient",),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["scope_key"] == "testclient"
    assert rows[0]["attempt_count"] == 3


def test_failed_password_and_failed_mfa_stay_counted_then_success_resets_pair(identity, monkeypatch):
    db.create_user(identity, hash_password(PASSWORD), "owner", "Throttle Owner")
    db.set_mfa_secret(identity, "JBSWY3DPEHPK3PXP")
    db.enable_mfa(identity, ["GOODBACKUP"])
    fixed = datetime.fromtimestamp(2_000_000_000, timezone.utc)
    monkeypatch.setattr(auth_service, "_now", lambda: fixed)
    signal = "198.51.100.42"

    with pytest.raises(AdminError) as wrong_password:
        auth_service.login(identity, "wrong", mfa_code=None, client_signal=signal)
    assert getattr(wrong_password.value, "code", None) == "ADMIN_INVALID_CREDENTIALS"
    with pytest.raises(AdminError) as wrong_mfa:
        auth_service.login(identity, PASSWORD, mfa_code="BAD", client_signal=signal)
    assert getattr(wrong_mfa.value, "code", None) == "ADMIN_INVALID_MFA"
    assert row(identity, signal)["attempt_count"] == 2

    session, _, _ = auth_service.login(
        identity, PASSWORD, mfa_code="GOODBACKUP", client_signal=signal
    )
    assert session.record.owner_user_id == identity
    assert row(identity, signal) is None


def test_separate_repository_and_database_instances_observe_durable_state(identity):
    first_db, second_db = Database(), Database()
    try:
        first, second = AdminSessionRepository(first_db), AdminSessionRepository(second_db)
        assert reserve(first, identity, "203.0.113.9", 100).allowed
        assert reserve(second, identity, "203.0.113.9", 101).allowed
        assert reserve(first, identity, "203.0.113.9", 102).allowed
        assert not reserve(second, identity, "203.0.113.9", 103).allowed
    finally:
        first_db._get_conn().close()
        second_db._get_conn().close()


def test_concurrent_reservations_across_independent_locks_never_exceed_threshold(identity):
    databases = [Database() for _ in range(8)]
    repositories = [AdminSessionRepository(database) for database in databases]
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            decisions = list(
                pool.map(
                    lambda item: reserve(item[1], identity, "192.0.2.99", 500, threshold=5),
                    enumerate(repositories),
                )
            )
        assert sum(decision.allowed for decision in decisions) == 5
        persisted = row(identity, "192.0.2.99")
        assert persisted["attempt_count"] == 5
    finally:
        for database in databases:
            database._get_conn().close()


def test_failed_session_transaction_rolls_back_and_does_not_clear_counter(identity):
    db.create_user(identity, hash_password(PASSWORD), "owner", "Rollback Owner")
    repo = AdminSessionRepository()
    signal = "203.0.113.55"
    assert reserve(repo, identity, signal, 700).allowed
    before = dict(row(identity, signal))

    common: dict[str, Any] = dict(
        token_hash="same-token-hash",
        csrf_hash="csrf-hash",
        user_id=identity,
        role="owner",
        created_at="2026-07-28T00:00:00+00:00",
        idle_expires_at="2026-07-28T00:15:00+00:00",
        absolute_expires_at="2026-07-28T08:00:00+00:00",
        mfa_code=None,
        login_identity=identity,
        client_signal=signal,
    )
    assert repo.create_after_mfa(session_id="existing", **common) == "created"
    assert reserve(repo, identity, signal, 701).allowed
    before_failure = dict(row(identity, signal))

    with pytest.raises(sqlite3.IntegrityError):
        repo.create_after_mfa(session_id="duplicate-token", **common)

    assert dict(row(identity, signal)) == before_failure
    with db._lock:
        count = db._get_conn().execute(
            "SELECT COUNT(*) FROM admin_sessions WHERE owner_user_id=?", (identity,)
        ).fetchone()[0]
    assert count == 1
    assert before["attempt_count"] == 1
