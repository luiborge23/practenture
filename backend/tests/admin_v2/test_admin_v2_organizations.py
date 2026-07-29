"""Focused contracts for Admin V2 overview and organizations."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from admin_v2.dependencies import require_admin_session, require_csrf_session
from admin_v2.errors import AdminError, error_envelope
from admin_v2.organizations_routes import router
from database import db


@pytest.fixture
def app() -> FastAPI:
    isolated = FastAPI()

    @isolated.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = "req-organizations-test"
        response = await call_next(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["Cache-Control"] = "no-store"
        return response

    @isolated.exception_handler(AdminError)
    async def admin_error(request: Request, exc: AdminError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(
                exc.code, exc.message, getattr(request.state, "request_id", None)
            ),
            headers=exc.headers,
        )

    isolated.include_router(router, prefix="/api/admin/v2")
    return isolated


@pytest.fixture
def owner_session():
    return SimpleNamespace(
        record=SimpleNamespace(owner_user_id="owner", role="owner"),
        user={"username": "owner", "role": "owner", "status": "active"},
    )


@pytest.fixture
def owner_client(app: FastAPI, owner_session):
    app.dependency_overrides[require_admin_session] = lambda: owner_session
    app.dependency_overrides[require_csrf_session] = lambda: owner_session
    with TestClient(app) as client:
        yield client


def _insert_org(
    organization_id: str,
    name: str,
    *,
    slug: str | None = None,
    status: str = "active",
    created_at: str = "2026-07-28T10:00:00+00:00",
):
    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO organizations
                   (id, name, university_name, slug, status, created_by, created_at)
               VALUES (?, ?, ?, ?, ?, 'owner', ?)""",
            (organization_id, name, f"{name} University", slug or name.casefold(), status, created_at),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_user(username: str, role: str):
    conn = db.connect()
    try:
        conn.execute(
            """INSERT OR REPLACE INTO users
                   (username, password_hash, role, name, status)
               VALUES (?, 'not-used', ?, ?, 'active')""",
            (username, role, username.title()),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_membership(organization_id: str, username: str, role: str):
    conn = db.connect()
    try:
        conn.execute(
            "INSERT INTO memberships (id, user_id, org_id, role) VALUES (?, ?, ?, ?)",
            (f"membership-{organization_id}-{username}", username, organization_id, role),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_session(code: str, professor: str, state: str):
    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO sessions
                   (code, session_id, config_json, teams_json, professor_user_id, state)
               VALUES (?, ?, '{}', '[]', ?, ?)""",
            (code, f"session-{code}", professor, state),
        )
        conn.commit()
    finally:
        conn.close()


def _assert_error(response, status_code: int, code: str):
    assert response.status_code == status_code, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["requestId"] == "req-organizations-test"


def test_routes_use_owner_cookie_and_csrf_foundation_dependencies(app: FastAPI):
    routes = {
        (next(iter(route.methods)), route.path): route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/admin/v2")
    }
    for method, path in (
        ("GET", "/api/admin/v2/overview"),
        ("GET", "/api/admin/v2/organizations"),
        ("GET", "/api/admin/v2/organizations/{organization_id}"),
    ):
        calls = [dependency.call for dependency in routes[(method, path)].dependant.dependencies]
        assert require_admin_session in calls
    for method, path in (
        ("POST", "/api/admin/v2/organizations"),
        ("PATCH", "/api/admin/v2/organizations/{organization_id}"),
    ):
        calls = [dependency.call for dependency in routes[(method, path)].dependant.dependencies]
        assert require_csrf_session in calls


def test_anonymous_overview_is_denied_by_owner_cookie_auth(app: FastAPI):
    with TestClient(app) as client:
        response = client.get("/api/admin/v2/overview")
    _assert_error(response, 401, "ADMIN_AUTH_REQUIRED")


def test_overview_returns_typed_aggregate_counts(owner_client: TestClient):
    _insert_org("org-a", "Alpha", slug="alpha")
    _insert_user("prof-a", "professor")
    _insert_user("student-a", "student")
    _insert_membership("org-a", "prof-a", "professor")
    _insert_membership("org-a", "student-a", "student")
    _insert_session("ACTIVE1", "prof-a", "active")
    _insert_session("DONE001", "prof-a", "completed")

    response = owner_client.get("/api/admin/v2/overview")

    assert response.status_code == 200
    assert response.json() == {
        "overview": {
            "organizationCount": 1,
            "activeOrganizationCount": 1,
            "userCount": 4,
            "professorCount": 2,
            "studentCount": 1,
            "sessionCount": 2,
            "activeSessionCount": 1,
        }
    }
    assert response.headers["cache-control"] == "no-store"


def test_organization_list_supports_search_filter_sort_and_cursor(owner_client: TestClient):
    _insert_org("org-a", "Alpha", slug="alpha", created_at="2026-07-28T10:00:00+00:00")
    _insert_org("org-b", "Beta", slug="beta", status="inactive", created_at="2026-07-28T11:00:00+00:00")
    _insert_org("org-g", "Gamma", slug="gamma", created_at="2026-07-28T12:00:00+00:00")

    filtered = owner_client.get(
        "/api/admin/v2/organizations",
        params={"search": "university", "status": "active", "sort": "-createdAt", "limit": 1},
    )
    assert filtered.status_code == 200, filtered.text
    first = filtered.json()
    assert first["totalCount"] == 2
    assert [item["name"] for item in first["organizations"]] == ["Gamma"]
    assert first["pageInfo"]["hasNextPage"] is True
    assert first["pageInfo"]["nextCursor"]
    item = first["organizations"][0]
    assert set(item) == {
        "id", "name", "universityName", "slug", "status", "createdBy",
        "createdAt", "version", "professorCount", "studentCount",
        "sessionCount", "activeSessionCount",
    }

    second = owner_client.get(
        "/api/admin/v2/organizations",
        params={
            "search": "university",
            "status": "active",
            "sort": "-createdAt",
            "limit": 1,
            "cursor": first["pageInfo"]["nextCursor"],
        },
    )
    assert [item["name"] for item in second.json()["organizations"]] == ["Alpha"]
    assert second.json()["pageInfo"] == {"nextCursor": None, "hasNextPage": False}


def test_cursor_cannot_be_reused_for_a_different_query(owner_client: TestClient):
    _insert_org("org-a", "Alpha", slug="alpha")
    _insert_org("org-b", "Beta", slug="beta")
    cursor = owner_client.get(
        "/api/admin/v2/organizations", params={"limit": 1}
    ).json()["pageInfo"]["nextCursor"]

    response = owner_client.get(
        "/api/admin/v2/organizations", params={"limit": 1, "search": "beta", "cursor": cursor}
    )
    _assert_error(response, 400, "ADMIN_CURSOR_INVALID")


def test_create_is_unique_atomic_audited_and_idempotent(owner_client: TestClient):
    headers = {"Idempotency-Key": "create-alpha"}
    payload = {"name": "Alpha School", "universityName": "Alpha University"}

    first = owner_client.post("/api/admin/v2/organizations", json=payload, headers=headers)
    replay = owner_client.post("/api/admin/v2/organizations", json=payload, headers=headers)

    assert first.status_code == 201, first.text
    assert replay.status_code == first.status_code
    assert replay.json() == first.json()
    assert replay.headers["etag"] == first.headers["etag"]
    assert replay.headers["location"] == first.headers["location"]
    organization = first.json()["organization"]
    assert organization["name"] == "Alpha School"
    assert organization["universityName"] == "Alpha University"
    assert organization["slug"] == "alpha-school"
    assert organization["status"] == "active"
    assert organization["createdBy"] == "owner"

    conn = db.connect()
    try:
        assert conn.execute("SELECT COUNT(*) FROM organizations").fetchone()[0] == 1
        audit = conn.execute(
            "SELECT action, target_json FROM admin_audit_events"
        ).fetchone()
        assert audit["action"] == "organization.create"
        assert organization["id"] in audit["target_json"]
    finally:
        conn.close()

    conflict = owner_client.post(
        "/api/admin/v2/organizations",
        json={"name": "Different Name", "slug": "alpha-school"},
        headers={"Idempotency-Key": "create-duplicate"},
    )
    _assert_error(conflict, 409, "ADMIN_ORGANIZATION_CONFLICT")


def test_create_requires_idempotency_key(owner_client: TestClient):
    response = owner_client.post(
        "/api/admin/v2/organizations", json={"name": "No Retry Safety"}
    )
    _assert_error(response, 400, "ADMIN_IDEMPOTENCY_KEY_INVALID")


def test_detail_and_patch_use_etag_optimistic_concurrency_and_audit(owner_client: TestClient):
    _insert_org("org-a", "Alpha", slug="alpha")
    detail = owner_client.get("/api/admin/v2/organizations/org-a")
    assert detail.status_code == 200
    etag = detail.headers["etag"]
    assert etag == f'"{detail.json()["organization"]["version"]}"'

    missing = owner_client.patch(
        "/api/admin/v2/organizations/org-a",
        json={"name": "Alpha Two"},
        headers={"Idempotency-Key": "patch-missing"},
    )
    _assert_error(missing, 428, "ADMIN_PRECONDITION_REQUIRED")

    stale = owner_client.patch(
        "/api/admin/v2/organizations/org-a",
        json={"name": "Alpha Two"},
        headers={"Idempotency-Key": "patch-stale", "If-Match": '"orgv_stale"'},
    )
    _assert_error(stale, 409, "ADMIN_VERSION_CONFLICT")

    headers = {"Idempotency-Key": "patch-alpha", "If-Match": etag}
    updated = owner_client.patch(
        "/api/admin/v2/organizations/org-a",
        json={"name": "Alpha Two", "status": "inactive"},
        headers=headers,
    )
    replay = owner_client.patch(
        "/api/admin/v2/organizations/org-a",
        json={"name": "Alpha Two", "status": "inactive"},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert replay.status_code == 200
    assert replay.json() == updated.json()
    assert replay.headers["etag"] == updated.headers["etag"]
    assert updated.json()["organization"]["name"] == "Alpha Two"
    assert updated.json()["organization"]["status"] == "inactive"
    assert updated.headers["etag"] != etag

    conn = db.connect()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE action='organization.update'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_missing_organization_has_stable_not_found(owner_client: TestClient):
    response = owner_client.get("/api/admin/v2/organizations/missing")
    _assert_error(response, 404, "ADMIN_ORGANIZATION_NOT_FOUND")
