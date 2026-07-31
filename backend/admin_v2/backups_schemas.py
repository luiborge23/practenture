"""Typed contracts for the Admin V2 backup and restore-drill slice."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BackupCreateRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid", frozen=True)


class BackupVerificationResponse(BaseModel):
    quick_check: str = Field(alias="quickCheck")
    integrity_check: str = Field(alias="integrityCheck")
    foreign_key_violations: int = Field(alias="foreignKeyViolations", ge=0)
    table_counts: dict[str, int] = Field(alias="tableCounts")

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class BackupResponse(BaseModel):
    id: str
    status: str
    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime | None = Field(alias="endedAt")
    object_key: str | None = Field(alias="objectKey")
    sha256: str | None
    database_size: int | None = Field(alias="databaseSize", ge=0)
    migration_version: str | None = Field(alias="migrationVersion")
    label: str | None = None
    verification: BackupVerificationResponse | None
    restore_drill_id: str | None = Field(alias="restoreDrillId")

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class BackupCreateResponse(BaseModel):
    backup: BackupResponse

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class PageInfo(BaseModel):
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    has_next_page: bool = Field(alias="hasNextPage")

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class BackupListResponse(BaseModel):
    items: list[BackupResponse]
    total_count: int = Field(alias="totalCount", ge=0)
    page_info: PageInfo = Field(alias="pageInfo")

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class RestoreDrillResponse(BaseModel):
    id: str
    backup_id: str = Field(alias="backupId")
    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime | None = Field(alias="endedAt")
    status: str
    error_message: str | None = Field(alias="errorMessage")

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class RestoreDrillListResponse(BaseModel):
    items: list[RestoreDrillResponse]
    total_count: int = Field(alias="totalCount", ge=0)
    page_info: PageInfo = Field(alias="pageInfo")

    model_config = ConfigDict(populate_by_name=True, frozen=True)
