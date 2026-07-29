"""Un-mounted Admin V2 domain router for read-only operational sessions."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Response

from .dependencies import require_admin_session
from .service import AuthenticatedSession
from .sessions_schemas import OperationalSessionListResponse
from .sessions_service import operational_sessions_service

router = APIRouter(prefix="/sessions", tags=["admin-v2-sessions"])


@router.get("", response_model=OperationalSessionListResponse)
def list_operational_sessions(
    response: Response,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    search: Annotated[str | None, Query(min_length=1, max_length=100)] = None,
    state: Annotated[str | None, Query(min_length=1, max_length=32)] = None,
    scenario_id: Annotated[
        str | None, Query(alias="scenarioId", min_length=1, max_length=128)
    ] = None,
    professor_user_id: Annotated[
        str | None, Query(alias="professorUserId", min_length=1, max_length=128)
    ] = None,
    organization_id: Annotated[
        str | None, Query(alias="organizationId", min_length=1, max_length=128)
    ] = None,
    class_id: Annotated[
        str | None, Query(alias="classId", min_length=1, max_length=128)
    ] = None,
    created_from: Annotated[datetime | None, Query(alias="createdFrom")] = None,
    created_to: Annotated[datetime | None, Query(alias="createdTo")] = None,
    sort_by: Annotated[
        Literal["createdAt", "code", "state", "currentRound"],
        Query(alias="sortBy"),
    ] = "createdAt",
    sort_direction: Annotated[
        Literal["asc", "desc"], Query(alias="sortDirection")
    ] = "desc",
    cursor: str | None = None,
    _admin: AuthenticatedSession = Depends(require_admin_session),
) -> OperationalSessionListResponse:
    response.headers["Cache-Control"] = "no-store"
    return operational_sessions_service.list_sessions(
        limit=limit,
        search=search,
        state=state,
        scenario_id=scenario_id,
        professor_user_id=professor_user_id,
        organization_id=organization_id,
        class_id=class_id,
        created_from=created_from,
        created_to=created_to,
        sort_by=sort_by,
        sort_direction=sort_direction,
        cursor=cursor,
    )
