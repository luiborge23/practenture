"""Focused coverage for the un-mounted Admin V2 operations health slice."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from admin_v2.dependencies import require_admin_session
from admin_v2.errors import AdminError, error_envelope
from admin_v2.health_repository import OperationsHealthRepository
from admin_v2.health_routes import router as health_router
from admin_v2.health_service import OperationsHealthService
import admin_v2.health_routes as health_routes_module


NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)


class TemporaryDatabase:
    def __init__(self, path: Path) -> None:
        self.database_path = str(path)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


@pytest.fixture
def health_database(tmp_path: Path) -> TemporaryDatabase:
    database = TemporaryDatabase(tmp_path / "health.sqlite3")
    conn = database.connect()
    conn.executescript(
        """
        CREATE TABLE alembic_version (version_num TEXT PRIMARY KEY);
        INSERT INTO alembic_version VALUES ('003');
        CREATE TABLE users (
            username TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            status TEXT NOT NULL
        );
        CREATE TABLE organizations (id TEXT PRIMARY KEY);
        CREATE TABLE memberships (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            org_id TEXT NOT NULL,
            role TEXT NOT NULL
        );
        CREATE TABLE classes (
            id TEXT PRIMARY KEY,
            professor_user_id TEXT NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1
        );
        CREATE TABLE class_enrollments (
            id TEXT PRIMARY KEY,
            class_id TEXT NOT NULL,
            student_user_id TEXT NOT NULL
        );
        CREATE TABLE sessions (
            code TEXT PRIMARY KEY,
            professor_user_id TEXT,
            class_id TEXT,
            state TEXT NOT NULL
        );
        CREATE TABLE professor_invitations (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            max_uses INTEGER NOT NULL,
            use_count INTEGER NOT NULL
        );
        CREATE TABLE backup_runs (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT NOT NULL,
            integrity_result TEXT NOT NULL
        );
        CREATE TABLE restore_drills (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT NOT NULL
        );
        INSERT INTO users VALUES ('owner-1', 'owner', 'active');
        INSERT INTO users VALUES ('professor-1', 'professor', 'active');
        INSERT INTO users VALUES ('student-1', 'student', 'active');
        INSERT INTO organizations VALUES ('org-1');
        INSERT INTO memberships VALUES ('membership-1', 'professor-1', 'org-1', 'professor');
        INSERT INTO classes VALUES ('class-1', 'professor-1', 1);
        INSERT INTO class_enrollments VALUES ('enrollment-1', 'class-1', 'student-1');
        INSERT INTO sessions VALUES ('HEALTHY-1', 'professor-1', 'class-1', 'active');
        INSERT INTO professor_invitations VALUES ('invite-1', 'active', 1, 0);
        INSERT INTO backup_runs VALUES (
            'backup-1', '2026-07-28T10:00:00+00:00',
            '2026-07-28T10:05:00+00:00', 'completed', 'ok'
        );
        INSERT INTO restore_drills VALUES (
            'drill-1', '2026-07-27T10:00:00+00:00',
            '2026-07-27T10:05:00+00:00', 'passed'
        );
        """
    )
    conn.commit()
    conn.close()
    return database


def _service(database: TemporaryDatabase) -> OperationsHealthService:
    return OperationsHealthService(OperationsHealthRepository(database))


def _database_digest(database: TemporaryDatabase) -> str:
    conn = database.connect()
    try:
        payload = "\n".join(
            str(tuple(row))
            for table in (
                "users", "memberships", "sessions", "professor_invitations",
                "backup_runs", "restore_drills",
            )
            for row in conn.execute(f'SELECT * FROM "{table}" ORDER BY 1').fetchall()
        )
    finally:
        conn.close()
    return hashlib.sha256(payload.encode()).hexdigest()


def test_healthy_report_covers_every_required_layer_and_is_read_only(
    health_database: TemporaryDatabase,
) -> None:
    before = _database_digest(health_database)
    report = _service(health_database).get_health(request_id="req-health", now=NOW)
    after = _database_digest(health_database)

    assert report.status == "healthy"
    assert report.request_id == "req-health"
    assert report.engine.name == "sqlite"
    assert report.engine.migration_version == "003"
    assert report.summary.failed == 0
    assert report.summary.warnings == 0
    assert {check.code for check in report.checks} == {
        "DATABASE_CONNECTIVITY",
        "MIGRATION_VERSION",
        "SQLITE_QUICK_CHECK",
        "SQLITE_FOREIGN_KEY_CHECK",
        "LOGICAL_ORPHAN_CHECK",
        "DOMAIN_INVARIANT_CHECK",
        "BACKUP_FRESHNESS",
        "RESTORE_DRILL_FRESHNESS",
        "SQLITE_STORAGE",
    }
    assert before == after


def test_seeded_orphans_domain_drift_and_failed_evidence_are_machine_readable_and_redacted(
    health_database: TemporaryDatabase,
) -> None:
    conn = health_database.connect()
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute(
        "INSERT INTO memberships VALUES ('raw-sensitive-id', 'missing-user', 'org-1', 'invalid')"
    )
    conn.execute("UPDATE backup_runs SET status='failed' WHERE id='backup-1'")
    conn.execute("UPDATE restore_drills SET status='failed' WHERE id='drill-1'")
    conn.commit()
    conn.close()

    report = _service(health_database).get_health(request_id="req-failure", now=NOW)
    checks = {check.code: check for check in report.checks}

    assert report.status == "unhealthy"
    assert checks["LOGICAL_ORPHAN_CHECK"].affected_count == 1
    assert checks["DOMAIN_INVARIANT_CHECK"].affected_count == 1
    assert checks["BACKUP_FRESHNESS"].status == "fail"
    assert checks["RESTORE_DRILL_FRESHNESS"].status == "fail"
    serialized = report.model_dump_json(by_alias=True)
    assert "raw-sensitive-id" not in serialized
    assert all(sample.startswith("id_") for check in report.checks for sample in check.sample_ids)


def test_connectivity_failure_is_fail_closed_without_leaking_exception_text() -> None:
    class FailedRepository:
        def collect(self):
            raise sqlite3.OperationalError("secret database path /private/db.sqlite")

    report = OperationsHealthService(FailedRepository()).get_health(  # type: ignore[arg-type]
        request_id="req-connectivity", now=NOW
    )

    assert report.status == "unhealthy"
    assert report.summary.failed == 1
    assert report.checks[0].code == "DATABASE_CONNECTIVITY"
    assert "/private/db.sqlite" not in report.model_dump_json(by_alias=True)


def test_http_contract_is_owner_authenticated_camel_case_and_not_mounted_globally(
    health_database: TemporaryDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    app = FastAPI()
    app.include_router(health_router, prefix="/api/admin/v2")
    app.dependency_overrides[require_admin_session] = lambda: object()
    monkeypatch.setattr(
        health_routes_module.operations_health_service,
        "repository",
        OperationsHealthRepository(health_database),
    )

    with TestClient(app) as client:
        response = client.get(
            "/api/admin/v2/operations/health",
            headers={"X-Request-ID": "req-http-health"},
        )

    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-request-id"] == "req-http-health"
    body = response.json()
    assert body["requestId"] == "req-http-health"
    assert set(body) == {"status", "checkedAt", "requestId", "engine", "summary", "checks"}
    assert set(body["engine"]) == {
        "name", "version", "migrationVersion", "expectedMigrationVersion"
    }
    assert all("affectedCount" in check and "sampleIds" in check for check in body["checks"])


def test_http_contract_rejects_anonymous_callers() -> None:
    app = FastAPI()
    app.include_router(health_router, prefix="/api/admin/v2")

    @app.exception_handler(AdminError)
    async def handle_admin_error(request: Request, exc: AdminError) -> JSONResponse:
        request_id = "req-anonymous-health"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(exc.code, exc.message, request_id),
            headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
        )

    with TestClient(app) as client:
        response = client.get("/api/admin/v2/operations/health")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "ADMIN_AUTH_REQUIRED"
