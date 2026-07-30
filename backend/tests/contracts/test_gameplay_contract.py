"""Backend-authoritative gameplay API contracts."""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from auth import _create_token
from database import db
from main import app
from models import PlayerDecision, RoundResult, SessionConfiguration, SessionState, TeamConfig
from security import hash_password

client=TestClient(app)

def H(sub,role):
    token=_create_token({"sub":sub,"role":role,"exp":(datetime.now(timezone.utc)+timedelta(minutes=15)).timestamp()})
    return {"Authorization":f"Bearer {token}"}

def seed(name,role): db.create_user(name,hash_password("Contract123!"),role,name,f"{name}@example.test")

@pytest.fixture(autouse=True)
def clean():
    for store in (db.sessions,db.decisions,db.announcements,db.results,db.team_states): store.clear()
    with db._get_conn() as c:
        for table in ("sessions","users"):
            c.execute(f"DELETE FROM {table}")
        c.commit()
    for name,role in (("owner-x","owner"),("prof-a","professor"),("prof-b","professor"),("student-a","student"),("student-b","student")):
        seed(name,role)

def session(teams=None,total=2):
    teams=teams or [TeamConfig(teamName="Zulu",studentId="student-a"),TeamConfig(teamName="Alpha",studentId="student-b"),TeamConfig(teamName="AI-Balanced",isAI=True,aiStrategy="balanced")]
    code=db.create_session(SessionConfiguration(totalRounds=total),teams,"prof-a",30,professor_user_id="prof-a")
    db.update_session(code,{"state":SessionState.ACTIVE,"currentRound":1})
    return code

def payload(team="Zulu",round_num=1,decision=None):
    return {"round":round_num,"teamId":team,"decision":decision if decision is not None else {}}

def submit(code,**kw):
    return client.post(f"/api/sessions/{code}/submit_decision",json=payload(**kw),headers=H("student-a","student"))

def test_all_gameplay_routes_require_authentication():
    code=session()
    assert client.post(f"/api/sessions/{code}/submit_decision",json=payload()).status_code==401
    assert client.get(f"/api/sessions/{code}/decisions/1").status_code==401
    assert client.post(f"/api/sessions/{code}/process_round").status_code==401
    assert client.get(f"/api/sessions/{code}/leaderboard").status_code==401


def test_session_join_requires_matching_authenticated_student_identity():
    code=session(
        teams=[TeamConfig(teamName="AI-Balanced",isAI=True,aiStrategy="balanced")]
    )
    db.update_session(code, {"state": SessionState.CREATING, "currentRound": 0})
    url=f"/api/sessions/{code}/join"
    body={"teamName":"Honest Team","studentId":"student-a"}

    assert client.put(url,json=body).status_code==401

    professor=client.put(url,json=body,headers=H("prof-a","professor"))
    assert professor.status_code==403
    assert professor.json()=={"detail":"Student access required"}

    spoofed=client.put(url,json=body,headers=H("student-b","student"))
    assert spoofed.status_code==403
    assert spoofed.json()=={
        "detail":"Student ID does not match authenticated user"
    }

    joined=client.put(url,json=body,headers=H("student-a","student"))
    assert joined.status_code==200,joined.text
    assert joined.json()["teamId"]=="Honest Team"
    assert any(
        team.teamName=="Honest Team" and team.studentId=="student-a"
        for team in db.get_session(code).teams
    )

def test_submit_exact_contract_persists_every_default_field_and_rejects_duplicate():
    code=session(); r=submit(code)
    assert r.status_code==200,r.text
    assert r.json()=={"status":"accepted","round":1,"teamId":"Zulu"}
    stored=db.get_decisions(code,1)["Zulu"]
    assert stored.model_dump()==PlayerDecision().model_dump()
    duplicate=submit(code)
    assert duplicate.status_code==409
    assert duplicate.json()=={"detail":"Decision already submitted for this team and round"}

def test_submit_enforces_round_team_role_and_student_team_ownership():
    code=session()
    wrong_round=submit(code,round_num=2)
    assert wrong_round.status_code==400 and wrong_round.json()=={"detail":"Current round is 1, cannot submit for round 2"}
    missing=submit(code,team="Missing")
    assert missing.status_code==400 and missing.json()=={"detail":"Team not found in session"}
    other=submit(code,team="Alpha")
    assert other.status_code==403 and other.json()=={"detail":"Not your team"}
    ai=submit(code,team="AI-Balanced")
    assert ai.status_code==403 and ai.json()=={"detail":"Not your team"}
    professor=client.post(f"/api/sessions/{code}/submit_decision",json=payload(),headers=H("prof-a","professor"))
    assert professor.status_code==403 and professor.json()=={"detail":"Student access required"}
    assert db.get_decisions(code,1)=={}

def test_submit_rejects_non_active_state_without_mutation():
    code=session(); db.update_session(code,{"state":SessionState.FINISHED})
    r=submit(code)
    assert r.status_code==400 and r.json()=={"detail":"Session is finished"}
    assert db.get_decisions(code,1)=={}

def test_decision_retrieval_is_typed_and_owner_or_owning_professor_only():
    code=session(); assert submit(code).status_code==200
    url=f"/api/sessions/{code}/decisions/1"
    assert client.get(url,headers=H("student-a","student")).status_code==403
    foreign=client.get(url,headers=H("prof-b","professor"))
    assert foreign.status_code==403 and foreign.json()=={"detail":"Not your session"}
    for principal,role in (("prof-a","professor"),("owner-x","owner")):
        r=client.get(url,headers=H(principal,role)); assert r.status_code==200
        body=r.json(); assert set(body)=={"sessionId","round","decisions"}
        assert body["round"]==1 and set(body["decisions"])=={"Zulu"}
        assert set(body["decisions"]["Zulu"])==set(PlayerDecision().model_dump())

def test_process_round_requires_owning_professor_and_advances_atomically():
    code=session(); assert submit(code).status_code==200
    url=f"/api/sessions/{code}/process_round"
    assert client.post(url,headers=H("student-a","student")).status_code==403
    foreign=client.post(url,headers=H("prof-b","professor"))
    assert foreign.status_code==403 and foreign.json()=={"detail":"Not your session"}
    assert db.get_session(code).currentRound==1 and db.get_all_results(code)=={}
    incomplete=client.post(url,headers=H("prof-a","professor"))
    assert incomplete.status_code==409
    assert incomplete.json()=={"detail":"Missing decisions from teams: Alpha"}
    assert db.get_session(code).currentRound==1 and db.get_all_results(code)=={}
    second=client.post(
        f"/api/sessions/{code}/submit_decision",
        json=payload(team="Alpha"),headers=H("student-b","student")
    )
    assert second.status_code==200
    r=client.post(url,headers=H("prof-a","professor")); assert r.status_code==200,r.text
    body=r.json(); assert set(body)=={"round","results"} and body["round"]==1
    assert {x["teamId"] for x in body["results"]}=={"Zulu","Alpha","AI-Balanced"}
    expected={"teamId","round","revenue","costs","profit","marketShare","sqRating","reputation","cumulativeProfit","cash","inventory","equity","debt","sharesOutstanding","eps","roe","stockPrice","epsScore","roeScore","stockPriceScore","imageScore","awarenessScore","creditScore","totalScore","productionCost","marketingCost","unitCost","demand","wholesaleRevenue","internetRevenue","amazonRevenue","privateLabelRevenue","wholesaleUnitsSold","internetUnitsSold","amazonUnitsSold","privateLabelUnitsSold","workforceCosts","csrCosts","endorsementCosts","rebateCosts","deliveryCosts","storageCosts","interestExpense","dividendsPaid","socialMediaCosts","amazonFees","imageRating","creditRating","customerSatisfaction","rejectionRate"}
    assert all(set(x)==expected and x["round"]==1 for x in body["results"])
    assert db.get_session(code).currentRound==2
    assert len(db.get_all_results(code)[1])==3


def test_legacy_advance_is_authenticated_and_delegates_authoritative_round_policy():
    code=session(); url=f"/api/sessions/{code}/advance"
    assert client.post(url).status_code==401
    assert client.post(url,headers=H("student-a","student")).status_code==403
    foreign=client.post(url,headers=H("prof-b","professor"))
    assert foreign.status_code==403 and foreign.json()=={"detail":"Not your session"}
    assert db.get_session(code).currentRound==1 and db.get_all_results(code)=={}

    # The legacy alias must not bypass process_round's all-human-submissions gate.
    assert submit(code).status_code==200
    incomplete=client.post(url,headers=H("prof-a","professor"))
    assert incomplete.status_code==409,incomplete.text
    assert incomplete.json()=={"detail":"Missing decisions from teams: Alpha"}
    assert db.get_session(code).currentRound==1 and db.get_all_results(code)=={}

    second=client.post(
        f"/api/sessions/{code}/submit_decision",
        json=payload(team="Alpha"),headers=H("student-b","student"),
    )
    assert second.status_code==200
    processed=client.post(url,headers=H("prof-a","professor"))
    assert processed.status_code==200,processed.text
    assert set(processed.json())=={"round","status","results"}
    assert processed.json()["round"]==1 and processed.json()["status"]=="processed"
    assert db.get_session(code).currentRound==2
    assert len(db.get_all_results(code)[1])==3

    # A repeated legacy request cannot silently process the next round: it is
    # subject to the same human-submission gate as the authoritative endpoint.
    replay=client.post(url,headers=H("prof-a","professor"))
    assert replay.status_code==409,replay.text
    assert replay.json()=={"detail":"Missing decisions from teams: Alpha, Zulu"}
    assert db.get_session(code).currentRound==2
    assert set(db.get_all_results(code))=={1}


def test_final_round_processing_finishes_without_advancing_past_total():
    code=session(teams=[TeamConfig(teamName="AI-Balanced",isAI=True,aiStrategy="balanced")],total=1)
    r=client.post(f"/api/sessions/{code}/process_round",headers=H("owner-x","owner"))
    assert r.status_code==200
    persisted=db.get_session(code)
    assert persisted.state==SessionState.FINISHED and persisted.currentRound==1

def test_leaderboard_requires_tenant_or_participant_and_initial_rank_matches_sort_order():
    code=session(); url=f"/api/sessions/{code}/leaderboard"
    foreign=client.get(url,headers=H("prof-b","professor"))
    assert foreign.status_code==403 and foreign.json()=={"detail":"Not your session"}
    seed("outsider","student")
    outsider=client.get(url,headers=H("outsider","student"))
    assert outsider.status_code==403 and outsider.json()=={"detail":"Not enrolled in session"}
    for principal,role in (("student-a","student"),("prof-a","professor"),("owner-x","owner")):
        r=client.get(url,headers=H(principal,role)); assert r.status_code==200
        body=r.json(); assert set(body)=={"sessionId","round","leaderboard"}
        assert [x["teamName"] for x in body["leaderboard"]]==["AI-Balanced","Alpha","Zulu"]
        assert [x["rank"] for x in body["leaderboard"]]==[1,2,3]
        exact={"teamName","studentName","totalScore","eps","roe","stockPrice","imageRating","creditRating","cumulativeProfit","marketShare","rank"}
        assert all(set(x)==exact for x in body["leaderboard"])


def test_teams_and_results_require_authentication_and_participant_tenancy():
    code=session()
    urls=(f"/api/sessions/{code}/teams",f"/api/sessions/{code}/results")
    seed("outsider","student")
    for url in urls:
        assert client.get(url).status_code==401
        foreign=client.get(url,headers=H("prof-b","professor"))
        assert foreign.status_code==403 and foreign.json()=={"detail":"Not your session"}
        outsider=client.get(url,headers=H("outsider","student"))
        assert outsider.status_code==403 and outsider.json()=={"detail":"Not enrolled in session"}
        for principal,role in (("student-a","student"),("prof-a","professor"),("owner-x","owner")):
            assert client.get(url,headers=H(principal,role)).status_code==200


def test_teams_exact_typed_contract_matches_swift_team_config_backend():
    code=session(); r=client.get(f"/api/sessions/{code}/teams",headers=H("student-a","student"))
    assert r.status_code==200
    body=r.json(); assert set(body)=={"sessionId","teams"}
    assert body["sessionId"]==db.get_session(code).id
    assert [team["teamName"] for team in body["teams"]]==["Zulu","Alpha","AI-Balanced"]
    assert all(set(team)=={"teamName","isAI","aiStrategy","studentId"} for team in body["teams"])


def test_results_exact_typed_contract_preserves_sorted_complete_round_history():
    code=session(total=2)
    assert submit(code).status_code==200
    assert client.post(f"/api/sessions/{code}/submit_decision",json=payload(team="Alpha"),headers=H("student-b","student")).status_code==200
    assert client.post(f"/api/sessions/{code}/process_round",headers=H("prof-a","professor")).status_code==200
    r=client.get(f"/api/sessions/{code}/results",headers=H("student-a","student"))
    assert r.status_code==200
    body=r.json(); assert set(body)=={"sessionId","results"} and list(body["results"])==["1"]
    assert body["sessionId"]==db.get_session(code).id
    results=body["results"]["1"]
    assert {item["teamId"] for item in results}=={"Zulu","Alpha","AI-Balanced"}
    exact=set(RoundResult(teamId="x",round=1).model_dump())
    assert all(set(item)==exact and item["round"]==1 for item in results)


def test_teams_and_results_return_typed_empty_collections_and_404():
    code=session()
    teams=client.get(f"/api/sessions/{code}/teams",headers=H("owner-x","owner")).json()
    results=client.get(f"/api/sessions/{code}/results",headers=H("owner-x","owner")).json()
    assert len(teams["teams"])==3 and results["results"]=={}
    for suffix in ("teams","results"):
        missing=client.get(f"/api/sessions/NO-SUCH/{suffix}",headers=H("owner-x","owner"))
        assert missing.status_code==404 and missing.json()=={"detail":"Session not found"}
