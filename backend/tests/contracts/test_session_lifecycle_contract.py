"""Contracts for session lifecycle, capacity, tenancy, and announcements."""
from datetime import datetime, timedelta, timezone
import re
import pytest
from fastapi.testclient import TestClient
from auth import _create_token
from database import db
from main import app
from models import SessionConfiguration, SessionState, TeamConfig
from security import hash_password

client=TestClient(app)

def H(sub,role):
    token=_create_token({"sub":sub,"role":role,"exp":(datetime.now(timezone.utc)+timedelta(minutes=15)).timestamp()})
    return {"Authorization":f"Bearer {token}"}

@pytest.fixture(autouse=True)
def clean():
    for store in (db.sessions,db.decisions,db.announcements,db.results,db.team_states): store.clear()
    with db._get_conn() as c:
        for table in ("class_enrollments","classes","memberships","organizations","sessions","users"):
            c.execute(f"DELETE FROM {table}")
        c.commit()
    for name,role in (("owner-x","owner"),("prof-a","professor"),("prof-b","professor"),("student-a","student")):
        db.create_user(name,hash_password("Contract123!"),role,name)
    db.get_or_create_organization("org-a", "Organization A")
    db.get_or_create_organization("org-b", "Organization B")
    db.add_membership("prof-a", "org-a", "professor")
    db.add_membership("prof-b", "org-b", "professor")

def create(prof="prof-a",max_humans=2,ai=1,class_id=None):
    body={"config":{"totalRounds":2,"numberOfAICompetitors":ai},"teams":[],"created_by":"ignored","maxHumanTeams":max_humans}
    if class_id: body["classId"]=class_id
    r=client.post("/api/sessions",json=body,headers=H(prof,"professor")); assert r.status_code==201,r.text
    return r.json()["code"]


def test_bearer_creation_is_durably_idempotent_and_payload_bound():
    headers = {**H("prof-a", "professor"), "Idempotency-Key": "ios-retry-key-0001"}
    body = {
        "config": {"totalRounds": 2, "numberOfAICompetitors": 1},
        "teams": [],
        "maxHumanTeams": 2,
    }
    first = client.post("/api/sessions", json=body, headers=headers)
    replay = client.post("/api/sessions", json=body, headers=headers)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert len(db.list_sessions(professor_user_id="prof-a")) == 1

    conflicting = client.post(
        "/api/sessions",
        json={**body, "maxHumanTeams": 3},
        headers=headers,
    )
    assert conflicting.status_code == 409

def test_create_exact_response_ai_generation_and_stored_tenant():
    code=create(ai=3)
    r=client.get(f"/api/sessions/{code}",headers=H("prof-a","professor"))
    assert r.status_code==200
    body=r.json()
    assert set(body)=={"id","code","config","teams","currentRound","state","results","created_by","created_at","maxHumanTeams","scenarioId","scenarioVersion"}
    assert re.fullmatch(r"BIZ-[A-Z0-9]{4}",code)
    assert [t["teamName"] for t in body["teams"]]==["AI-Aggressive-1","AI-Quality-2","AI-Lowcost-3"]
    assert all(t["isAI"] for t in body["teams"])
    assert db.get_session_professor_user_id(code)=="prof-a"

def test_create_rejects_missing_or_foreign_class():
    cls=db.create_class("prof-b","Foreign","x")
    body={"config":{"totalRounds":2},"classId":"missing"}
    assert client.post("/api/sessions",json=body,headers=H("prof-a","professor")).status_code==404
    foreign=client.post("/api/sessions",json={"config":{"totalRounds":2},"classId":cls["id"]},headers=H("prof-a","professor"))
    assert foreign.status_code==403 and foreign.json()=={"detail":"Not your class"}

def test_join_capacity_counts_humans_only_and_failed_join_does_not_mutate():
    code=create(max_humans=1,ai=2)
    first=client.put(f"/api/sessions/{code}/join",json={"teamName":"Human-1","studentId":"student-a"},headers=H("student-a","student"))
    assert first.status_code==200
    assert first.json()=={"teamId":"Human-1","teamName":"Human-1","round":0,"state":"creating"}
    second=client.put(f"/api/sessions/{code}/join",json={"teamName":"Human-2","studentId":"student-b"},headers=H("student-b","student"))
    assert second.status_code==400 and second.json()=={"detail":"Maximum team capacity reached"}
    assert [t.teamName for t in db.get_session(code).teams]==["AI-Aggressive-1","AI-Quality-2","Human-1"]

def test_join_duplicate_and_finished_state_errors():
    code=create(ai=0)
    payload={"teamName":"Alpha","studentId":"student-a"}
    student_a_headers=H("student-a","student")
    assert client.put(f"/api/sessions/{code}/join",json=payload,headers=student_a_headers).status_code==200
    # Same student re-joining the same team is now idempotent (returns 200)
    idempotent=client.put(f"/api/sessions/{code}/join",json=payload,headers=student_a_headers)
    assert idempotent.status_code==200
    # A DIFFERENT student trying to join the same team name gets 409
    duplicate=client.put(f"/api/sessions/{code}/join",json={"teamName":"Alpha","studentId":"student-b"},headers=H("student-b","student"))
    assert duplicate.status_code==409 and duplicate.json()=={"detail":"Team name already taken by another student"}
    db.update_session(code,{"state":SessionState.FINISHED})
    blocked=client.put(f"/api/sessions/{code}/join",json={"teamName":"Beta","studentId":"student-b"},headers=H("student-b","student"))
    assert blocked.status_code==400 and blocked.json()=={"detail":"Session is finished, cannot join"}

def test_status_exact_contract_and_auth():
    code=create(ai=0)
    client.put(f"/api/sessions/{code}/join",json={"teamName":"Alpha","studentId":"student-a"},headers=H("student-a","student"))
    db.decisions[code]={1:{"Alpha":object()}}
    assert client.get(f"/api/sessions/{code}/status").status_code==401
    r=client.get(f"/api/sessions/{code}/status",headers=H("student-a","student"))
    assert r.status_code==200
    assert r.json()=={"sessionId":db.get_session(code).id,"code":code,"state":"creating","currentRound":0,"totalRounds":2,"teamsSubmitted":0,"totalTeams":1,"humanTeams":1}

def test_reads_scope_professors_and_redact_public_and_student_identity_data():
    code=create(ai=0)
    client.put(f"/api/sessions/{code}/join",json={"teamName":"Alpha","studentId":"student-a"},headers=H("student-a","student"))
    assert client.get(f"/api/sessions/{code}",headers=H("prof-b","professor")).status_code==403
    assert client.get(f"/api/sessions/{code}/status",headers=H("prof-b","professor")).status_code==403
    public=client.get(f"/api/sessions/{code}/public")
    assert public.status_code==200
    assert "teams" not in public.json() and "config" not in public.json()
    student=client.get(f"/api/sessions/{code}",headers=H("student-a","student"))
    assert student.status_code==200
    assert [team.get("studentId") for team in student.json()["teams"]]==["student-a"]

@pytest.mark.parametrize("method,suffix",[("post","start"),("post","end"),("delete","")])
def test_state_changes_require_owning_professor_or_owner(method,suffix):
    code=create(ai=0); url=f"/api/sessions/{code}"+(f"/{suffix}" if suffix else "")
    call=getattr(client,method)
    assert call(url).status_code==401
    assert call(url,headers=H("student-a","student")).status_code==403
    foreign=call(url,headers=H("prof-b","professor"))
    assert foreign.status_code==403 and foreign.json()=={"detail":"Not your session"}
    # Use a fresh session because successful end/delete mutate it.
    own_code=create(ai=0); own_url=f"/api/sessions/{own_code}"+(f"/{suffix}" if suffix else "")
    assert call(own_url,headers=H("owner-x","owner")).status_code in (200,204)

def test_start_end_and_delete_exact_contracts():
    start_code=create(ai=0)
    started=client.post(f"/api/sessions/{start_code}/start",headers=H("prof-a","professor"))
    assert started.status_code==200
    assert started.json()=={"status":"started","sessionId":db.get_session(start_code).id,"code":start_code}
    assert db.get_session(start_code).currentRound==1 and db.get_session(start_code).state.value=="active"
    again=client.post(f"/api/sessions/{start_code}/start",headers=H("prof-a","professor"))
    assert again.status_code==409 and again.json()=={
        "detail":"Session state changed; refresh and retry"
    }
    ended=client.post(f"/api/sessions/{start_code}/end",headers=H("prof-a","professor"))
    assert ended.status_code==200 and ended.json()=={"status":"ended","finalResults":None}
    delete_code=create(ai=0)
    deleted=client.delete(f"/api/sessions/{delete_code}",headers=H("prof-a","professor"))
    assert deleted.status_code==204 and deleted.content==b""
    assert db.get_session(delete_code) is None

def test_announcements_auth_tenant_identity_and_exact_list_contract():
    code=create(ai=0); payload={"message":"Round one","authorId":"spoofed","authorName":"Professor A"}
    assert client.post(f"/api/sessions/{code}/announcements",json=payload).status_code==401
    assert client.post(f"/api/sessions/{code}/announcements",json=payload,headers=H("student-a","student")).status_code==403
    foreign=client.post(f"/api/sessions/{code}/announcements",json=payload,headers=H("prof-b","professor"))
    assert foreign.status_code==403 and foreign.json()=={"detail":"Not your session"}
    created=client.post(f"/api/sessions/{code}/announcements",json=payload,headers=H("prof-a","professor"))
    assert created.status_code==200 and set(created.json())=={"status","announcementId"}
    assert created.json()["status"]=="sent"
    assert client.get(f"/api/sessions/{code}/announcements").status_code==401
    listing=client.get(f"/api/sessions/{code}/announcements",headers=H("student-a","student"))
    assert listing.status_code==200 and len(listing.json())==1
    item=listing.json()[0]
    assert set(item)=={"id","sessionId","message","authorId","authorName","timestamp"}
    assert item["id"]==created.json()["announcementId"]
    assert item["sessionId"]==db.get_session(code).id
    assert item["message"]=="Round one" and item["authorId"]=="prof-a"

    db.sessions.pop(code, None)
    assert db.delete_session(code) is True
    with db._get_conn() as connection:
        remaining=connection.execute(
            "SELECT COUNT(*) FROM announcements WHERE session_id=?", (item["sessionId"],)
        ).fetchone()[0]
    assert remaining==0
