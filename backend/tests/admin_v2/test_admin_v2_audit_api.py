"""Complete contracts for the owner-only Admin V2 audit-events read API."""

from __future__ import annotations

import json
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from admin_v2.audit_routes import router as audit_router
from admin_v2.dependencies import require_admin_session
from admin_v2.errors import AdminError, error_envelope
from database import db


EVENT_IDS = ["audit-api-001", "audit-api-002", "audit-api-003", "audit-api-004"]


def _error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID") or "req-audit-test"
    return JSONResponse(
        status_code=status,
        content=error_envelope(code, message, request_id),
        headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


@pytest.fixture
def audit_app() -> FastAPI:
    app = FastAPI()
    app.include_router(audit_router, prefix="/api/admin/v2")

    @app.exception_handler(AdminError)
    async def handle_admin_error(request: Request, exc: AdminError):
        return _error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        return _error_response(
            request, 400, "ADMIN_VALIDATION_ERROR", "Request validation failed"
        )

    return app


@pytest.fixture
def seeded_events():
    rows = [
        (
            EVENT_IDS[0],
            "req-001",
            {"id": "owner-a", "role": "owner"},
            {"type": "user", "id": "user-1"},
            "user.suspend",
            "succeeded",
            {"reason": "policy", "password": "legacy-secret"},
            "2026-07-28T09:00:00+00:00",
        ),
        (
            EVENT_IDS[1],
            "req-002",
            {"id": "owner-b", "role": "owner"},
            {"type": "organization", "id": "org-1"},
            "organization.update",
            "failed",
            {"note": "Needle Alpha", "nested": {"authorization": "Bearer hidden"}},
            "2026-07-28T10:00:00+00:00",
        ),
        (
            EVENT_IDS[2],
            "req-003",
            {"id": "owner-a", "role": "owner"},
            {"type": "user", "id": "user-2"},
            "user.reactivate",
            "succeeded",
            {"note": "Needle Beta", "tokenCount": 2},
            "2026-07-28T10:00:00+00:00",
        ),
        (
            EVENT_IDS[3],
            "req-004",
            {"id": "owner-a", "role": "owner"},
            {"type": "user", "id": "user-3"},
            "user.suspend",
            "succeeded",
            {"note": "last"},
            "2026-07-28T11:00:00+00:00",
        ),
    ]
    conn = db.connect()
    try:
        conn.executemany(
            """INSERT INTO admin_audit_events
                   (id, request_id, actor_json, target_json, action, outcome,
                    metadata_json, occurred_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    event_id,
                    request_id,
                    json.dumps(actor),
                    json.dumps(target),
                    action,
                    outcome,
                    json.dumps(metadata),
                    occurred_at,
                )
                for (
                    event_id,
                    request_id,
                    actor,
                    target,
                    action,
                    outcome,
                    metadata,
                    occurred_at,
                ) in rows
            ],
        )
        conn.commit()
    finally:
        conn.close()
    yield rows
    conn = db.connect()
    try:
        placeholders = ",".join("?" for _ in EVENT_IDS)
        conn.execute(
            f"DELETE FROM admin_idempotency_records WHERE audit_event_id IN ({placeholders})",
            EVENT_IDS,
        )
        # The production immutability trigger intentionally prevents cleanup.
        # Test rows live only in pytest's temporary migrated database.
        conn.commit()
    finally:
        conn.close()


def _authorized_client(app: FastAPI) -> TestClient:
    app.dependency_overrides[require_admin_session] = lambda: object()
    return TestClient(app)


def _assert_error(response, status: int, code: str) -> dict[str, Any]:
    assert response.status_code == status, response.text
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "requestId", "fieldErrors"}
    assert body["error"]["code"] == code
    assert body["error"]["requestId"] == response.headers["x-request-id"]
    assert body["error"]["fieldErrors"] == []
    assert response.headers["cache-control"] == "no-store"
    return body


def test_list_and_detail_require_an_owner_session(audit_app: FastAPI) -> None:
    with TestClient(audit_app) as client:
        _assert_error(
            client.get("/api/admin/v2/audit-events"), 401, "ADMIN_AUTH_REQUIRED"
        )
        _assert_error(
            client.get("/api/admin/v2/audit-events/unknown"),
            401,
            "ADMIN_AUTH_REQUIRED",
        )


def test_list_has_typed_camel_case_envelope_and_read_time_redaction(
    audit_app: FastAPI, seeded_events
) -> None:
    with _authorized_client(audit_app) as client:
        response = client.get("/api/admin/v2/audit-events")
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body) == {"items", "page"}
    assert body["page"] == {"limit": 50, "hasMore": False, "nextCursor": None}
    assert [item["eventId"] for item in body["items"]][:4] == list(reversed(EVENT_IDS))
    event = next(item for item in body["items"] if item["eventId"] == EVENT_IDS[0])
    assert set(event) == {
        "eventId", "requestId", "actor", "target", "action", "outcome",
        "metadata", "occurredAt",
    }
    assert event["metadata"] == {"reason": "policy", "password": "[REDACTED]"}
    assert "legacy-secret" not in response.text
    assert "Bearer hidden" not in response.text
    assert "occurred_at" not in response.text


def test_detail_is_typed_redacted_and_does_not_mutate_persisted_metadata(
    audit_app: FastAPI, seeded_events
) -> None:
    with _authorized_client(audit_app) as client:
        first = client.get(f"/api/admin/v2/audit-events/{EVENT_IDS[1]}")
        second = client.get(f"/api/admin/v2/audit-events/{EVENT_IDS[1]}")
    assert first.status_code == 200
    assert first.json() == second.json()
    assert set(first.json()) == {"auditEvent"}
    event = first.json()["auditEvent"]
    assert event["metadata"]["nested"]["authorization"] == "[REDACTED]"

    conn = db.connect()
    try:
        persisted = conn.execute(
            "SELECT metadata_json FROM admin_audit_events WHERE id=?", (EVENT_IDS[1],)
        ).fetchone()[0]
    finally:
        conn.close()
    assert "Bearer hidden" in persisted


def test_bounded_filters_search_time_range_and_sort(
    audit_app: FastAPI, seeded_events
) -> None:
    params = {
        "actorId": "owner-a",
        "targetType": "user",
        "outcome": "succeeded",
        "search": "needle",
        "occurredFrom": "2026-07-28T09:30:00Z",
        "occurredTo": "2026-07-28T10:30:00Z",
        "sort": "action",
        "sortDirection": "asc",
    }
    with _authorized_client(audit_app) as client:
        response = client.get("/api/admin/v2/audit-events", params=params)
    assert response.status_code == 200, response.text
    assert [item["eventId"] for item in response.json()["items"]] == [EVENT_IDS[2]]

    with _authorized_client(audit_app) as client:
        target = client.get(
            "/api/admin/v2/audit-events",
            params={"targetId": "org-1", "action": "organization.update"},
        )
    assert [item["eventId"] for item in target.json()["items"]] == [EVENT_IDS[1]]


def test_cursor_pagination_is_stable_with_tied_sort_values(
    audit_app: FastAPI, seeded_events
) -> None:
    seen: list[str] = []
    cursor = None
    with _authorized_client(audit_app) as client:
        for expected_has_more in (True, False):
            params = {"limit": 2, "sort": "occurredAt", "sortDirection": "desc"}
            if cursor:
                params["cursor"] = cursor
            response = client.get("/api/admin/v2/audit-events", params=params)
            assert response.status_code == 200, response.text
            page = response.json()
            seen.extend(item["eventId"] for item in page["items"])
            assert page["page"]["hasMore"] is expected_has_more
            cursor = page["page"]["nextCursor"]
    assert seen == [EVENT_IDS[3], EVENT_IDS[2], EVENT_IDS[1], EVENT_IDS[0]]
    assert len(seen) == len(set(seen))
    assert cursor is None


def test_cursor_is_rejected_when_malformed_or_reused_with_changed_query(
    audit_app: FastAPI, seeded_events
) -> None:
    with _authorized_client(audit_app) as client:
        malformed = client.get("/api/admin/v2/audit-events", params={"cursor": "not-a-cursor"})
        _assert_error(malformed, 400, "ADMIN_AUDIT_CURSOR_INVALID")

        first = client.get(
            "/api/admin/v2/audit-events", params={"limit": 1, "action": "user.suspend"}
        )
        cursor = first.json()["page"]["nextCursor"]
        changed = client.get(
            "/api/admin/v2/audit-events",
            params={"limit": 1, "action": "user.reactivate", "cursor": cursor},
        )
        _assert_error(changed, 400, "ADMIN_AUDIT_CURSOR_INVALID")


def test_query_bounds_and_inverted_time_range_have_stable_errors(
    audit_app: FastAPI, seeded_events
) -> None:
    with _authorized_client(audit_app) as client:
        _assert_error(
            client.get("/api/admin/v2/audit-events", params={"limit": 101}),
            400,
            "ADMIN_VALIDATION_ERROR",
        )
        _assert_error(
            client.get("/api/admin/v2/audit-events", params={"search": "x" * 201}),
            400,
            "ADMIN_VALIDATION_ERROR",
        )
        _assert_error(
            client.get(
                "/api/admin/v2/audit-events",
                params={
                    "occurredFrom": "2026-07-29T00:00:00Z",
                    "occurredTo": "2026-07-28T00:00:00Z",
                },
            ),
            400,
            "ADMIN_AUDIT_TIME_RANGE_INVALID",
        )


def test_missing_event_has_stable_non_enumerating_error(
    audit_app: FastAPI, seeded_events
) -> None:
    with _authorized_client(audit_app) as client:
        response = client.get("/api/admin/v2/audit-events/audit-does-not-exist")
    body = _assert_error(response, 404, "ADMIN_AUDIT_EVENT_NOT_FOUND")
    assert body["error"]["message"] == "Audit event not found"
    assert "audit-does-not-exist" not in response.text


def test_read_lane_preserves_database_immutability(
    audit_app: FastAPI, seeded_events
) -> None:
    conn = db.connect()
    try:
        before = [tuple(row) for row in conn.execute(
            "SELECT * FROM admin_audit_events WHERE id IN (?, ?, ?, ?) ORDER BY id",
            EVENT_IDS,
        )]
    finally:
        conn.close()

    with _authorized_client(audit_app) as client:
        assert client.get("/api/admin/v2/audit-events").status_code == 200
        assert client.get(f"/api/admin/v2/audit-events/{EVENT_IDS[0]}").status_code == 200

    conn = db.connect()
    try:
        after = [tuple(row) for row in conn.execute(
            "SELECT * FROM admin_audit_events WHERE id IN (?, ?, ?, ?) ORDER BY id",
            EVENT_IDS,
        )]
    finally:
        conn.close()
    assert after == before
