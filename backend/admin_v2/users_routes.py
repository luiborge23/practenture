"""Owner-authenticated Admin V2 user administration routes (mounted by composition root)."""
from __future__ import annotations

import secrets
from typing import Annotated, Literal
from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from .dependencies import require_admin_session, require_recent_auth_session
from .service import AuthenticatedSession
from .users_schemas import UserActionRequest, UserActionResponse, UserListResponse, UserPrecreateRequest, UserPrecreateResponse, UserResponse
from .users_service import user_service

router = APIRouter(tags=["admin-v2-users"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or f"req_{secrets.token_urlsafe(18)}"


def _mutation_response(execution) -> JSONResponse:
    return JSONResponse(status_code=execution.response.status_code, content=execution.response.body, headers=dict(execution.response.headers))


@router.get("/users", response_model=UserListResponse)
def list_users(
    search: Annotated[str | None, Query(max_length=200)] = None,
    role: Annotated[Literal["owner", "professor", "student"] | None, Query()] = None,
    user_status: Annotated[Literal["active", "suspended"] | None, Query(alias="status")] = None,
    organization_id: Annotated[str | None, Query(alias="organizationId", max_length=200)] = None,
    sort: Annotated[str, Query(max_length=40)] = "username",
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    session: AuthenticatedSession = Depends(require_admin_session),
) -> UserListResponse:
    del session
    return user_service.list_users(search=search, role=role, status=user_status, organization_id=organization_id, sort=sort, cursor=cursor, limit=limit)


@router.post("/users/precreate", response_model=UserPrecreateResponse, status_code=status.HTTP_201_CREATED)
def precreate_user(request: Request, payload: UserPrecreateRequest, session: AuthenticatedSession = Depends(require_recent_auth_session)) -> Response:
    return _mutation_response(user_service.precreate(session=session, payload=payload, request_id=_request_id(request)))


@router.get("/users/{userId}", response_model=UserResponse)
def get_user(userId: str, session: AuthenticatedSession = Depends(require_admin_session)) -> UserResponse:
    del session
    return user_service.get_user(userId)


def _perform_action(userId: str, action: str, request: Request, payload: UserActionRequest, idempotency_key: str | None, session: AuthenticatedSession) -> Response:
    return _mutation_response(user_service.action(session=session, user_id=userId, action=action, payload=payload, idempotency_key=idempotency_key, request_id=_request_id(request)))


@router.post("/users/{userId}/suspend", response_model=UserActionResponse)
def suspend_user(userId: str, request: Request, payload: UserActionRequest, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)] = None, session: AuthenticatedSession = Depends(require_recent_auth_session)) -> Response:
    return _perform_action(userId, "suspend", request, payload, idempotency_key, session)


@router.post("/users/{userId}/reactivate", response_model=UserActionResponse)
def reactivate_user(userId: str, request: Request, payload: UserActionRequest, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)] = None, session: AuthenticatedSession = Depends(require_recent_auth_session)) -> Response:
    return _perform_action(userId, "reactivate", request, payload, idempotency_key, session)


@router.post("/users/{userId}/require-password-reset", response_model=UserActionResponse)
def require_password_reset(userId: str, request: Request, payload: UserActionRequest, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)] = None, session: AuthenticatedSession = Depends(require_recent_auth_session)) -> Response:
    return _perform_action(userId, "require-password-reset", request, payload, idempotency_key, session)


@router.post("/users/{userId}/revoke-sessions", response_model=UserActionResponse)
def revoke_sessions(userId: str, request: Request, payload: UserActionRequest, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key", max_length=255)] = None, session: AuthenticatedSession = Depends(require_recent_auth_session)) -> Response:
    return _perform_action(userId, "revoke-sessions", request, payload, idempotency_key, session)
