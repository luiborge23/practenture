"""Un-mounted Admin V2 router for read-only operational health."""

from __future__ import annotations

from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response

from .dependencies import require_admin_session
from .health_schemas import OperationsHealthResponse
from .health_service import operations_health_service
from .service import AuthenticatedSession


router = APIRouter(prefix="/operations", tags=["admin-v2-operations-health"])


@router.get("/health", response_model=OperationsHealthResponse)
def get_operations_health(
    request: Request,
    response: Response,
    _admin: AuthenticatedSession = Depends(require_admin_session),
) -> OperationsHealthResponse:
    """Return redacted, bounded SQLite health evidence for an authenticated Owner."""
    response.headers["Cache-Control"] = "no-store"
    request_id = str(
        getattr(request.state, "request_id", "")
        or request.headers.get("X-Request-ID")
        or f"req_{uuid4()}"
    )
    response.headers["X-Request-ID"] = request_id
    return operations_health_service.get_health(request_id=request_id)
