"""Transactional Admin V2 audit and idempotency foundation contracts."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import json
import sqlite3
import threading
import time
from uuid import uuid4

import pytest

from admin_v2.errors import AdminError
from admin_v2.repository import (
    AdminMutationRepository,
    StoredResponse,
    fingerprint_request,
)
from database import db


@pytest.fixture
def mutation_repository() -> AdminMutationRepository:
    conn = db.connect()
    try:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS admin_v2_test_effects (
                   id TEXT PRIMARY KEY,
                   value TEXT NOT NULL
               )"""
        )
        conn.execute("DELETE FROM admin_v2_test_effects")
        conn.execute("DELETE FROM admin_idempotency_records")
        conn.commit()
    finally:
        conn.close()
    yield AdminMutationRepository(db)
    conn = db.connect()
    try:
        conn.execute("DELETE FROM admin_v2_test_effects")
        conn.execute("DELETE FROM admin_idempotency_records")
        conn.commit()
    finally:
        conn.close()


def _execute(
    repository: AdminMutationRepository,
    *,
    effect_id: str,
    key: str,
    request_value: str = "alpha",
    metadata: dict | None = None,
    callback=None,
):
    def default_callback(conn: sqlite3.Connection) -> StoredResponse:
        conn.execute(
            "INSERT INTO admin_v2_test_effects (id, value) VALUES (?, ?)",
            (effect_id, request_value),
        )
        return StoredResponse(
            status_code=201,
            body={"effectId": effect_id, "value": request_value},
            headers={"Location": f"/effects/{effect_id}", "ETag": '"v1"'},
        )

    return repository.execute_idempotent(
        owner_id="owner-001",
        route="POST /api/admin/v2/high-risk-test",
        idempotency_key=key,
        request_fingerprint=fingerprint_request(
            {"effectId": effect_id, "value": request_value}
        ),
        request_id=f"req-{effect_id}",
        actor={"id": "owner-001", "role": "owner"},
        target={"type": "testEffect", "id": effect_id},
        action="testEffect.create",
        outcome="succeeded",
        metadata=metadata or {"value": request_value},
        mutation=callback or default_callback,
    )


def test_mutation_audit_and_idempotency_commit_in_one_transaction(
    mutation_repository: AdminMutationRepository,
) -> None:
    effect_id = f"effect-{uuid4()}"
    result = _execute(
        mutation_repository,
        effect_id=effect_id,
        key="key-commit",
        metadata={
            "safe": "kept",
            "nested": {"password": "password-never-persist"},
            "authorization": "Bearer token-never-persist",
        },
    )

    assert result.replayed is False
    assert result.response.status_code == 201
    event = mutation_repository.get_audit_event(result.audit_event_id)
    assert event is not None
    assert event.request_id == f"req-{effect_id}"
    assert event.actor == {"id": "owner-001", "role": "owner"}
    assert event.target == {"type": "testEffect", "id": effect_id}
    assert event.action == "testEffect.create"
    assert event.outcome == "succeeded"
    assert event.metadata == {
        "safe": "kept",
        "nested": {"password": "[REDACTED]"},
        "authorization": "[REDACTED]",
    }
    assert datetime.fromisoformat(event.timestamp).tzinfo is not None

    raw = db.connect()
    try:
        persisted = "\n".join(
            str(value)
            for table in ("admin_audit_events", "admin_idempotency_records")
            for row in raw.execute(f'SELECT * FROM "{table}"')
            for value in row
            if value is not None
        )
    finally:
        raw.close()
    assert "password-never-persist" not in persisted
    assert "token-never-persist" not in persisted
    assert "key-commit" not in persisted


def test_failed_mutation_rolls_back_effect_audit_and_idempotency(
    mutation_repository: AdminMutationRepository,
) -> None:
    effect_id = f"effect-{uuid4()}"

    def fail_after_effect(conn: sqlite3.Connection) -> StoredResponse:
        conn.execute(
            "INSERT INTO admin_v2_test_effects (id, value) VALUES (?, 'partial')",
            (effect_id,),
        )
        raise RuntimeError("forced failure")

    with pytest.raises(RuntimeError, match="forced failure"):
        _execute(
            mutation_repository,
            effect_id=effect_id,
            key="key-rollback",
            callback=fail_after_effect,
        )

    conn = db.connect()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_v2_test_effects WHERE id=?", (effect_id,)
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE request_id=?",
            (f"req-{effect_id}",),
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_idempotency_records"
        ).fetchone()[0] == 0
    finally:
        conn.close()


def test_replay_returns_exact_status_body_and_headers_without_second_effect(
    mutation_repository: AdminMutationRepository,
) -> None:
    effect_id = f"effect-{uuid4()}"
    first = _execute(mutation_repository, effect_id=effect_id, key="key-replay")
    second = _execute(mutation_repository, effect_id=effect_id, key="key-replay")

    assert first.replayed is False
    assert second.replayed is True
    assert second.audit_event_id == first.audit_event_id
    assert second.response == first.response
    conn = db.connect()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_v2_test_effects WHERE id=?", (effect_id,)
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE request_id=?",
            (f"req-{effect_id}",),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT state FROM admin_idempotency_records"
        ).fetchone()[0] == "completed"
    finally:
        conn.close()


def test_same_owner_route_key_with_different_request_has_stable_conflict(
    mutation_repository: AdminMutationRepository,
) -> None:
    effect_id = f"effect-{uuid4()}"
    _execute(mutation_repository, effect_id=effect_id, key="key-conflict")

    with pytest.raises(AdminError) as raised:
        _execute(
            mutation_repository,
            effect_id=effect_id,
            key="key-conflict",
            request_value="different",
        )

    error = raised.value
    assert error.status_code == 409
    assert error.code == "ADMIN_IDEMPOTENCY_CONFLICT"
    assert error.message == "Idempotency key was already used for a different request"


def test_idempotency_scope_includes_owner_and_route(
    mutation_repository: AdminMutationRepository,
) -> None:
    first_id = f"effect-{uuid4()}"
    second_id = f"effect-{uuid4()}"
    _execute(mutation_repository, effect_id=first_id, key="shared-key")

    def second_callback(conn: sqlite3.Connection) -> StoredResponse:
        conn.execute(
            "INSERT INTO admin_v2_test_effects (id, value) VALUES (?, 'second')",
            (second_id,),
        )
        return StoredResponse(202, {"effectId": second_id}, {"X-Mode": "other"})

    second = mutation_repository.execute_idempotent(
        owner_id="owner-002",
        route="POST /api/admin/v2/other-high-risk-test",
        idempotency_key="shared-key",
        request_fingerprint=fingerprint_request({"effectId": second_id}),
        request_id="req-second",
        actor={"id": "owner-002"},
        target={"type": "testEffect", "id": second_id},
        action="testEffect.other",
        outcome="succeeded",
        metadata={},
        mutation=second_callback,
    )
    assert second.replayed is False


def test_concurrent_duplicates_produce_one_effect_and_one_exact_replay(
    mutation_repository: AdminMutationRepository,
) -> None:
    effect_id = f"effect-{uuid4()}"
    entered = threading.Event()
    release = threading.Event()
    callback_count = 0
    callback_lock = threading.Lock()

    def slow_callback(conn: sqlite3.Connection) -> StoredResponse:
        nonlocal callback_count
        with callback_lock:
            callback_count += 1
        conn.execute(
            "INSERT INTO admin_v2_test_effects (id, value) VALUES (?, 'once')",
            (effect_id,),
        )
        entered.set()
        assert release.wait(timeout=5)
        return StoredResponse(202, {"effectId": effect_id}, {"X-Result": "stable"})

    def invoke():
        return _execute(
            mutation_repository,
            effect_id=effect_id,
            key="key-concurrent",
            callback=slow_callback,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        first_future = pool.submit(invoke)
        assert entered.wait(timeout=5)
        second_future = pool.submit(invoke)
        time.sleep(0.05)
        release.set()
        results = [first_future.result(timeout=5), second_future.result(timeout=5)]

    assert callback_count == 1
    assert sorted(result.replayed for result in results) == [False, True]
    assert results[0].response == results[1].response


def test_expired_record_is_replaced_with_a_new_effect(
    mutation_repository: AdminMutationRepository,
) -> None:
    first_id = f"effect-{uuid4()}"
    first = _execute(mutation_repository, effect_id=first_id, key="key-expiry")
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE admin_idempotency_records SET expires_at=?",
            ((datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()

    second_id = f"effect-{uuid4()}"
    second = _execute(mutation_repository, effect_id=second_id, key="key-expiry")
    assert first.replayed is False
    assert second.replayed is False
    assert first.audit_event_id != second.audit_event_id


def test_audit_events_are_database_immutable(
    mutation_repository: AdminMutationRepository,
) -> None:
    result = _execute(
        mutation_repository,
        effect_id=f"effect-{uuid4()}",
        key="key-immutable",
    )
    conn = db.connect()
    try:
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                "UPDATE admin_audit_events SET action='tampered' WHERE id=?",
                (result.audit_event_id,),
            )
        conn.rollback()
        with pytest.raises(sqlite3.IntegrityError, match="immutable"):
            conn.execute(
                "DELETE FROM admin_audit_events WHERE id=?", (result.audit_event_id,)
            )
    finally:
        conn.rollback()
        conn.close()
