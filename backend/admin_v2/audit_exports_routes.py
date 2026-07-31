"""Standalone, intentionally unmounted Admin V2 audit export router."""

from __future__ import annotations

import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request, Response, status
from fastapi.responses import FileResponse, JSONResponse

from admin_v2.dependencies import require_admin_session, require_recent_auth_session
from admin_v2.service import AuthenticatedSession

from .audit_exports_schemas import AuditExportRequest, AuditExportResponse
from .audit_exports_service import audit_export_service


router = APIRouter(tags=["admin-v2-audit-exports"])


def _request_id(request: Request) -> str:
    return (
        getattr(request.state, "request_id", None)
        or request.headers.get("X-Request-ID")
        or f"req_{secrets.token_urlsafe(18)}"
    )


@router.get("/audit-events/exports/{artifact_id}", include_in_schema=False)
def download_audit_export(
    artifact_id: str,
    session: AuthenticatedSession = Depends(require_admin_session),
) -> FileResponse:
    del session
    path, media_type = audit_export_service.resolve_download(artifact_id)
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        headers={
            "Cache-Control": "no-store, max-age=0",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post(
    "/audit-events/exports",
    response_model=AuditExportResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_audit_export(
    request: Request,
    payload: AuditExportRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255)
    ] = None,
    session: AuthenticatedSession = Depends(require_recent_auth_session),
) -> Response:
    request_id = _request_id(request)
    execution = audit_export_service.create(
        session=session,
        request=payload,
        idempotency_key=idempotency_key,  # type: ignore[arg-type]
        request_id=request_id,
    )
    headers = dict(execution.response.headers)
    headers["X-Request-ID"] = request_id
    headers["Idempotency-Replayed"] = "true" if execution.replayed else "false"
    headers["Cache-Control"] = "no-store"
    return JSONResponse(
        status_code=execution.response.status_code,
        content=execution.response.body,
        headers=headers,
    )
