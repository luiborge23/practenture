"""Cross-connection SQLite concurrency contracts for session state."""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from database import Database
from models import SessionConfiguration


def databases(tmp_path, monkeypatch) -> tuple[Database, Database]:
    path = tmp_path / "session-concurrency.db"
    monkeypatch.setenv("PRACTENTURE_DB_PATH", str(path))
    return Database(), Database()


def run_together(first, second):
    barrier = threading.Barrier(2)

    def wrapped(operation):
        barrier.wait(timeout=5)
        return operation()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(wrapped, operation) for operation in (first, second)]
        return [future.result(timeout=10) for future in futures]


def test_concurrent_joins_cannot_exceed_capacity(tmp_path, monkeypatch):
    db_a, db_b = databases(tmp_path, monkeypatch)
    for username, role in (("professor-a", "professor"), ("student-a", "student"), ("student-b", "student")):
        assert db_a.create_user(username, "test-hash", role, username)
    organization = db_a.get_or_create_organization("Concurrency University", "professor-a")
    for username, role in (("professor-a", "professor"), ("student-a", "student"), ("student-b", "student")):
        assert db_a.add_membership(username, organization["id"], role)
    code = db_a.create_session(
        SessionConfiguration(totalRounds=2),
        [],
        created_by="professor",
        professor_user_id="professor-a",
        organization_id=organization["id"],
        max_human_teams=1,
    )

    outcomes = run_together(
        lambda: db_a.join_session_atomic(
            code=code, team_name="Alpha", student_id="student-a"
        ),
        lambda: db_b.join_session_atomic(
            code=code, team_name="Beta", student_id="student-b"
        ),
    )

    assert sorted(outcome["status"] for outcome in outcomes) == ["capacity", "joined"]
    with db_a._lock:
        teams_json = db_a._get_conn().execute(
            "SELECT teams_json FROM sessions WHERE code=?", (code,)
        ).fetchone()[0]
    import json

    assert len(json.loads(teams_json)) == 1


def test_start_and_end_have_one_compare_and_swap_winner(tmp_path, monkeypatch):
    db_a, db_b = databases(tmp_path, monkeypatch)
    code = db_a.create_session(
        SessionConfiguration(totalRounds=2),
        [],
        created_by="professor",
        professor_user_id="professor-a",
    )

    outcomes = run_together(
        lambda: db_a.transition_session_owned(
            code=code,
            professor_user_id="professor-a",
            allowed_states=("creating",),
            new_state="active",
            current_round=1,
        ),
        lambda: db_b.transition_session_owned(
            code=code,
            professor_user_id="professor-a",
            allowed_states=("creating",),
            new_state="finished",
        ),
    )

    assert sum(outcome is not None for outcome in outcomes) == 1
    with db_a._lock:
        row = db_a._get_conn().execute(
            "SELECT state, version FROM sessions WHERE code=?", (code,)
        ).fetchone()
    assert row["state"] in {"active", "finished"}
    assert row["version"] == 1


def test_round_finalization_has_one_cross_connection_winner(tmp_path, monkeypatch):
    db_a, db_b = databases(tmp_path, monkeypatch)
    code = db_a.create_session(
        SessionConfiguration(totalRounds=2),
        [],
        created_by="professor",
        professor_user_id="professor-a",
    )
    assert db_a.transition_session_owned(
        code=code,
        professor_user_id="professor-a",
        allowed_states=("creating",),
        new_state="active",
        current_round=1,
    )

    operation = lambda database: database.finalize_round_atomic(
        code=code,
        professor_user_id="professor-a",
        expected_round=1,
        engine_results=[],
        new_team_states={},
        total_rounds=2,
    )
    outcomes = run_together(lambda: operation(db_a), lambda: operation(db_b))

    assert sorted(outcomes) == [False, True]
    with db_a._lock:
        row = db_a._get_conn().execute(
            "SELECT state, current_round, version FROM sessions WHERE code=?", (code,)
        ).fetchone()
    assert dict(row) == {"state": "active", "current_round": 2, "version": 2}
