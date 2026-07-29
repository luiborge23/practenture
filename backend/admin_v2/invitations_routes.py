"""Owner-authenticated Admin V2 invitation routes.

This domain router is intentionally not mounted here; the composition root owns
registration after its API manifest review.
"""

from __future__ import annotations

import secrets
from typing import Annotated, Literal

from fastapi import APIRouter, Body, Depends, Header, Query, Request, Response, status
from fastapi.responses import JSONResponse

from .dependencies import require_admin_session, require_recent_auth_session
from .invitations_schemas import (
    InvitationCreateRequest,
    InvitationEmailDeliveryResponse,
    InvitationEmailSendRequest,
    InvitationListResponse,
    InvitationResponse,
    InvitationResendRequest,
    InvitationRevokeRequest,
    InvitationSecretResponse,
)
from .invitations_service import invitation_service
from .service import AuthenticatedSession


router = APIRouter(tags=["admin-v2-invitations"])


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", None) or f"req_{secrets.token_urlsafe(18)}"


def _mutation_response(execution) -> JSONResponse:
    return JSONResponse(
        status_code=execution.response.status_code,
        content=execution.response.body,
        headers=dict(execution.response.headers),
    )


@router.get("/invitations", response_model=InvitationListResponse)
def list_invitations(
    search: Annotated[str | None, Query(max_length=320)] = None,
    organization_id: Annotated[
        str | None, Query(alias="organizationId", max_length=255)
    ] = None,
    invitation_status: Annotated[
        Literal["ACTIVE", "REDEEMED", "EXPIRED", "REVOKED"] | None,
        Query(alias="status"),
    ] = None,
    sort: Annotated[str, Query(max_length=40)] = "-createdAt",
    cursor: Annotated[str | None, Query(max_length=1000)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    session: AuthenticatedSession = Depends(require_admin_session),
) -> InvitationListResponse:
    del session
    return invitation_service.list_invitations(
        search=search,
        organization_id=organization_id,
        status=invitation_status,
        sort=sort,
        cursor=cursor,
        limit=limit,
    )


@router.post(
    "/invitations",
    response_model=InvitationSecretResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_invitation(
    request: Request,
    payload: InvitationCreateRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255)
    ] = None,
    session: AuthenticatedSession = Depends(require_recent_auth_session),
) -> Response:
    execution = invitation_service.create_invitation(
        session=session,
        payload=payload,
        idempotency_key=idempotency_key,
        request_id=_request_id(request),
    )
    return _mutation_response(execution)


@router.get("/invitations/{invitationId}", response_model=InvitationResponse)
def get_invitation(
    invitationId: str,
    session: AuthenticatedSession = Depends(require_admin_session),
) -> InvitationResponse:
    del session
    return invitation_service.get_invitation(invitationId)


@router.post(
    "/invitations/{invitationId}/revoke", response_model=InvitationResponse
)
def revoke_invitation(
    invitationId: str,
    request: Request,
    payload: Annotated[InvitationRevokeRequest | None, Body()] = None,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255)
    ] = None,
    session: AuthenticatedSession = Depends(require_recent_auth_session),
) -> Response:
    execution = invitation_service.revoke_invitation(
        session=session,
        invitation_id=invitationId,
        reason=payload.reason if payload else None,
        idempotency_key=idempotency_key,
        request_id=_request_id(request),
    )
    return _mutation_response(execution)


@router.post(
    "/invitations/{invitationId}/resend", response_model=InvitationSecretResponse
)
def resend_invitation(
    invitationId: str,
    request: Request,
    payload: Annotated[InvitationResendRequest | None, Body()] = None,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255)
    ] = None,
    session: AuthenticatedSession = Depends(require_recent_auth_session),
) -> Response:
    execution = invitation_service.resend_invitation(
        session=session,
        invitation_id=invitationId,
        payload=payload or InvitationResendRequest(),
        idempotency_key=idempotency_key,
        request_id=_request_id(request),
    )
    return _mutation_response(execution)


@router.post(
    "/invitations/{invitationId}/send-email",
    response_model=InvitationEmailDeliveryResponse,
)
def send_invitation_email(
    invitationId: str,
    request: Request,
    payload: InvitationEmailSendRequest,
    idempotency_key: Annotated[
        str | None, Header(alias="Idempotency-Key", max_length=255)
    ] = None,
    session: AuthenticatedSession = Depends(require_recent_auth_session),
) -> InvitationEmailDeliveryResponse:
    return invitation_service.send_invitation_email(
        session=session,
        invitation_id=invitationId,
        payload=payload,
        idempotency_key=idempotency_key,
        request_id=_request_id(request),
    )
