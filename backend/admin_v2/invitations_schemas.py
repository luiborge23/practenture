"""Typed camelCase contracts for the Admin V2 invitation domain."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


InvitationStatus = Literal["ACTIVE", "REDEEMED", "EXPIRED", "REVOKED"]


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class PageInfo(CamelModel):
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    has_next_page: bool = Field(alias="hasNextPage")


class Invitation(CamelModel):
    id: str
    organization_id: str = Field(alias="organizationId")
    intended_email: str = Field(alias="intendedEmail")
    status: InvitationStatus
    masked_code: str = Field(alias="maskedCode")
    expires_at: datetime = Field(alias="expiresAt")
    issued_by: str | None = Field(default=None, alias="issuedBy")
    created_at: datetime = Field(alias="createdAt")
    revoked_at: datetime | None = Field(default=None, alias="revokedAt")
    revoked_by: str | None = Field(default=None, alias="revokedBy")
    redeemed_at: datetime | None = Field(default=None, alias="redeemedAt")
    notes: str | None = None
    change_ticket: str | None = Field(default=None, alias="changeTicket")


class InvitationResponse(CamelModel):
    invitation: Invitation


class InvitationSecretResponse(InvitationResponse):
    secret: str = Field(min_length=32)


class InvitationListResponse(CamelModel):
    invitations: list[Invitation]
    page_info: PageInfo = Field(alias="pageInfo")
    total_count: int = Field(alias="totalCount", ge=0)


class InvitationCreateRequest(CamelModel):
    organization_id: str = Field(alias="organizationId", min_length=1, max_length=255)
    intended_email: str = Field(alias="intendedEmail", min_length=3, max_length=320)
    expires_in_hours: int = Field(default=48, alias="expiresInHours", ge=1, le=720)
    notes: str | None = Field(default=None, max_length=1000)
    change_ticket: str | None = Field(default=None, alias="changeTicket", max_length=255)

    @field_validator("organization_id", "intended_email")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value must not be blank")
        return value

    @field_validator("intended_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.casefold()
        local, separator, domain = value.rpartition("@")
        if not separator or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("a valid intended email is required")
        return value


class InvitationRevokeRequest(CamelModel):
    reason: str | None = Field(default=None, max_length=1000)


class InvitationResendRequest(CamelModel):
    expires_in_hours: int = Field(default=48, alias="expiresInHours", ge=1, le=720)


class InvitationEmailSendRequest(CamelModel):
    """Proof of possession for the just-disclosed invitation code.

    The secret is request-only: no response model includes it.
    """

    intended_email: str = Field(alias="intendedEmail", min_length=3, max_length=320)
    secret: str = Field(min_length=32, max_length=256)

    @field_validator("intended_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().casefold()
        local, separator, domain = value.rpartition("@")
        if not separator or not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
            raise ValueError("a valid intended email is required")
        return value


class InvitationEmailDelivery(CamelModel):
    id: str
    status: Literal["SENT", "FAILED"]
    recipient_email: str = Field(alias="recipientEmail")
    provider: str | None = None
    provider_message_id: str | None = Field(default=None, alias="providerMessageId")
    failed_code: str | None = Field(default=None, alias="failedCode")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class InvitationEmailDeliveryResponse(CamelModel):
    delivery: InvitationEmailDelivery
