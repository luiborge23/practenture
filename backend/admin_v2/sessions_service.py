"""Projection, redaction, and keyset-cursor logic for session visibility."""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from .errors import AdminError
from .redaction import redact_secrets
from .sessions_repository import OperationalSessionsRepository, SessionListQuery
from .sessions_schemas import (
    OperationalSessionListResponse,
    OperationalSessionResponse,
    SessionClassroomResponse,
    SessionOrganizationResponse,
    SessionPageResponse,
    SessionProfessorResponse,
    SessionScenarioResponse,
    SessionTeamSummaryResponse,
)

_CURSOR_VERSION = 1
_MAX_CURSOR_LENGTH = 2_048
_VALID_STATES = frozenset({"creating", "active", "completed", "finished"})


class OperationalSessionsService:
    def __init__(self, repository: OperationalSessionsRepository | None = None) -> None:
        self.repository = repository or OperationalSessionsRepository()

    def list_sessions(
        self,
        *,
        limit: int,
        search: str | None,
        state: str | None,
        scenario_id: str | None,
        professor_user_id: str | None,
        organization_id: str | None,
        class_id: str | None,
        created_from: datetime | None,
        created_to: datetime | None,
        sort_by: str,
        sort_direction: str,
        cursor: str | None,
    ) -> OperationalSessionListResponse:
        normalized_search = search.strip() if search else None
        if not normalized_search:
            normalized_search = None
        if state is not None and state not in _VALID_STATES:
            raise AdminError(400, "ADMIN_SESSIONS_STATE_INVALID", "Session state is invalid")
        self._require_aware(created_from)
        self._require_aware(created_to)
        if created_from and created_to and created_from > created_to:
            raise AdminError(
                400,
                "ADMIN_SESSIONS_TIME_RANGE_INVALID",
                "Session time range is invalid",
            )

        fingerprint = self._query_fingerprint(
            search=normalized_search,
            state=state,
            scenario_id=scenario_id,
            professor_user_id=professor_user_id,
            organization_id=organization_id,
            class_id=class_id,
            created_from=created_from,
            created_to=created_to,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
        cursor_sort_value: str | int | float | None = None
        cursor_code: str | None = None
        if cursor:
            cursor_sort_value, cursor_code = self._decode_cursor(
                cursor, fingerprint, sort_by
            )

        query = SessionListQuery(
            limit=limit,
            search=normalized_search,
            state=state,
            scenario_id=scenario_id,
            professor_user_id=professor_user_id,
            organization_id=organization_id,
            class_id=class_id,
            created_from=created_from,
            created_to=created_to,
            sort_by=sort_by,
            sort_direction=sort_direction,
            cursor_sort_value=cursor_sort_value,
            cursor_code=cursor_code,
        )
        page = self.repository.list_sessions(query)
        items = [
            self._project(row, page.organizations_by_professor)
            for row in page.rows
        ]
        next_cursor = None
        if page.has_more and page.rows:
            last = page.rows[-1]
            next_cursor = self._encode_cursor(
                fingerprint, last["cursor_sort_value"], last["code"]
            )
        return OperationalSessionListResponse(
            items=items,
            page=SessionPageResponse(
                limit=limit, hasMore=page.has_more, nextCursor=next_cursor
            ),
        )

    @staticmethod
    def _project(
        row: dict[str, Any],
        organizations_by_professor: dict[str, list[dict[str, str]]],
    ) -> OperationalSessionResponse:
        warnings: list[str] = []
        configuration = OperationalSessionsService._parse_object_json(
            row.get("config_json"), "invalidConfigurationJson", warnings
        )
        teams = OperationalSessionsService._parse_teams(row.get("teams_json"), warnings)
        safe_configuration = redact_secrets(
            configuration, max_depth=10, max_items=250, max_string_length=1_024
        )
        safe_teams = [
            redact_secrets(team, max_depth=10, max_items=250, max_string_length=1_024)
            for team in teams
        ]
        ai_count = sum(1 for team in teams if team.get("isAI") is True)
        total_rounds = configuration.get("totalRounds")
        if isinstance(total_rounds, bool) or not isinstance(total_rounds, int):
            total_rounds = None

        professor_id = row.get("professor_user_id")
        professor = None
        if professor_id:
            professor = SessionProfessorResponse(
                userId=professor_id,
                name=row.get("professor_name"),
                email=row.get("professor_email"),
            )
        classroom = None
        if row.get("class_id"):
            classroom = SessionClassroomResponse(
                classId=row["class_id"], name=row.get("class_name") or ""
            )
        created_at = OperationalSessionsService._parse_created_at(
            row.get("created_at"), warnings
        )
        organizations = [
            SessionOrganizationResponse(
                organizationId=organization["organization_id"],
                name=organization["name"],
            )
            for organization in organizations_by_professor.get(professor_id or "", [])
        ]
        return OperationalSessionResponse(
            sessionId=row.get("session_id") or "",
            code=row.get("code") or "",
            state=row.get("state") or "",
            currentRound=int(row.get("current_round") or 0),
            totalRounds=total_rounds,
            scenario=SessionScenarioResponse(
                id=row.get("scenario_id") or "",
                version=row.get("scenario_version") or "",
            ),
            createdAt=created_at,
            createdBy=row.get("created_by"),
            professor=professor,
            classroom=classroom,
            organizations=organizations,
            maxHumanTeams=int(row.get("max_human_teams") or 0),
            teamSummary=SessionTeamSummaryResponse(
                total=len(teams), human=len(teams) - ai_count, ai=ai_count
            ),
            configuration=safe_configuration,
            teams=safe_teams,
            dataWarnings=warnings,
        )

    @staticmethod
    def _parse_object_json(
        raw: Any, warning: str, warnings: list[str]
    ) -> dict[str, Any]:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError, json.JSONDecodeError):
            warnings.append(warning)
            return {}
        if not isinstance(value, dict):
            warnings.append(warning)
            return {}
        return value

    @staticmethod
    def _parse_teams(raw: Any, warnings: list[str]) -> list[dict[str, Any]]:
        try:
            value = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, ValueError, json.JSONDecodeError):
            warnings.append("invalidTeamsJson")
            return []
        if not isinstance(value, list) or any(not isinstance(team, dict) for team in value):
            warnings.append("invalidTeamsJson")
            return []
        return value

    @staticmethod
    def _parse_created_at(raw: Any, warnings: list[str]) -> datetime:
        try:
            parsed = datetime.fromisoformat(str(raw))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except (TypeError, ValueError):
            warnings.append("invalidCreatedAt")
            return datetime(1970, 1, 1, tzinfo=timezone.utc)

    @staticmethod
    def _require_aware(value: datetime | None) -> None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise AdminError(
                400,
                "ADMIN_SESSIONS_TIME_RANGE_INVALID",
                "Session time range is invalid",
            )

    @staticmethod
    def _query_fingerprint(**values: Any) -> str:
        canonical: dict[str, Any] = {}
        for key, value in values.items():
            if isinstance(value, datetime):
                value = value.astimezone(timezone.utc).isoformat()
            canonical[key] = value
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @staticmethod
    def _encode_cursor(fingerprint: str, sort_value: Any, code: str) -> str:
        payload = json.dumps(
            {"v": _CURSOR_VERSION, "q": fingerprint, "s": sort_value, "c": code},
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return base64.urlsafe_b64encode(payload).decode().rstrip("=")

    @staticmethod
    def _decode_cursor(
        cursor: str, fingerprint: str, sort_by: str
    ) -> tuple[str | int | float, str]:
        try:
            if not cursor or len(cursor) > _MAX_CURSOR_LENGTH:
                raise ValueError
            padding = "=" * (-len(cursor) % 4)
            decoded = base64.b64decode(
                cursor + padding, altchars=b"-_", validate=True
            )
            payload = json.loads(decoded)
            if (
                not isinstance(payload, dict)
                or set(payload) != {"v", "q", "s", "c"}
                or payload["v"] != _CURSOR_VERSION
                or payload["q"] != fingerprint
                or not isinstance(payload["c"], str)
                or not payload["c"]
            ):
                raise ValueError
            sort_value = payload["s"]
            if sort_by in {"code", "state"}:
                valid_sort = isinstance(sort_value, str)
            elif sort_by == "currentRound":
                valid_sort = isinstance(sort_value, int) and not isinstance(sort_value, bool)
            else:
                valid_sort = isinstance(sort_value, (int, float)) and not isinstance(
                    sort_value, bool
                )
            if not valid_sort:
                raise ValueError
            return sort_value, payload["c"]
        except (ValueError, TypeError, KeyError, UnicodeDecodeError, binascii.Error, json.JSONDecodeError):
            raise AdminError(
                400,
                "ADMIN_SESSIONS_CURSOR_INVALID",
                "Session cursor is invalid",
            ) from None


operational_sessions_service = OperationalSessionsService()
