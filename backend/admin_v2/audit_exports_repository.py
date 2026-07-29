"""Bounded transaction-local reads for Admin V2 audit export creation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
import sqlite3
from typing import Any

from admin_v2.audit_exports_schemas import AuditExportFilters


@dataclass(frozen=True)
class AuditExportRecord:
    event_id: str
    request_id: str
    actor_json: str
    target_json: str
    action: str
    outcome: str
    metadata_json: str
    occurred_at: str


_SORT_COLUMNS = {
    "occurredAt": "occurred_at",
    "eventId": "id",
    "action": "action",
    "outcome": "outcome",
}


class AdminAuditExportRepository:
    """Read at most ``row_limit + 1`` rows through a caller-owned transaction."""

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    def list_for_export(
        self,
        conn: sqlite3.Connection,
        *,
        filters: AuditExportFilters,
        row_limit: int,
    ) -> tuple[AuditExportRecord, ...]:
        if row_limit < 1:
            raise ValueError("row_limit must be positive")
        sort_column = _SORT_COLUMNS[filters.sort]
        direction = "ASC" if filters.sort_direction == "asc" else "DESC"
        clauses: list[str] = []
        parameters: list[Any] = []

        if filters.search:
            needle = f"%{self._escape_like(filters.search)}%"
            clauses.append(
                "(" + " OR ".join(
                    f"{column} LIKE ? ESCAPE '\\'"
                    for column in (
                        "id",
                        "request_id",
                        "actor_json",
                        "target_json",
                        "action",
                        "outcome",
                        "metadata_json",
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
            parameters.append(filters.occurred_from.astimezone(timezone.utc).isoformat())
        if filters.occurred_to is not None:
            clauses.append("occurred_at <= ?")
            parameters.append(filters.occurred_to.astimezone(timezone.utc).isoformat())

        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        sql = (
            "SELECT id, request_id, actor_json, target_json, action, outcome, "
            "metadata_json, occurred_at FROM admin_audit_events"
            f"{where} ORDER BY {sort_column} {direction}, id {direction} LIMIT ?"
        )
        parameters.append(row_limit + 1)
        rows = conn.execute(sql, parameters).fetchall()
        return tuple(AuditExportRecord(*tuple(row)) for row in rows)
