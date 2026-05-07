"""Session CRUD endpoints."""

from datetime import datetime

from fastapi import APIRouter, HTTPException

from database import db
from models import (
    Announcement,
    CreateAnnouncementRequest,
    CreateSessionRequest,
    CreateSessionResponse,
    EndSessionResponse,
    ErrorResponse,
    JoinSessionRequest,
    JoinSessionResponse,
    Session,
    SessionConfiguration,
    SessionState,
    StatusResponse,
    TeamConfig,
)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post("", response_model=CreateSessionResponse, status_code=201)
async def create_session(req: CreateSessionRequest):
    """Create a new simulation session. Returns session code for students to join."""
    code = db.create_session(
        config=req.config,
        teams=req.teams,
        created_by=req.created_by,
        max_human_teams=req.maxHumanTeams,
    )
    return CreateSessionResponse(sessionId=db.sessions[code].id, code=code)


@router.get("/{code}", response_model=Session)
async def get_session(code: str):
    """Get session details by code."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.put("/{code}/join", response_model=JoinSessionResponse)
async def join_session(code: str, req: JoinSessionRequest):
    """Student joins an active session, gets assigned to a team."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.state != SessionState.ACTIVE:
        raise HTTPException(status_code=400, detail=f"Session is {session.state.value}, cannot join")

    # Check team name not already taken
    team_names = {t.teamName for t in session.teams}
    if req.teamName in team_names:
        raise HTTPException(status_code=400, detail="Team name already taken")

    # Generate team ID
    team_id = req.teamName  # Use team name as team ID
    team = TeamConfig(teamName=req.teamName, studentId=req.studentId)
    session.teams.append(team)

    if len(session.teams) > session.maxHumanTeams:
        raise HTTPException(status_code=400, detail="Maximum team capacity reached")

    db.update_session(code, {"teams": session.teams})
    return JoinSessionResponse(
        teamId=team_id,
        teamName=req.teamName,
        round=session.currentRound,
        state=session.state.value,
    )


@router.get("/{code}/status", response_model=StatusResponse)
async def get_session_status(code: str):
    """Quick status check for a session."""
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


@router.post("/{code}/start")
async def start_session(code: str):
    """Professor starts the session (transitions from creating → active, round 1)."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.state != SessionState.CREATING:
        raise HTTPException(status_code=400, detail=f"Session is already {session.state.value}")
    if len(session.teams) == 0:
        raise HTTPException(status_code=400, detail="No teams in session")

    db.update_session(code, {"state": SessionState.ACTIVE, "currentRound": 1})
    
    # Broadcast session start via WebSocket
    broadcast_msg = {
        "type": "session_started",
        "sessionId": session.id,
        "code": session.code,
        "currentRound": 1,
        "teamCount": len(session.teams),
    }
    import asyncio
    from ws_manager import manager
    try:
        asyncio.create_task(manager.broadcast(code, broadcast_msg))
    except Exception:
        pass
    
    return {"status": "started", "sessionId": session.id, "code": code}


@router.post("/{code}/end", response_model=EndSessionResponse)
async def end_session(code: str):
    """Professor manually ends the session."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get final results
    all_results = db.get_all_results(code)
    final = []
    for round_num in sorted(all_results.keys()):
        final.extend(all_results[round_num])

    db.update_session(code, {"state": SessionState.FINISHED})
    return EndSessionResponse(status="ended", finalResults=final if final else None)
