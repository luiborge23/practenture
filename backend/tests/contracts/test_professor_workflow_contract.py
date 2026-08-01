"""Browser Professor command-center contracts: CSRF, ownership, and lifecycle."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from auth import _create_access_token
from database import db
from main import app
from routers.decisions import _round_processing_locks
from security import hash_password


def professor_client(user_id: str) -> tuple[TestClient, dict[str, str]]:
    db.create_user(
        user_id,
        hash_password("WorkflowTest123!"),
        "professor",
        user_id,
        f"{user_id}@example.edu",
    )
    org_id = f"org-{uuid.uuid4().hex}"
    with db._lock:
        conn = db._get_conn()
        conn.execute(
            "INSERT INTO organizations (id, name, created_by) VALUES (?, ?, ?)",
            (org_id, f"Organization for {user_id}", "test"),
        )
        conn.execute(
            "INSERT INTO memberships (id, user_id, org_id, role) VALUES (?, ?, ?, 'professor')",
            (uuid.uuid4().hex, user_id, org_id),
        )
        conn.commit()
    client = TestClient(app, base_url="https://practenture.com")
    token = _create_access_token(
        {
            "sub": user_id,
            "role": "professor",
            "name": user_id,
            "exp": (datetime.now(timezone.utc) + timedelta(hours=1)).timestamp(),
        }
    )
    csrf = f"csrf-{uuid.uuid4().hex}"
    client.cookies.set("practenture_professor_session", token)
    client.cookies.set("practenture_professor_csrf", csrf)
    return client, {
        "X-CSRF-Token": csrf,
        "Idempotency-Key": f"create-{uuid.uuid4().hex}",
    }


def create_payload(*, class_id: str | None = None, ai: int = 1) -> dict:
    return {
        "config": {
            "name": "Web Operations Lab",
            "courseCode": "OPS 510",
            "semester": "Fall 2026",
            "totalRounds": 2,
            "numberOfAICompetitors": ai,
            "marketType": "moderate",
            "aiDifficulty": "medium",
            "scoringMetric": "investor_score",
        },
        "teams": [],
        "created_by": "attacker-selected-owner",
        "maxHumanTeams": 12,
        "classId": class_id,
        "scenarioId": "athletic-footwear-classic",
        "scenarioVersion": "1.0.0",
    }


def test_portal_mutations_require_matching_csrf_and_server_select_owner():
    professor = f"web-prof-{uuid.uuid4().hex}"
    client, csrf = professor_client(professor)
    payload = create_payload()

    assert client.post(
        "/api/professor-portal/sessions",
        json=payload,
        headers={"Idempotency-Key": csrf["Idempotency-Key"]},
    ).status_code == 403
    assert client.post(
        "/api/professor-portal/sessions",
        json=payload,
        headers={
            "X-CSRF-Token": "wrong",
            "Idempotency-Key": csrf["Idempotency-Key"],
        },
    ).status_code == 403

    created = client.post("/api/professor-portal/sessions", json=payload, headers=csrf)
    assert created.status_code == 201, created.text
    code = created.json()["code"]
    try:
        assert db.get_session_professor_user_id(code) == professor
        session = db.get_session(code)
        assert session is not None
        assert session.created_by == "professor"
        assert session.config.name == "Web Operations Lab"
        assert session.config.courseCode == "OPS 510"
        assert session.config.semester == "Fall 2026"

        progress = client.get("/api/professor-portal/progress")
        assert progress.status_code == 200
        item = next(item for item in progress.json()["sessions"] if item["code"] == code)
        assert item == {
            "code": code,
            "name": "Web Operations Lab",
            "state": "creating",
            "currentRound": 0,
            "totalRounds": 2,
            "humanTeams": 0,
            "maxHumanTeams": 12,
            "currentRoundSubmissions": 0,
            "totalSubmissions": 0,
            "scenarioId": "athletic-footwear-classic",
            "scenarioVersion": "1.0.0",
        }
    finally:
        db.delete_session(code)
        client.close()


def test_portal_session_creation_is_durably_idempotent():
    professor = f"idempotent-prof-{uuid.uuid4().hex}"
    client, headers = professor_client(professor)
    payload = create_payload()
    first = client.post(
        "/api/professor-portal/sessions", json=payload, headers=headers
    )
    assert first.status_code == 201, first.text
    code = first.json()["code"]
    try:
        replay = client.post(
            "/api/professor-portal/sessions", json=payload, headers=headers
        )
        assert replay.status_code == 201
        assert replay.json() == first.json()

        changed = create_payload()
        changed["config"]["totalRounds"] = 3
        conflict = client.post(
            "/api/professor-portal/sessions", json=changed, headers=headers
        )
        assert conflict.status_code == 409
        assert conflict.json() == {
            "detail": "Idempotency key was already used for another request"
        }
        with db._lock:
            count = db._get_conn().execute(
                "SELECT COUNT(*) FROM sessions WHERE professor_user_id=?",
                (professor,),
            ).fetchone()[0]
        assert count == 1
    finally:
        db.delete_session(code)
        client.close()


def test_portal_class_scope_lifecycle_announcement_and_foreign_denial():
    owner = f"owner-{uuid.uuid4().hex}"
    foreign = f"foreign-{uuid.uuid4().hex}"
    owner_client, owner_csrf = professor_client(owner)
    foreign_client, foreign_csrf = professor_client(foreign)

    own_class = owner_client.post(
        "/api/professor-portal/classes",
        json={"name": "Operations Alpha", "description": "Morning section"},
        headers=owner_csrf,
    )
    assert own_class.status_code == 201, own_class.text
    class_id = own_class.json()["id"]

    denied_class = foreign_client.post(
        "/api/professor-portal/sessions",
        json=create_payload(class_id=class_id),
        headers=foreign_csrf,
    )
    assert denied_class.status_code == 403
    assert denied_class.json() == {"detail": "Not your class"}

    created = owner_client.post(
        "/api/professor-portal/sessions",
        json=create_payload(class_id=class_id),
        headers=owner_csrf,
    )
    assert created.status_code == 201, created.text
    code = created.json()["code"]
    try:
        for path in ("start", "process-round", "end"):
            denied = foreign_client.post(
                f"/api/professor-portal/sessions/{code}/{path}", headers=foreign_csrf
            )
            assert denied.status_code == 403, (path, denied.text)
            assert denied.json() == {"detail": "Not your session"}
        assert foreign_client.delete(
            f"/api/professor-portal/sessions/{code}", headers=foreign_csrf
        ).status_code == 403
        denied_monitor = foreign_client.get(
            f"/api/professor-portal/progress/{code}/monitor"
        )
        assert denied_monitor.status_code == 403
        assert denied_monitor.json() == {"detail": "Not your session"}

        started = owner_client.post(
            f"/api/professor-portal/sessions/{code}/start", headers=owner_csrf
        )
        assert started.status_code == 200, started.text
        active_session = db.get_session(code)
        assert active_session is not None
        assert active_session.state.value == "active"
        assert active_session.currentRound == 1

        announced = owner_client.post(
            f"/api/professor-portal/sessions/{code}/announcements",
            json={"message": "Round one starts now.", "authorName": "Professor"},
            headers=owner_csrf,
        )
        assert announced.status_code == 200, announced.text

        processed = owner_client.post(
            f"/api/professor-portal/sessions/{code}/process-round", headers=owner_csrf
        )
        assert processed.status_code == 200, processed.text
        round_two = db.get_session(code)
        assert round_two is not None
        assert round_two.currentRound == 2

        monitor = owner_client.get(f"/api/professor-portal/progress/{code}/monitor")
        assert monitor.status_code == 200, monitor.text
        monitor_payload = monitor.json()
        assert monitor_payload["code"] == code
        assert monitor_payload["state"] == "active"
        assert monitor_payload["currentRound"] == 2
        assert len(monitor_payload["teams"]) == 1
        assert monitor_payload["teams"][0]["isAI"] is True
        assert monitor_payload["teams"][0]["currentRoundSubmitted"] is False
        assert monitor_payload["rounds"][0]["round"] == 1
        assert len(monitor_payload["rounds"][0]["results"]) == 1

        ended = owner_client.post(
            f"/api/professor-portal/sessions/{code}/end", headers=owner_csrf
        )
        assert ended.status_code == 200, ended.text
        finished = db.get_session(code)
        assert finished is not None
        assert finished.state.value == "finished"

        removed = owner_client.delete(
            f"/api/professor-portal/sessions/{code}", headers=owner_csrf
        )
        assert removed.status_code == 204, removed.text
        assert db.get_session(code) is None
    finally:
        if db.get_session(code):
            db.delete_session(code)
        owner_client.close()
        foreign_client.close()


def test_portal_creation_options_are_authenticated_and_owned():
    user = f"options-{uuid.uuid4().hex}"
    client, csrf = professor_client(user)
    unauthenticated = TestClient(app, base_url="https://practenture.com")
    assert unauthenticated.get("/api/professor-portal/scenarios").status_code == 401
    assert unauthenticated.get("/api/professor-portal/classes").status_code == 401

    created_class = client.post(
        "/api/professor-portal/classes",
        json={"name": "My class", "description": ""},
        headers=csrf,
    )
    assert created_class.status_code == 201
    scenarios = client.get("/api/professor-portal/scenarios")
    assert scenarios.status_code == 200
    assert scenarios.json()["scenarios"][0]["scenario_id"] == "athletic-footwear-classic"
    classes = client.get("/api/professor-portal/classes")
    assert classes.status_code == 200
    assert [item["id"] for item in classes.json()["classes"]] == [created_class.json()["id"]]
    client.close()
    unauthenticated.close()


def test_portal_rejects_overlapping_round_processing():
    class AlreadyLocked:
        def locked(self) -> bool:
            return True

    owner = f"lock-owner-{uuid.uuid4().hex}"
    client, csrf = professor_client(owner)
    created = client.post(
        "/api/professor-portal/sessions", json=create_payload(), headers=csrf
    )
    assert created.status_code == 201, created.text
    code = created.json()["code"]
    try:
        started = client.post(
            f"/api/professor-portal/sessions/{code}/start", headers=csrf
        )
        assert started.status_code == 200, started.text
        _round_processing_locks[code] = AlreadyLocked()  # type: ignore[assignment]
        overlapping = client.post(
            f"/api/professor-portal/sessions/{code}/process-round", headers=csrf
        )
        assert overlapping.status_code == 409
        assert overlapping.json() == {
            "detail": "Round processing is already in progress"
        }
    finally:
        _round_processing_locks.pop(code, None)
        db.delete_session(code)
        client.close()


def test_portal_reloads_persisted_role_and_account_status():
    professor = f"persisted-role-{uuid.uuid4().hex}"
    client, _ = professor_client(professor)
    try:
        with db._get_conn() as connection:
            connection.execute(
                "UPDATE users SET role='student' WHERE username=?", (professor,)
            )
            connection.commit()
        assert client.get("/api/professor-portal/session").status_code == 403

        with db._get_conn() as connection:
            connection.execute(
                "UPDATE users SET role='professor', status='suspended' WHERE username=?",
                (professor,),
            )
            connection.commit()
        suspended = client.get("/api/professor-portal/session")
        # The earlier persisted-role rejection invalidates the stale browser
        # session; suspension must continue to deny that invalidated cookie.
        assert suspended.status_code == 401
        assert suspended.json() == {"detail": "Invalid or expired token"}
    finally:
        client.close()
