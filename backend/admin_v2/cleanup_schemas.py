"""Typed contracts for bounded Admin V2 cleanup plans."""
from __future__ import annotations
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, field_validator

class CleanupSelector(BaseModel):
    session_codes: list[str] = Field(alias="sessionCodes", min_length=1, max_length=100)
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)

    @field_validator("session_codes")
    @classmethod
    def validate_codes(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values]
        if any(not value for value in normalized):
            raise ValueError("session codes must be nonblank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("session codes must be unique")
        return sorted(normalized)

class CleanupPlanCreateRequest(BaseModel):
    selector: CleanupSelector
    model_config = ConfigDict(extra="forbid", frozen=True)

class CleanupExecuteRequest(BaseModel):
    plan_hash: str = Field(alias="planHash", min_length=64, max_length=64, pattern=r"^[0-9a-f]{64}$")
    confirmation: str = Field(min_length=1, max_length=512)
    model_config = ConfigDict(extra="forbid", populate_by_name=True, frozen=True)

class CleanupPlanResponse(BaseModel):
    plan: dict
    model_config = ConfigDict(frozen=True)

class CleanupExecutionResponse(BaseModel):
    plan_id: str = Field(alias="planId")
    status: str
    deleted_counts: dict[str, int] = Field(alias="deletedCounts")
    completed_at: datetime = Field(alias="completedAt")
    model_config = ConfigDict(populate_by_name=True, frozen=True)
