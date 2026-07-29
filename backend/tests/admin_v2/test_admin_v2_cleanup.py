"""Standalone contracts for the Admin V2 bounded cleanup-plan slice."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from admin_v2.cleanup_repository import CleanupRepository
from admin_v2.cleanup_routes import get_cleanup_service, router
from admin_v2.cleanup_service import CleanupService
from admin_v2.dependencies import require_admin_session, require_recent_auth_session
from admin_v2.errors import AdminError, error_envelope
from admin_v2.repository import AdminMutationRepository
from admin_v2.service import AdminMutationService
from database import db


@pytest.fixture
def owner_session():
    return SimpleNamespace(record=SimpleNamespace(owner_user_id="owner", role="owner"), user={"username": "owner"})


@pytest.fixture
def cleanup_service():
    return CleanupService(repository=CleanupRepository(db), mutations=AdminMutationService(AdminMutationRepository(db)))


@pytest.fixture
def app(owner_session, cleanup_service):
    app = FastAPI()
    @app.middleware("http")
    async def context(request: Request, call_next):
        request.state.request_id = "req-cleanup-test"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response
    @app.exception_handler(AdminError)
    async def admin_error(request: Request, exc: AdminError):
        return JSONResponse(status_code=exc.status_code, content=error_envelope(exc.code, exc.message, request.state.request_id), headers=exc.headers)
    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return JSONResponse(status_code=422, content=error_envelope("ADMIN_VALIDATION_ERROR", "Request validation failed", request.state.request_id))
    app.dependency_overrides[require_admin_session] = lambda: owner_session
    app.dependency_overrides[require_recent_auth_session] = lambda: owner_session
    app.dependency_overrides[get_cleanup_service] = lambda: cleanup_service
    app.include_router(router, prefix="/api/admin/v2")
    return app


@pytest.fixture
def client(app):
    with TestClient(app) as value:
        yield value


def seed():
    conn = db.connect()
    try:
        for code, sid in (("A", "sid-a"), ("B", "sid-b")):
            conn.execute("INSERT INTO sessions(code,session_id,config_json,teams_json) VALUES(?,?,?,?)", (code, sid, "{}", "[]"))
            conn.execute("INSERT INTO decisions VALUES(?,?,?,?)", (code, 1, "t1", "{}"))
            conn.execute("INSERT INTO results VALUES(?,?,?,?)", (code, 1, "t1", "{}"))
            conn.execute("INSERT INTO team_states VALUES(?,?,?)", (code, "t1", "{}"))
            conn.execute("INSERT INTO announcements(id,session_id,message,author_id,author_name) VALUES(?,?,?,?,?)", (f"ann-{code}", sid, "x", "u", "U"))
        conn.commit()
    finally:
        conn.close()


def backup(**overrides):
    now = datetime.now(timezone.utc)
    values = {"id":"backup-good", "started_at":now.isoformat(), "ended_at":now.isoformat(), "status":"succeeded", "checksum":"a"*64, "database_size":100, "integrity_result":json.dumps({"quickCheck":"ok","integrityCheck":"ok","foreignKeyViolations":0})}
    values.update(overrides)
    conn=db.connect()
    try:
        conn.execute("INSERT INTO backup_runs(id,started_at,ended_at,status,checksum,database_size,integrity_result) VALUES(:id,:started_at,:ended_at,:status,:checksum,:database_size,:integrity_result)", values)
        if values["status"] == "succeeded":
            conn.execute("INSERT INTO restore_drills(id,backup_id,started_at,ended_at,status) VALUES(?,?,?,?,?)", ("drill-good",values["id"],values["started_at"],values["ended_at"],"succeeded"))
        conn.commit()
    finally: conn.close()


def test_route_inventory_and_dependencies(app):
    routes=[r for r in app.routes if isinstance(r,APIRoute) and "cleanup-plans" in r.path]
    assert {(next(iter(r.methods)),r.path) for r in routes} == {("POST","/api/admin/v2/operations/cleanup-plans"),("GET","/api/admin/v2/operations/cleanup-plans/{plan_id}"),("POST","/api/admin/v2/operations/cleanup-plans/{plan_id}/execute")}
    assert require_admin_session in [d.call for d in routes[0].dependant.dependencies]
    execute=next(r for r in routes if r.path.endswith("/execute"))
    assert require_recent_auth_session in [d.call for d in execute.dependant.dependencies]


@pytest.mark.parametrize("payload", [{}, {"selector":{}}, {"selector":{"sessionCodes":[]}}, {"selector":{"sessionCodes":[" "]}}, {"selector":{"sessionCodes":["A","A"]}}, {"selector":{"all":True}}])
def test_selector_is_explicit_nonempty_unique_and_bounded(client,payload):
    assert client.post("/api/admin/v2/operations/cleanup-plans",json=payload).status_code == 422


def test_preview_selected_only_and_canonical_hash(client):
    seed()
    first=client.post("/api/admin/v2/operations/cleanup-plans",json={"selector":{"sessionCodes":["B","A"]}})
    second=client.post("/api/admin/v2/operations/cleanup-plans",json={"selector":{"sessionCodes":["A","B"]}})
    assert first.status_code == second.status_code == 201
    a,b=first.json()["plan"],second.json()["plan"]
    assert a["selector"] == {"sessionCodes":["A","B"]}
    assert a["previewCounts"] == {"sessions":2,"decisions":2,"results":2,"teamStates":2,"announcements":2}
    assert a["planHash"] == b["planHash"] and len(a["planHash"]) == 64
    assert client.get(f"/api/admin/v2/operations/cleanup-plans/{a['id']}").json()["plan"]["planHash"] == a["planHash"]


def test_backup_required_and_drift_are_fail_closed(client):
    seed(); plan=client.post("/api/admin/v2/operations/cleanup-plans",json={"selector":{"sessionCodes":["A"]}}).json()["plan"]
    body={"planHash":plan["planHash"],"confirmation":plan["confirmationText"]}
    missing=client.post(f"/api/admin/v2/operations/cleanup-plans/{plan['id']}/execute",json=body,headers={"Idempotency-Key":"cleanup-1"})
    assert missing.status_code == 409 and missing.json()["error"]["code"] == "ADMIN_BACKUP_REQUIRED"
    backup()
    conn=db.connect(); conn.execute("INSERT INTO decisions VALUES('A',2,'t1','{}')"); conn.commit(); conn.close()
    drift=client.post(f"/api/admin/v2/operations/cleanup-plans/{plan['id']}/execute",json=body,headers={"Idempotency-Key":"cleanup-2"})
    assert drift.status_code == 409 and drift.json()["error"]["code"] == "ADMIN_CLEANUP_PLAN_CHANGED"
    conn=db.connect(); assert conn.execute("SELECT COUNT(*) FROM sessions WHERE code='A'").fetchone()[0] == 1; conn.close()


def test_success_atomic_audited_and_idempotent(client):
    seed(); backup()
    plan=client.post("/api/admin/v2/operations/cleanup-plans",json={"selector":{"sessionCodes":["A"]}}).json()["plan"]
    body={"planHash":plan["planHash"],"confirmation":plan["confirmationText"]}; url=f"/api/admin/v2/operations/cleanup-plans/{plan['id']}/execute"; headers={"Idempotency-Key":"cleanup-ok"}
    first=client.post(url,json=body,headers=headers); replay=client.post(url,json=body,headers=headers)
    assert first.status_code == replay.status_code == 200 and first.json() == replay.json()
    assert first.json()["deletedCounts"] == plan["previewCounts"]
    conflict=client.post(url,json={**body,"confirmation":"wrong"},headers=headers)
    assert conflict.status_code == 409 and conflict.json()["error"]["code"] == "ADMIN_IDEMPOTENCY_CONFLICT"
    conn=db.connect()
    assert conn.execute("SELECT COUNT(*) FROM sessions WHERE code='A'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM sessions WHERE code='B'").fetchone()[0] == 1
    assert conn.execute("SELECT status FROM cleanup_plans WHERE id=?",(plan["id"],)).fetchone()[0] == "completed"
    assert conn.execute("SELECT COUNT(*) FROM admin_audit_events WHERE action='cleanup.execute'").fetchone()[0] == 1
    conn.close()


def test_confirmation_mismatch(client):
    seed(); backup(); plan=client.post("/api/admin/v2/operations/cleanup-plans",json={"selector":{"sessionCodes":["A"]}}).json()["plan"]
    response=client.post(f"/api/admin/v2/operations/cleanup-plans/{plan['id']}/execute",json={"planHash":plan["planHash"],"confirmation":"wrong"},headers={"Idempotency-Key":"bad-confirm"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "ADMIN_CLEANUP_CONFIRMATION_MISMATCH"


@pytest.mark.parametrize("evidence", ["stale", "failed", "unverified", "no-drill"])
def test_stale_failed_unverified_or_undrilled_backup_is_denied(client, evidence):
    seed()
    now = datetime.now(timezone.utc)
    if evidence == "stale":
        backup(started_at=(now-timedelta(hours=2)).isoformat(), ended_at=(now-timedelta(hours=2)).isoformat())
    elif evidence == "failed":
        backup(status="failed")
    elif evidence == "unverified":
        backup(integrity_result=json.dumps({"quickCheck":"ok","integrityCheck":"failed","foreignKeyViolations":0}))
    else:
        backup()
        conn=db.connect(); conn.execute("DELETE FROM restore_drills"); conn.commit(); conn.close()
    plan=client.post("/api/admin/v2/operations/cleanup-plans",json={"selector":{"sessionCodes":["A"]}}).json()["plan"]
    response=client.post(f"/api/admin/v2/operations/cleanup-plans/{plan['id']}/execute",json={"planHash":plan["planHash"],"confirmation":plan["confirmationText"]},headers={"Idempotency-Key":f"evidence-{evidence}"})
    assert response.status_code == 409 and response.json()["error"]["code"] == "ADMIN_BACKUP_REQUIRED"
    conn=db.connect(); assert conn.execute("SELECT COUNT(*) FROM sessions WHERE code='A'").fetchone()[0] == 1; conn.close()


def test_mid_delete_failure_rolls_back_deletes_plan_audit_and_idempotency(client, cleanup_service, monkeypatch):
    seed(); backup()
    plan=client.post("/api/admin/v2/operations/cleanup-plans",json={"selector":{"sessionCodes":["A"]}}).json()["plan"]
    def partial_then_fail(conn, codes):
        conn.execute("DELETE FROM announcements WHERE session_id='sid-a'")
        raise RuntimeError("injected mid-delete failure")
    monkeypatch.setattr(cleanup_service.repository, "delete_selected", partial_then_fail)
    with pytest.raises(RuntimeError, match="injected mid-delete failure"):
        client.post(f"/api/admin/v2/operations/cleanup-plans/{plan['id']}/execute",json={"planHash":plan["planHash"],"confirmation":plan["confirmationText"]},headers={"Idempotency-Key":"rollback-key"})
    conn=db.connect()
    assert conn.execute("SELECT COUNT(*) FROM announcements WHERE session_id='sid-a'").fetchone()[0] == 1
    assert conn.execute("SELECT status FROM cleanup_plans WHERE id=?",(plan["id"],)).fetchone()[0] == "pending"
    assert conn.execute("SELECT COUNT(*) FROM admin_audit_events WHERE action='cleanup.execute'").fetchone()[0] == 0
    assert conn.execute("SELECT COUNT(*) FROM admin_idempotency_records WHERE route LIKE '%cleanup-plans%'").fetchone()[0] == 0
    conn.close()


def test_anonymous_plan_read_and_recent_auth_execute_boundaries(app, client):
    app.dependency_overrides.pop(require_admin_session)
    denied_plan=client.post("/api/admin/v2/operations/cleanup-plans",json={"selector":{"sessionCodes":["A"]}})
    assert denied_plan.status_code == 401 and denied_plan.json()["error"]["code"] == "ADMIN_AUTH_REQUIRED"
    app.dependency_overrides[require_admin_session] = lambda: SimpleNamespace(record=SimpleNamespace(owner_user_id="owner",role="owner"),user={"username":"owner"})
    app.dependency_overrides.pop(require_recent_auth_session)
    denied_execute=client.post("/api/admin/v2/operations/cleanup-plans/unknown/execute",json={"planHash":"a"*64,"confirmation":"x"},headers={"Idempotency-Key":"auth-boundary"})
    assert denied_execute.status_code == 401 and denied_execute.json()["error"]["code"] == "ADMIN_AUTH_REQUIRED"
