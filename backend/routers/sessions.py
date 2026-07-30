"""Session CRUD endpoints — sessions are tied to professor and class."""

import asyncio
import hashlib
import json
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel

from auth import get_current_user, verify_professor
from database import db
from scenario_packs import SCENARIO_PACKS

from models import (
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionResponse,
    JoinSessionRequest,
    JoinSessionResponse,
    Session,
    SessionConfiguration,
    SessionState,
    StatusResponse,
    TeamConfig,
)
from ws_manager import manager

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def _verify_session_professor(code: str, user: dict) -> None:
    if user.get("role") == "owner":
        return
    if db.get_session_professor_user_id(code) != user.get("sub"):
        raise HTTPException(status_code=403, detail="Not your session")


class StartSessionResponse(BaseModel):
    status: str = "started"
    sessionId: str
    code: str


class PublicSessionResponse(BaseModel):
    """Join-safe session metadata with no team or student identifiers."""

    code: str
    state: str
    currentRound: int
    totalRounds: int
    humanTeams: int
    maxHumanTeams: int
    scenarioId: str
    scenarioVersion: str


class CreateSessionRequestWithClass(BaseModel):
    """Extended create session request with optional class_id."""
    config: SessionConfiguration = None
    teams: list = []
    created_by: str = "professor"
    maxHumanTeams: int = 30
    classId: Optional[str] = None




@router.get("/scenarios")
def list_scenario_packs():
    """List selectable, production-backed scenario packs.

    Research-only scenarios are intentionally excluded until their formulas and
    calibration gates pass.
    """
    return {"scenarios": [pack.to_dict() for pack in SCENARIO_PACKS.list()]}

def prepare_session_creation(
    req: CreateSessionRequest, user: dict
) -> tuple[list[TeamConfig], Optional[str]]:
    """Validate server-owned scope and build the canonical initial team list."""
    organization_id = db.get_single_organization_id(user["sub"])
    if user.get("role") == "professor" and not organization_id:
        raise HTTPException(
            status_code=403,
            detail="Professor organization membership is missing or ambiguous",
        )

    if req.classId:
        cls = db.get_class(req.classId)
        if not cls:
            raise HTTPException(status_code=404, detail="Class not found")
        if cls["professor_user_id"] != user["sub"] and user.get("role") != "owner":
            raise HTTPException(status_code=403, detail="Not your class")
        class_org = cls.get("organization_id")
        if user.get("role") == "professor" and class_org != organization_id:
            raise HTTPException(status_code=403, detail="Class belongs to another organization")

    # If num_rounds is provided, override config.totalRounds
    if req.num_rounds:
        req.config.totalRounds = req.num_rounds

    # Build teams list: start with any provided teams, then add AI competitors
    teams = list(req.teams) if req.teams else []
    
    # Create AI competitor teams if configured
    ai_count = getattr(req.config, 'numberOfAICompetitors', 0) or 0
    strategies = ["aggressive", "quality", "lowcost", "balanced", "premium"]
    for i in range(ai_count):
        strategy = strategies[i % len(strategies)]
        ai_team = TeamConfig(
            teamName=f"AI-{strategy.capitalize()}-{i+1}",
            isAI=True,
            aiStrategy=strategy,
        )
        teams.append(ai_team)
    return teams, organization_id


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(
    req: CreateSessionRequest,
    user=Depends(verify_professor),
    idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key"),
):
    """Create an authoritative session in the Professor's tenant."""
    teams, organization_id = prepare_session_creation(req, user)
    assert organization_id is not None  # Professor creation fails closed above.
    if idempotency_key:
        canonical = json.dumps(
            {"organizationId": organization_id, "request": req.model_dump(mode="json")},
            sort_keys=True,
            separators=(",", ":"),
        )
        try:
            code, session_id, _ = db.create_session_idempotent(
                config=req.config,
                teams=teams,
                created_by="professor",
                professor_user_id=user["sub"],
                organization_id=organization_id,
                idempotency_key_hash=hashlib.sha256(
                    f"{organization_id}\0{idempotency_key}".encode()
                ).hexdigest(),
                request_fingerprint=hashlib.sha256(canonical.encode()).hexdigest(),
                max_human_teams=req.maxHumanTeams,
                class_id=req.classId,
                scenario_id=req.scenarioId,
                scenario_version=req.scenarioVersion,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return CreateSessionResponse(sessionId=session_id, code=code)

    code = db.create_session(
        config=req.config,
        teams=teams,
        # Ownership and provenance are server-selected. Never trust a client
        # supplied actor/owner label for an authoritative online session.
        created_by="professor",
        max_human_teams=req.maxHumanTeams,
        professor_user_id=user["sub"],
        class_id=req.classId,
        organization_id=organization_id,
        scenario_id=req.scenarioId,
        scenario_version=req.scenarioVersion,
    )
    return CreateSessionResponse(sessionId=db.sessions[code].id, code=code)


def _session_for_authenticated_reader(session: Session, user: dict) -> Session:
    """Scope Professor reads and redact other students' identifiers."""
    role = user.get("role")
    subject = user.get("sub")
    if role == "professor" and db.get_session_professor_user_id(session.code) != subject:
        raise HTTPException(status_code=403, detail="Not your session")
    if role not in {"owner", "professor", "student"}:
        raise HTTPException(status_code=403, detail="Session access denied")
    visible = session.model_copy(deep=True)
    if role == "student":
        for team in visible.teams:
            if team.studentId != subject:
                team.studentId = None
    return visible


@router.get("/{code}", response_model=Session)
async def get_session(code: str, user=Depends(get_current_user)):
    """Get session details by code. Requires authentication."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return _session_for_authenticated_reader(session, user)


@router.get("/{code}/public", response_model=PublicSessionResponse)
async def get_session_public(code: str):
    """Return join-safe metadata without teams or student identifiers."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "code": session.code,
        "state": session.state.value,
        "currentRound": session.currentRound,
        "totalRounds": session.config.totalRounds,
        "humanTeams": sum(1 for team in session.teams if not team.isAI),
        "maxHumanTeams": session.maxHumanTeams,
        "scenarioId": session.scenarioId,
        "scenarioVersion": session.scenarioVersion,
    }


@router.put("/{code}/join", response_model=JoinSessionResponse)
async def join_session(
    code: str,
    req: JoinSessionRequest,
    user=Depends(get_current_user),
):
    """Authenticated student joins a session using their own identity."""
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    # If studentId is not provided in the request, use the JWT sub (authenticated user)
    effective_student_id = req.studentId if req.studentId else user.get("sub", "")
    if not effective_student_id:
        raise HTTPException(status_code=403, detail="Student ID is required")
    if effective_student_id != user.get("sub"):
        raise HTTPException(status_code=403, detail="Student ID does not match authenticated user")
    outcome = db.join_session_atomic(
        code=code, team_name=req.teamName, student_id=effective_student_id
    )
    if outcome["status"] == "not_found":
        raise HTTPException(status_code=404, detail="Session not found")
    if outcome["status"] == "invalid_state":
        raise HTTPException(
            status_code=400,
            detail=f"Session is {outcome['state']}, cannot join",
        )
    if outcome["status"] == "name_taken":
        raise HTTPException(
            status_code=409, detail="Team name already taken by another student"
        )
    if outcome["status"] == "capacity":
        raise HTTPException(status_code=400, detail="Maximum team capacity reached")
    return JoinSessionResponse(
        teamId=req.teamName,
        teamName=req.teamName,
        round=outcome["round"],
        state=outcome["state"],
    )


@router.get("/{code}/status", response_model=StatusResponse)
async def get_session_status(code: str, user=Depends(get_current_user)):
    """Quick status check for a session. Requires authentication."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if user.get("role") == "professor" and db.get_session_professor_user_id(code) != user.get("sub"):
        raise HTTPException(status_code=403, detail="Not your session")
    if user.get("role") not in {"owner", "professor", "student"}:
        raise HTTPException(status_code=403, detail="Session access denied")

    current_round = session.currentRound
    submitted = db.count_submitted_decisions(code, current_round) if current_round > 0 else 0
    human_teams = [t for t in session.teams if not t.isAI]
    human_team_count = len(human_teams)

    return StatusResponse(
        sessionId=session.id,
        code=session.code,
        state=session.state.value,
        currentRound=current_round,
        totalRounds=session.config.totalRounds,
        teamsSubmitted=submitted,
        totalTeams=len(session.teams),
        humanTeams=human_team_count,
    )


@router.post("/{code}/start", response_model=StartSessionResponse)
async def start_session(code: str, user=Depends(verify_professor)):
    """Professor starts the session (transitions from creating → active, round 1)."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_session_professor(code, user)
    transitioned = db.transition_session_owned(
        code=code,
        professor_user_id=None if user.get("role") == "owner" else user["sub"],
        allowed_states=(SessionState.CREATING.value,),
        new_state=SessionState.ACTIVE.value,
        current_round=1,
    )
    if not transitioned:
        raise HTTPException(status_code=409, detail="Session state changed; refresh and retry")
    
    # Broadcast session start via WebSocket
    broadcast_msg = {
        "type": "session_started",
        "sessionId": session.id,
        "code": session.code,
        "currentRound": 1,
        "teamCount": len(session.teams),
    }
    try:
        asyncio.create_task(manager.broadcast(code, broadcast_msg))
    except Exception:
        pass
    
    return StartSessionResponse(sessionId=session.id, code=code)


@router.post("/{code}/end", response_model=EndSessionResponse)
async def end_session(code: str, user=Depends(verify_professor)):
    """Professor manually ends the session."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_session_professor(code, user)

    # Get final results
    all_results = db.get_all_results(code)
    final = []
    for round_num in sorted(all_results.keys()):
        final.extend(all_results[round_num])

    transitioned = db.transition_session_owned(
        code=code,
        professor_user_id=None if user.get("role") == "owner" else user["sub"],
        allowed_states=(SessionState.CREATING.value, SessionState.ACTIVE.value),
        new_state=SessionState.FINISHED.value,
    )
    if not transitioned:
        raise HTTPException(status_code=409, detail="Session state changed; refresh and retry")
    return EndSessionResponse(status="ended", finalResults=final if final else None)


@router.delete("/{code}", status_code=204)
async def delete_session(code: str, user=Depends(verify_professor)):
    """Professor deletes a session and all associated data."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_session_professor(code, user)

    # Use the database method which handles both SQLite and in-memory cleanup
    db.delete_session(code)

    return None
