"""Typed camelCase contracts for Admin V2 operational session visibility."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class SessionScenarioResponse(BaseModel):
    id: str
    version: str

    model_config = ConfigDict(frozen=True)


class SessionProfessorResponse(BaseModel):
    user_id: str = Field(alias="userId")
    name: str | None = None
    email: str | None = None

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class SessionClassroomResponse(BaseModel):
    class_id: str = Field(alias="classId")
    name: str

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class SessionOrganizationResponse(BaseModel):
    organization_id: str = Field(alias="organizationId")
    name: str

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class SessionTeamSummaryResponse(BaseModel):
    total: int
    human: int
    ai: int

    model_config = ConfigDict(frozen=True)


class OperationalSessionResponse(BaseModel):
    session_id: str = Field(alias="sessionId")
    code: str
    state: str
    current_round: int = Field(alias="currentRound")
    total_rounds: int | None = Field(alias="totalRounds")
    scenario: SessionScenarioResponse
    created_at: datetime = Field(alias="createdAt")
    created_by: str | None = Field(alias="createdBy")
    professor: SessionProfessorResponse | None
    classroom: SessionClassroomResponse | None
    organizations: list[SessionOrganizationResponse]
    max_human_teams: int = Field(alias="maxHumanTeams")
    team_summary: SessionTeamSummaryResponse = Field(alias="teamSummary")
    configuration: dict[str, Any]
    teams: list[dict[str, Any]]
    data_warnings: list[str] = Field(alias="dataWarnings")

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class SessionPageResponse(BaseModel):
    limit: int
    has_more: bool = Field(alias="hasMore")
    next_cursor: str | None = Field(alias="nextCursor")

    model_config = ConfigDict(populate_by_name=True, frozen=True)


class OperationalSessionListResponse(BaseModel):
    items: list[OperationalSessionResponse]
    page: SessionPageResponse

    model_config = ConfigDict(populate_by_name=True, frozen=True)
