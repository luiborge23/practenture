"""Focused contracts and security tests for Admin V2 invitations."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from admin_v2.dependencies import require_admin_session, require_recent_auth_session
from admin_v2.errors import AdminError, error_envelope
from admin_v2.invitations_routes import router
from admin_v2.invitations_service import invitation_service
from database import db


@pytest.fixture
def app() -> FastAPI:
    isolated = FastAPI()

    @isolated.middleware("http")
    async def request_context(request: Request, call_next):
        request.state.request_id = "req-invitations-test"
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
    app.dependency_overrides[require_recent_auth_session] = lambda: owner_session
    with TestClient(app) as client:
        yield client


def _insert_org(organization_id: str = "org-a") -> None:
    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO organizations
               (id, name, university_name, slug, status, created_by, created_at)
               VALUES (?, 'Alpha', 'Alpha University', 'alpha', 'active', 'owner', ?)""",
            (organization_id, datetime.now(timezone.utc).isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def _insert_invitation(
    invitation_id: str,
    *,
    email: str = "prof@example.edu",
    status: str = "active",
    expires_at: datetime | None = None,
    created_at: datetime | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO professor_invitations
               (id, secret_hash, masked_code, organization_id, intended_email,
                status, expires_at, max_uses, use_count, issued_by)
               VALUES (?, ?, 'mask...code', 'org-a', ?, ?, ?, 1, 0, 'owner')""",
            (
                invitation_id,
                hashlib.sha256(f"secret-{invitation_id}".encode()).hexdigest(),
                email,
                status,
                (expires_at or now + timedelta(hours=48)).isoformat(),
            ),
        )
        conn.execute(
            """INSERT INTO admin_audit_events
               (id, request_id, actor_json, target_json, action, outcome,
                metadata_json, occurred_at)
               VALUES (?, ?, '{}', ?, 'invitation.create', 'success', '{}', ?)""",
            (
                f"audit-{invitation_id}",
                f"req-{invitation_id}",
                json.dumps({"type": "invitation", "id": invitation_id}),
                (created_at or now).isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def _assert_error(response, status_code: int, code: str):
    assert response.status_code == status_code, response.text
    assert response.json()["error"]["code"] == code
    assert response.json()["error"]["requestId"] == "req-invitations-test"


def _create(client: TestClient, key: str = "create-prof"):
    return client.post(
        "/api/admin/v2/invitations",
        json={
            "organizationId": "org-a",
            "intendedEmail": "Professor@Example.edu",
            "expiresInHours": 72,
            "notes": "Fall cohort",
            "changeTicket": "CHG-42",
        },
        headers={"Idempotency-Key": key},
    )


def test_routes_use_owner_reads_and_recent_auth_mutation_boundaries(app: FastAPI):
    routes = {
        (next(iter(route.methods)), route.path): route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith("/api/admin/v2")
    }
    for method, path in (
        ("GET", "/api/admin/v2/invitations"),
        ("GET", "/api/admin/v2/invitations/{invitationId}"),
    ):
        calls = [dependency.call for dependency in routes[(method, path)].dependant.dependencies]
        assert require_admin_session in calls
    for method, path in (
        ("POST", "/api/admin/v2/invitations"),
        ("POST", "/api/admin/v2/invitations/{invitationId}/revoke"),
        ("POST", "/api/admin/v2/invitations/{invitationId}/resend"),
    ):
        calls = [dependency.call for dependency in routes[(method, path)].dependant.dependencies]
        assert require_recent_auth_session in calls


def test_anonymous_read_is_denied_by_owner_cookie_auth(app: FastAPI):
    with TestClient(app) as client:
        response = client.get("/api/admin/v2/invitations")
    _assert_error(response, 401, "ADMIN_AUTH_REQUIRED")


def test_create_is_idempotent_audited_and_never_persists_plaintext_secret(
    owner_client: TestClient,
):
    _insert_org()

    first = _create(owner_client)
    replay = _create(owner_client)

    assert first.status_code == 201, first.text
    assert replay.status_code == 201
    assert replay.json() == first.json()
    assert first.headers["location"].endswith(first.json()["invitation"]["id"])
    body = first.json()
    assert len(body["secret"]) >= 32
    assert body["invitation"]["intendedEmail"] == "professor@example.edu"
    assert body["invitation"]["status"] == "ACTIVE"
    assert "secretHash" not in json.dumps(body)

    conn = db.connect()
    try:
        stored = conn.execute(
            "SELECT secret_hash FROM professor_invitations"
        ).fetchone()[0]
        assert stored == hashlib.sha256(body["secret"].encode()).hexdigest()
        assert body["secret"] not in stored
        idempotency_body = conn.execute(
            "SELECT response_body_json FROM admin_idempotency_records"
        ).fetchone()[0]
        assert body["secret"] not in idempotency_body
        audit_rows = conn.execute(
            "SELECT action, actor_json, target_json, metadata_json FROM admin_audit_events"
        ).fetchall()
        assert len(audit_rows) == 1
        assert audit_rows[0]["action"] == "invitation.create"
        assert body["secret"] not in json.dumps(dict(audit_rows[0]))
    finally:
        conn.close()


def test_create_requires_valid_org_payload_and_idempotency(owner_client: TestClient):
    missing_key = owner_client.post(
        "/api/admin/v2/invitations",
        json={"organizationId": "missing", "intendedEmail": "prof@example.edu"},
    )
    _assert_error(missing_key, 400, "ADMIN_IDEMPOTENCY_KEY_INVALID")

    missing_org = owner_client.post(
        "/api/admin/v2/invitations",
        json={"organizationId": "missing", "intendedEmail": "prof@example.edu"},
        headers={"Idempotency-Key": "missing-org"},
    )
    _assert_error(missing_org, 404, "ADMIN_ORGANIZATION_NOT_FOUND")

    invalid_email = owner_client.post(
        "/api/admin/v2/invitations",
        json={"organizationId": "missing", "intendedEmail": "not-email"},
        headers={"Idempotency-Key": "bad-email"},
    )
    assert invalid_email.status_code == 422


def test_list_detail_filter_and_bounded_opaque_cursor_never_reveal_secret(
    owner_client: TestClient,
):
    _insert_org()
    now = datetime.now(timezone.utc)
    _insert_invitation("inv-old", email="old@example.edu", created_at=now - timedelta(days=2))
    _insert_invitation("inv-new", email="new@example.edu", created_at=now - timedelta(days=1))
    _insert_invitation(
        "inv-expired",
        email="expired@example.edu",
        expires_at=now - timedelta(minutes=1),
        created_at=now,
    )

    first = owner_client.get(
        "/api/admin/v2/invitations",
        params={"status": "ACTIVE", "sort": "createdAt", "limit": 1},
    )
    assert first.status_code == 200, first.text
    result = first.json()
    assert result["totalCount"] == 2
    assert [item["id"] for item in result["invitations"]] == ["inv-old"]
    assert result["pageInfo"]["hasNextPage"] is True
    assert result["pageInfo"]["nextCursor"]
    assert "secret" not in json.dumps(result).casefold()

    second = owner_client.get(
        "/api/admin/v2/invitations",
        params={
            "status": "ACTIVE",
            "sort": "createdAt",
            "limit": 1,
            "cursor": result["pageInfo"]["nextCursor"],
        },
    )
    assert [item["id"] for item in second.json()["invitations"]] == ["inv-new"]
    assert second.json()["pageInfo"] == {"nextCursor": None, "hasNextPage": False}

    detail = owner_client.get("/api/admin/v2/invitations/inv-expired")
    assert detail.status_code == 200
    assert detail.json()["invitation"]["status"] == "EXPIRED"
    assert "secret" not in json.dumps(detail.json()).casefold()


def test_cursor_is_bound_to_the_exact_query(owner_client: TestClient):
    _insert_org()
    _insert_invitation("inv-a", email="a@example.edu")
    _insert_invitation("inv-b", email="b@example.edu")
    cursor = owner_client.get(
        "/api/admin/v2/invitations", params={"limit": 1}
    ).json()["pageInfo"]["nextCursor"]

    response = owner_client.get(
        "/api/admin/v2/invitations",
        params={"limit": 1, "search": "b@example.edu", "cursor": cursor},
    )
    _assert_error(response, 400, "ADMIN_CURSOR_INVALID")


def test_search_matches_operational_notes_ticket_and_organization(owner_client: TestClient):
    _insert_org()
    _insert_invitation("inv-searchable")
    conn = db.connect()
    try:
        conn.execute(
            "UPDATE professor_invitations SET notes=?, change_ticket=? WHERE id=?",
            ("Fall cohort onboarding", "CHG-2048", "inv-searchable"),
        )
        conn.commit()
    finally:
        conn.close()

    for search in ("fall cohort", "chg-2048", "org-a"):
        response = owner_client.get("/api/admin/v2/invitations", params={"search": search})
        assert response.status_code == 200, response.text
        assert [item["id"] for item in response.json()["invitations"]] == ["inv-searchable"]


def test_resend_rotates_secret_is_idempotent_and_secret_free_at_rest(
    owner_client: TestClient,
):
    _insert_org()
    created = _create(owner_client, "create-for-resend").json()
    invitation_id = created["invitation"]["id"]

    response = owner_client.post(
        f"/api/admin/v2/invitations/{invitation_id}/resend",
        json={"expiresInHours": 96},
        headers={"Idempotency-Key": "resend-one"},
    )
    replay = owner_client.post(
        f"/api/admin/v2/invitations/{invitation_id}/resend",
        json={"expiresInHours": 96},
        headers={"Idempotency-Key": "resend-one"},
    )

    assert response.status_code == 200, response.text
    assert replay.json() == response.json()
    assert response.json()["secret"] != created["secret"]
    assert response.json()["invitation"]["maskedCode"] != created["invitation"]["maskedCode"]

    conn = db.connect()
    try:
        stored = conn.execute(
            "SELECT secret_hash FROM professor_invitations WHERE id=?", (invitation_id,)
        ).fetchone()[0]
        assert stored == hashlib.sha256(response.json()["secret"].encode()).hexdigest()
        persisted = " ".join(
            str(value)
            for row in conn.execute(
                "SELECT response_body_json FROM admin_idempotency_records"
            ).fetchall()
            for value in row
        )
        assert response.json()["secret"] not in persisted
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE action='invitation.resend'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_revoke_is_terminal_idempotent_and_audited(owner_client: TestClient):
    _insert_org()
    invitation_id = _create(owner_client, "create-for-revoke").json()["invitation"]["id"]
    headers = {"Idempotency-Key": "revoke-one"}

    revoked = owner_client.post(
        f"/api/admin/v2/invitations/{invitation_id}/revoke",
        json={"reason": "Role no longer needed"},
        headers=headers,
    )
    replay = owner_client.post(
        f"/api/admin/v2/invitations/{invitation_id}/revoke",
        json={"reason": "Role no longer needed"},
        headers=headers,
    )

    assert revoked.status_code == 200, revoked.text
    assert replay.json() == revoked.json()
    assert revoked.json()["invitation"]["status"] == "REVOKED"
    assert revoked.json()["invitation"]["revokedBy"] == "owner"

    resend = owner_client.post(
        f"/api/admin/v2/invitations/{invitation_id}/resend",
        headers={"Idempotency-Key": "resend-revoked"},
    )
    _assert_error(resend, 409, "ADMIN_INVITATION_NOT_ACTIVE")

    conn = db.connect()
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE action='invitation.revoke'"
        ).fetchone()[0] == 1
    finally:
        conn.close()


def test_expired_invitation_rejects_terminal_mutations(owner_client: TestClient):
    _insert_org()
    _insert_invitation(
        "inv-expired", expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
    )

    revoke = owner_client.post(
        "/api/admin/v2/invitations/inv-expired/revoke",
        headers={"Idempotency-Key": "revoke-expired"},
    )
    resend = owner_client.post(
        "/api/admin/v2/invitations/inv-expired/resend",
        headers={"Idempotency-Key": "resend-expired"},
    )
    _assert_error(revoke, 409, "ADMIN_INVITATION_NOT_ACTIVE")
    _assert_error(resend, 409, "ADMIN_INVITATION_NOT_ACTIVE")


def test_missing_invitation_has_stable_not_found(owner_client: TestClient):
    detail = owner_client.get("/api/admin/v2/invitations/missing")
    _assert_error(detail, 404, "ADMIN_INVITATION_NOT_FOUND")
    revoke = owner_client.post(
        "/api/admin/v2/invitations/missing/revoke",
        headers={"Idempotency-Key": "revoke-missing"},
    )
    _assert_error(revoke, 404, "ADMIN_INVITATION_NOT_FOUND")


def test_concurrent_revocation_allows_exactly_one_active_to_terminal_transition(
    owner_session,
):
    _insert_org()
    _insert_invitation("inv-race")

    def revoke(key: str):
        try:
            result = invitation_service.revoke_invitation(
                session=owner_session,
                invitation_id="inv-race",
                reason="concurrency test",
                idempotency_key=key,
                request_id=f"req-{key}",
            )
            return result.response.status_code
        except AdminError as exc:
            return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(revoke, ("race-a", "race-b")))

    assert sorted(outcomes, key=str) == sorted(
        [200, "ADMIN_INVITATION_NOT_ACTIVE"], key=str
    )
    conn = db.connect()
    try:
        assert conn.execute(
            "SELECT status FROM professor_invitations WHERE id='inv-race'"
        ).fetchone()[0] == "revoked"
        assert conn.execute(
            "SELECT COUNT(*) FROM admin_audit_events WHERE action='invitation.revoke'"
        ).fetchone()[0] == 1
    finally:
        conn.close()
