"""Contracts for professor pre-creation, password change, and owner audit logs."""
from datetime import datetime, timedelta, timezone
import re
import pytest
from fastapi.testclient import TestClient
from audit import get_audit_logs, log_event
from auth import _create_token
from database import db
from main import app
from security import hash_password

client=TestClient(app)

def H(sub,role):
    token=_create_token({"sub":sub,"role":role,"exp":(datetime.now(timezone.utc)+timedelta(minutes=15)).timestamp()})
    return {"Authorization":f"Bearer {token}"}

def seed(name,role,password="Contract123!"):
    db.create_user(name,hash_password(password),role,name,f"{name}@example.test")

@pytest.fixture(autouse=True)
def clean():
    for store in (db.sessions,db.decisions,db.announcements,db.results,db.team_states): store.clear()
    with db._get_conn() as c:
        for table in ("audit_logs","memberships","organizations","professor_codes","sessions","users"):
            c.execute(f"DELETE FROM {table}")
        c.commit()
    seed("owner-x","owner"); seed("prof-a","professor"); seed("student-a","student")

def precreate(username="new-prof",password="Temporary123!"):
    return client.post("/api/professor/pre-create",json={
        "username":username,"password":password,"name":"New Professor",
        "email":"new@example.test","university_name":"Contract University",
    },headers=H("owner-x","owner"))

def test_precreate_requires_owner_and_enforces_password_complexity():
    payload={"username":"x","password":"Temporary123!"}
    assert client.post("/api/professor/pre-create",json=payload).status_code==401
    denied=client.post("/api/professor/pre-create",json=payload,headers=H("prof-a","professor"))
    assert denied.status_code==403 and denied.json()=={"detail":"Owner access required"}
    weak=precreate(password="weak")
    assert weak.status_code==400
    assert "8 characters" in weak.json()["detail"]
    assert db.get_user("new-prof") is None

def test_precreate_exact_contract_persistence_org_membership_and_audit():
    r=precreate(); assert r.status_code==201,r.text
    body=r.json()
    assert set(body)=={"status","username","professor_code","message"}
    assert body["status"]=="created" and body["username"]=="new-prof"
    assert re.fullmatch(r"PROF-[23456789A-HJ-NP-Z]{4}-[23456789A-HJ-NP-Z]{4}",body["professor_code"])
    assert "must change their password" in body["message"]
    user=db.get_user("new-prof")
    assert user["role"]=="professor" and user["must_change_password"]==1
    assert user["name"]=="New Professor" and user["email"]=="new@example.test"
    with db._get_conn() as c:
        membership=c.execute("SELECT m.user_id,m.role,o.university_name,o.created_by FROM memberships m JOIN organizations o ON o.id=m.org_id WHERE m.user_id=?",("new-prof",)).fetchone()
    assert tuple(membership)==("new-prof","professor","Contract University","owner-x")
    logs=get_audit_logs(actor="owner-x")
    assert len(logs)==1 and logs[0]["action"]=="professor_pre_created"
    assert logs[0]["details"]=={"new_professor":"new-prof","university":"Contract University"}

def test_precreate_duplicate_is_conflict_without_overwrite():
    assert precreate().status_code==201
    duplicate=precreate(password="Different123!")
    assert duplicate.status_code==409 and duplicate.json()=={"detail":"Username already exists"}
    assert db.verify_user("new-prof","Temporary123!") is not None
    assert db.verify_user("new-prof","Different123!") is None

def test_change_password_auth_old_password_complexity_and_success_persistence():
    payload={"old_password":"Contract123!","new_password":"Replacement456!"}
    assert client.post("/api/professor/change-password",json=payload).status_code==401
    wrong=client.post("/api/professor/change-password",json={**payload,"old_password":"Wrong123!"},headers=H("prof-a","professor"))
    assert wrong.status_code==401 and wrong.json()=={"detail":"Current password is incorrect"}
    weak=client.post("/api/professor/change-password",json={**payload,"new_password":"weak"},headers=H("prof-a","professor"))
    assert weak.status_code==400 and "8 characters" in weak.json()["detail"]
    with db._get_conn() as c:
        c.execute("UPDATE users SET must_change_password=1 WHERE username='prof-a'"); c.commit()
    changed=client.post("/api/professor/change-password",json=payload,headers=H("prof-a","professor"))
    assert changed.status_code==200 and changed.json()=={"status":"changed"}
    assert db.verify_user("prof-a","Contract123!") is None
    assert db.verify_user("prof-a","Replacement456!") is not None
    assert db.get_user("prof-a")["must_change_password"]==0
    logs=get_audit_logs(actor="prof-a")
    assert len(logs)==1 and logs[0]["action"]=="password_changed" and logs[0]["details"]=={}

def test_audit_requires_owner_and_has_exact_typed_filtered_paginated_contract():
    assert client.get("/api/professor/audit").status_code==401
    denied=client.get("/api/professor/audit",headers=H("prof-a","professor"))
    assert denied.status_code==403 and denied.json()=={"detail":"Owner access required"}
    log_event("prof-a","first",{"n":1},"10.0.0.1")
    log_event("student-a","middle",{"n":2},"10.0.0.2")
    log_event("prof-a","last",{"n":3},"10.0.0.3")
    filtered=client.get("/api/professor/audit?actor=prof-a",headers=H("owner-x","owner"))
    assert filtered.status_code==200
    body=filtered.json(); assert set(body)=={"logs","count"} and body["count"]==2
    assert [x["action"] for x in body["logs"]]==["last","first"]
    for item in body["logs"]:
        assert set(item)=={"id","actor","action","details","ip","timestamp"}
        assert isinstance(item["timestamp"],float)
    page=client.get("/api/professor/audit?limit=1&offset=1",headers=H("owner-x","owner"))
    assert page.status_code==200 and page.json()["count"]==1
    assert page.json()["logs"][0]["action"]=="middle"

@pytest.mark.parametrize(
    "query,field,error_type",
    [
        ("limit=0", "limit", "greater_than_equal"),
        ("limit=101", "limit", "less_than_equal"),
        ("offset=-1", "offset", "greater_than_equal"),
    ],
)
def test_audit_query_bounds_are_validation_errors(query, field, error_type):
    r=client.get(f"/api/professor/audit?{query}",headers=H("owner-x","owner"))
    assert r.status_code==400
    body=r.json()
    assert set(body)=={"detail"} and len(body["detail"])==1
    issue=body["detail"][0]
    assert issue["loc"]==["query",field]
    assert issue["type"]==error_type
    assert set(issue)>={"type","loc","msg","input","ctx"}
