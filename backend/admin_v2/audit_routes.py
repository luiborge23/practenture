"""Owner-authenticated Admin V2 routes for immutable audit-event reads."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, Response

from .audit_schemas import (
    AuditEventDetailResponse,
    AuditEventListResponse,
    AuditSort,
    SortDirection,
)
from .audit_service import audit_service
from .dependencies import require_admin_session
from .service import AuthenticatedSession


router = APIRouter(prefix="/audit-events", tags=["admin-v2-audit"])

BoundedText = Annotated[str | None, Query(min_length=1, max_length=200)]


@router.get("", response_model=AuditEventListResponse)
def list_audit_events(
    response: Response,
    search: Annotated[str | None, Query(min_length=1, max_length=200)] = None,
    action: BoundedText = None,
    outcome: BoundedText = None,
    actor_id: Annotated[
        str | None, Query(alias="actorId", min_length=1, max_length=200)
    ] = None,
    target_type: Annotated[
        str | None, Query(alias="targetType", min_length=1, max_length=200)
    ] = None,
    target_id: Annotated[
        str | None, Query(alias="targetId", min_length=1, max_length=200)
    ] = None,
    occurred_from: Annotated[
        datetime | None, Query(alias="occurredFrom")
    ] = None,
    occurred_to: Annotated[
        datetime | None, Query(alias="occurredTo")
    ] = None,
    sort: AuditSort = AuditSort.occurred_at,
    sort_direction: Annotated[
        SortDirection, Query(alias="sortDirection")
    ] = SortDirection.desc,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    cursor: Annotated[str | None, Query(min_length=1, max_length=2048)] = None,
    _session: AuthenticatedSession = Depends(require_admin_session),
) -> AuditEventListResponse:
    result = audit_service.list_events(
        search=search,
        action=action,
        outcome=outcome,
        actor_id=actor_id,
        target_type=target_type,
        target_id=target_id,
        occurred_from=occurred_from,
        occurred_to=occurred_to,
        sort=sort.value,
        direction=sort_direction.value,
        limit=limit,
        cursor=cursor,
    )
    response.headers["Cache-Control"] = "no-store"
    return result


@router.get("/{event_id}", response_model=AuditEventDetailResponse)
def get_audit_event(
    response: Response,
    event_id: Annotated[str, Path(min_length=1, max_length=512)],
    _session: AuthenticatedSession = Depends(require_admin_session),
) -> AuditEventDetailResponse:
    result = audit_service.get_event(event_id)
    response.headers["Cache-Control"] = "no-store"
    return result
