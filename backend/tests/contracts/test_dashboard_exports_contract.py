"""Contracts for dashboard tenancy and professor CSV exports."""
from __future__ import annotations

import csv
import io
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from auth import _create_token
from database import db
from main import app
from models import RoundResult, SessionConfiguration, SessionState, TeamConfig
from security import hash_password

client = TestClient(app)
DASHBOARD_KEYS = {
    "code", "state", "currentRound", "totalRounds", "teamsCount",
    "aiTeamsCount", "totalTeams", "totalSubmissions", "lastRound",
}
GRADES_HEADER = [
    "Team", "Round", "Revenue", "Costs", "Profit", "Market Share", "S/Q Rating",
    "Reputation", "Cumulative Profit", "Cash", "Inventory", "Equity", "Debt",
    "Shares Outstanding", "EPS", "ROE", "Stock Price", "EPS Score", "ROE Score",
    "Stock Price Score", "Image Score", "Credit Score", "Total Score", "Unit Cost",
    "Production Cost", "Marketing Cost", "Wholesale Demand", "Internet Demand",
    "Amazon Demand", "Total Sold",
]
LEADERBOARD_HEADER = [
    "Rank", "Team", "Revenue", "Costs", "Profit", "Cumulative Profit", "Cash",
    "Equity", "Debt", "Stock Price", "EPS", "ROE", "Total Score", "S/Q Rating",
    "Reputation", "Market Share",
]


def _headers(sub: str, role: str) -> dict[str, str]:
    token = _create_token({
        "sub": sub, "role": role,
        "exp": (datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp(),
    })
    return {"Authorization": f"Bearer {token}"}


def _seed_user(username: str, role: str) -> None:
    db.create_user(username, hash_password("Contract123!"), role, username)


@pytest.fixture(autouse=True)
def isolated_state():
    for store in (db.sessions, db.decisions, db.announcements, db.results, db.team_states):
        store.clear()
    with db._get_conn() as conn:
        for table in ("class_enrollments", "classes", "sessions", "users"):
            conn.execute(f"DELETE FROM {table}")
        conn.commit()
    for username, role in (("owner-x", "owner"), ("prof-a", "professor"),
                           ("prof-b", "professor"), ("student-a", "student")):
        _seed_user(username, role)
    yield


def _class(professor: str) -> dict:
    return db.create_class(professor, f"{professor} class", "Contract class")


def _session(professor: str, class_id: str | None = None) -> str:
    code = db.create_session(
        config=SessionConfiguration(totalRounds=2, numberOfAICompetitors=0),
        teams=[TeamConfig(teamName="Human", isAI=False), TeamConfig(teamName="Bot", isAI=True)],
        created_by=professor, professor_user_id=professor, class_id=class_id,
    )
    db.update_session(code, {"state": SessionState.ACTIVE, "currentRound": 1})
    db.decisions[code] = {1: {"Human": object()}}
    return code


def _result(team: str, score: float, revenue: float) -> RoundResult:
    return RoundResult(
        teamId=team, round=1, revenue=revenue, costs=1234.5, profit=revenue - 1234.5,
        marketShare=.2345, sqRating=6.25, reputation=72.5, cumulativeProfit=8765.5,
        cash=12345.5, inventory=88.0, equity=20000.0, debt=3000.0,
        sharesOutstanding=10000, eps=1.2345, roe=.1234, stockPrice=45.67,
        epsScore=80, roeScore=81, stockPriceScore=82, imageScore=83, creditScore=84,
        totalScore=score, unitCost=31.25, productionCost=5000, marketingCost=2500,
        demand={"wholesale": 100, "internet": 50, "amazon": 25, "totalSold": 175},
    )


def _rows(response) -> list[list[str]]:
    return list(csv.reader(io.StringIO(response.text)))


def test_dashboard_exact_fields_counts_and_professor_owner_filtering():
    code_a = _session("prof-a")
    code_b = _session("prof-b")
    own = client.get("/api/dashboard/sessions", headers=_headers("prof-a", "professor"))
    owner = client.get("/api/dashboard/sessions", headers=_headers("owner-x", "owner"))
    assert own.status_code == owner.status_code == 200
    assert len(own.json()["sessions"]) == 1
    item = own.json()["sessions"][0]
    assert set(item) == DASHBOARD_KEYS
    assert item == {
        "code": code_a, "state": "active", "currentRound": 1, "totalRounds": 2,
        "teamsCount": 1, "aiTeamsCount": 1, "totalTeams": 2,
        "totalSubmissions": 1, "lastRound": 1,
    }
    assert {s["code"] for s in owner.json()["sessions"]} == {code_a, code_b}


def test_student_dashboard_is_limited_to_enrolled_classes():
    class_a = _class("prof-a")
    class_b = _class("prof-b")
    code_a = _session("prof-a", class_a["id"])
    _session("prof-b", class_b["id"])
    assert db.enroll_student(class_a["id"], "student-a")
    response = client.get("/api/dashboard/sessions", headers=_headers("student-a", "student"))
    assert response.status_code == 200
    assert [s["code"] for s in response.json()["sessions"]] == [code_a]


def test_dashboard_requires_valid_auth_and_unknown_role_sees_empty_list():
    assert client.get("/api/dashboard/sessions").status_code == 401
    invalid = client.get(
        "/api/dashboard/sessions", headers={"Authorization": "Bearer invalid.token"}
    )
    unknown = client.get("/api/dashboard/sessions", headers=_headers("service-x", "service"))
    assert invalid.status_code == 401
    assert unknown.status_code == 200
    assert unknown.json() == {"sessions": []}


def test_grade_export_exact_csv_contract_and_formatting():
    code = _session("prof-a")
    db.results[code] = {1: [_result("Alpha", 91.5, 10000.25)]}
    response = client.get(
        f"/api/sessions/{code}/export/grades", headers=_headers("prof-a", "professor")
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert response.headers["content-disposition"] == f'attachment; filename="bizsimai_{code}_grades.csv"'
    rows = _rows(response)
    assert rows[0] == GRADES_HEADER
    assert len(rows) == 2
    assert rows[1] == [
        "Alpha", "1", "10,000.25", "1,234.50", "8,765.75", "0.2345", "6.25",
        "72.50", "8,765.50", "12,345.50", "88.00", "20,000.00", "3,000.00",
        "10,000.00", "1.2345", "0.1234", "45.67", "80.00", "81.00", "82.00",
        "83.00", "84.00", "91.50", "31.25", "5,000.00", "2,500.00",
        "100.00", "50.00", "25.00", "175.00",
    ]


def test_leaderboard_export_ranks_and_preserves_latest_operating_values():
    code = _session("prof-a")
    db.results[code] = {1: [_result("Second", 70, 7000), _result("First", 95, 9500)]}
    response = client.get(
        f"/api/sessions/{code}/export/leaderboard", headers=_headers("prof-a", "professor")
    )
    assert response.status_code == 200
    assert response.headers["content-disposition"] == f'attachment; filename="bizsimai_{code}_leaderboard.csv"'
    rows = _rows(response)
    assert rows[0] == LEADERBOARD_HEADER
    assert [row[:2] for row in rows[1:]] == [["1", "First"], ["2", "Second"]]
    assert rows[1][2:5] == ["9,500.00", "1,234.50", "8,265.50"]
    assert rows[1][12] == "95.00"


@pytest.mark.parametrize("suffix", ["grades", "leaderboard"])
def test_exports_require_owner_or_owning_professor(suffix):
    code = _session("prof-a")
    db.results[code] = {1: [_result("Alpha", 90, 9000)]}
    url = f"/api/sessions/{code}/export/{suffix}"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=_headers("student-a", "student")).status_code == 403
    foreign = client.get(url, headers=_headers("prof-b", "professor"))
    assert foreign.status_code == 403
    assert foreign.json() == {"detail": "Not your session"}
    assert client.get(url, headers=_headers("owner-x", "owner")).status_code == 200


@pytest.mark.parametrize("suffix,detail", [
    ("grades", "No results available for export"), ("leaderboard", "No results available")
])
def test_exports_distinguish_missing_session_from_no_results(suffix, detail):
    missing = client.get(
        f"/api/sessions/BIZ-NONE/export/{suffix}", headers=_headers("prof-a", "professor")
    )
    assert missing.status_code == 404
    assert missing.json() == {"detail": "Session not found"}
    code = _session("prof-a")
    empty = client.get(
        f"/api/sessions/{code}/export/{suffix}", headers=_headers("prof-a", "professor")
    )
    assert empty.status_code == 400
    assert empty.json() == {"detail": detail}
