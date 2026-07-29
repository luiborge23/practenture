"""Focused contracts for the standalone Admin V2 audit export slice."""

from __future__ import annotations

import csv
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from admin_v2.audit_exports_routes import router
from admin_v2.dependencies import require_recent_auth_session
from admin_v2.errors import AdminError, error_envelope
from database import db


@pytest.fixture
def export_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "audit-exports"
    monkeypatch.setenv("PRACTENTURE_ADMIN_AUDIT_EXPORT_ROOT", str(root))
    return root


@pytest.fixture
def export_app() -> FastAPI:
    app = FastAPI()
    app.include_router(router, prefix="/api/admin/v2")

    @app.exception_handler(AdminError)
    async def handle_admin_error(request: Request, exc: AdminError):
        request_id = request.headers.get("X-Request-ID") or "req-audit-export-test"
        headers = {"X-Request-ID": request_id, "Cache-Control": "no-store"}
        headers.update(exc.headers)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(exc.code, exc.message, request_id),
            headers=headers,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(request: Request, exc: RequestValidationError):
        request_id = request.headers.get("X-Request-ID") or "req-audit-export-test"
        return JSONResponse(
            status_code=400,
            content=error_envelope(
                "ADMIN_VALIDATION_ERROR", "Request validation failed", request_id
            ),
            headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
        )

    return app


@pytest.fixture
def owner_client(export_app: FastAPI):
    session = SimpleNamespace(
        record=SimpleNamespace(owner_user_id="owner-export", role="owner")
    )
    export_app.dependency_overrides[require_recent_auth_session] = lambda: session
    with TestClient(export_app) as client:
        yield client


def _insert_event(
    *,
    event_id: str,
    action: str,
    actor_id: str = "owner-export",
    outcome: str = "succeeded",
    metadata: dict | None = None,
    occurred_at: str = "2026-07-28T10:00:00+00:00",
) -> None:
    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO admin_audit_events
               (id, request_id, actor_json, target_json, action, outcome,
                metadata_json, occurred_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event_id,
                f"req-{event_id}",
                json.dumps({"id": actor_id, "role": "owner"}),
                json.dumps({"type": "user", "id": "user-export"}),
                action,
                outcome,
                json.dumps(metadata or {}),
                occurred_at,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _post(client: TestClient, payload: dict, key: str, request_id: str = "req-export"):
    return client.post(
        "/api/admin/v2/audit-events/exports",
        json=payload,
        headers={"Idempotency-Key": key, "X-Request-ID": request_id},
    )


def _assert_error(response, status: int, code: str) -> None:
    assert response.status_code == status, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["requestId"] == response.headers["x-request-id"]
    assert response.headers["cache-control"] == "no-store"


def test_route_is_standalone_owner_recent_auth_mutation() -> None:
    routes = [route for route in router.routes if isinstance(route, APIRoute)]
    assert len(routes) == 1
    route = routes[0]
    assert route.path == "/audit-events/exports"
    assert route.methods == {"POST"}
    assert require_recent_auth_session in [d.call for d in route.dependant.dependencies]


def test_anonymous_request_is_denied_before_export(export_app: FastAPI, export_root: Path) -> None:
    with TestClient(export_app) as client:
        response = _post(client, {"format": "json"}, "anonymous")
    _assert_error(response, 401, "ADMIN_AUTH_REQUIRED")
    assert not export_root.exists()


def test_json_export_is_filtered_bounded_redacted_and_audited(
    owner_client: TestClient, export_root: Path
) -> None:
    marker = uuid4().hex
    included = f"export-json-{marker}"
    _insert_event(
        event_id=included,
        action=f"export.action.{marker}",
        metadata={
            "password": "raw-password",
            "nested": {"authorization": "Bearer hidden-token"},
            "safe": "visible",
        },
    )
    _insert_event(event_id=f"excluded-{marker}", action=f"other.action.{marker}")

    response = _post(
        owner_client,
        {
            "format": "json",
            "filters": {"action": f"export.action.{marker}", "outcome": "succeeded"},
        },
        f"json-{marker}",
        request_id=f"req-json-{marker}",
    )

    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == f"req-json-{marker}"
    body = response.json()
    assert body["status"] == "completed"
    assert body["format"] == "json"
    assert body["rowCount"] == 1
    assert body["fileName"].endswith(".json")
    assert body["artifactId"] in body["fileName"]
    assert body["expiresAt"] > body["createdAt"]
    assert "path" not in json.dumps(body).casefold()

    artifacts = list(export_root.iterdir())
    assert [path.name for path in artifacts] == [body["fileName"]]
    raw = artifacts[0].read_bytes()
    assert len(raw) == body["byteSize"]
    assert hashlib.sha256(raw).hexdigest() == body["sha256"]
    assert b"raw-password" not in raw
    assert b"hidden-token" not in raw
    document = json.loads(raw)
    assert [item["eventId"] for item in document["auditEvents"]] == [included]
    assert document["auditEvents"][0]["metadata"] == {
        "nested": {"authorization": "[REDACTED]"},
        "password": "[REDACTED]",
        "safe": "visible",
    }

    conn = db.connect()
    try:
        audit = conn.execute(
            """SELECT metadata_json FROM admin_audit_events
               WHERE action='admin.audit_export.created'
                 AND request_id=?""",
            (f"req-json-{marker}",),
        ).fetchone()
        stored_response = conn.execute(
            """SELECT response_body_json FROM admin_idempotency_records
               WHERE audit_event_id IN (
                   SELECT id FROM admin_audit_events WHERE request_id=?
               )""",
            (f"req-json-{marker}",),
        ).fetchone()
    finally:
        conn.close()
    assert audit is not None and stored_response is not None
    persisted = audit[0] + stored_response[0]
    assert "raw-password" not in persisted
    assert "hidden-token" not in persisted
    assert str(export_root) not in persisted


def test_csv_export_neutralizes_formula_cells(
    owner_client: TestClient, export_root: Path
) -> None:
    marker = uuid4().hex
    action = f"=HYPERLINK(\"https://invalid/{marker}\")"
    _insert_event(event_id=f"csv-{marker}", action=action)

    response = _post(
        owner_client,
        {"format": "csv", "filters": {"action": action}},
        f"csv-{marker}",
    )
    assert response.status_code == 201, response.text
    raw = (export_root / response.json()["fileName"]).read_text(encoding="utf-8")
    rows = list(csv.DictReader(io.StringIO(raw)))
    assert len(rows) == 1
    assert rows[0]["action"] == "'" + action
    assert not rows[0]["action"].startswith("=")


def test_idempotent_replay_returns_same_metadata_without_duplicate_file_or_audit(
    owner_client: TestClient, export_root: Path
) -> None:
    marker = uuid4().hex
    action = f"replay.action.{marker}"
    _insert_event(event_id=f"replay-{marker}", action=action)
    payload = {"format": "json", "filters": {"action": action}}

    first = _post(owner_client, payload, f"replay-{marker}", f"req-first-{marker}")
    replay = _post(owner_client, payload, f"replay-{marker}", f"req-second-{marker}")

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert replay.headers["idempotency-replayed"] == "true"
    assert first.headers["idempotency-replayed"] == "false"
    assert len(list(export_root.iterdir())) == 1
    conn = db.connect()
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE request_id=?",
            (f"req-first-{marker}",),
        ).fetchone()[0]
        replay_count = conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE request_id=?",
            (f"req-second-{marker}",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 1
    assert replay_count == 0

    conflict = _post(
        owner_client,
        {"format": "csv", "filters": {"action": action}},
        f"replay-{marker}",
    )
    _assert_error(conflict, 409, "ADMIN_IDEMPOTENCY_CONFLICT")
    assert len(list(export_root.iterdir())) == 1


def test_missing_key_invalid_format_and_unknown_filter_fail_closed(
    owner_client: TestClient, export_root: Path
) -> None:
    missing = owner_client.post(
        "/api/admin/v2/audit-events/exports", json={"format": "json"}
    )
    _assert_error(missing, 400, "ADMIN_IDEMPOTENCY_KEY_INVALID")
    invalid = _post(owner_client, {"format": "xml"}, "bad-format")
    _assert_error(invalid, 400, "ADMIN_VALIDATION_ERROR")
    unknown = _post(
        owner_client,
        {"format": "json", "filters": {"organizationId": "not-supported"}},
        "unknown-filter",
    )
    _assert_error(unknown, 400, "ADMIN_VALIDATION_ERROR")
    assert not export_root.exists()


def test_row_cap_rejects_without_partial_artifact_or_audit(
    owner_client: TestClient, export_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import admin_v2.audit_exports_service as service_module

    monkeypatch.setattr(service_module, "MAX_EXPORT_ROWS", 2)
    marker = uuid4().hex
    action = f"over-cap.{marker}"
    for index in range(3):
        _insert_event(event_id=f"cap-{marker}-{index}", action=action)

    response = _post(
        owner_client,
        {"format": "json", "filters": {"action": action}},
        f"cap-{marker}",
        request_id=f"req-cap-{marker}",
    )
    _assert_error(response, 413, "ADMIN_AUDIT_EXPORT_ROW_LIMIT")
    assert not export_root.exists() or list(export_root.iterdir()) == []
    conn = db.connect()
    try:
        audit_count = conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE request_id=?",
            (f"req-cap-{marker}",),
        ).fetchone()[0]
        key_count = conn.execute(
            """SELECT COUNT(*) FROM admin_idempotency_records
               WHERE audit_event_id IN (SELECT id FROM admin_audit_events WHERE request_id=?)""",
            (f"req-cap-{marker}",),
        ).fetchone()[0]
    finally:
        conn.close()
    assert audit_count == key_count == 0


def test_size_cap_rejects_before_writing_an_artifact(
    owner_client: TestClient, export_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import admin_v2.audit_exports_service as service_module

    monkeypatch.setattr(service_module, "MAX_EXPORT_BYTES", 80)
    marker = uuid4().hex
    action = f"size-cap.{marker}"
    _insert_event(
        event_id=f"size-{marker}",
        action=action,
        metadata={"safe": "x" * 200},
    )
    response = _post(
        owner_client,
        {"format": "json", "filters": {"action": action}},
        f"size-{marker}",
    )
    _assert_error(response, 413, "ADMIN_AUDIT_EXPORT_SIZE_LIMIT")
    assert not export_root.exists() or list(export_root.iterdir()) == []


def test_artifact_is_removed_when_transaction_finalization_fails(
    export_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from admin_v2.audit_exports_schemas import AuditExportFilters, AuditExportRequest
    from admin_v2.audit_exports_service import audit_export_service

    marker = uuid4().hex
    action = f"rollback-cleanup.{marker}"
    _insert_event(event_id=f"rollback-{marker}", action=action)

    class FailingMutations:
        def execute_high_risk(self, **kwargs):
            conn = db.connect()
            try:
                conn.execute("BEGIN IMMEDIATE")
                kwargs["mutation"](conn)
                raise RuntimeError("simulated audit finalization failure")
            finally:
                conn.rollback()
                conn.close()

    monkeypatch.setattr(audit_export_service, "mutations", FailingMutations())
    session = SimpleNamespace(
        record=SimpleNamespace(owner_user_id="owner-export", role="owner")
    )
    with pytest.raises(RuntimeError, match="simulated audit finalization failure"):
        audit_export_service.create(
            session=session,
            request=AuditExportRequest(
                format="json", filters=AuditExportFilters(action=action)
            ),
            idempotency_key=f"rollback-{marker}",
            request_id=f"req-rollback-{marker}",
        )
    assert export_root.exists()
    assert list(export_root.iterdir()) == []
