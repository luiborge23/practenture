"""Decision submission and retrieval endpoints."""

from fastapi import APIRouter, HTTPException

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


@router.post("/{code}/submit_decision", response_model=SubmitDecisionResponse)
async def submit_decision(code: str, req: SubmitDecisionRequest):
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

    # Check for double submission
    if db.has_decision(code, req.round, req.teamId):
        raise HTTPException(status_code=409, detail="Decision already submitted for this team and round")

    success = db.store_decision(code, req.round, req.teamId, req.decision)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to store decision")

    return SubmitDecisionResponse(status="accepted", round=req.round, teamId=req.teamId)


@router.get("/{code}/decisions/{round_num}")
async def get_decisions(code: str, round_num: int):
    """Get all decisions for a specific round."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    decisions = db.get_decisions(code, round_num)
    return {
        "sessionId": session.id,
        "round": round_num,
        "decisions": {tid: d.model_dump() for tid, d in decisions.items()},
    }


@router.post("/{code}/process_round", response_model=ProcessRoundResponse)
async def process_round_endpoint(code: str):
    """Professor triggers round processing for all teams."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.state.value not in ("active",):
        raise HTTPException(status_code=400, detail=f"Session is {session.state.value}, cannot process")

    current_round = session.currentRound

    # Get all decisions for this round
    decisions = db.get_decisions(code, current_round)

    # Process round
    team_states = db.team_states.get(code, {})
    engine_results, new_team_states = process_round(
        config=session.config,
        teams=session.teams,
        decisions=decisions,
        round_num=current_round,
        team_states=team_states,
    )

    # Store results
    db.store_results(code, current_round, engine_results)

    # Update team states
    for tid, state in new_team_states.items():
        db.update_team_state(code, tid, state)

    # If all rounds completed, mark session as finished
    if current_round >= session.config.totalRounds:
        db.update_session(code, {"state": SessionState.FINISHED, "currentRound": current_round})
    else:
        # Advance to next round
        db.update_session(code, {"currentRound": current_round + 1})

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
    
    import asyncio
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
