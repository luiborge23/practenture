"""Owner-authenticated Admin V2 overview and organization routes."""

from __future__ import annotations

import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from .dependencies import require_admin_session, require_csrf_session
from .organizations_schemas import (
    OrganizationCreateRequest,
    OrganizationListResponse,
    OrganizationPatchRequest,
    OrganizationResponse,
    OverviewResponse,
)
from .organizations_service import OrganizationService, organization_service
from .service import AuthenticatedSession


router = APIRouter(tags=["admin-v2-organizations"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or f"req_{secrets.token_urlsafe(18)}"


def _mutation_response(execution) -> JSONResponse:
    return JSONResponse(
        status_code=execution.response.status_code,
        content=execution.response.body,
        headers=dict(execution.response.headers),
    )


@router.get("/overview", response_model=OverviewResponse)
def get_overview(
    session: AuthenticatedSession = Depends(require_admin_session),
) -> OverviewResponse:
    del session
    return organization_service.get_overview()


@router.get("/organizations", response_model=OrganizationListResponse)
def list_organizations(
    search: Annotated[str | None, Query(max_length=200)] = None,
    organization_status: Annotated[
        Literal["active", "inactive"] | None, Query(alias="status")
    ] = None,
    sort: Annotated[str, Query(max_length=40)] = "name",
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    session: AuthenticatedSession = Depends(require_admin_session),
) -> OrganizationListResponse:
    del session
    return organization_service.list_organizations(
        search=search,
        status=organization_status,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/organizations",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    request: Request,
    payload: OrganizationCreateRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255)
    ] = None,
    session: AuthenticatedSession = Depends(require_csrf_session),
) -> Response:
    execution = organization_service.create_organization(
        session=session,
        payload=payload,
        idempotency_key=idempotency_key,
        request_id=_request_id(request),
    )
    return _mutation_response(execution)


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
def get_organization(
    organization_id: str,
    response: Response,
    session: AuthenticatedSession = Depends(require_admin_session),
) -> OrganizationResponse:
    del session
    result = organization_service.get_organization(organization_id)
    response.headers["ETag"] = f'"{result.organization.version}"'
    return result


@router.patch("/organizations/{organization_id}", response_model=OrganizationResponse)
def update_organization(
    organization_id: str,
    request: Request,
    payload: OrganizationPatchRequest,
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255)
    ] = None,
    session: AuthenticatedSession = Depends(require_csrf_session),
) -> Response:
    execution = organization_service.update_organization(
        session=session,
        organization_id=organization_id,
        payload=payload,
        if_match=if_match,
        idempotency_key=idempotency_key,
        request_id=_request_id(request),
    )
    return _mutation_response(execution)
