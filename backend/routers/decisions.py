"""Decision submission and retrieval endpoints."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user, verify_professor
from database import db
from models import (
    PlayerDecision,
    ProcessRoundResponse,
    SessionState,
    SubmitDecisionRequest,
    SubmitDecisionResponse,
)
from simulation_engine import process_round

router = APIRouter(prefix="/api/sessions", tags=["decisions"])
_round_processing_locks: dict[str, asyncio.Lock] = {}


def _verify_session_professor(code: str, user: dict) -> None:
    if user.get("role") != "owner" and db.get_session_professor_user_id(code) != user.get("sub"):
        raise HTTPException(status_code=403, detail="Not your session")


class DecisionsResponse(BaseModel):
    sessionId: str
    round: int
    decisions: dict[str, PlayerDecision]


@router.post("/{code}/submit_decision", response_model=SubmitDecisionResponse)
async def submit_decision(code: str, req: SubmitDecisionRequest, user=Depends(get_current_user)):
    """Submit a team's decision for the current round."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.state.value not in ("active", "creating"):
        raise HTTPException(status_code=400, detail=f"Session is {session.state.value}")

    current_round = session.currentRound
    if req.round != current_round:
        raise HTTPException(
            status_code=400,
            detail=f"Current round is {current_round}, cannot submit for round {req.round}",
        )

    # Check team exists
    team_ids = {t.teamName for t in session.teams}
    if req.teamId not in team_ids:
        raise HTTPException(status_code=400, detail="Team not found in session")
    if user.get("role") != "student":
        raise HTTPException(status_code=403, detail="Student access required")
    team = next(t for t in session.teams if t.teamName == req.teamId)
    if team.isAI or team.studentId != user.get("sub"):
        raise HTTPException(status_code=403, detail="Not your team")

    # Check for double submission
    if db.has_decision(code, req.round, req.teamId):
        raise HTTPException(status_code=409, detail="Decision already submitted for this team and round")

    success = db.store_decision(code, req.round, req.teamId, req.decision)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to store decision")

    return SubmitDecisionResponse(status="accepted", round=req.round, teamId=req.teamId)


@router.get("/{code}/decisions/{round_num}", response_model=DecisionsResponse)
async def get_decisions(code: str, round_num: int, user=Depends(verify_professor)):
    """Get all decisions for a specific round."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_session_professor(code, user)

    decisions = db.get_decisions(code, round_num)
    return {
        "sessionId": session.id,
        "round": round_num,
        "decisions": {tid: d.model_dump() for tid, d in decisions.items()},
    }


@router.post("/{code}/process_round", response_model=ProcessRoundResponse)
async def process_round_endpoint(code: str, user=Depends(verify_professor)):
    """Serialize processing so a round can advance at most once per worker."""
    lock = _round_processing_locks.setdefault(code, asyncio.Lock())
    if lock.locked():
        raise HTTPException(status_code=409, detail="Round processing is already in progress")
    async with lock:
        return await _process_round_locked(code, user)


async def _process_round_locked(code: str, user: dict):
    """Professor triggers round processing for all teams."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_session_professor(code, user)
    if session.state.value not in ("active",):
        raise HTTPException(status_code=400, detail=f"Session is {session.state.value}, cannot process")

    current_round = session.currentRound

    # Require every human team to submit before processing. Missing AI
    # decisions are generated deterministically by the simulation engine.
    decisions = db.get_decisions(code, current_round)
    missing_human_teams = sorted(
        team.teamName
        for team in session.teams
        if not team.isAI and team.teamName not in decisions
    )
    if missing_human_teams:
        raise HTTPException(
            status_code=409,
            detail=f"Missing decisions from teams: {', '.join(missing_human_teams)}",
        )

    # Process round
    team_states = {
        team.teamName: db.get_team_state(code, team.teamName)
        for team in session.teams
    }
    engine_results, new_team_states = process_round(
        config=session.config,
        teams=session.teams,
        decisions=decisions,
        round_num=current_round,
        team_states=team_states,
        scenario_id=session.scenarioId,
        scenario_version=session.scenarioVersion,
    )

    committed = db.finalize_round_atomic(
        code=code,
        professor_user_id=None if user.get("role") == "owner" else user["sub"],
        expected_round=current_round,
        engine_results=engine_results,
        new_team_states=new_team_states,
        total_rounds=session.config.totalRounds,
    )
    if not committed:
        raise HTTPException(
            status_code=409,
            detail="Round state changed while processing; refresh before retrying",
        )

    # Broadcast results via WebSocket
    broadcast_msg = {
        "type": "round_complete",
        "sessionId": session.id,
        "code": session.code,
        "round": current_round,
        "nextRound": current_round + 1 if current_round < session.config.totalRounds else None,
        "state": "finished" if current_round >= session.config.totalRounds else "active",
        "results": [r.model_dump() for r in engine_results],
    }
    
    from ws_manager import manager
    try:
        # Run broadcast in background task
        asyncio.create_task(manager.broadcast(code, broadcast_msg))
    except Exception:
        pass  # Don't fail the endpoint if broadcast fails

    return ProcessRoundResponse(round=current_round, results=engine_results)


# Note: WebSocket broadcast is handled in main.py's process_round wrapper
# to avoid circular imports. See the advance endpoint and process_round_endpoint
# integration below.
