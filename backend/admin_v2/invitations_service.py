"""Domain orchestration for Admin V2 invitations."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import os
import secrets
from typing import cast
from uuid import uuid4

from .errors import AdminError
from .invitations_repository import (
    InvitationRecord,
    InvitationRepository,
    hash_invitation_secret,
)
from .invitations_schemas import (
    Invitation,
    InvitationCreateRequest,
    InvitationListResponse,
    InvitationResponse,
    InvitationResendRequest,
    InvitationStatus,
    PageInfo,
)
from .repository import MutationExecution, StoredResponse
from .service import AdminMutationService, AuthenticatedSession, mutation_service


_CREATE_ROUTE = "POST /api/admin/v2/invitations"
_REVOKE_ROUTE = "POST /api/admin/v2/invitations/{invitationId}/revoke"
_RESEND_ROUTE = "POST /api/admin/v2/invitations/{invitationId}/resend"
_PROCESS_INVITATION_KEY = secrets.token_bytes(32)


def _invitation_key() -> bytes:
    configured = (
        os.environ.get("PRACTENTURE_ADMIN_INVITATION_SECRET")
        or os.environ.get("PRACTENTURE_ADMIN_CSRF_SECRET")
        or os.environ.get("PRACTENTURE_JWT_SECRET")
    )
    return configured.encode("utf-8") if configured else _PROCESS_INVITATION_KEY


def _derive_secret(*, route: str, invitation_id: str, idempotency_key: str) -> str:
    """Derive a replayable high-entropy secret without persisting it.

    The server key and random invitation identifier provide cryptographic
    entropy. The idempotency key makes each resend rotate the credential while
    allowing an exact retry to reveal the same credential.
    """
    message = f"v1\0{route}\0{invitation_id}\0{idempotency_key}".encode("utf-8")
    digest = hmac.new(_invitation_key(), message, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def _masked(secret: str) -> str:
    return f"{secret[:4]}...{secret[-4:]}"


def _invitation(record: InvitationRecord) -> Invitation:
    return Invitation(
        id=record.id,
        organizationId=record.organization_id,
        intendedEmail=record.intended_email,
        status=cast(InvitationStatus, record.status),
        maskedCode=record.masked_code,
        expiresAt=datetime.fromisoformat(record.expires_at),
        issuedBy=record.issued_by,
        createdAt=datetime.fromisoformat(record.created_at),
        revokedAt=datetime.fromisoformat(record.revoked_at) if record.revoked_at else None,
        revokedBy=record.revoked_by,
        redeemedAt=datetime.fromisoformat(record.redeemed_at) if record.redeemed_at else None,
        notes=record.notes,
        changeTicket=record.change_ticket,
    )


def _body(model) -> dict:
    return model.model_dump(by_alias=True, mode="json")


def _with_one_time_secret(
    execution: MutationExecution, *, route: str, idempotency_key: str
) -> MutationExecution:
    invitation_id = str(execution.response.body["invitation"]["id"])
    secret = _derive_secret(
        route=route, invitation_id=invitation_id, idempotency_key=idempotency_key
    )
    body = dict(execution.response.body)
    body["secret"] = secret
    return MutationExecution(
        response=StoredResponse(
            status_code=execution.response.status_code,
            body=body,
            headers=execution.response.headers,
        ),
        replayed=execution.replayed,
        audit_event_id=execution.audit_event_id,
    )


class InvitationService:
    def __init__(
        self,
        repository: InvitationRepository | None = None,
        mutations: AdminMutationService | None = None,
    ) -> None:
        self.repository = repository or InvitationRepository()
        self.mutations = mutations or mutation_service

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def list_invitations(
        self,
        *,
        search: str | None,
        organization_id: str | None,
        status: str | None,
        sort: str,
        cursor: str | None,
        limit: int,
    ) -> InvitationListResponse:
        page = self.repository.list(
            search=search,
            organization_id=organization_id,
            status=status,
            sort=sort,
            cursor=cursor,
            limit=limit,
        )
        return InvitationListResponse(
            invitations=[_invitation(item) for item in page.items],
            pageInfo=PageInfo(
                nextCursor=page.next_cursor,
                hasNextPage=page.next_cursor is not None,
            ),
            totalCount=page.total_count,
        )

    def get_invitation(self, invitation_id: str) -> InvitationResponse:
        record = self.repository.get(invitation_id)
        if record is None:
            raise AdminError(404, "ADMIN_INVITATION_NOT_FOUND", "Invitation not found")
        return InvitationResponse(invitation=_invitation(record))

    def create_invitation(
        self,
        *,
        session: AuthenticatedSession,
        payload: InvitationCreateRequest,
        idempotency_key: str | None,
        request_id: str,
    ) -> MutationExecution:
        key = idempotency_key or ""
        invitation_id = f"inv_{uuid4()}"
        secret = _derive_secret(
            route=_CREATE_ROUTE, invitation_id=invitation_id, idempotency_key=key
        )
        now = self._now()
        expires_at = now + timedelta(hours=payload.expires_in_hours)
        request_payload = payload.model_dump(by_alias=True, mode="json")

        def create(conn) -> StoredResponse:
            created = self.repository.create(
                conn,
                invitation_id=invitation_id,
                secret_hash=hash_invitation_secret(secret),
                masked_code=_masked(secret),
                organization_id=payload.organization_id,
                intended_email=payload.intended_email,
                expires_at=expires_at.isoformat(),
                issued_by=session.record.owner_user_id,
                notes=payload.notes,
                change_ticket=payload.change_ticket,
                created_at=now.isoformat(),
            )
            # The persisted idempotency body intentionally omits the secret.
            return StoredResponse(
                201,
                _body(InvitationResponse(invitation=_invitation(created))),
                {"Location": f"/api/admin/v2/invitations/{created.id}"},
            )

        execution = self.mutations.execute_high_risk(
            session=session,
            route=_CREATE_ROUTE,
            idempotency_key=key,
            request_payload=request_payload,
            request_id=request_id,
            target={"type": "invitation", "id": invitation_id},
            action="invitation.create",
            metadata={
                "invitationId": invitation_id,
                "organizationId": payload.organization_id,
                "intendedEmail": payload.intended_email,
                "expiresAt": expires_at.isoformat(),
            },
            mutation=create,
        )
        return _with_one_time_secret(execution, route=_CREATE_ROUTE, idempotency_key=key)

    def revoke_invitation(
        self,
        *,
        session: AuthenticatedSession,
        invitation_id: str,
        reason: str | None,
        idempotency_key: str | None,
        request_id: str,
    ) -> MutationExecution:
        key = idempotency_key or ""
        normalized_reason = reason.strip() if reason else None
        now = self._now()

        def revoke(conn) -> StoredResponse:
            revoked = self.repository.revoke(
                conn,
                invitation_id=invitation_id,
                revoked_by=session.record.owner_user_id,
                now=now,
            )
            return StoredResponse(
                200, _body(InvitationResponse(invitation=_invitation(revoked))), {}
            )

        return self.mutations.execute_high_risk(
            session=session,
            route=_REVOKE_ROUTE,
            idempotency_key=key,
            request_payload={"invitationId": invitation_id, "reason": normalized_reason},
            request_id=request_id,
            target={"type": "invitation", "id": invitation_id},
            action="invitation.revoke",
            metadata={"invitationId": invitation_id, "reason": normalized_reason},
            mutation=revoke,
        )

    def resend_invitation(
        self,
        *,
        session: AuthenticatedSession,
        invitation_id: str,
        payload: InvitationResendRequest,
        idempotency_key: str | None,
        request_id: str,
    ) -> MutationExecution:
        key = idempotency_key or ""
        secret = _derive_secret(
            route=_RESEND_ROUTE, invitation_id=invitation_id, idempotency_key=key
        )
        now = self._now()
        expires_at = now + timedelta(hours=payload.expires_in_hours)

        def resend(conn) -> StoredResponse:
            updated = self.repository.resend(
                conn,
                invitation_id=invitation_id,
                secret_hash=hash_invitation_secret(secret),
                masked_code=_masked(secret),
                expires_at=expires_at.isoformat(),
                now=now,
            )
            return StoredResponse(
                200, _body(InvitationResponse(invitation=_invitation(updated))), {}
            )

        execution = self.mutations.execute_high_risk(
            session=session,
            route=_RESEND_ROUTE,
            idempotency_key=key,
            request_payload={
                "invitationId": invitation_id,
                "expiresInHours": payload.expires_in_hours,
            },
            request_id=request_id,
            target={"type": "invitation", "id": invitation_id},
            action="invitation.resend",
            metadata={
                "invitationId": invitation_id,
                "expiresAt": expires_at.isoformat(),
            },
            mutation=resend,
        )
        return _with_one_time_secret(execution, route=_RESEND_ROUTE, idempotency_key=key)


invitation_service = InvitationService()
