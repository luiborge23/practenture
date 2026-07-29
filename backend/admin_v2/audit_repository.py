"""Read-only SQLite repository for immutable Admin V2 audit events."""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
from typing import Any

from database import db


@dataclass(frozen=True)
class AuditFilters:
    search: str | None = None
    action: str | None = None
    outcome: str | None = None
    actor_id: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    occurred_from: str | None = None
    occurred_to: str | None = None


@dataclass(frozen=True)
class AuditRecord:
    event_id: str
    request_id: str
    actor_json: str
    target_json: str
    action: str
    outcome: str
    metadata_json: str
    occurred_at: str


@dataclass(frozen=True)
class AuditRecordPage:
    records: tuple[AuditRecord, ...]
    next_cursor: str | None
    has_more: bool


_SORT_COLUMNS = {
    "occurredAt": "occurred_at",
    "eventId": "id",
    "action": "action",
    "outcome": "outcome",
}


class InvalidAuditCursor(ValueError):
    pass


class AdminAuditRepository:
    """Perform bounded, parameterized, keyset-paginated reads only."""

    MAX_CURSOR_LENGTH = 2048

    def __init__(self, database=db) -> None:
        self._db = database

    @staticmethod
    def _filter_fingerprint(filters: AuditFilters, sort: str, direction: str) -> str:
        payload = {
            "filters": {
                "search": filters.search,
                "action": filters.action,
                "outcome": filters.outcome,
                "actorId": filters.actor_id,
                "targetType": filters.target_type,
                "targetId": filters.target_id,
                "occurredFrom": filters.occurred_from,
                "occurredTo": filters.occurred_to,
            },
            "sort": sort,
            "direction": direction,
        }
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def _encode_cursor(
        cls,
        *,
        value: str,
        event_id: str,
        fingerprint: str,
    ) -> str:
        raw = json.dumps(
            {"v": 1, "value": value, "eventId": event_id, "query": fingerprint},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")

    @classmethod
    def _decode_cursor(cls, cursor: str, fingerprint: str) -> tuple[str, str]:
        if not cursor or len(cursor) > cls.MAX_CURSOR_LENGTH:
            raise InvalidAuditCursor("invalid cursor")
        try:
            padded = cursor + "=" * (-len(cursor) % 4)
            raw = base64.b64decode(padded, altchars=b"-_", validate=True)
            if len(raw) > 1024:
                raise ValueError
            payload = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise InvalidAuditCursor("invalid cursor") from exc
        if (
            not isinstance(payload, dict)
            or set(payload) != {"v", "value", "eventId", "query"}
            or payload.get("v") != 1
            or not isinstance(payload.get("value"), str)
            or not isinstance(payload.get("eventId"), str)
            or not payload["eventId"]
            or len(payload["value"]) > 4096
            or len(payload["eventId"]) > 512
            or payload.get("query") != fingerprint
        ):
            raise InvalidAuditCursor("invalid cursor")
        return payload["value"], payload["eventId"]

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def list_events(
        self,
        *,
        filters: AuditFilters,
        sort: str,
        direction: str,
        limit: int,
        cursor: str | None,
    ) -> AuditRecordPage:
        try:
            sort_column = _SORT_COLUMNS[sort]
        except KeyError as exc:
            raise ValueError("unsupported audit sort") from exc
        if direction not in {"asc", "desc"}:
            raise ValueError("unsupported audit sort direction")
        if not 1 <= limit <= 100:
            raise ValueError("audit page limit must be between 1 and 100")

        clauses: list[str] = []
        parameters: list[Any] = []
        if filters.search:
            needle = f"%{self._escape_like(filters.search)}%"
            clauses.append(
                "(" + " OR ".join(
                    f"{column} LIKE ? ESCAPE '\\'" for column in (
                        "id", "request_id", "actor_json", "target_json", "action",
                        "outcome", "metadata_json",
                    )
                ) + ")"
            )
            parameters.extend([needle] * 7)
        for column, value in (("action", filters.action), ("outcome", filters.outcome)):
            if value is not None:
                clauses.append(f"{column} = ?")
                parameters.append(value)
        for json_column, path, value in (
            ("actor_json", "$.id", filters.actor_id),
            ("target_json", "$.type", filters.target_type),
            ("target_json", "$.id", filters.target_id),
        ):
            if value is not None:
                clauses.append(
                    f"CASE WHEN json_valid({json_column}) "
                    f"THEN json_extract({json_column}, ?) END = ?"
                )
                parameters.extend((path, value))
        if filters.occurred_from is not None:
            clauses.append("occurred_at >= ?")
            parameters.append(filters.occurred_from)
        if filters.occurred_to is not None:
            clauses.append("occurred_at <= ?")
            parameters.append(filters.occurred_to)

        fingerprint = self._filter_fingerprint(filters, sort, direction)
        if cursor is not None:
            cursor_value, cursor_id = self._decode_cursor(cursor, fingerprint)
            operator = ">" if direction == "asc" else "<"
            if sort_column == "id":
                clauses.append(f"id {operator} ?")
                parameters.append(cursor_id)
            else:
                clauses.append(
                    f"({sort_column} {operator} ? OR ({sort_column} = ? AND id {operator} ?))"
                )
                parameters.extend((cursor_value, cursor_value, cursor_id))

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        order = "ASC" if direction == "asc" else "DESC"
        sql = (
            "SELECT id, request_id, actor_json, target_json, action, outcome, "
            "metadata_json, occurred_at FROM admin_audit_events"
            f"{where} ORDER BY {sort_column} {order}, id {order} LIMIT ?"
        )
        parameters.append(limit + 1)
        conn = self._db.connect()
        try:
            rows = conn.execute(sql, parameters).fetchall()
        finally:
            conn.close()

        has_more = len(rows) > limit
        visible = rows[:limit]
        records = tuple(AuditRecord(*tuple(row)) for row in visible)
        next_cursor = None
        if has_more and records:
            last_row = visible[-1]
            next_cursor = self._encode_cursor(
                value=str(last_row[sort_column]),
                event_id=str(last_row["id"]),
                fingerprint=fingerprint,
            )
        return AuditRecordPage(records, next_cursor, has_more)

    def get_event(self, event_id: str) -> AuditRecord | None:
        conn = self._db.connect()
        try:
            row = conn.execute(
                """SELECT id, request_id, actor_json, target_json, action, outcome,
                          metadata_json, occurred_at
                   FROM admin_audit_events WHERE id=?""",
                (event_id,),
            ).fetchone()
        finally:
            conn.close()
        return None if row is None else AuditRecord(*tuple(row))
