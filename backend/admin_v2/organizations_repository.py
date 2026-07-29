"""SQLite persistence for Admin V2 overview and organization resources.

Schema ownership remains with Alembic. This repository deliberately creates no
runtime tables and can read legacy organization rows that predate slug/status.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import json
import re
import sqlite3
import unicodedata
from typing import Any

from database import db
from .errors import AdminError


_ACTIVE_SESSION_STATES = ("creating", "active", "running", "paused")
_SORT_COLUMNS = {
    "name": "lower(o.name)",
    "universityName": "lower(COALESCE(o.university_name, ''))",
    "createdAt": "o.created_at",
    "status": "effective_status",
}


@dataclass(frozen=True)
class OrganizationRecord:
    id: str
    name: str
    university_name: str | None
    slug: str
    status: str
    created_by: str | None
    created_at: str
    professor_count: int
    student_count: int
    session_count: int
    active_session_count: int
    version: str


@dataclass(frozen=True)
class OrganizationPage:
    items: list[OrganizationRecord]
    total_count: int
    next_cursor: str | None


@dataclass(frozen=True)
class OverviewRecord:
    organization_count: int
    active_organization_count: int
    user_count: int
    professor_count: int
    student_count: int
    session_count: int
    active_session_count: int


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.casefold()).strip("-")
    return slug[:100] or "organization"


def _version(values: dict[str, Any]) -> str:
    canonical = json.dumps(values, sort_keys=True, separators=(",", ":"), default=str)
    return "orgv_" + hashlib.sha256(canonical.encode()).hexdigest()[:24]


def _cursor_fingerprint(*, search: str | None, status: str | None, sort: str) -> str:
    value = json.dumps(
        {"search": search or "", "status": status or "", "sort": sort},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(value.encode()).hexdigest()[:16]


def _encode_cursor(offset: int, fingerprint: str) -> str:
    raw = json.dumps({"v": 1, "o": offset, "f": fingerprint}, separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode()).decode().rstrip("=")


def _decode_cursor(value: str | None, fingerprint: str) -> int:
    if value is None:
        return 0
    try:
        padded = value + "=" * (-len(value) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode()).decode())
        if (
            payload.get("v") != 1
            or payload.get("f") != fingerprint
            or not isinstance(payload.get("o"), int)
            or payload["o"] < 0
        ):
            raise ValueError
        return payload["o"]
    except (ValueError, TypeError, KeyError, json.JSONDecodeError, UnicodeDecodeError):
        raise AdminError(400, "ADMIN_CURSOR_INVALID", "Cursor is invalid for this query")


class OrganizationRepository:
    def __init__(self, database=db) -> None:
        self._db = database

    @staticmethod
    def _columns(conn: sqlite3.Connection) -> set[str]:
        return {str(row[1]) for row in conn.execute("PRAGMA table_info(organizations)")}

    @classmethod
    def _select_sql(cls, conn: sqlite3.Connection) -> str:
        columns = cls._columns(conn)
        slug_expr = "COALESCE(o.slug, '')" if "slug" in columns else "''"
        status_expr = "COALESCE(o.status, 'active')" if "status" in columns else "'active'"
        active_marks = ",".join("?" for _ in _ACTIVE_SESSION_STATES)
        return f"""
            SELECT o.id, o.name, o.university_name, {slug_expr} AS effective_slug,
                   {status_expr} AS effective_status, o.created_by, o.created_at,
                   (SELECT COUNT(*) FROM memberships m
                    WHERE m.org_id=o.id AND m.role='professor') AS professor_count,
                   (SELECT COUNT(*) FROM memberships m
                    WHERE m.org_id=o.id AND m.role='student') AS student_count,
                   (SELECT COUNT(*) FROM sessions s
                    JOIN memberships m ON m.user_id=s.professor_user_id
                    WHERE m.org_id=o.id AND m.role='professor') AS session_count,
                   (SELECT COUNT(*) FROM sessions s
                    JOIN memberships m ON m.user_id=s.professor_user_id
                    WHERE m.org_id=o.id AND m.role='professor'
                      AND s.state IN ({active_marks})) AS active_session_count
            FROM organizations o
        """

    @staticmethod
    def _record(row: sqlite3.Row) -> OrganizationRecord:
        raw = {
            "id": row["id"],
            "name": row["name"],
            "university_name": row["university_name"],
            "slug": row["effective_slug"] or slugify(row["name"]),
            "status": row["effective_status"],
            "created_by": row["created_by"],
            "created_at": row["created_at"],
        }
        return OrganizationRecord(
            **raw,
            professor_count=int(row["professor_count"]),
            student_count=int(row["student_count"]),
            session_count=int(row["session_count"]),
            active_session_count=int(row["active_session_count"]),
            version=_version(raw),
        )

    def overview(self) -> OverviewRecord:
        conn = self._db.connect()
        try:
            columns = self._columns(conn)
            status_expr = "COALESCE(status, 'active')" if "status" in columns else "'active'"
            org = conn.execute(
                f"SELECT COUNT(*), SUM(CASE WHEN {status_expr}='active' THEN 1 ELSE 0 END) "
                "FROM organizations"
            ).fetchone()
            users = conn.execute(
                """SELECT COUNT(*),
                          SUM(CASE WHEN role='professor' THEN 1 ELSE 0 END),
                          SUM(CASE WHEN role='student' THEN 1 ELSE 0 END)
                   FROM users"""
            ).fetchone()
            marks = ",".join("?" for _ in _ACTIVE_SESSION_STATES)
            sessions = conn.execute(
                f"SELECT COUNT(*), SUM(CASE WHEN state IN ({marks}) THEN 1 ELSE 0 END) FROM sessions",
                _ACTIVE_SESSION_STATES,
            ).fetchone()
            return OverviewRecord(
                organization_count=int(org[0] or 0),
                active_organization_count=int(org[1] or 0),
                user_count=int(users[0] or 0),
                professor_count=int(users[1] or 0),
                student_count=int(users[2] or 0),
                session_count=int(sessions[0] or 0),
                active_session_count=int(sessions[1] or 0),
            )
        finally:
            conn.close()

    def list(
        self,
        *,
        search: str | None,
        status: str | None,
        sort: str,
        cursor: str | None,
        limit: int,
    ) -> OrganizationPage:
        descending = sort.startswith("-")
        sort_name = sort[1:] if descending else sort
        if sort_name not in _SORT_COLUMNS:
            raise AdminError(400, "ADMIN_SORT_INVALID", "Unsupported organization sort")
        normalized_search = search.strip() if search else None
        normalized_sort = ("-" if descending else "") + sort_name
        fingerprint = _cursor_fingerprint(
            search=normalized_search, status=status, sort=normalized_sort
        )
        offset = _decode_cursor(cursor, fingerprint)

        conn = self._db.connect()
        try:
            columns = self._columns(conn)
            where: list[str] = []
            params: list[Any] = []
            if normalized_search:
                slug_search = " OR lower(COALESCE(o.slug, '')) LIKE ?" if "slug" in columns else ""
                where.append(
                    "(lower(o.name) LIKE ? OR lower(COALESCE(o.university_name, '')) LIKE ?"
                    + slug_search
                    + ")"
                )
                needle = f"%{normalized_search.casefold()}%"
                params.extend([needle, needle])
                if "slug" in columns:
                    params.append(needle)
            if status:
                status_expr = "COALESCE(o.status, 'active')" if "status" in columns else "'active'"
                where.append(f"{status_expr}=?")
                params.append(status)
            where_sql = " WHERE " + " AND ".join(where) if where else ""
            total = conn.execute(
                "SELECT COUNT(*) FROM organizations o" + where_sql, params
            ).fetchone()[0]
            direction = "DESC" if descending else "ASC"
            query = (
                self._select_sql(conn)
                + where_sql
                + f" ORDER BY {_SORT_COLUMNS[sort_name]} {direction}, o.id {direction} LIMIT ? OFFSET ?"
            )
            rows = conn.execute(
                query,
                [*_ACTIVE_SESSION_STATES, *params, limit + 1, offset],
            ).fetchall()
            has_next = len(rows) > limit
            items = [self._record(row) for row in rows[:limit]]
            return OrganizationPage(
                items=items,
                total_count=int(total),
                next_cursor=(
                    _encode_cursor(offset + limit, fingerprint) if has_next else None
                ),
            )
        finally:
            conn.close()

    def get(self, organization_id: str, *, conn: sqlite3.Connection | None = None) -> OrganizationRecord | None:
        owned = conn is None
        connection = conn or self._db.connect()
        try:
            row = connection.execute(
                self._select_sql(connection) + " WHERE o.id=?",
                [*_ACTIVE_SESSION_STATES, organization_id],
            ).fetchone()
            return self._record(row) if row else None
        finally:
            if owned:
                connection.close()

    @staticmethod
    def _ensure_unique(
        conn: sqlite3.Connection,
        *,
        name: str,
        slug: str,
        exclude_id: str | None = None,
    ) -> None:
        columns = {str(row[1]) for row in conn.execute("PRAGMA table_info(organizations)")}
        conditions = ["lower(name)=lower(?)"]
        params: list[Any] = [name]
        if "slug" in columns:
            conditions.append("lower(COALESCE(slug, ''))=lower(?)")
            params.append(slug)
        sql = "SELECT id FROM organizations WHERE (" + " OR ".join(conditions) + ")"
        if exclude_id:
            sql += " AND id<>?"
            params.append(exclude_id)
        if conn.execute(sql, params).fetchone():
            raise AdminError(
                409,
                "ADMIN_ORGANIZATION_CONFLICT",
                "Organization name or slug already exists",
            )

    def create(
        self,
        conn: sqlite3.Connection,
        *,
        organization_id: str,
        name: str,
        university_name: str | None,
        slug: str,
        status: str,
        created_by: str,
    ) -> OrganizationRecord:
        self._ensure_unique(conn, name=name, slug=slug)
        columns = self._columns(conn)
        insert_columns = ["id", "name", "university_name", "created_by"]
        values: list[Any] = [organization_id, name, university_name, created_by]
        if "slug" in columns:
            insert_columns.append("slug")
            values.append(slug)
        if "status" in columns:
            insert_columns.append("status")
            values.append(status)
        marks = ",".join("?" for _ in insert_columns)
        try:
            conn.execute(
                f"INSERT INTO organizations ({','.join(insert_columns)}) VALUES ({marks})",
                values,
            )
        except sqlite3.IntegrityError as exc:
            raise AdminError(
                409,
                "ADMIN_ORGANIZATION_CONFLICT",
                "Organization name or slug already exists",
            ) from exc
        record = self.get(organization_id, conn=conn)
        assert record is not None
        return record

    def update(
        self,
        conn: sqlite3.Connection,
        *,
        organization_id: str,
        expected_version: str,
        changes: dict[str, Any],
    ) -> OrganizationRecord:
        current = self.get(organization_id, conn=conn)
        if current is None:
            raise AdminError(404, "ADMIN_ORGANIZATION_NOT_FOUND", "Organization not found")
        if current.version != expected_version:
            raise AdminError(
                409,
                "ADMIN_VERSION_CONFLICT",
                "Organization was modified by another request",
            )
        desired_name = changes.get("name", current.name)
        desired_slug = changes.get("slug", current.slug)
        self._ensure_unique(
            conn,
            name=desired_name,
            slug=desired_slug,
            exclude_id=organization_id,
        )
        columns = self._columns(conn)
        assignments: list[str] = []
        params: list[Any] = []
        mapping = {
            "name": "name",
            "university_name": "university_name",
            "slug": "slug",
            "status": "status",
        }
        for key, column in mapping.items():
            if key in changes and column in columns:
                assignments.append(f"{column}=?")
                params.append(changes[key])
        if assignments:
            params.append(organization_id)
            try:
                conn.execute(
                    f"UPDATE organizations SET {', '.join(assignments)} WHERE id=?",
                    params,
                )
            except sqlite3.IntegrityError as exc:
                raise AdminError(
                    409,
                    "ADMIN_ORGANIZATION_CONFLICT",
                    "Organization name or slug already exists",
                ) from exc
        updated = self.get(organization_id, conn=conn)
        assert updated is not None
        return updated
