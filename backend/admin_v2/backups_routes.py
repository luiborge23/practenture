"""Standalone, intentionally unmounted Admin V2 operational backup router."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from .backups_schemas import (
    BackupCreateRequest,
    BackupCreateResponse,
    BackupListResponse,
    RestoreDrillListResponse,
)
from .backups_service import BackupService, backup_service
from .dependencies import require_admin_session, require_recent_auth_session
from .service import AuthenticatedSession


router = APIRouter(prefix="/operations", tags=["admin-v2-backups"])


def get_backup_service() -> BackupService:
    """Injection seam for isolated databases and backup roots in tests."""
    return backup_service


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or f"req_{secrets.token_urlsafe(18)}"


@router.get("/backups", response_model=BackupListResponse)
def list_backups(
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=1000)] = None,
    _session: AuthenticatedSession = Depends(require_admin_session),
    service: BackupService = Depends(get_backup_service),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return service.list_backups(limit, cursor)


@router.post(
    "/backups",
    response_model=BackupCreateResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_backup(
    request: Request,
    payload: BackupCreateRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255)
    ] = None,
    session: AuthenticatedSession = Depends(require_recent_auth_session),
    service: BackupService = Depends(get_backup_service),
) -> Response:
    execution = service.create_backup(
        session=session,
        label=payload.label,
        idempotency_key=idempotency_key,
        request_id=_request_id(request),
    )
    return JSONResponse(
        status_code=execution.response.status_code,
        content=execution.response.body,
        headers=dict(execution.response.headers),
    )


@router.get("/restore-drills", response_model=RestoreDrillListResponse)
def list_restore_drills(
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=1000)] = None,
    _session: AuthenticatedSession = Depends(require_admin_session),
    service: BackupService = Depends(get_backup_service),
) -> dict:
    response.headers["Cache-Control"] = "no-store"
    return service.list_restore_drills(limit, cursor)
