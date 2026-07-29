"""Authentication routes for the Admin Console V2 API."""

from datetime import datetime
import os
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response, status

from .dependencies import require_csrf_session, require_recent_auth_session
from .repository import AdminSessionRecord
from .schemas import (
    AdminSession,
    LoginRequest,
    MfaChallengeVerifyRequest,
    PasswordChangeRequest,
    PasswordChangeResponse,
    ReauthenticateRequest,
    ReauthenticateResponse,
    RecoveryCompleteRequest,
    RecoveryCompleteResponse,
    RecoveryStartRequest,
    RecoveryStartResponse,
    SessionResponse,
)
from .service import (
    AuthenticatedSession,
    COOKIE_NAME,
    COOKIE_PATH,
    auth_service,
    cookie_secure,
)

router = APIRouter(prefix="/auth", tags=["admin-v2-auth"])


def _admin_session(record: AdminSessionRecord, csrf_token: str) -> AdminSession:
    return AdminSession(
        userId=record.owner_user_id,
        role=record.role,
        csrfToken=csrf_token,
        createdAt=datetime.fromisoformat(record.created_at),
        lastSeenAt=datetime.fromisoformat(record.last_seen_at),
        idleExpiresAt=datetime.fromisoformat(record.idle_expires_at),
        absoluteExpiresAt=datetime.fromisoformat(record.absolute_expires_at),
    )


def _response(record: AdminSessionRecord, csrf_token: str) -> SessionResponse:
    return SessionResponse(session=_admin_session(record, csrf_token))


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=auth_service.absolute_seconds,
        httponly=True,
        secure=cookie_secure(),
        samesite="strict",
        path=COOKIE_PATH,
    )
    response.headers["Cache-Control"] = "no-store"


@router.post("/login", response_model=SessionResponse)
def login(request: Request, response: Response, payload: LoginRequest) -> SessionResponse:
    client_signal = request.client.host if request.client is not None else None
    session, token, csrf_token = auth_service.login(
        payload.username,
        payload.password,
        mfa_code=payload.mfa_code,
        client_signal=client_signal,
        replacement_token=request.cookies.get(COOKIE_NAME),
    )
    _set_session_cookie(response, token)
    return _response(session.record, csrf_token)


@router.get("/session", response_model=SessionResponse)
def get_session(request: Request, response: Response) -> SessionResponse:
    session, csrf_token = auth_service.authenticate(request.cookies.get(COOKIE_NAME))
    response.headers["Cache-Control"] = "no-store"
    return _response(session.record, csrf_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    session: AuthenticatedSession = Depends(require_csrf_session),
) -> None:
    auth_service.logout(session)
    response.delete_cookie(
        COOKIE_NAME,
        path=COOKIE_PATH,
        secure=cookie_secure(),
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "") or f"req_{uuid4()}")


@router.post("/mfa/verify", response_model=SessionResponse)
def verify_mfa_challenge(
    response: Response, payload: MfaChallengeVerifyRequest
) -> SessionResponse:
    session, token, csrf = auth_service.verify_mfa_challenge(
        payload.challenge_token, payload.mfa_code
    )
    _set_session_cookie(response, token)
    return _response(session.record, csrf)


@router.post("/reauthenticate", response_model=ReauthenticateResponse)
def reauthenticate(
    payload: ReauthenticateRequest,
    session: AuthenticatedSession = Depends(require_csrf_session),
) -> ReauthenticateResponse:
    expires = auth_service.reauthenticate(session, payload.password, payload.mfa_code)
    return ReauthenticateResponse(recentAuthExpiresAt=expires)


@router.post("/password/change", response_model=PasswordChangeResponse)
def change_password(
    request: Request,
    response: Response,
    payload: PasswordChangeRequest,
    session: AuthenticatedSession = Depends(require_recent_auth_session),
) -> PasswordChangeResponse:
    replacement, token, csrf = auth_service.change_password(
        session, payload.current_password, payload.new_password, _request_id(request)
    )
    _set_session_cookie(response, token)
    return PasswordChangeResponse(session=_admin_session(replacement.record, csrf))


@router.post(
    "/recovery/start",
    response_model=RecoveryStartResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def start_recovery(
    request: Request, response: Response, payload: RecoveryStartRequest
) -> RecoveryStartResponse:
    token = auth_service.start_recovery(payload.identifier, _request_id(request))
    if token and os.environ.get("PRACTENTURE_TESTING") == "1":
        response.headers["X-Admin-Recovery-Token"] = token
    response.headers["Cache-Control"] = "no-store"
    return RecoveryStartResponse()


@router.post("/recovery/complete", response_model=RecoveryCompleteResponse)
def complete_recovery(
    request: Request, payload: RecoveryCompleteRequest
) -> RecoveryCompleteResponse:
    auth_service.complete_recovery(
        payload.recovery_token, payload.new_password, _request_id(request)
    )
    return RecoveryCompleteResponse()
