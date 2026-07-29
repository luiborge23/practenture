"""Read-only, bounded SQLite access for Admin V2 operational sessions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from database import db


_SORT_EXPRESSIONS = {
    "createdAt": "COALESCE(julianday(s.created_at), -1.0)",
    "code": "s.code",
    "state": "s.state",
    "currentRound": "COALESCE(s.current_round, 0)",
}


@dataclass(frozen=True)
class SessionListQuery:
    limit: int
    search: str | None
    state: str | None
    scenario_id: str | None
    professor_user_id: str | None
    organization_id: str | None
    class_id: str | None
    created_from: datetime | None
    created_to: datetime | None
    sort_by: str
    sort_direction: str
    cursor_sort_value: str | int | float | None = None
    cursor_code: str | None = None


@dataclass(frozen=True)
class SessionRowsPage:
    rows: list[dict[str, Any]]
    organizations_by_professor: dict[str, list[dict[str, str]]]
    has_more: bool


class OperationalSessionsRepository:
    """Perform at most two bounded reads for one list page; never mutate state."""

    def list_sessions(self, query: SessionListQuery) -> SessionRowsPage:
        sort_expression = _SORT_EXPRESSIONS[query.sort_by]
        where: list[str] = []
        params: list[Any] = []

        if query.search:
            escaped = self._escape_like(query.search)
            pattern = f"%{escaped}%"
            where.append(
                "("
                "s.code LIKE ? ESCAPE '\\' OR s.session_id LIKE ? ESCAPE '\\' OR "
                "COALESCE(s.created_by, '') LIKE ? ESCAPE '\\' OR "
                "COALESCE(s.professor_user_id, '') LIKE ? ESCAPE '\\' OR "
                "COALESCE(u.name, '') LIKE ? ESCAPE '\\' OR "
                "COALESCE(u.email, '') LIKE ? ESCAPE '\\' OR "
                "COALESCE(c.name, '') LIKE ? ESCAPE '\\' OR "
                "s.scenario_id LIKE ? ESCAPE '\\' OR "
                "EXISTS (SELECT 1 FROM memberships sm "
                "JOIN organizations so ON so.id = sm.org_id "
                "WHERE sm.user_id = s.professor_user_id "
                "AND so.name LIKE ? ESCAPE '\\')"
                ")"
            )
            params.extend([pattern] * 9)
        if query.state:
            where.append("s.state = ?")
            params.append(query.state)
        if query.scenario_id:
            where.append("s.scenario_id = ?")
            params.append(query.scenario_id)
        if query.professor_user_id:
            where.append("s.professor_user_id = ?")
            params.append(query.professor_user_id)
        if query.organization_id:
            where.append(
                "EXISTS (SELECT 1 FROM memberships fm "
                "WHERE fm.user_id = s.professor_user_id AND fm.org_id = ?)"
            )
            params.append(query.organization_id)
        if query.class_id:
            where.append("s.class_id = ?")
            params.append(query.class_id)
        if query.created_from:
            where.append("julianday(s.created_at) >= julianday(?)")
            params.append(self._sqlite_datetime(query.created_from))
        if query.created_to:
            where.append("julianday(s.created_at) <= julianday(?)")
            params.append(self._sqlite_datetime(query.created_to))
        if query.cursor_code is not None:
            operator = ">" if query.sort_direction == "asc" else "<"
            where.append(
                f"({sort_expression} {operator} ? OR "
                f"({sort_expression} = ? AND s.code {operator} ?))"
            )
            params.extend(
                [query.cursor_sort_value, query.cursor_sort_value, query.cursor_code]
            )

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        direction = "ASC" if query.sort_direction == "asc" else "DESC"
        sql = f"""
            SELECT s.code, s.session_id, s.config_json, s.teams_json,
                   s.created_by, s.professor_user_id, s.class_id,
                   COALESCE(s.max_human_teams, 30) AS max_human_teams,
                   COALESCE(s.current_round, 0) AS current_round,
                   s.state, s.scenario_id, s.scenario_version, s.created_at,
                   u.name AS professor_name, u.email AS professor_email,
                   c.name AS class_name, {sort_expression} AS cursor_sort_value
              FROM sessions s
              LEFT JOIN users u ON u.username = s.professor_user_id
              LEFT JOIN classes c ON c.id = s.class_id
              {where_sql}
             ORDER BY {sort_expression} {direction}, s.code {direction}
             LIMIT ?
        """
        params.append(query.limit + 1)

        conn = db.connect()
        try:
            fetched = [dict(row) for row in conn.execute(sql, params).fetchall()]
            has_more = len(fetched) > query.limit
            rows = fetched[: query.limit]
            organizations = self._load_organizations(conn, rows)
        finally:
            conn.close()
        return SessionRowsPage(rows, organizations, has_more)

    @staticmethod
    def _load_organizations(conn, rows: list[dict[str, Any]]) -> dict[str, list[dict[str, str]]]:
        professor_ids = sorted(
            {str(row["professor_user_id"]) for row in rows if row["professor_user_id"]}
        )
        result: dict[str, list[dict[str, str]]] = {
            professor_id: [] for professor_id in professor_ids
        }
        if not professor_ids:
            return result
        placeholders = ",".join("?" for _ in professor_ids)
        org_rows = conn.execute(
            f"""SELECT m.user_id, o.id, o.name
                  FROM memberships m
                  JOIN organizations o ON o.id = m.org_id
                 WHERE m.user_id IN ({placeholders})
                 ORDER BY o.name ASC, o.id ASC""",
            professor_ids,
        ).fetchall()
        for row in org_rows:
            result[row["user_id"]].append(
                {"organization_id": row["id"], "name": row["name"]}
            )
        return result

    @staticmethod
    def _escape_like(value: str) -> str:
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _sqlite_datetime(value: datetime) -> str:
        normalized = value.astimezone(timezone.utc)
        return normalized.strftime("%Y-%m-%d %H:%M:%S.%f")
