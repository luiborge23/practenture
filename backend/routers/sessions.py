"""Session CRUD endpoints — sessions are tied to professor and class."""

import asyncio
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, verify_professor
from database import db
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


class CreateSessionRequestWithClass(BaseModel):
    """Extended create session request with optional class_id."""
    config: SessionConfiguration = None
    teams: list = []
    created_by: str = "professor"
    maxHumanTeams: int = 30
    classId: Optional[str] = None


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(req: CreateSessionRequest, user=Depends(verify_professor)):
    """Create a new simulation session. Ties to professor_user_id from JWT.

    Optional classId in the request body ties the session to a specific class.
    Creates AI competitor teams based on numberOfAICompetitors in config.
    """
    if req.classId:
        cls = db.get_class(req.classId)
        if not cls:
            raise HTTPException(status_code=404, detail="Class not found")
        if cls["professor_user_id"] != user["sub"] and user.get("role") != "owner":
            raise HTTPException(status_code=403, detail="Not your class")

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
    
    code = db.create_session(
        config=req.config,
        teams=teams,
        created_by=req.created_by,
        max_human_teams=req.maxHumanTeams,
        professor_user_id=user["sub"],
        class_id=req.classId,
    )
    return CreateSessionResponse(sessionId=db.sessions[code].id, code=code)


@router.get("/{code}", response_model=Session)
async def get_session(code: str, user=Depends(get_current_user)):
    """Get session details by code. Requires authentication."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.put("/{code}/join", response_model=JoinSessionResponse)
async def join_session(
    code: str,
    req: JoinSessionRequest,
    user=Depends(get_current_user),
):
    """Authenticated student joins a session using their own identity."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    if req.studentId != user.get("sub"):
        raise HTTPException(status_code=403, detail="Student ID does not match authenticated user")
    if session.state not in (SessionState.CREATING, SessionState.ACTIVE):
        raise HTTPException(status_code=400, detail=f"Session is {session.state.value}, cannot join")

    # Check team name not already taken
    team_names = {t.teamName for t in session.teams}
    if req.teamName in team_names:
        raise HTTPException(status_code=409, detail="Team name already taken")

    human_team_count = sum(1 for team in session.teams if not team.isAI)
    if human_team_count >= session.maxHumanTeams:
        raise HTTPException(status_code=400, detail="Maximum team capacity reached")

    # Generate team ID
    team_id = req.teamName  # Use team name as team ID
    team = TeamConfig(teamName=req.teamName, studentId=req.studentId)
    session.teams.append(team)

    # Auto-transition to active when first team joins (fixes creating→active deadlock)
    new_state = session.state
    if session.state == SessionState.CREATING and len(session.teams) > 0:
        new_state = SessionState.ACTIVE
        session.currentRound = 1

    db.update_session(code, {"teams": session.teams, "state": new_state, "currentRound": session.currentRound})
    return JoinSessionResponse(
        teamId=team_id,
        teamName=req.teamName,
        round=session.currentRound,
        state=new_state.value,
    )


@router.get("/{code}/status", response_model=StatusResponse)
async def get_session_status(code: str, user=Depends(get_current_user)):
    """Quick status check for a session. Requires authentication."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    current_round = session.currentRound
    submitted = db.count_submitted_decisions(code, current_round) if current_round > 0 else 0

    return StatusResponse(
        sessionId=session.id,
        code=session.code,
        state=session.state.value,
        currentRound=current_round,
        totalRounds=session.config.totalRounds,
        teamsSubmitted=submitted,
        totalTeams=len(session.teams),
    )


@router.post("/{code}/start", response_model=StartSessionResponse)
async def start_session(code: str, user=Depends(verify_professor)):
    """Professor starts the session (transitions from creating → active, round 1)."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_session_professor(code, user)
    if session.state == SessionState.ACTIVE:
        raise HTTPException(status_code=400, detail=f"Session is already {session.state.value}")
    if session.state == SessionState.FINISHED or session.state == SessionState.COMPLETED:
        raise HTTPException(status_code=400, detail=f"Session is {session.state.value}, cannot start")

    # Auto-transition to active (teams already handled by join endpoint)
    db.update_session(code, {"state": SessionState.ACTIVE, "currentRound": 1})
    
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

    db.update_session(code, {"state": SessionState.FINISHED})
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
