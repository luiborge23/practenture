"""BizSimAI FastAPI application."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import db
from routers import announcements, auth, decisions, grades, leaderboard, sessions, websocket


# ── Production configuration ──────────────────────────────────────────────

HOST = os.environ.get("BIZSIMAI_HOST", "0.0.0.0")
PORT = int(os.environ.get("BIZSIMAI_PORT", "8000"))
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("BIZSIMAI_CORS_ORIGINS", "*").split(",")
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — startup/shutdown hooks."""
    # Startup logging
    print(f"[BizSimAI] Starting on {HOST}:{PORT}")
    print(f"[BizSimAI] CORS origins: {CORS_ORIGINS}")
    print(f"[BizSimAI] JWT_SECRET configured: {'yes' if os.environ.get('BIZSIMAI_JWT_SECRET') else 'no'}")
    print(f"[BizSimAI] JWT expiry: {os.environ.get('BIZSIMAI_JWT_EXPIRY_HOURS', '24')} hours")
    yield
    # Shutdown
    print("[BizSimAI] Shutting down")


app = FastAPI(
    title="BizSimAI Backend",
    description="Real-time business simulation platform for classrooms",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow all origins in dev, configurable via env var for prod
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Global error handlers ──────────────────────────────────────────────────


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors()},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Health check ───────────────────────────────────────────────────────────


@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "bizsimai-backend",
        "config": {
            "host": HOST,
            "port": PORT,
            "cors_origins": CORS_ORIGINS,
            "jwt_secret_configured": bool(os.environ.get("BIZSIMAI_JWT_SECRET")),
            "jwt_expiry_hours": os.environ.get("BIZSIMAI_JWT_EXPIRY_HOURS", "24"),
        },
    }


# ── Register routers ───────────────────────────────────────────────────────

app.include_router(auth.router)
app.include_router(websocket.router)
app.include_router(sessions.router)
app.include_router(decisions.router)
app.include_router(announcements.router)
app.include_router(grades.router)
app.include_router(leaderboard.router)


# ── Team listing endpoint ──────────────────────────────────────────────────


@app.get("/api/sessions/{code}/teams")
async def get_teams(code: str):
    """Get all teams in a session."""
    session = db.get_session(code)
    if not session:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})
    return {
        "sessionId": session.id,
        "teams": [
            {
                "teamName": t.teamName,
                "isAI": t.isAI,
                "aiStrategy": t.aiStrategy,
                "studentId": t.studentId,
            }
            for t in session.teams
        ],
    }


# ── Round results endpoint ─────────────────────────────────────────────────


@app.get("/api/sessions/{code}/results")
async def get_results(code: str):
    """Get all round results for a session."""
    session = db.get_session(code)
    if not session:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})

    all_results = db.get_all_results(code)
    output = {}
    for round_num, results in sorted(all_results.items()):
        output[str(round_num)] = [r.model_dump() for r in results]
    return {"sessionId": session.id, "results": output}


# ── Advance endpoint ───────────────────────────────────────────────────────


@app.post("/api/sessions/{code}/advance")
async def advance_round(code: str):
    """Advance to next round: process current round, then auto-generate AI decisions for next."""
    session = db.get_session(code)
    if not session:
        return JSONResponse(status_code=404, content={"detail": "Session not found"})

    current_round = session.currentRound
    if current_round >= session.config.totalRounds:
        return JSONResponse(status_code=400, content={"detail": "All rounds completed"})

    # Process current round (will also auto-advance via process_round logic)
    # We use the decisions router's logic
    from models import ProcessRoundResponse

    # Get decisions
    decisions_map = db.get_decisions(code, current_round)

    # If no human decisions, we still want to process (AI will auto-generate)
    team_states = db.team_states.get(code, {})
    engine_results, new_team_states = __import__("simulation_engine", fromlist=["process_round"]).process_round(
        config=session.config,
        teams=session.teams,
        decisions=decisions_map,
        round_num=current_round,
        team_states=team_states,
    )

    db.store_results(code, current_round, engine_results)
    for tid, state in new_team_states.items():
        db.update_team_state(code, tid, state)

    # Advance round
    next_round = current_round + 1
    if next_round > session.config.totalRounds:
        new_state = "finished"
    else:
        new_state = "active"
    db.update_session(code, {"currentRound": next_round, "state": new_state})

    return {
        "round": current_round,
        "status": "processed",
        "nextRound": next_round,
        "results": [r.model_dump() for r in engine_results],
    }
