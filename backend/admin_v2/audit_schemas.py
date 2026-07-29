"""Typed camelCase contracts for Admin V2 immutable audit-event reads."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, JsonValue


class AuditCamelModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        serialize_by_alias=True,
        frozen=True,
    )


class AuditSort(str, Enum):
    occurred_at = "occurredAt"
    event_id = "eventId"
    action = "action"
    outcome = "outcome"


class SortDirection(str, Enum):
    asc = "asc"
    desc = "desc"


class AuditEvent(AuditCamelModel):
    event_id: str = Field(alias="eventId")
    request_id: str = Field(alias="requestId")
    actor: JsonValue
    target: JsonValue
    action: str
    outcome: str
    metadata: JsonValue
    occurred_at: datetime = Field(alias="occurredAt")


class AuditPage(AuditCamelModel):
    limit: int
    has_more: bool = Field(alias="hasMore")
    next_cursor: str | None = Field(alias="nextCursor")


class AuditEventListResponse(AuditCamelModel):
    items: tuple[AuditEvent, ...]
    page: AuditPage


class AuditEventDetailResponse(AuditCamelModel):
    audit_event: AuditEvent = Field(alias="auditEvent")
