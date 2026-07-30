"""Secure browser portal for professor onboarding and progress visibility."""
from __future__ import annotations

import hmac
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Cookie, Depends, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from auth import (
    ACCESS_TOKEN_SOTA_MINUTES,
    LoginRequest,
    LoginResponse,
    ProfessorActivationRequest,
    _verify_token,
    activate_password_professor,
    login,
)
from database import db
from models import (
    CreateAnnouncementRequest,
    CreateClassRequest,
    CreateSessionRequest,
    CreateSessionResponse,
)
from routers.announcements import create_announcement
from routers.classes import create_class, list_classes
from routers.decisions import process_round_endpoint
from routers.grades import export_grades, export_leaderboard
from routers.sessions import (
    delete_session,
    end_session,
    prepare_session_creation,
    start_session,
)
from scenario_packs import SCENARIO_PACKS


router = APIRouter(include_in_schema=False)
api_router = APIRouter(
    prefix="/api/professor-portal",
    tags=["professor-portal"],
    include_in_schema=False,
)
_TEMPLATE = Path(__file__).resolve().parent / "templates" / "professor_portal.html"
_COOKIE = "practenture_professor_session"
_CSRF_COOKIE = "practenture_professor_csrf"
_HEADERS = {
    "Cache-Control": "no-store",
    "Content-Security-Policy": (
        "default-src 'self'; script-src 'self'; style-src 'self'; "
        "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
        "base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    ),
    "Referrer-Policy": "no-referrer",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
}


class PortalSession(BaseModel):
    userId: str
    role: str
    name: str | None = None


class ProgressItem(BaseModel):
    code: str
    name: str
    state: str
    currentRound: int
    totalRounds: int
    humanTeams: int
    maxHumanTeams: int
    currentRoundSubmissions: int
    totalSubmissions: int
    scenarioId: str
    scenarioVersion: str


class ProgressResponse(BaseModel):
    sessions: list[ProgressItem]


def _set_cookie(response: Response, token: str) -> None:
    from admin_v2.service import cookie_secure

    response.set_cookie(
        _COOKIE,
        token,
        max_age=ACCESS_TOKEN_SOTA_MINUTES * 60,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.set_cookie(
        _CSRF_COOKIE,
        secrets.token_urlsafe(32),
        max_age=ACCESS_TOKEN_SOTA_MINUTES * 60,
        httponly=False,
        secure=cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def _clear_cookie(response: Response) -> None:
    from admin_v2.service import cookie_secure

    response.delete_cookie(
        _COOKIE,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.delete_cookie(
        _CSRF_COOKIE,
        httponly=False,
        secure=cookie_secure(),
        samesite="strict",
        path="/",
    )
    response.headers["Cache-Control"] = "no-store"


def require_professor_session(
    practenture_professor_session: str | None = Cookie(default=None),
) -> dict[str, Any]:
    if not practenture_professor_session:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = _verify_token(practenture_professor_session)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired")
    if payload.get("role") != "professor":
        raise HTTPException(status_code=403, detail="Professor access required")
    subject = payload.get("sub")
    record = db.get_user(subject) if isinstance(subject, str) else None
    if not record:
        raise HTTPException(status_code=401, detail="Account no longer exists")
    if record.get("role") != "professor":
        raise HTTPException(status_code=403, detail="Professor access required")
    if record.get("status") not in (None, "active"):
        raise HTTPException(status_code=403, detail="Account is suspended")
    return {
        **payload,
        "sub": record["username"],
        "role": record["role"],
        "name": record.get("name") or payload.get("name"),
    }


def require_professor_csrf(
    x_csrf_token: str | None = Header(default=None, alias="X-CSRF-Token"),
    practenture_professor_csrf: str | None = Cookie(default=None),
) -> None:
    """Require a constant-time double-submit token for cookie mutations."""
    if (
        not x_csrf_token
        or not practenture_professor_csrf
        or not hmac.compare_digest(x_csrf_token, practenture_professor_csrf)
    ):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


def require_same_origin(request: Request) -> None:
    """Protect pre-authentication browser mutations from login fixation CSRF."""
    source = request.headers.get("origin")
    if not source:
        referer = request.headers.get("referer")
        if referer:
            parsed = urlsplit(referer)
            source = f"{parsed.scheme}://{parsed.netloc}"
    expected = os.environ.get(
        "PRACTENTURE_PUBLIC_ORIGIN", "https://practenture.com"
    ).strip().rstrip("/")
    if not source or not hmac.compare_digest(source.rstrip("/"), expected):
        raise HTTPException(status_code=403, detail="Invalid request origin")


@router.get("/login", response_class=HTMLResponse)
@router.get("/login/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/dashboard/", response_class=HTMLResponse)
async def professor_portal_shell() -> HTMLResponse:
    return HTMLResponse(_TEMPLATE.read_text(encoding="utf-8"), headers=_HEADERS)


@api_router.post("/login", response_model=PortalSession)
def portal_login(
    response: Response,
    payload: LoginRequest,
    origin: None = Depends(require_same_origin),
) -> PortalSession:
    del origin
    if payload.provider != "password":
        raise HTTPException(status_code=400, detail="Password login is required")
    result = LoginResponse.model_validate(login(payload))
    if result.mfa_required:
        raise HTTPException(status_code=409, detail="Enter the MFA code to continue")
    if result.role != "professor" or not result.access_token:
        raise HTTPException(status_code=403, detail="Professor access required")
    _set_cookie(response, result.access_token)
    user = db.get_user(result.user_id)
    return PortalSession(
        userId=result.user_id,
        role=result.role,
        name=user.get("name") if user else None,
    )


@api_router.post("/activate", response_model=PortalSession, status_code=201)
def portal_activate(
    response: Response,
    payload: ProfessorActivationRequest,
    origin: None = Depends(require_same_origin),
) -> PortalSession:
    del origin
    result = activate_password_professor(payload)
    _set_cookie(response, result.access_token)
    user = db.get_user(result.user_id)
    return PortalSession(
        userId=result.user_id,
        role=result.role,
        name=user.get("name") if user else None,
    )


@api_router.get("/session", response_model=PortalSession)
def portal_session(user: dict[str, Any] = Depends(require_professor_session)) -> PortalSession:
    record = db.get_user(user["sub"])
    return PortalSession(
        userId=user["sub"],
        role=user["role"],
        name=record.get("name") if record else user.get("name"),
    )


@api_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
def portal_logout(
    response: Response,
    user: dict[str, Any] = Depends(require_professor_session),
    csrf: None = Depends(require_professor_csrf),
) -> None:
    del user, csrf
    _clear_cookie(response)


@api_router.get("/progress", response_model=ProgressResponse)
def professor_progress(
    user: dict[str, Any] = Depends(require_professor_session),
) -> ProgressResponse:
    items: list[ProgressItem] = []
    for session in db.list_sessions(professor_user_id=user["sub"]):
        current_round = session.currentRound
        current_submissions = (
            db.count_submitted_decisions(session.code, current_round)
            if current_round > 0
            else 0
        )
        total_submissions = sum(
            len(db.get_decisions(session.code, round_number))
            for round_number in range(1, session.config.totalRounds + 1)
        )
        items.append(
            ProgressItem(
                code=session.code,
                name=session.config.name,
                state=session.state.value,
                currentRound=current_round,
                totalRounds=session.config.totalRounds,
                humanTeams=sum(1 for team in session.teams if not team.isAI),
                maxHumanTeams=session.maxHumanTeams,
                currentRoundSubmissions=current_submissions,
                totalSubmissions=total_submissions,
                scenarioId=session.scenarioId,
                scenarioVersion=session.scenarioVersion,
            )
        )
    return ProgressResponse(sessions=items)


@api_router.get("/scenarios")
def portal_scenarios(
    user: dict[str, Any] = Depends(require_professor_session),
) -> dict[str, Any]:
    del user
    return {"scenarios": [pack.to_dict() for pack in SCENARIO_PACKS.list()]}


@api_router.get("/classes")
async def portal_classes(
    user: dict[str, Any] = Depends(require_professor_session),
) -> Any:
    return await list_classes(user)


@api_router.post("/classes", status_code=201)
async def portal_create_class(
    payload: CreateClassRequest,
    user: dict[str, Any] = Depends(require_professor_session),
    csrf: None = Depends(require_professor_csrf),
) -> Any:
    del csrf
    return await create_class(payload, user)


@api_router.post("/sessions", status_code=201)
async def portal_create_session(
    payload: CreateSessionRequest,
    user: dict[str, Any] = Depends(require_professor_session),
    csrf: None = Depends(require_professor_csrf),
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=16, max_length=128),
) -> CreateSessionResponse:
    del csrf
    teams, organization_id = prepare_session_creation(payload, user)
    if not organization_id:
        raise HTTPException(
            status_code=403,
            detail="Professor organization membership is missing or ambiguous",
        )
    canonical_payload = json.dumps(
        {"organizationId": organization_id, "request": payload.model_dump(mode="json")},
        separators=(",", ":"),
        sort_keys=True,
    )
    key_hash = hashlib.sha256(
        f"{organization_id}\0{idempotency_key}".encode("utf-8")
    ).hexdigest()
    fingerprint = hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()
    try:
        code, session_id, _replayed = db.create_session_idempotent(
            config=payload.config,
            teams=teams,
            created_by="professor",
            professor_user_id=user["sub"],
            organization_id=organization_id,
            idempotency_key_hash=key_hash,
            request_fingerprint=fingerprint,
            max_human_teams=payload.maxHumanTeams,
            class_id=payload.classId,
            scenario_id=payload.scenarioId,
            scenario_version=payload.scenarioVersion,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return CreateSessionResponse(sessionId=session_id, code=code)


@api_router.post("/sessions/{code}/start")
async def portal_start_session(
    code: str,
    user: dict[str, Any] = Depends(require_professor_session),
    csrf: None = Depends(require_professor_csrf),
) -> Any:
    del csrf
    return await start_session(code, user)


@api_router.post("/sessions/{code}/process-round")
async def portal_process_round(
    code: str,
    user: dict[str, Any] = Depends(require_professor_session),
    csrf: None = Depends(require_professor_csrf),
) -> Any:
    del csrf
    return await process_round_endpoint(code, user)


@api_router.post("/sessions/{code}/end")
async def portal_end_session(
    code: str,
    user: dict[str, Any] = Depends(require_professor_session),
    csrf: None = Depends(require_professor_csrf),
) -> Any:
    del csrf
    return await end_session(code, user)


@api_router.post("/sessions/{code}/announcements")
async def portal_create_announcement(
    code: str,
    payload: CreateAnnouncementRequest,
    user: dict[str, Any] = Depends(require_professor_session),
    csrf: None = Depends(require_professor_csrf),
) -> Any:
    del csrf
    return await create_announcement(code, payload, user)


@api_router.delete(
    "/sessions/{code}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    response_model=None,
)
async def portal_delete_session(
    code: str,
    user: dict[str, Any] = Depends(require_professor_session),
    csrf: None = Depends(require_professor_csrf),
) -> Response:
    del csrf
    await delete_session(code, user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@api_router.get("/progress/{code}/grades", response_class=Response)
async def portal_grade_export(
    code: str, user: dict[str, Any] = Depends(require_professor_session)
) -> Response:
    return await export_grades(code, user)


@api_router.get("/progress/{code}/leaderboard", response_class=Response)
async def portal_leaderboard_export(
    code: str, user: dict[str, Any] = Depends(require_professor_session)
) -> Response:
    return await export_leaderboard(code, user)
