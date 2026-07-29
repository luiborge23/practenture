"""Focused contracts for the owner-only Admin V2 operational sessions list."""

from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from admin_v2.dependencies import require_admin_session
from admin_v2.errors import AdminError, error_envelope
from admin_v2.sessions_routes import router as sessions_router
from database import db


SESSION_CODES = ("OPS-A001", "OPS-B002", "OPS-C003", "OPS-D004")


def _error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    request_id = request.headers.get("X-Request-ID") or "req-sessions-test"
    return JSONResponse(
        status_code=status,
        content=error_envelope(code, message, request_id),
        headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


@pytest.fixture
def sessions_app() -> FastAPI:
    app = FastAPI()
    app.include_router(sessions_router, prefix="/api/admin/v2")

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
def seeded_sessions() -> dict[str, str]:
    config_a = {
        "totalRounds": 8,
        "numberOfAICompetitors": 1,
        "integration": {
            "password": "legacy-password",
            "safeLabel": "visible",
            "nested": {"accessToken": "legacy-token", "tokenCount": 2},
        },
    }
    teams_a = [
        {"teamName": "Humans", "isAI": False, "studentId": "student-1"},
        {
            "teamName": "AI One",
            "isAI": True,
            "aiStrategy": "balanced",
            "privateKey": "legacy-private-key",
        },
    ]
    rows = [
        (
            SESSION_CODES[0], "session-a", json.dumps(config_a), json.dumps(teams_a),
            "prof-a", "prof-a", "class-a", 30, 1, "active",
            "athletic-footwear-classic", "1.0.0", "2026-07-28T09:00:00+00:00",
        ),
        (
            SESSION_CODES[1], "session-b", json.dumps({"totalRounds": 10}),
            json.dumps([{"teamName": "Beta", "isAI": False}]),
            "prof-a", "prof-a", "class-a", 30, 2, "active",
            "athletic-footwear-classic", "1.0.0", "2026-07-28T09:00:00+00:00",
        ),
        (
            SESSION_CODES[2], "session-c", json.dumps({"totalRounds": 12}),
            json.dumps([{"teamName": "AI Wear", "isAI": True}]),
            "prof-b", "prof-b", "class-b", 20, 12, "finished",
            "wearable-technology", "1.0.0", "2026-07-28T11:00:00+00:00",
        ),
        (
            SESSION_CODES[3], "session-d", "{malformed", "not-json",
            "prof-b", "prof-b", None, 15, 0, "creating",
            "athletic-footwear-classic", "1.0.0", "2026-07-28T12:00:00+00:00",
        ),
    ]
    conn = db.connect()
    try:
        conn.executemany(
            """INSERT OR REPLACE INTO users
                   (username, password_hash, role, name, email, status)
               VALUES (?, 'hash', 'professor', ?, ?, 'active')""",
            [
                ("prof-a", "Professor Alpha", "alpha@example.edu"),
                ("prof-b", "Professor Beta", "beta@example.edu"),
            ],
        )
        conn.executemany(
            """INSERT INTO organizations
                   (id, name, university_name, slug, status, created_by, created_at)
               VALUES (?, ?, ?, ?, 'active', 'owner', ?)""",
            [
                ("org-a", "Alpha University", "Alpha U", "alpha-u", "2026-01-01"),
                ("org-b", "Beta University", "Beta U", "beta-u", "2026-01-01"),
            ],
        )
        conn.executemany(
            """INSERT INTO memberships (id, user_id, org_id, role, created_at)
               VALUES (?, ?, ?, 'professor', '2026-01-01')""",
            [("membership-a", "prof-a", "org-a"), ("membership-b", "prof-b", "org-b")],
        )
        conn.executemany(
            """INSERT INTO classes
                   (id, professor_user_id, name, join_code, is_active, created_at)
               VALUES (?, ?, ?, ?, 1, '2026-01-01')""",
            [
                ("class-a", "prof-a", "Operations Alpha", "JOIN-A"),
                ("class-b", "prof-b", "Operations Beta", "JOIN-B"),
            ],
        )
        conn.executemany(
            """INSERT INTO sessions
                   (code, session_id, config_json, teams_json, created_by,
                    professor_user_id, class_id, max_human_teams, current_round,
                    state, scenario_id, scenario_version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            rows,
        )
        conn.commit()
    finally:
        conn.close()

    digest = hashlib.sha256(
        "".join(row[2] + row[3] for row in rows).encode()
    ).hexdigest()
    return {"persistenceDigest": digest}


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


def test_sessions_require_an_owner_cookie_session(sessions_app: FastAPI) -> None:
    with TestClient(sessions_app) as client:
        response = client.get("/api/admin/v2/sessions")
    _assert_error(response, 401, "ADMIN_AUTH_REQUIRED")


def test_list_is_typed_camel_case_operational_and_recursively_redacted(
    sessions_app: FastAPI, seeded_sessions: dict[str, str]
) -> None:
    with _authorized_client(sessions_app) as client:
        response = client.get("/api/admin/v2/sessions")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert set(body) == {"items", "page"}
    assert body["page"] == {"limit": 50, "hasMore": False, "nextCursor": None}
    assert [item["code"] for item in body["items"]] == list(reversed(SESSION_CODES))

    item = next(row for row in body["items"] if row["code"] == SESSION_CODES[0])
    assert set(item) == {
        "sessionId", "code", "state", "currentRound", "totalRounds",
        "scenario", "createdAt", "createdBy", "professor", "classroom",
        "organizations", "maxHumanTeams", "teamSummary", "configuration",
        "teams", "dataWarnings",
    }
    assert item["scenario"] == {"id": "athletic-footwear-classic", "version": "1.0.0"}
    assert item["professor"] == {
        "userId": "prof-a", "name": "Professor Alpha", "email": "alpha@example.edu"
    }
    assert item["classroom"] == {"classId": "class-a", "name": "Operations Alpha"}
    assert item["organizations"] == [{"organizationId": "org-a", "name": "Alpha University"}]
    assert item["teamSummary"] == {"total": 2, "human": 1, "ai": 1}
    assert item["configuration"]["integration"] == {
        "password": "[REDACTED]",
        "safeLabel": "visible",
        "nested": {"accessToken": "[REDACTED]", "tokenCount": 2},
    }
    assert item["teams"][1]["privateKey"] == "[REDACTED]"


def test_malformed_legacy_json_is_contained_and_reported(
    sessions_app: FastAPI, seeded_sessions: dict[str, str]
) -> None:
    with _authorized_client(sessions_app) as client:
        response = client.get("/api/admin/v2/sessions", params={"search": SESSION_CODES[3]})
    assert response.status_code == 200, response.text
    item = response.json()["items"][0]
    assert item["configuration"] == {}
    assert item["teams"] == []
    assert item["totalRounds"] is None
    assert item["teamSummary"] == {"total": 0, "human": 0, "ai": 0}
    assert item["dataWarnings"] == ["invalidConfigurationJson", "invalidTeamsJson"]


def test_bounded_search_filters_and_time_window(
    sessions_app: FastAPI, seeded_sessions: dict[str, str]
) -> None:
    with _authorized_client(sessions_app) as client:
        by_org = client.get("/api/admin/v2/sessions", params={"organizationId": "org-a", "state": "active"})
        by_search = client.get("/api/admin/v2/sessions", params={"search": "Professor Beta"})
        by_window = client.get(
            "/api/admin/v2/sessions",
            params={
                "scenarioId": "wearable-technology",
                "classId": "class-b",
                "professorUserId": "prof-b",
                "createdFrom": "2026-07-28T10:00:00+00:00",
                "createdTo": "2026-07-28T11:30:00+00:00",
            },
        )
        invalid = client.get("/api/admin/v2/sessions", params={"limit": 101})
    assert [row["code"] for row in by_org.json()["items"]] == [SESSION_CODES[1], SESSION_CODES[0]]
    assert [row["code"] for row in by_search.json()["items"]] == [SESSION_CODES[3], SESSION_CODES[2]]
    assert [row["code"] for row in by_window.json()["items"]] == [SESSION_CODES[2]]
    _assert_error(invalid, 400, "ADMIN_VALIDATION_ERROR")


def test_allowlisted_sort_and_tied_keyset_pagination_are_stable(
    sessions_app: FastAPI, seeded_sessions: dict[str, str]
) -> None:
    with _authorized_client(sessions_app) as client:
        first = client.get(
            "/api/admin/v2/sessions",
            params={"state": "active", "sortBy": "createdAt", "sortDirection": "asc", "limit": 1},
        )
        first_body = first.json()
        second = client.get(
            "/api/admin/v2/sessions",
            params={
                "state": "active", "sortBy": "createdAt", "sortDirection": "asc",
                "limit": 1, "cursor": first_body["page"]["nextCursor"],
            },
        )
        by_round = client.get(
            "/api/admin/v2/sessions",
            params={"state": "active", "sortBy": "currentRound", "sortDirection": "desc"},
        )
    assert [row["code"] for row in first_body["items"]] == [SESSION_CODES[0]]
    assert first_body["page"]["hasMore"] is True
    assert first_body["page"]["nextCursor"]
    assert [row["code"] for row in second.json()["items"]] == [SESSION_CODES[1]]
    assert second.json()["page"] == {"limit": 1, "hasMore": False, "nextCursor": None}
    assert [row["code"] for row in by_round.json()["items"]] == [SESSION_CODES[1], SESSION_CODES[0]]


def test_cursor_is_query_bound_versioned_and_stably_rejected(
    sessions_app: FastAPI, seeded_sessions: dict[str, str]
) -> None:
    with _authorized_client(sessions_app) as client:
        page = client.get("/api/admin/v2/sessions", params={"limit": 1, "state": "active"}).json()
        cursor = page["page"]["nextCursor"]
        malformed = client.get("/api/admin/v2/sessions", params={"cursor": "not-a-cursor"})
        mismatched = client.get(
            "/api/admin/v2/sessions", params={"cursor": cursor, "limit": 1, "state": "finished"}
        )
    _assert_error(malformed, 400, "ADMIN_SESSIONS_CURSOR_INVALID")
    _assert_error(mismatched, 400, "ADMIN_SESSIONS_CURSOR_INVALID")


def test_read_does_not_mutate_persisted_session_json(
    sessions_app: FastAPI, seeded_sessions: dict[str, str]
) -> None:
    with _authorized_client(sessions_app) as client:
        assert client.get("/api/admin/v2/sessions").status_code == 200
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT config_json, teams_json FROM sessions WHERE code IN (?, ?, ?, ?) ORDER BY code",
            SESSION_CODES,
        ).fetchall()
    finally:
        conn.close()
    digest = hashlib.sha256(
        "".join(row["config_json"] + row["teams_json"] for row in rows).encode()
    ).hexdigest()
    assert digest == seeded_sessions["persistenceDigest"]
