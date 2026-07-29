"""Typed camelCase contracts for Admin V2 overview and organizations."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


OrganizationStatus = Literal["active", "inactive"]


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class PageInfo(CamelModel):
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    has_next_page: bool = Field(alias="hasNextPage")


class Organization(CamelModel):
    id: str
    name: str
    university_name: str | None = Field(default=None, alias="universityName")
    slug: str
    status: OrganizationStatus
    created_by: str | None = Field(default=None, alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    version: str
    professor_count: int = Field(alias="professorCount", ge=0)
    student_count: int = Field(alias="studentCount", ge=0)
    session_count: int = Field(alias="sessionCount", ge=0)
    active_session_count: int = Field(alias="activeSessionCount", ge=0)


class OrganizationResponse(CamelModel):
    organization: Organization


class OrganizationListResponse(CamelModel):
    organizations: list[Organization]
    page_info: PageInfo = Field(alias="pageInfo")
    total_count: int = Field(alias="totalCount", ge=0)


class OrganizationCreateRequest(CamelModel):
    name: str = Field(min_length=1, max_length=200)
    university_name: str | None = Field(
        default=None, alias="universityName", max_length=300
    )
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    status: OrganizationStatus = "active"


class OrganizationPatchRequest(CamelModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    university_name: str | None = Field(
        default=None, alias="universityName", max_length=300
    )
    slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=100,
        pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
    )
    status: OrganizationStatus | None = None

    @model_validator(mode="after")
    def require_change(self) -> "OrganizationPatchRequest":
        if not self.model_fields_set:
            raise ValueError("at least one organization field is required")
        return self


class OverviewMetrics(CamelModel):
    organization_count: int = Field(alias="organizationCount", ge=0)
    active_organization_count: int = Field(alias="activeOrganizationCount", ge=0)
    user_count: int = Field(alias="userCount", ge=0)
    professor_count: int = Field(alias="professorCount", ge=0)
    student_count: int = Field(alias="studentCount", ge=0)
    session_count: int = Field(alias="sessionCount", ge=0)
    active_session_count: int = Field(alias="activeSessionCount", ge=0)


class OverviewResponse(CamelModel):
    overview: OverviewMetrics
