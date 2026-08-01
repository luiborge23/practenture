"""Executable contracts for class tenancy and professor-code administration."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from auth import _create_token
from database import db
from main import app
from security import hash_password

client = TestClient(app)


def _headers(username: str, role: str) -> dict[str, str]:
    token = _create_token({
        "sub": username,
        "role": role,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp(),
    })
    return {"Authorization": f"Bearer {token}"}


def _seed_user(username: str, role: str, name: str = "", email: str = "") -> None:
    db.create_user(
        username=username,
        password_hash=hash_password("Contract123!"),
        role=role,
        name=name or username,
        email=email,
    )


@pytest.fixture(autouse=True)
def isolated_contract_state():
    db.sessions.clear()
    db.decisions.clear()
    db.announcements.clear()
    db.results.clear()
    db.team_states.clear()
    with db._get_conn() as conn:
        for table in (
            "class_enrollments",
            "classes",
            "professor_codes",
            "memberships",
            "organizations",
            "sessions",
            "users",
        ):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    _seed_user("owner-contract", "owner", "Contract Owner", "owner@example.test")
    _seed_user("prof-a", "professor", "Professor A", "a@example.test")
    _seed_user("prof-b", "professor", "Professor B", "b@example.test")
    _seed_user("student-a", "student", "Student A", "student@example.test")
    _seed_user("student-b", "student", "Student B", "student-b@example.test")
    db.get_or_create_organization("org-a", "Organization A")
    db.get_or_create_organization("org-b", "Organization B")
    db.add_membership("prof-a", "org-a", "professor")
    db.add_membership("prof-b", "org-b", "professor")
    yield


def _create_class(headers: dict[str, str], name: str = "Strategy 401") -> dict:
    response = client.post(
        "/api/classes",
        json={"name": name, "description": "Capstone"},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_and_list_class_exact_contract_and_tenant_isolation():
    created = _create_class(_headers("prof-a", "professor"))
    assert set(created) == {
        "id", "professor_user_id", "name", "description", "join_code", "is_active"
    }
    assert created["professor_user_id"] == "prof-a"
    assert created["name"] == "Strategy 401"
    assert created["description"] == "Capstone"
    assert created["is_active"] is True
    assert re.fullmatch(r"BIZ-[A-Z0-9]{4}", created["join_code"])

    own = client.get("/api/classes", headers=_headers("prof-a", "professor"))
    other = client.get("/api/classes", headers=_headers("prof-b", "professor"))
    assert own.status_code == other.status_code == 200
    assert own.json() == {"classes": [created]}
    assert other.json() == {"classes": []}


def test_class_create_requires_professor_and_valid_body():
    no_auth = client.post("/api/classes", json={"name": "Forbidden"})
    student = client.post(
        "/api/classes", json={"name": "Forbidden"}, headers=_headers("student-a", "student")
    )
    invalid = client.post("/api/classes", json={}, headers=_headers("prof-a", "professor"))
    assert no_auth.status_code == 401
    assert student.status_code == 403
    # The application intentionally maps RequestValidationError to 400.
    assert invalid.status_code == 400
    assert invalid.json()["detail"][0]["loc"] == ["body", "name"]


def test_get_class_enforces_ownership_but_owner_can_read():
    created = _create_class(_headers("prof-a", "professor"))
    own = client.get(f"/api/classes/{created['id']}", headers=_headers("prof-a", "professor"))
    foreign = client.get(f"/api/classes/{created['id']}", headers=_headers("prof-b", "professor"))
    owner = client.get(f"/api/classes/{created['id']}", headers=_headers("owner-contract", "owner"))
    missing = client.get("/api/classes/not-found", headers=_headers("prof-a", "professor"))
    assert own.status_code == owner.status_code == 200
    assert own.json() == owner.json() == created
    assert foreign.status_code == 403
    assert foreign.json() == {"detail": "Not your class"}
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Class not found"}


def test_student_join_idempotency_my_classes_and_roster_exact_contract():
    created = _create_class(_headers("prof-a", "professor"))
    first = client.post(
        "/api/classes/join",
        json={"join_code": created["join_code"]},
        headers=_headers("student-a", "student"),
    )
    second = client.post(
        "/api/classes/join",
        json={"join_code": created["join_code"]},
        headers=_headers("student-a", "student"),
    )
    assert first.status_code == second.status_code == 200
    assert first.json() == {
        "status": "enrolled", "class_id": created["id"],
        "class_name": created["name"], "message": None,
    }
    assert second.json() == {
        "status": "enrolled", "class_id": created["id"],
        "class_name": created["name"], "message": "Already enrolled in this class",
    }

    mine = client.get("/api/classes/my/classes", headers=_headers("student-a", "student"))
    assert mine.status_code == 200, mine.text
    assert mine.json() == {"classes": [created]}

    roster = client.get(
        f"/api/classes/{created['id']}/students", headers=_headers("prof-a", "professor")
    )
    assert roster.status_code == 200
    students = roster.json()["students"]
    assert len(students) == 1
    assert set(students[0]) == {"username", "name", "email", "enrolled_at"}
    assert students[0]["username"] == "student-a"
    assert students[0]["name"] == "Student A"
    assert students[0]["email"] == "student@example.test"
    assert students[0]["enrolled_at"]


def test_join_rejects_invalid_code_and_deleted_professor():
    invalid = client.post(
        "/api/classes/join", json={"join_code": "BIZ-NOPE"},
        headers=_headers("student-a", "student"),
    )
    assert invalid.status_code == 404
    assert invalid.json() == {"detail": "Invalid or inactive class code"}

    created = _create_class(_headers("prof-a", "professor"))
    with db._get_conn() as conn:
        conn.execute("DELETE FROM users WHERE username='prof-a'")
        conn.commit()
    gone = client.post(
        "/api/classes/join", json={"join_code": created["join_code"]},
        headers=_headers("student-a", "student"),
    )
    assert gone.status_code == 410
    assert "professor account has been removed" in gone.json()["detail"]


def test_owner_professor_code_create_list_and_role_gates():
    payload = {"university_name": "MIT", "notes": "Fall 2026"}
    created = client.post(
        "/api/professor/codes", json=payload, headers=_headers("owner-contract", "owner")
    )
    assert created.status_code == 201
    data = created.json()
    assert set(data) == {"code", "university_name", "notes", "used", "used_by"}
    assert re.fullmatch(r"PROF-[23456789A-HJ-NP-Z]{4}-[23456789A-HJ-NP-Z]{4}", data["code"])
    assert data | {"code": data["code"]} == {
        "code": data["code"], "university_name": "MIT", "notes": "Fall 2026",
        "used": False, "used_by": None,
    }

    listed = client.get("/api/professor/codes", headers=_headers("owner-contract", "owner"))
    assert listed.status_code == 200
    assert listed.json() == {"codes": [data]}

    for role, username in (("professor", "prof-a"), ("student", "student-a")):
        denied = client.post(
            "/api/professor/codes", json=payload, headers=_headers(username, role)
        )
        assert denied.status_code == 403
        assert denied.json() == {"detail": "Owner access required"}


def test_student_redeems_code_once_and_receives_camel_case_token_contract():
    made = client.post(
        "/api/professor/codes",
        json={"university_name": "MIT", "notes": "Promotion"},
        headers=_headers("owner-contract", "owner"),
    ).json()
    promoted = client.post(
        "/api/professor/redeem", json={"code": made["code"]},
        headers=_headers("student-a", "student"),
    )
    assert promoted.status_code == 200
    body = promoted.json()
    assert set(body) == {"status", "role", "accessToken", "tokenType"}
    assert body["status"] == "promoted"
    assert body["role"] == "professor"
    assert body["tokenType"] == "bearer"
    assert body["accessToken"]
    assert db.get_user("student-a")["role"] == "professor"

    reused = client.post(
        "/api/professor/redeem", json={"code": made["code"]},
        headers=_headers("student-b", "student"),
    )
    assert reused.status_code == 404
    assert reused.json() == {"detail": "Invalid, already used, or expired code"}


def test_professor_and_owner_cannot_redeem_professor_code():
    made = client.post(
        "/api/professor/codes", json={}, headers=_headers("owner-contract", "owner")
    ).json()
    professor = client.post(
        "/api/professor/redeem", json={"code": made["code"]},
        headers=_headers("prof-a", "professor"),
    )
    owner = client.post(
        "/api/professor/redeem", json={"code": made["code"]},
        headers=_headers("owner-contract", "owner"),
    )
    assert professor.status_code == owner.status_code == 400
    assert professor.json() == {"detail": "You are already a professor"}
    assert owner.json() == {"detail": "Owner cannot redeem professor code"}
