"""Secure, hermetic contracts for the unmounted Admin V2 backup slice."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from admin_v2.backups_repository import BackupRepository
from admin_v2.backups_routes import get_backup_service, router
from admin_v2.backups_service import BackupService
from admin_v2.dependencies import require_admin_session, require_recent_auth_session
from admin_v2.errors import AdminError, error_envelope
from admin_v2.repository import AdminMutationRepository
from admin_v2.service import AdminMutationService
from database import db


@pytest.fixture
def owner_session():
    return SimpleNamespace(
        record=SimpleNamespace(owner_user_id="owner", role="owner"),
        user={"username": "owner", "role": "owner", "status": "active"},
    )


@pytest.fixture
def backup_root(tmp_path: Path) -> Path:
    return tmp_path / "configured-backups"


@pytest.fixture
def backup_service(backup_root: Path) -> BackupService:
    return BackupService(
        repository=BackupRepository(db),
        mutations=AdminMutationService(AdminMutationRepository(db)),
        database=db,
        backup_root=backup_root,
    )


@pytest.fixture
def app(owner_session, backup_service: BackupService) -> FastAPI:
    isolated = FastAPI()

    @isolated.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = "req-backups-test"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @isolated.exception_handler(AdminError)
    async def admin_error(request: Request, exc: AdminError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(exc.code, exc.message, request.state.request_id),
            headers=exc.headers,
        )

    @isolated.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        del exc
        return JSONResponse(
            status_code=422,
            content=error_envelope(
                "ADMIN_VALIDATION_ERROR", "Request validation failed", request.state.request_id
            ),
        )

    isolated.dependency_overrides[require_admin_session] = lambda: owner_session
    isolated.dependency_overrides[require_recent_auth_session] = lambda: owner_session
    isolated.dependency_overrides[get_backup_service] = lambda: backup_service
    isolated.include_router(router, prefix="/api/admin/v2")
    return isolated


@pytest.fixture
def owner_client(app: FastAPI):
    with TestClient(app) as client:
        yield client


def _assert_error(response, status_code: int, code: str):
    assert response.status_code == status_code, response.text
    assert response.json()["error"] == {
        "code": code,
        "message": response.json()["error"]["message"],
        "requestId": "req-backups-test",
        "fieldErrors": [],
    }
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == "req-backups-test"


def _insert_marker() -> None:
    conn = db.connect()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS backup_slice_marker (id INTEGER PRIMARY KEY, value TEXT)")
        conn.execute("INSERT INTO backup_slice_marker (value) VALUES ('source-only-marker')")
        conn.commit()
    finally:
        conn.close()


def test_router_is_standalone_and_uses_owner_and_high_risk_dependencies(app: FastAPI):
    assert router.prefix == "/operations"
    routes = {
        (next(iter(route.methods)), route.path): route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/admin/v2/operations")
    }
    assert set(routes) == {
        ("GET", "/api/admin/v2/operations/backups"),
        ("POST", "/api/admin/v2/operations/backups"),
        ("GET", "/api/admin/v2/operations/restore-drills"),
    }
    assert require_admin_session in [
        dependency.call
        for dependency in routes[("GET", "/api/admin/v2/operations/backups")].dependant.dependencies
    ]
    assert require_recent_auth_session in [
        dependency.call
        for dependency in routes[("POST", "/api/admin/v2/operations/backups")].dependant.dependencies
    ]


def test_anonymous_lists_are_denied_by_owner_cookie_auth(app: FastAPI):
    app.dependency_overrides.pop(require_admin_session)
    with TestClient(app) as client:
        backups = client.get("/api/admin/v2/operations/backups")
        drills = client.get("/api/admin/v2/operations/restore-drills")
    _assert_error(backups, 401, "ADMIN_AUTH_REQUIRED")
    _assert_error(drills, 401, "ADMIN_AUTH_REQUIRED")


def test_create_requires_idempotency_key(owner_client: TestClient):
    response = owner_client.post("/api/admin/v2/operations/backups", json={"label": "nightly"})
    _assert_error(response, 400, "ADMIN_IDEMPOTENCY_KEY_INVALID")


def test_create_performs_real_online_backup_verification_manifest_and_audit(
    owner_client: TestClient, backup_root: Path
):
    _insert_marker()
    # The suite's autouse database fixture injects a migrated temp source; this
    # guards against ever exercising the repository's production data.db.
    source_path = Path(db.database_path).resolve()
    production_path = (Path(__file__).parents[2] / "data.db").resolve()
    assert source_path != production_path
    assert source_path.parent.name.startswith("practenture-tests-")

    response = owner_client.post(
        "/api/admin/v2/operations/backups",
        json={"label": "release checkpoint"},
        headers={"Idempotency-Key": "backup-real-1"},
    )

    assert response.status_code == 201, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == "req-backups-test"
    backup = response.json()["backup"]
    assert backup["status"] == "succeeded"
    assert backup["label"] == "release checkpoint"
    assert Path(backup["objectKey"]).name == backup["objectKey"]
    assert str(backup_root.resolve()) not in response.text

    artifact = (backup_root / backup["objectKey"]).resolve()
    artifact.relative_to(backup_root.resolve())
    assert artifact.is_file()
    assert artifact.stat().st_size == backup["databaseSize"] > 0
    assert hashlib.sha256(artifact.read_bytes()).hexdigest() == backup["sha256"]
    assert len(backup["sha256"]) == 64
    assert backup["verification"] == {
        "quickCheck": "ok",
        "integrityCheck": "ok",
        "foreignKeyViolations": 0,
        "tableCounts": backup["verification"]["tableCounts"],
    }
    assert backup["verification"]["tableCounts"]["backup_slice_marker"] == 1

    import sqlite3

    opened = sqlite3.connect(f"file:{artifact}?mode=ro", uri=True)
    try:
        assert opened.execute("SELECT value FROM backup_slice_marker").fetchone()[0] == "source-only-marker"
        assert opened.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    finally:
        opened.close()

    drills = owner_client.get("/api/admin/v2/operations/restore-drills").json()
    assert drills["items"] == [
        {
            "id": backup["restoreDrillId"],
            "backupId": backup["id"],
            "startedAt": backup["startedAt"],
            "endedAt": backup["endedAt"],
            "status": "succeeded",
            "errorMessage": None,
        }
    ]

    conn = db.connect()
    try:
        stored = conn.execute(
            "SELECT object_key, checksum, database_size, integrity_result FROM backup_runs WHERE id=?",
            (backup["id"],),
        ).fetchone()
        assert stored["object_key"] == backup["objectKey"]
        assert stored["checksum"] == backup["sha256"]
        assert stored["database_size"] == backup["databaseSize"]
        assert json.loads(stored["integrity_result"])["tableCounts"]["backup_slice_marker"] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE action='backup.create'"
        ).fetchone()[0] == 1
        persisted = "\n".join(
            str(value)
            for table in ("backup_runs", "restore_drills", "admin_audit_events")
            for row in conn.execute(f'SELECT * FROM "{table}"')
            for value in row
            if value is not None
        )
        assert str(backup_root.resolve()) not in persisted
        assert "backup-real-1" not in persisted
    finally:
        conn.close()


def test_replay_is_exact_and_conflict_does_not_create_another_artifact(
    owner_client: TestClient, backup_root: Path
):
    headers = {"Idempotency-Key": "backup-replay"}
    first = owner_client.post(
        "/api/admin/v2/operations/backups", json={"label": "one"}, headers=headers
    )
    replay = owner_client.post(
        "/api/admin/v2/operations/backups", json={"label": "one"}, headers=headers
    )
    conflict = owner_client.post(
        "/api/admin/v2/operations/backups", json={"label": "two"}, headers=headers
    )

    assert first.status_code == replay.status_code == 201
    assert replay.json() == first.json()
    assert replay.headers["location"] == first.headers["location"]
    _assert_error(conflict, 409, "ADMIN_IDEMPOTENCY_CONFLICT")
    assert len(list(backup_root.glob("*.sqlite3"))) == 1

    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM backup_runs").fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM restore_drills").fetchone()[0] == 1
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE action='backup.create'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_failed_verification_cleans_partial_artifact_and_rolls_back_metadata(
    app: FastAPI, owner_client: TestClient, backup_service: BackupService, backup_root: Path, monkeypatch
):
    def fail_verification(path: Path):
        assert path.exists()
        raise RuntimeError("forced verifier failure with /secret/path")

    monkeypatch.setattr(backup_service, "_verify_backup", fail_verification)
    response = owner_client.post(
        "/api/admin/v2/operations/backups",
        json={"label": "must fail cleanly"},
        headers={"Idempotency-Key": "backup-failure"},
    )

    _assert_error(response, 500, "ADMIN_BACKUP_FAILED")
    assert not list(backup_root.glob("*"))
    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM backup_runs").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM restore_drills").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_idempotency_records WHERE route LIKE '%backups%'"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE action='backup.create'"
        ).fetchone()[0] == 0
    finally:
        conn.close()
    assert "/secret/path" not in response.text


def test_lists_are_bounded_sorted_and_validation_is_stable(owner_client: TestClient):
    for index in range(3):
        response = owner_client.post(
            "/api/admin/v2/operations/backups",
            json={"label": f"backup-{index}"},
            headers={"Idempotency-Key": f"backup-list-{index}"},
        )
        assert response.status_code == 201, response.text

    backups = owner_client.get("/api/admin/v2/operations/backups", params={"limit": 2})
    drills = owner_client.get("/api/admin/v2/operations/restore-drills", params={"limit": 2})
    assert backups.status_code == drills.status_code == 200
    assert len(backups.json()["items"]) == len(drills.json()["items"]) == 2
    assert backups.json()["totalCount"] == drills.json()["totalCount"] == 3
    assert backups.json()["pageInfo"]["hasNextPage"] is True
    assert drills.json()["pageInfo"]["hasNextPage"] is True
    assert backups.json()["items"][0]["startedAt"] >= backups.json()["items"][1]["startedAt"]
    assert drills.json()["items"][0]["startedAt"] >= drills.json()["items"][1]["startedAt"]

    backup_next = owner_client.get(
        "/api/admin/v2/operations/backups",
        params={"limit": 2, "cursor": backups.json()["pageInfo"]["nextCursor"]},
    )
    drill_next = owner_client.get(
        "/api/admin/v2/operations/restore-drills",
        params={"limit": 2, "cursor": drills.json()["pageInfo"]["nextCursor"]},
    )
    assert len(backup_next.json()["items"]) == len(drill_next.json()["items"]) == 1
    assert backup_next.json()["pageInfo"] == {"nextCursor": None, "hasNextPage": False}
    assert drill_next.json()["pageInfo"] == {"nextCursor": None, "hasNextPage": False}

    wrong_collection = owner_client.get(
        "/api/admin/v2/operations/restore-drills",
        params={"cursor": backups.json()["pageInfo"]["nextCursor"]},
    )
    _assert_error(wrong_collection, 400, "ADMIN_CURSOR_INVALID")

    invalid = owner_client.get("/api/admin/v2/operations/backups", params={"limit": 101})
    _assert_error(invalid, 422, "ADMIN_VALIDATION_ERROR")
