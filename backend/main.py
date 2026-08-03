"""Practenture FastAPI application."""

import os
import asyncio
from contextlib import suppress
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
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

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
from legal_pages import router as legal_pages_router
from routers import ai, announcements, auth, classes, dashboard, decisions, grades, leaderboard, professor, sessions, websocket
from admin_v2.errors import AdminError, error_envelope
from admin_v2.router import router as admin_v2_router
from admin_v2.shell import router as admin_v2_shell_router
from professor_portal import api_router as professor_portal_api_router
from professor_portal import router as professor_portal_shell_router
from simulation_engine import process_round
from starlette.exceptions import HTTPException as StarletteHTTPException


# ── Production configuration ──────────────────────────────────────────────

HOST = os.environ.get("PRACTENTURE_HOST", "0.0.0.0")
PORT = int(os.environ.get("PRACTENTURE_PORT", "8000"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle — startup/shutdown hooks."""
    from account_deletion_security import validate_provider_security_configuration
    from apple_token_revocation import validate_apple_revocation_configuration

    validate_provider_security_configuration()
    validate_apple_revocation_configuration()

    # Bootstrap owner account (creates in SQLite if not exists)
    from auth import ensure_owner, ensure_professor
    ensure_owner()
    ensure_professor()

    # Startup logging
    print(f"[Practenture] Starting on {HOST}:{PORT}")
    print(f"[Practenture] CORS origins: {CORS_ORIGINS}")
    print(f"[Practenture] JWT_SECRET configured: {'yes' if os.environ.get('PRACTENTURE_JWT_SECRET') else 'no'}")
    print(f"[Practenture] JWT expiry: {os.environ.get('PRACTENTURE_JWT_EXPIRY_HOURS', '24')} hours")

    async def provider_revocation_worker() -> None:
        from account_deletion_security import process_pending_provider_revocations
        from database import db

        while True:
            try:
                await asyncio.to_thread(process_pending_provider_revocations, db)
            except Exception as exc:
                print(f"[Practenture] Provider revocation worker error: {exc}")
            await asyncio.sleep(60)

    revocation_task = asyncio.create_task(provider_revocation_worker())
    try:
        yield
    finally:
        revocation_task.cancel()
        with suppress(asyncio.CancelledError):
            await revocation_task
        print("[Practenture] Shutting down")


app = FastAPI(
    title="Practenture Backend",
    description="Real-time business simulation platform for classrooms",
    version="1.0.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Give each response an opaque server-generated correlation ID."""
    import secrets

    request.state.request_id = f"req_{secrets.token_urlsafe(18)}"
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    if request.url.path.startswith("/api/admin/v2"):
        response.headers["Cache-Control"] = "no-store"
    return response

# CORS — use configured origins (SOTA: no wildcard in production)
# Default: iOS native app origins + localhost for dev
_DEFAULT_CORS = "http://localhost,http://localhost:8080,capacitor://,http://localhost"
CORS_ORIGINS = [
    origin.strip()
    for origin in os.environ.get("PRACTENTURE_CORS_ORIGINS", _DEFAULT_CORS).split(",")
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files are anchored to this module, never the process working directory.
from fastapi.staticfiles import StaticFiles

_BACKEND_DIR = os.path.dirname(os.path.abspath(__file__))
app.mount("/static", StaticFiles(directory=os.path.join(_BACKEND_DIR, "static")), name="static")


# ── Global error handlers ──────────────────────────────────────────────────

def _admin_v2_error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    body = error_envelope(code, message, request_id)
    response_request_id = body["error"]["requestId"]
    response_headers = dict(headers or {})
    response_headers.update(
        {
            "Cache-Control": "no-store",
            "X-Request-ID": response_request_id,
        }
    )
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=response_headers,
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler_for_admin_v2(
    request: Request, exc: StarletteHTTPException
):
    if not request.url.path.startswith("/api/admin/v2"):
        return await http_exception_handler(request, exc)
    if exc.status_code == 404:
        return _admin_v2_error_response(
            request, 404, "ADMIN_NOT_FOUND", "Admin V2 resource not found"
        )
    if exc.status_code == 405:
        return _admin_v2_error_response(
            request,
            405,
            "ADMIN_METHOD_NOT_ALLOWED",
            "Method not allowed",
            headers=dict(exc.headers or {}),
        )
    return _admin_v2_error_response(
        request,
        exc.status_code,
        "ADMIN_HTTP_ERROR",
        str(exc.detail),
        headers=dict(exc.headers or {}),
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    if request.url.path.startswith("/api/admin/v2"):
        return _admin_v2_error_response(
            request,
            400,
            "ADMIN_VALIDATION_ERROR",
            "Request validation failed",
        )
    return JSONResponse(
        status_code=400,
        content={"detail": exc.errors()},
    )


@app.exception_handler(AdminError)
async def admin_v2_exception_handler(request: Request, exc: AdminError):
    return _admin_v2_error_response(
        request, exc.status_code, exc.code, exc.message, headers=exc.headers
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    if request.url.path.startswith("/api/admin/v2"):
        return _admin_v2_error_response(
            request, 500, "ADMIN_INTERNAL_ERROR", "Internal server error"
        )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# ── Security headers middleware ─────────────────────────────────────────────

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    
    # Browser shells use external assets; native SwiftUI is unaffected by CSP.
    # Do not overwrite their stricter policy with inline-script exceptions.
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self'; "
        "style-src 'self'; "
        "img-src 'self' data:; "
        "font-src 'self'; "
        "connect-src 'self'; "
        "object-src 'none'; "
        "frame-ancestors 'none'; "
        "base-uri 'none'; "
        "form-action 'self';"
    )
    
    # X-Content-Type-Options (prevent MIME type sniffing)
    response.headers["X-Content-Type-Options"] = "nosniff"
    
    # X-Frame-Options (prevent clickjacking)
    response.headers["X-Frame-Options"] = "DENY"
    
    # X-XSS-Protection (legacy, but still useful)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    
    return response


# ── Health check ───────────────────────────────────────────────────────────


@app.get("/api/health", response_model=HealthResponse)
async def health_check():
    return {
        "status": "healthy",
        "service": "practenture-backend",
        "config": {
            "host": HOST,
            "port": PORT,
            "cors_origins": CORS_ORIGINS,
            "jwt_secret_configured": bool(os.environ.get("PRACTENTURE_JWT_SECRET")),
            "jwt_expiry_hours": os.environ.get("PRACTENTURE_JWT_EXPIRY_HOURS", "24"),
        },
    }


# ── Register routers ───────────────────────────────────────────────────────

app.include_router(ai.router)
app.include_router(legal_pages_router)
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

# Admin Console V2 is the only mounted privileged administration surface.
# The legacy owner routers are intentionally retired: they bypassed the V2
# session, CSRF, recent-authentication, audit, and bounded-cleanup contracts.
app.include_router(admin_v2_router)
app.include_router(admin_v2_shell_router)
app.include_router(professor_portal_api_router)
app.include_router(professor_portal_shell_router)


@app.get("/owner", include_in_schema=False)
@app.get("/owner/", include_in_schema=False)
async def legacy_owner_redirect():
    return RedirectResponse(url="/admin", status_code=308)

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
    visible = session.model_copy(deep=True)
    if user.get("role") == "student":
        for team in visible.teams:
            if team.studentId != user.get("sub"):
                team.studentId = None
    return TeamsResponse(sessionId=session.id, teams=visible.teams)


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
