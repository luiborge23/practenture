"""Typed, redacted contracts for Admin V2 operational database health."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class HealthCheckResponse(BaseModel):
    code: str
    status: Literal["pass", "warn", "fail"]
    severity: Literal["info", "warning", "critical"]
    affected_count: int = Field(alias="affectedCount", ge=0)
    sample_ids: list[str] = Field(alias="sampleIds")
    details: dict[str, Any]

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class HealthEngineResponse(BaseModel):
    name: Literal["sqlite"] = "sqlite"
    version: str | None
    migration_version: str | None = Field(alias="migrationVersion")
    expected_migration_version: str = Field(alias="expectedMigrationVersion")

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class HealthSummaryResponse(BaseModel):
    passed: int = Field(ge=0)
    warnings: int = Field(ge=0)
    failed: int = Field(ge=0)

    model_config = ConfigDict(frozen=True)


class OperationsHealthResponse(BaseModel):
    status: Literal["healthy", "degraded", "unhealthy"]
    checked_at: datetime = Field(alias="checkedAt")
    request_id: str = Field(alias="requestId")
    engine: HealthEngineResponse
    summary: HealthSummaryResponse
    checks: list[HealthCheckResponse]

    model_config = ConfigDict(populate_by_name=True, frozen=True)
