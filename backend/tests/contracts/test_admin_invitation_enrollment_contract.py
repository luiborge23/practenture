"""End-to-end contracts for Admin V2 professor invitation redemption."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import hashlib

import pytest
from fastapi.testclient import TestClient

import auth
import auth_enrollment
from auth_enrollment import ensure_identity_schema
from database import db
from main import app
from models import SessionConfiguration, TeamConfig
from security import hash_password


client = TestClient(app)
SECRET = "test-admin-invitation-secret-with-enough-entropy"
ORG_ID = "org-invitation-contract"
EMAIL = "professor@example.edu"


@pytest.fixture(autouse=True)
def clean_invitation_state():
    ensure_identity_schema()
    for store in (db.sessions, db.decisions, db.announcements, db.results, db.team_states):
        store.clear()
    with db._get_conn() as conn:
        for table in (
            "auth_identities",
            "refresh_tokens",
            "memberships",
            "professor_invitations",
            "sessions",
            "organizations",
            "users",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.execute(
            "INSERT INTO organizations (id,name,university_name,created_by) VALUES (?,?,?,?)",
            (ORG_ID, "Contract University", "Contract University", "admin-contract"),
        )
        conn.commit()
    yield


def seed_invitation(*, email: str = EMAIL, secret: str = SECRET) -> None:
    with db._get_conn() as conn:
        conn.execute(
            """INSERT INTO professor_invitations
               (id,secret_hash,masked_code,organization_id,intended_email,status,
                expires_at,max_uses,use_count,issued_by)
               VALUES (?,?,?,?,?,'active',?,1,0,?)""",
            (
                "inv-contract",
                hashlib.sha256(secret.encode()).hexdigest(),
                "test...ropy",
                ORG_ID,
                email,
                (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                "admin-contract",
            ),
        )
        conn.commit()


def activate(*, email: str = EMAIL, username: str = "invited-professor"):
    return client.post(
        "/api/auth/password/activate-professor",
        json={
            "professorCode": SECRET,
            "username": username,
            "email": email,
            "name": "Invited Professor",
            "password": "SecurePass123!",
            "confirmPassword": "SecurePass123!",
        },
    )


def test_admin_invitation_atomically_creates_professor_and_org_membership():
    seed_invitation()

    response = activate()

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["role"] == "professor"
    assert body["userId"] == "invited-professor"
    assert body["accessToken"]
    assert body["refreshToken"]
    user = db.get_user("invited-professor")
    assert user is not None
    assert user["role"] == "professor"
    assert user["email"] == EMAIL
    with db._get_conn() as conn:
        invitation = conn.execute(
            "SELECT status,use_count FROM professor_invitations WHERE id='inv-contract'"
        ).fetchone()
        membership = conn.execute(
            "SELECT org_id,role FROM memberships WHERE user_id='invited-professor'"
        ).fetchone()
    assert tuple(invitation) == ("redeemed", 1)
    assert tuple(membership) == (ORG_ID, "professor")


def test_invitation_email_mismatch_rolls_back_without_consuming_secret():
    seed_invitation()

    response = activate(email="attacker@example.edu")

    assert response.status_code == 400
    assert response.json() == {"detail": "Invitation email does not match"}
    assert db.get_user("invited-professor") is None
    with db._get_conn() as conn:
        invitation = conn.execute(
            "SELECT status,use_count FROM professor_invitations WHERE id='inv-contract'"
        ).fetchone()
    assert tuple(invitation) == ("active", 0)


def test_admin_invitation_is_single_use():
    seed_invitation()
    assert activate().status_code == 201

    replay = activate(username="second-professor")

    assert replay.status_code == 409
    assert replay.json() == {"detail": "Invitation was already used"}
    assert db.get_user("second-professor") is None


def test_account_conflict_does_not_consume_invitation():
    seed_invitation()
    db.create_user(
        "invited-professor",
        hash_password("SecurePass123!"),
        "professor",
        "Existing Professor",
        "existing@example.edu",
    )

    response = activate()

    assert response.status_code == 409
    assert response.json() == {"detail": "Username already exists"}
    with db._get_conn() as conn:
        invitation = conn.execute(
            "SELECT status,use_count FROM professor_invitations WHERE id='inv-contract'"
        ).fetchone()
    assert tuple(invitation) == ("active", 0)


def test_concurrent_redemption_has_exactly_one_winner():
    seed_invitation()

    def redeem(username: str):
        with TestClient(app) as concurrent_client:
            return concurrent_client.post(
                "/api/auth/password/activate-professor",
                json={
                    "professorCode": SECRET,
                    "username": username,
                    "email": EMAIL,
                    "name": "Invited Professor",
                    "password": "SecurePass123!",
                    "confirmPassword": "SecurePass123!",
                },
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(redeem, ("professor-a", "professor-b")))

    assert sorted(response.status_code for response in responses) == [201, 409]
    loser = next(response for response in responses if response.status_code == 409)
    assert loser.json() == {"detail": "Invitation was already used"}
    with db._get_conn() as conn:
        invitation = conn.execute(
            "SELECT status,use_count,redeemed_by FROM professor_invitations WHERE id='inv-contract'"
        ).fetchone()
        created_users = conn.execute(
            "SELECT username FROM users WHERE username IN ('professor-a','professor-b')"
        ).fetchall()
        memberships = conn.execute(
            "SELECT user_id,org_id,role FROM memberships WHERE org_id=?",
            (ORG_ID,),
        ).fetchall()
    assert invitation["status"] == "redeemed"
    assert invitation["use_count"] == 1
    assert invitation["redeemed_by"] in {"professor-a", "professor-b"}
    assert [row["username"] for row in created_users] == [invitation["redeemed_by"]]
    assert [tuple(row) for row in memberships] == [
        (invitation["redeemed_by"], ORG_ID, "professor")
    ]


def test_mid_enrollment_failure_rolls_back_every_record(monkeypatch):
    seed_invitation()

    def fail_membership(*_args, **_kwargs):
        raise RuntimeError("injected membership failure")

    monkeypatch.setattr(auth_enrollment, "_add_invitation_membership", fail_membership)

    with pytest.raises(RuntimeError, match="injected membership failure"):
        auth_enrollment.activate_password_professor(
            code=SECRET,
            username="rollback-professor",
            email=EMAIL,
            name="Rollback Professor",
            university_name="Caller University Must Not Persist",
            password_hash=hash_password("SecurePass123!"),
        )

    with db._get_conn() as conn:
        invitation = conn.execute(
            "SELECT status,use_count,redeemed_by,redeemed_at FROM professor_invitations WHERE id='inv-contract'"
        ).fetchone()
        user = conn.execute(
            "SELECT 1 FROM users WHERE username='rollback-professor'"
        ).fetchone()
        identity = conn.execute(
            "SELECT 1 FROM auth_identities WHERE user_id='rollback-professor'"
        ).fetchone()
        membership = conn.execute(
            "SELECT 1 FROM memberships WHERE user_id='rollback-professor'"
        ).fetchone()
    assert tuple(invitation) == ("active", 0, None, None)
    assert user is None
    assert identity is None
    assert membership is None


def test_social_enrollment_uses_provider_subject_and_never_merges_by_email():
    seed_invitation()
    db.create_user(
        "password-professor",
        hash_password("SecurePass123!"),
        "professor",
        "Existing Password Professor",
        EMAIL,
    )

    created = auth_enrollment.enroll_social_professor(
        provider="google",
        subject="google-stable-subject-123",
        email=EMAIL,
        name="Google Professor",
        code=SECRET,
        password_hash=hash_password("unusable-social-password"),
    )
    returned = auth_enrollment.enroll_social_professor(
        provider="google",
        subject="google-stable-subject-123",
        email="different-claim@example.edu",
        name="Changed Claim Must Not Create Another User",
        code="not-needed-for-returning-provider-user",
        password_hash=hash_password("different-unusable-password"),
    )

    assert created["username"].startswith("google_")
    assert created["username"] != "password-professor"
    assert returned["username"] == created["username"]
    with db._get_conn() as conn:
        invitation = conn.execute(
            "SELECT status,use_count FROM professor_invitations WHERE id='inv-contract'"
        ).fetchone()
        identity = conn.execute(
            "SELECT user_id,provider,provider_subject,email FROM auth_identities WHERE provider='google'"
        ).fetchone()
        memberships = conn.execute(
            "SELECT user_id,org_id,role FROM memberships WHERE org_id=?",
            (ORG_ID,),
        ).fetchall()
    assert tuple(invitation) == ("redeemed", 1)
    assert tuple(identity) == (
        created["username"],
        "google",
        "google-stable-subject-123",
        EMAIL,
    )
    assert [tuple(row) for row in memberships] == [
        (created["username"], ORG_ID, "professor")
    ]


def test_verified_google_identity_requires_then_consumes_invitation(monkeypatch):
    seed_invitation()
    claims = {
        "sub": "google-http-contract-subject",
        "email": EMAIL,
        "name": "Google HTTP Professor",
    }
    monkeypatch.setattr(
        auth,
        "verify_google_id_token",
        lambda _token, _audience: claims,
    )

    authorization_required = client.post(
        "/api/auth/login",
        json={"provider": "google", "id_token": "verified-provider-token"},
    )
    assert authorization_required.status_code == 200
    assert authorization_required.json()["professorCodeRequired"] is True
    assert authorization_required.json()["providerEmail"] == EMAIL
    assert db.get_user("google_http_contract_subject") is None

    claims.pop("email")
    authorization_retry = client.post(
        "/api/auth/login",
        json={"provider": "google", "id_token": "verified-provider-token"},
    )
    assert authorization_retry.status_code == 200
    assert authorization_retry.json()["providerEmail"] == EMAIL

    activated = client.post(
        "/api/auth/login",
        json={
            "provider": "google",
            "id_token": "verified-provider-token",
            "professor_code": SECRET,
        },
    )
    assert activated.status_code == 200, activated.text
    body = activated.json()
    assert body["role"] == "professor"
    assert body["accessToken"]
    assert body["professorCodeRequired"] is False
    with db._get_conn() as conn:
        pending_identity = conn.execute(
            """SELECT 1 FROM pending_provider_identities
               WHERE provider='google' AND provider_subject='google-http-contract-subject'"""
        ).fetchone()
    assert pending_identity is None

    returning = client.post(
        "/api/auth/login",
        json={"provider": "google", "id_token": "verified-provider-token"},
    )
    assert returning.status_code == 200, returning.text
    assert returning.json()["userId"] == body["userId"]


def test_expired_pending_provider_email_cannot_redeem_invitation(monkeypatch):
    seed_invitation()
    claims = {
        "sub": "expired-pending-provider-subject",
        "email": EMAIL,
        "name": "Expired Pending Provider",
    }
    monkeypatch.setattr(auth, "verify_google_id_token", lambda _token, _audience: claims)

    initial = client.post(
        "/api/auth/login",
        json={"provider": "google", "id_token": "verified-provider-token"},
    )
    assert initial.status_code == 200
    with db._get_conn() as conn:
        conn.execute(
            """UPDATE pending_provider_identities SET expires_at=0
               WHERE provider='google' AND provider_subject='expired-pending-provider-subject'"""
        )
        conn.commit()
    claims.pop("email")

    response = client.post(
        "/api/auth/login",
        json={
            "provider": "google",
            "id_token": "verified-provider-token",
            "professor_code": SECRET,
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": "Provider email is unavailable. Cancel and sign in again before using an invitation."
    }
    with db._get_conn() as conn:
        identity = conn.execute(
            """SELECT 1 FROM auth_identities
               WHERE provider='google' AND provider_subject='expired-pending-provider-subject'"""
        ).fetchone()
    assert identity is None


@pytest.mark.parametrize("status", ["revoked", "expired"])
def test_inactive_invitation_is_rejected_without_creating_account(status: str):
    seed_invitation()
    with db._get_conn() as conn:
        conn.execute(
            "UPDATE professor_invitations SET status=? WHERE id='inv-contract'",
            (status,),
        )
        conn.commit()

    response = activate()

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid, revoked, or expired invitation"}
    assert db.get_user("invited-professor") is None


def test_professor_portal_uses_http_only_cookie_and_filters_progress_by_owner():
    seed_invitation()
    with TestClient(app, base_url="https://practenture.com") as portal:
        response = portal.post(
            "/api/professor-portal/activate",
            headers={"Origin": "https://practenture.com"},
            json={
                "professorCode": SECRET,
                "username": "invited-professor",
                "email": EMAIL,
                "name": "Invited Professor",
                "password": "SecurePass123!",
                "confirmPassword": "SecurePass123!",
            },
        )
        assert response.status_code == 201, response.text
        cookie = response.headers["set-cookie"]
        assert "practenture_professor_session=" in cookie
        assert "HttpOnly" in cookie
        assert "SameSite=strict" in cookie

        own_code = db.create_session(
            SessionConfiguration(totalRounds=3),
            [TeamConfig(teamName="Alpha", studentId="student-alpha")],
            created_by="invited-professor",
            professor_user_id="invited-professor",
        )
        db.create_user(
            "other-professor",
            hash_password("SecurePass123!"),
            "professor",
            "Other Professor",
            "other@example.edu",
        )
        foreign_code = db.create_session(
            SessionConfiguration(totalRounds=2),
            [],
            created_by="other-professor",
            professor_user_id="other-professor",
        )

        progress = portal.get("/api/professor-portal/progress")
        assert progress.status_code == 200, progress.text
        assert [item["code"] for item in progress.json()["sessions"]] == [own_code]
        for export_name in ("grades", "leaderboard"):
            denied = portal.get(
                f"/api/professor-portal/progress/{foreign_code}/{export_name}"
            )
            assert denied.status_code == 403
            assert denied.json() == {"detail": "Not your session"}

        csrf = portal.cookies.get("practenture_professor_csrf")
        assert csrf
        logout = portal.post(
            "/api/professor-portal/logout",
            headers={"X-CSRF-Token": csrf},
        )
        assert logout.status_code == 204
        assert portal.get("/api/professor-portal/progress").status_code == 401
        login = portal.post(
            "/api/professor-portal/login",
            headers={"Origin": "https://practenture.com"},
            json={
                "provider": "password",
                "username": "invited-professor",
                "password": "SecurePass123!",
            },
        )
        assert login.status_code == 200, login.text
        assert portal.get("/api/professor-portal/progress").status_code == 200


def test_professor_portal_pre_authentication_mutations_require_same_origin():
    with TestClient(app, base_url="https://practenture.com") as portal:
        payload = {
            "provider": "password",
            "username": "nobody",
            "password": "NotARealPassword123!",
        }
        missing = portal.post("/api/professor-portal/login", json=payload)
        assert missing.status_code == 403
        assert missing.json() == {"detail": "Invalid request origin"}
        foreign = portal.post(
            "/api/professor-portal/login",
            headers={"Origin": "https://attacker.example"},
            json=payload,
        )
        assert foreign.status_code == 403
        assert foreign.json() == {"detail": "Invalid request origin"}


def test_public_login_is_the_secure_professor_portal_shell():
    response = client.get("/login")
    assert response.status_code == 200
    assert "Professor portal" in response.text
    assert 'id="activation-success"' in response.text
    assert 'id="forgot-password"' in response.text
    assert 'id="reset-form"' in response.text
    assert 'id="reset-success"' in response.text
    assert "portal.css?v=4" in response.text
    assert "portal.js?v=8" in response.text
    assert 'id="create-form"' in response.text
    assert 'id="nav-security"' in response.text
    assert 'id="mfa-start-form"' in response.text
    assert 'id="mfa-recovery-panel"' in response.text
    assert 'id="action-dialog"' in response.text
    assert "localhost:8000" not in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
