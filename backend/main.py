"""BizSimAI FastAPI application."""

import os
import sys
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# Load .env file into environment (local dev only)
load_dotenv()

# Ensure sibling modules (database, auth, models, etc.) are importable
# when running via gunicorn from /app (Docker) or uvicorn locally
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import db
from models import (
    AdvanceResponse,
    HealthResponse,
    ProcessRoundResponse,
    RoundResult,
    SessionResultsResponse,
    SessionState,
    TeamsResponse,
)
from auth import get_current_user, verify_professor
from routers import ai, announcements, auth, classes, dashboard, decisions, grades, leaderboard, professor, sessions, websocket
from simulation_engine import process_round


# ── Production configuration ──────────────────────────────────────────────

HOST = os.environ.get("BIZSIMAI_HOST", "0.0.0.0")
PORT = int(os.environ.get("BIZSIMAI_PORT", "8000"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — startup/shutdown hooks."""
    # Bootstrap owner account (creates in SQLite if not exists)
    from auth import ensure_owner, ensure_professor
    ensure_owner()
    ensure_professor()

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

# CORS — use configured origins (SOTA: no wildcard in production)
# Default: iOS native app origins + localhost for dev
_DEFAULT_CORS = "http://localhost,http://localhost:8080,capacitor://,http://localhost"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("BIZSIMAI_CORS_ORIGINS", _DEFAULT_CORS).split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
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


@app.get("/api/health", response_model=HealthResponse)
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

app.include_router(ai.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(websocket.router)
app.include_router(sessions.router)
app.include_router(decisions.router)
app.include_router(announcements.router)
app.include_router(grades.router)
app.include_router(leaderboard.router)
app.include_router(classes.router)
app.include_router(professor.router)

# SOTA Phase 2: SAML SSO + SCIM 2.0 user provisioning
import saml as saml_router_mod
import scim as scim_router_mod
app.include_router(saml_router_mod.router)
app.include_router(scim_router_mod.router)


# ── Team listing endpoint ──────────────────────────────────────────────────


def _verify_session_participant(code: str, session, user: dict) -> None:
    """Authorize the owning professor, owner, or a student enrolled in the session."""
    role = user.get("role")
    if role in ("professor", "owner"):
        if role != "owner" and db.get_session_professor_user_id(code) != user.get("sub"):
            raise HTTPException(status_code=403, detail="Not your session")
    elif role == "student":
        if not any(not team.isAI and team.studentId == user.get("sub") for team in session.teams):
            raise HTTPException(status_code=403, detail="Not enrolled in session")
    else:
        raise HTTPException(status_code=403, detail="Access denied")


@app.get("/api/sessions/{code}/teams", response_model=TeamsResponse)
async def get_teams(code: str, user=Depends(get_current_user)):
    """Get all teams in a session for an authorized participant."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_session_participant(code, session, user)
    return TeamsResponse(sessionId=session.id, teams=session.teams)


# ── Round results endpoint ─────────────────────────────────────────────────


@app.get("/api/sessions/{code}/results", response_model=SessionResultsResponse)
async def get_results(code: str, user=Depends(get_current_user)):
    """Get complete round history for an authorized session participant."""
    session = db.get_session(code)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    _verify_session_participant(code, session, user)
    all_results = db.get_all_results(code)
    output = {
        str(round_num): results
        for round_num, results in sorted(all_results.items())
    }
    return SessionResultsResponse(sessionId=session.id, results=output)


# ── Advance endpoint ───────────────────────────────────────────────────────


@app.post("/api/sessions/{code}/advance", response_model=AdvanceResponse)
async def advance_round(code: str, user=Depends(verify_professor)):
    """Compatibility alias for the authoritative, instructor-only round processor."""
    processed = await decisions.process_round_endpoint(code, user)
    return AdvanceResponse(
        round=processed.round,
        status="processed",
        results=processed.results,
    )
