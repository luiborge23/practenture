"""Security contracts for Admin V2 SES invitation delivery."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from admin_v2.dependencies import require_admin_session, require_recent_auth_session
from admin_v2.errors import AdminError, error_envelope
from admin_v2.invitations_routes import router
from database import db


@pytest.fixture
def app() -> FastAPI:
    isolated = FastAPI()

    @isolated.middleware("http")
    async def context(request: Request, call_next):
        request.state.request_id = "req-email-delivery"
        return await call_next(request)

    @isolated.exception_handler(AdminError)
    async def admin_error(request: Request, exc: AdminError):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_envelope(exc.code, exc.message, request.state.request_id),
            headers=exc.headers,
        )

    isolated.include_router(router, prefix="/api/admin/v2")
    return isolated


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    owner = SimpleNamespace(
        record=SimpleNamespace(owner_user_id="owner", role="owner"),
        user={"username": "owner", "role": "owner", "status": "active"},
    )
    app.dependency_overrides[require_admin_session] = lambda: owner
    app.dependency_overrides[require_recent_auth_session] = lambda: owner
    with TestClient(app) as test_client:
        yield test_client


def _org() -> None:
    conn = db.connect()
    try:
        conn.execute(
            """INSERT INTO organizations
               (id, name, university_name, slug, status, created_by, created_at)
               VALUES ('org-email', 'Email', 'Email University', 'email-u', 'active', 'owner', datetime('now'))"""
        )
        conn.commit()
    finally:
        conn.close()


def _create(client: TestClient) -> dict:
    response = client.post(
        "/api/admin/v2/invitations",
        json={"organizationId": "org-email", "intendedEmail": "Professor@Example.edu"},
        headers={"Idempotency-Key": "create-email"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _send(client: TestClient, invitation: dict, key: str = "send-email"):
    return client.post(
        f"/api/admin/v2/invitations/{invitation['invitation']['id']}/send-email",
        json={
            "intendedEmail": invitation["invitation"]["intendedEmail"],
            "secret": invitation["secret"],
        },
        headers={"Idempotency-Key": key},
    )


def test_ses_send_requires_current_secret_exact_email_is_idempotent_and_redacted(client, monkeypatch):
    _org()
    invitation = _create(client)
    calls: list[tuple[str, str]] = []

    def accepted(*, recipient: str, secret: str):
        calls.append((recipient, secret))
        return SimpleNamespace(message_id="010203040506070809abcdef")

    monkeypatch.setattr("admin_v2.invitation_email.send_professor_invitation", accepted)
    first = _send(client, invitation)
    replay = _send(client, invitation)

    assert first.status_code == 200, first.text
    assert replay.status_code == 200
    assert first.json() == replay.json()
    assert first.json()["delivery"]["status"] == "SENT"
    assert first.json()["delivery"]["providerMessageId"] == "ses:010203...cdef"
    assert "secret" not in json.dumps(first.json()).casefold()
    assert calls == [("professor@example.edu", invitation["secret"])]

    conn = db.connect()
    try:
        delivery = conn.execute(
            "SELECT state, provider_message_id, request_fingerprint FROM invitation_email_deliveries"
        ).fetchone()
        assert tuple(delivery)[:2] == ("accepted", "010203040506070809abcdef")
        assert invitation["secret"] not in " ".join(str(v) for v in delivery)
        audit = conn.execute(
            "SELECT metadata_json FROM admin_audit_events WHERE action='invitation.email_delivery'"
        ).fetchone()[0]
        assert "010203040506070809abcdef" not in audit
        assert "ses:010203...cdef" in audit
        persisted = " ".join(
            str(value)
            for row in conn.execute("SELECT response_body_json, request_fingerprint FROM admin_idempotency_records")
            for value in row
        )
        assert invitation["secret"] not in persisted
    finally:
        conn.close()


def test_ses_send_rejects_wrong_email_or_rotated_secret_without_calling_provider(client, monkeypatch):
    _org()
    invitation = _create(client)
    calls = []
    monkeypatch.setattr(
        "admin_v2.invitation_email.send_professor_invitation",
        lambda **kwargs: calls.append(kwargs),
    )
    wrong_email = client.post(
        f"/api/admin/v2/invitations/{invitation['invitation']['id']}/send-email",
        json={"intendedEmail": "other@example.edu", "secret": invitation["secret"]},
        headers={"Idempotency-Key": "wrong-email"},
    )
    assert wrong_email.status_code == 409
    assert wrong_email.json()["error"]["code"] == "ADMIN_INVITATION_EMAIL_PROOF_INVALID"

    rotated = client.post(
        f"/api/admin/v2/invitations/{invitation['invitation']['id']}/resend",
        headers={"Idempotency-Key": "rotate-before-send"},
    ).json()
    stale = _send(client, invitation, "stale-secret")
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "ADMIN_INVITATION_EMAIL_PROOF_INVALID"
    assert calls == []
    assert rotated["secret"] != invitation["secret"]


def test_provider_failure_records_failed_not_sent_and_keeps_manual_fallback(client, monkeypatch):
    _org()
    invitation = _create(client)

    def failed(**_kwargs):
        raise AdminError(503, "ADMIN_EMAIL_DELIVERY_FAILED", "SES could not accept the invitation email")

    monkeypatch.setattr("admin_v2.invitation_email.send_professor_invitation", failed)
    response = _send(client, invitation)
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ADMIN_EMAIL_DELIVERY_FAILED"

    conn = db.connect()
    try:
        row = conn.execute(
            "SELECT state, provider_message_id, failed_code FROM invitation_email_deliveries"
        ).fetchone()
        assert tuple(row) == ("failed", None, "ADMIN_EMAIL_DELIVERY_FAILED")
        assert conn.execute(
            "SELECT outcome FROM admin_audit_events WHERE action='invitation.email_delivery'"
        ).fetchone()[0] == "failed"
    finally:
        conn.close()
