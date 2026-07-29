"""Strict request and completed-artifact schemas for Admin V2 audit exports."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class AuditExportFilters(_StrictModel):
    search: str | None = Field(default=None, min_length=1, max_length=200)
    action: str | None = Field(default=None, min_length=1, max_length=200)
    outcome: str | None = Field(default=None, min_length=1, max_length=100)
    actor_id: str | None = Field(default=None, alias="actorId", min_length=1, max_length=200)
    target_type: str | None = Field(default=None, alias="targetType", min_length=1, max_length=100)
    target_id: str | None = Field(default=None, alias="targetId", min_length=1, max_length=200)
    occurred_from: datetime | None = Field(default=None, alias="occurredFrom")
    occurred_to: datetime | None = Field(default=None, alias="occurredTo")
    sort: Literal["occurredAt", "eventId", "action", "outcome"] = "occurredAt"
    sort_direction: Literal["asc", "desc"] = Field(default="desc", alias="sortDirection")

    @field_validator("search", "action", "outcome", "actor_id", "target_type", "target_id")
    @classmethod
    def reject_blank_values(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("filter must not be blank")
        return value

    @field_validator("occurred_from", "occurred_to")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("audit export time bounds must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_time_range(self) -> "AuditExportFilters":
        if (
            self.occurred_from is not None
            and self.occurred_to is not None
            and self.occurred_from > self.occurred_to
        ):
            raise ValueError("occurredFrom must not be after occurredTo")
        return self


class AuditExportRequest(_StrictModel):
    format: Literal["json", "csv"] = "json"
    filters: AuditExportFilters = Field(default_factory=AuditExportFilters)


class AuditExportResponse(_StrictModel):
    artifact_id: str = Field(alias="artifactId")
    status: Literal["completed"] = "completed"
    format: Literal["json", "csv"]
    file_name: str = Field(alias="fileName")
    row_count: int = Field(alias="rowCount", ge=0)
    byte_size: int = Field(alias="byteSize", ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: datetime = Field(alias="createdAt")
    expires_at: datetime = Field(alias="expiresAt")
