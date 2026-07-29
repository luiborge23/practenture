"""Typed camelCase contracts for Admin V2 user administration."""
from __future__ import annotations

from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator

UserRole = Literal["owner", "professor", "student"]
UserStatus = Literal["active", "suspended"]


class CamelModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True, serialize_by_alias=True)


class PageInfo(CamelModel):
    next_cursor: str | None = Field(default=None, alias="nextCursor")
    has_next_page: bool = Field(alias="hasNextPage")


class User(CamelModel):
    id: str
    username: str
    role: UserRole
    status: UserStatus
    name: str | None = None
    email: str | None = None
    provider: str
    organization_ids: list[str] = Field(default_factory=list, alias="organizationIds")
    must_change_password: bool = Field(alias="mustChangePassword")
    last_login_at: datetime | None = Field(default=None, alias="lastLoginAt")
    created_by: str | None = Field(default=None, alias="createdBy")
    created_at: datetime | None = Field(default=None, alias="createdAt")
    disabled_at: datetime | None = Field(default=None, alias="disabledAt")
    disabled_by: str | None = Field(default=None, alias="disabledBy")
    disable_reason: str | None = Field(default=None, alias="disableReason")


class UserResponse(CamelModel):
    user: User


class UserListResponse(CamelModel):
    users: list[User]
    page_info: PageInfo = Field(alias="pageInfo")
    total_count: int = Field(alias="totalCount", ge=0)


class UserPrecreateRequest(CamelModel):
    username: str = Field(min_length=3, max_length=100, pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
    role: Literal["professor", "student"]
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=320, pattern=r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
    organization_id: str | None = Field(default=None, alias="organizationId", max_length=200)

    @field_validator("username", "name")
    @classmethod
    def strip_required(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("value is required")
        return value


class UserPrecreateResponse(CamelModel):
    user: User
    temporary_password: str = Field(alias="temporaryPassword")


class UserActionRequest(CamelModel):
    reason: str | None = Field(default=None, max_length=1000)

    @field_validator("reason")
    @classmethod
    def strip_reason(cls, value: str | None) -> str | None:
        return value.strip() or None if value is not None else None


class UserActionResponse(CamelModel):
    user: User
    sessions_revoked: bool = Field(default=False, alias="sessionsRevoked")
