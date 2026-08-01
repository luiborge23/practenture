"""Adversarial contracts for atomic layered privileged-login throttling."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import threading

import pytest
from fastapi.testclient import TestClient

from admin_v2.repository import AdminSessionRepository
from admin_v2.routes import auth_service
from database import Database, db
from main import app


def reserve(
    repo: AdminSessionRepository,
    identity: str,
    client: str,
    *,
    now: float = 1_000.0,
    pair: int = 5,
    identity_limit: int = 20,
    client_limit: int = 50,
    window: int = 60,
):
    return repo.reserve_login_attempt(
        identity,
        client,
        now=now,
        threshold=pair,
        identity_threshold=identity_limit,
        client_threshold=client_limit,
        window_seconds=window,
    )


def bucket(scope_type: str, scope_key: str):
    with db._lock:
        return db._get_conn().execute(
            """SELECT attempt_count, window_started_at, locked_until, last_attempt_at
               FROM privileged_login_buckets
               WHERE scope_type=? AND scope_key=?""",
            (scope_type, scope_key),
        ).fetchone()


def test_rotating_clients_cannot_exceed_identity_wide_budget():
    repo = AdminSessionRepository(db)
    decisions = [
        reserve(repo, "DistributedOwner", f"192.0.2.{index}", identity_limit=4)
        for index in range(1, 6)
    ]

    assert [decision.allowed for decision in decisions] == [True, True, True, True, False]
    assert decisions[-1].retry_after == 60
    identity_row = bucket("identity", "distributedowner")
    assert identity_row["attempt_count"] == 4

    # No global lock: an unrelated principal from an unrelated source still proceeds.
    assert reserve(repo, "legitimate-owner", "198.51.100.40", identity_limit=4).allowed


def test_one_client_spraying_identities_hits_client_wide_budget():
    repo = AdminSessionRepository(db)
    decisions = [
        reserve(repo, f"guessed-owner-{index}", "203.0.113.9", client_limit=4)
        for index in range(1, 6)
    ]

    assert [decision.allowed for decision in decisions] == [True, True, True, True, False]
    assert decisions[-1].retry_after == 60
    assert bucket("client", "203.0.113.9")["attempt_count"] == 4
    assert reserve(repo, "other-owner", "203.0.113.10", client_limit=4).allowed


def test_pair_budget_remains_the_tightest_default_dimension():
    repo = AdminSessionRepository(db)
    first = reserve(repo, "pair-owner", "192.0.2.10", pair=2)
    second = reserve(repo, "pair-owner", "192.0.2.10", pair=2, now=1_001.0)
    blocked = reserve(repo, "pair-owner", "192.0.2.10", pair=2, now=1_002.0)

    assert first.allowed and second.allowed
    assert not blocked.allowed
    assert blocked.retry_after == 59


def test_case_and_ip_forms_share_normalized_buckets():
    repo = AdminSessionRepository(db)
    assert reserve(
        repo,
        "  CaseOwner  ",
        "2001:0DB8:0:0:0:0:0:1",
        pair=2,
    ).allowed
    assert reserve(
        repo,
        "caseowner",
        "2001:db8::1",
        pair=2,
        now=1_001.0,
    ).allowed
    blocked = reserve(
        repo,
        "CASEOWNER",
        "2001:DB8::1",
        pair=2,
        now=1_002.0,
    )

    assert not blocked.allowed
    assert bucket("identity", "caseowner")["attempt_count"] == 2
    assert bucket("client", "2001:db8::1")["attempt_count"] == 2


def test_longest_active_bucket_controls_retry_after_and_expiry_clock():
    repo = AdminSessionRepository(db)
    identity = "clock-owner"
    client = "192.0.2.70"
    pair_key = repo.pair_scope_key(identity, client)
    with db._lock:
        conn = db._get_conn()
        conn.executemany(
            """INSERT INTO privileged_login_buckets
                   (scope_type, scope_key, attempt_count, window_started_at,
                    locked_until, last_attempt_at)
               VALUES (?, ?, 5, 1000, ?, 1000)""",
            [
                ("pair", pair_key, 1_010.0),
                ("identity", identity, 1_025.0),
                ("client", client, 1_018.0),
            ],
        )
        conn.commit()

    blocked = reserve(repo, identity, client, now=1_005.2)
    assert not blocked.allowed
    assert blocked.retry_after == 20

    # Once the windows expire, all three scopes renew atomically.
    renewed = reserve(repo, identity, client, now=1_060.0)
    assert renewed.allowed
    assert bucket("identity", identity)["attempt_count"] == 1


def test_success_reset_only_removes_its_exact_reservations():
    repo = AdminSessionRepository(db)
    client = "198.51.100.77"
    first = reserve(repo, "successful-owner", client)
    reserve(repo, "successful-owner", client, now=1_001.0)
    reserve(repo, "unrelated-owner", client, now=1_002.0)
    successful_reservation = reserve(repo, "successful-owner", client, now=1_003.0)
    assert first.allowed and successful_reservation.allowed
    assert bucket("client", client)["attempt_count"] == 4

    with repo._transaction() as conn:
        repo.reset_login_attempt_in_transaction(
            conn,
            "SUCCESSFUL-OWNER",
            client,
            identity_window_started_at=(
                successful_reservation.identity_window_started_at
            ),
            pair_window_started_at=successful_reservation.pair_window_started_at,
            client_window_started_at=successful_reservation.client_window_started_at,
        )

    assert bucket("identity", "successful-owner")["attempt_count"] == 2
    assert bucket("identity", "unrelated-owner")["attempt_count"] == 1
    pair_key = repo.pair_scope_key(
        repo.normalize_identity("successful-owner"),
        repo.normalize_client_signal(client),
    )
    assert bucket("pair", pair_key)["attempt_count"] == 2
    assert bucket("client", client)["attempt_count"] == 3


def test_delayed_success_does_not_decrement_a_newer_window():
    repo = AdminSessionRepository(db)
    identity = "delayed-owner"
    client = "198.51.100.78"
    delayed = reserve(repo, identity, client, now=1_000.0)
    newer = reserve(repo, identity, client, now=1_060.0)
    assert delayed.allowed and newer.allowed

    with repo._transaction() as conn:
        repo.reset_login_attempt_in_transaction(
            conn,
            identity,
            client,
            identity_window_started_at=delayed.identity_window_started_at,
            pair_window_started_at=delayed.pair_window_started_at,
            client_window_started_at=delayed.client_window_started_at,
        )

    identity_key = repo.normalize_identity(identity)
    client_key = repo.normalize_client_signal(client)
    pair_key = repo.pair_scope_key(identity_key, client_key)
    assert bucket("identity", identity_key)["attempt_count"] == 1
    assert bucket("pair", pair_key)["attempt_count"] == 1
    assert bucket("client", client_key)["attempt_count"] == 1


def test_stale_expired_history_is_cleaned_during_reservation():
    repo = AdminSessionRepository(db)
    with db._lock:
        conn = db._get_conn()
        conn.execute(
            """INSERT INTO privileged_login_buckets
                   (scope_type, scope_key, attempt_count, window_started_at,
                    locked_until, last_attempt_at)
               VALUES ('identity', 'stale-owner', 2, 1, 2, 2)"""
        )
        conn.commit()

    assert reserve(repo, "fresh-owner", "192.0.2.90", now=100_000.0).allowed
    assert bucket("identity", "stale-owner") is None


def test_cross_repository_concurrency_cannot_oversubscribe_identity_budget():
    # Separate Database/Repository instances model separate workers and SQLite connections.
    worker_databases = [Database(), Database()]
    repositories = [AdminSessionRepository(item) for item in worker_databases]
    barrier = threading.Barrier(20)

    def attempt(index: int) -> bool:
        barrier.wait(timeout=5)
        return reserve(
            repositories[index % 2],
            "atomic-owner",
            f"198.18.0.{index + 1}",
            identity_limit=7,
            client_limit=100,
            pair=100,
        ).allowed

    try:
        with ThreadPoolExecutor(max_workers=20) as executor:
            results = list(executor.map(attempt, range(20)))
    finally:
        for item in worker_databases:
            if item._conn is not None:
                item._conn.close()
                item._conn = None

    assert sum(results) == 7
    assert bucket("identity", "atomic-owner")["attempt_count"] == 7


def test_429_envelope_integer_retry_after_and_forwarding_spoof_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("PRACTENTURE_ADMIN_COOKIE_SECURE", "false")
    monkeypatch.setattr(auth_service, "login_threshold", 2)
    monkeypatch.setattr(auth_service, "login_identity_threshold", 20)
    monkeypatch.setattr(auth_service, "login_client_threshold", 50)
    monkeypatch.setattr(auth_service, "login_window_seconds", 60)

    with TestClient(app, base_url="http://testserver") as client:
        payload = {"username": "spoof-target", "password": "wrong"}
        for spoof in ("192.0.2.1", "192.0.2.2"):
            response = client.post(
                "/api/admin/v2/auth/login",
                json=payload,
                headers={"X-Forwarded-For": spoof, "Forwarded": f"for={spoof}"},
            )
            assert response.status_code == 401
        response = client.post(
            "/api/admin/v2/auth/login",
            json=payload,
            headers={"X-Forwarded-For": "192.0.2.3", "X-Real-IP": "192.0.2.4"},
        )

    assert response.status_code == 429
    assert response.headers["retry-after"].isdecimal()
    assert int(response.headers["retry-after"]) >= 1
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "requestId", "fieldErrors"}
    assert body["error"]["code"] == "ADMIN_LOGIN_THROTTLED"
    assert body["error"]["fieldErrors"] == []
    assert bucket("client", "testclient")["attempt_count"] == 2
