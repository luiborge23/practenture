"""End-to-end contracts for professor password recovery by SES code."""
from __future__ import annotations

import hashlib
import uuid

import pytest
from fastapi.testclient import TestClient

from database import db
from main import app
from password_reset_email import PasswordResetDeliveryError
from security import hash_password, verify_password


@pytest.fixture
def professor():
    suffix = uuid.uuid4().hex
    username = f"recovery-{suffix}"
    email = f"recovery-{suffix}@example.com"
    assert db.create_user(
        username,
        hash_password("Original123!"),
        "professor",
        name="Recovery Professor",
        email=email,
    )
    yield username, email
    with db._lock:
        conn = db._get_conn()
        conn.execute("DELETE FROM password_reset_tokens WHERE user_id=?", (username,))
        conn.execute("DELETE FROM refresh_tokens WHERE user_id=?", (username,))
        conn.execute("DELETE FROM users WHERE username=?", (username,))
        conn.commit()


def test_known_professor_receives_code_and_can_reset(professor, monkeypatch):
    username, email = professor
    delivered: dict[str, str] = {}

    def capture(*, recipient: str, code: str) -> str:
        delivered.update(recipient=recipient, code=code)
        return "ses-message-id"

    monkeypatch.setattr("password_reset_email.send_password_reset_code", capture)
    client = TestClient(app)
    requested = client.post("/api/auth/forgot-password", json={"email": email})
    assert requested.status_code == 200
    assert requested.json() == {"status": "email_sent", "token": None}
    assert delivered["recipient"] == email

    with db._lock:
        row = db._get_conn().execute(
            "SELECT token_hash, used FROM password_reset_tokens WHERE user_id=?",
            (username,),
        ).fetchone()
    assert row["token_hash"] == hashlib.sha256(delivered["code"].encode()).hexdigest()
    assert delivered["code"] != row["token_hash"]
    assert row["used"] == 0

    completed = client.post(
        "/api/auth/reset-password",
        json={"token": delivered["code"], "newPassword": "Replacement123!"},
    )
    assert completed.status_code == 200
    assert completed.json() == {"status": "password_reset"}
    user = db.get_user(username)
    assert user is not None
    assert verify_password("Replacement123!", user["password_hash"])

    replay = client.post(
        "/api/auth/reset-password",
        json={"token": delivered["code"], "newPassword": "AnotherPass123!"},
    )
    assert replay.status_code == 400


def test_unknown_email_is_indistinguishable_and_sends_nothing(monkeypatch):
    monkeypatch.setattr(
        "password_reset_email.send_password_reset_code",
        lambda **kwargs: pytest.fail(f"unexpected send: {kwargs}"),
    )
    response = TestClient(app).post(
        "/api/auth/forgot-password",
        json={"email": f"missing-{uuid.uuid4().hex}@example.com"},
    )
    assert response.status_code == 200
    assert response.json() == {"status": "email_sent", "token": None}


def test_delivery_failure_invalidates_undisclosed_code(professor, monkeypatch):
    username, email = professor

    def fail(**_kwargs):
        raise PasswordResetDeliveryError("provider unavailable")

    monkeypatch.setattr("password_reset_email.send_password_reset_code", fail)
    response = TestClient(app).post("/api/auth/forgot-password", json={"email": email})
    assert response.status_code == 200
    assert response.json() == {"status": "email_sent", "token": None}
    with db._lock:
        rows = db._get_conn().execute(
            "SELECT used FROM password_reset_tokens WHERE user_id=?", (username,)
        ).fetchall()
    assert rows and all(row["used"] == 1 for row in rows)
