"""Secure browser portal for professor onboarding and progress visibility."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
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
from routers.grades import export_grades, export_leaderboard


router = APIRouter(include_in_schema=False)
api_router = APIRouter(
    prefix="/api/professor-portal",
    tags=["professor-portal"],
    include_in_schema=False,
)
_TEMPLATE = Path(__file__).resolve().parent / "templates" / "professor_portal.html"
_COOKIE = "practenture_professor_session"
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
    state: str
    currentRound: int
    totalRounds: int
    humanTeams: int
    currentRoundSubmissions: int
    totalSubmissions: int


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
    return payload


@router.get("/login", response_class=HTMLResponse)
@router.get("/login/", response_class=HTMLResponse)
@router.get("/dashboard", response_class=HTMLResponse)
@router.get("/dashboard/", response_class=HTMLResponse)
async def professor_portal_shell() -> HTMLResponse:
    return HTMLResponse(_TEMPLATE.read_text(encoding="utf-8"), headers=_HEADERS)


@api_router.post("/login", response_model=PortalSession)
def portal_login(response: Response, payload: LoginRequest) -> PortalSession:
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
    response: Response, payload: ProfessorActivationRequest
) -> PortalSession:
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
) -> None:
    del user
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
                state=session.state.value,
                currentRound=current_round,
                totalRounds=session.config.totalRounds,
                humanTeams=sum(1 for team in session.teams if not team.isAI),
                currentRoundSubmissions=current_submissions,
                totalSubmissions=total_submissions,
            )
        )
    return ProgressResponse(sessions=items)


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
