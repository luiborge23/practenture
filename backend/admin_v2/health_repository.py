"""Read-only SQLite evidence collection for Admin V2 operational health."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import sqlite3
from typing import Any, Protocol

from database import db


class DatabaseConnectionProvider(Protocol):
    @property
    def database_path(self) -> str: ...

    def connect(self) -> sqlite3.Connection: ...


EXPECTED_MIGRATION_VERSION = "006"
_SAMPLE_LIMIT = 10


@dataclass(frozen=True)
class CountEvidence:
    count: int
    sample_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class StorageEvidence:
    database_bytes: int
    wal_bytes: int
    free_bytes: int
    total_bytes: int


@dataclass(frozen=True)
class HealthEvidence:
    engine_version: str
    migration_version: str | None
    quick_check_errors: tuple[str, ...]
    foreign_keys: CountEvidence
    logical_orphans: CountEvidence
    domain_violations: CountEvidence
    last_backup: dict[str, Any] | None
    last_restore_drill: dict[str, Any] | None
    storage: StorageEvidence


class OperationsHealthRepository:
    """Collect bounded health evidence without changing application data or schema."""

    _LOGICAL_RELATIONSHIPS = (
        ("memberships", "id", "user_id", "users", "username"),
        ("memberships", "id", "org_id", "organizations", "id"),
        ("classes", "id", "professor_user_id", "users", "username"),
        ("class_enrollments", "id", "class_id", "classes", "id"),
        ("class_enrollments", "id", "student_user_id", "users", "username"),
        ("sessions", "code", "professor_user_id", "users", "username"),
        ("sessions", "code", "class_id", "classes", "id"),
    )

    _DOMAIN_RULES = (
        ("users", "username", "role IS NULL OR role NOT IN ('owner','professor','student','pending')", "invalid-role"),
        ("users", "username", "status IS NULL OR status NOT IN ('active','suspended','disabled')", "invalid-status"),
        ("memberships", "id", "role IS NULL OR role NOT IN ('owner','professor','student')", "invalid-membership-role"),
        ("classes", "id", "is_active IS NULL OR is_active NOT IN (0,1)", "invalid-class-state"),
        ("sessions", "code", "state IS NULL OR state NOT IN ('creating','active','completed','finished')", "invalid-session-state"),
        (
            "professor_invitations",
            "id",
            "status IS NULL OR status NOT IN ('active','redeemed','expired','revoked') "
            "OR max_uses IS NULL OR use_count IS NULL OR max_uses < 1 "
            "OR use_count < 0 OR use_count > max_uses",
            "invalid-invitation",
        ),
    )

    _ROLE_RELATIONSHIPS = (
        ("classes", "id", "professor_user_id", "professor", "class-non-professor"),
        ("class_enrollments", "id", "student_user_id", "student", "enrollment-non-student"),
        ("sessions", "code", "professor_user_id", "professor", "session-non-professor"),
    )

    def __init__(self, database: DatabaseConnectionProvider = db) -> None:
        self._db = database

    def collect(self) -> HealthEvidence:
        conn = self._db.connect()
        try:
            # This explicitly verifies transaction operation but always rolls back.
            conn.execute("BEGIN")
            conn.execute("SELECT 1").fetchone()
            conn.rollback()

            tables = self._tables(conn)
            columns = {table: self._columns(conn, table) for table in tables}
            engine_version = str(conn.execute("SELECT sqlite_version()").fetchone()[0])
            migration_version = self._migration_version(conn, tables)
            quick_errors = tuple(
                str(row[0]) for row in conn.execute("PRAGMA quick_check").fetchall()
                if str(row[0]).casefold() != "ok"
            )
            foreign_keys = self._foreign_keys(conn)
            logical_orphans = self._logical_orphans(conn, tables, columns)
            domain_violations = self._domain_violations(conn, tables, columns)
            last_backup = self._latest_row(conn, tables, "backup_runs", "started_at")
            last_restore = self._latest_row(conn, tables, "restore_drills", "started_at")
        finally:
            conn.close()

        return HealthEvidence(
            engine_version=engine_version,
            migration_version=migration_version,
            quick_check_errors=quick_errors,
            foreign_keys=foreign_keys,
            logical_orphans=logical_orphans,
            domain_violations=domain_violations,
            last_backup=last_backup,
            last_restore_drill=last_restore,
            storage=self._storage(),
        )

    @staticmethod
    def _tables(conn: sqlite3.Connection) -> set[str]:
        return {
            str(row[0])
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }

    @staticmethod
    def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
        return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}

    @staticmethod
    def _migration_version(conn: sqlite3.Connection, tables: set[str]) -> str | None:
        if "alembic_version" not in tables:
            return None
        row = conn.execute("SELECT version_num FROM alembic_version LIMIT 1").fetchone()
        return str(row[0]) if row and row[0] is not None else None

    @staticmethod
    def _foreign_keys(conn: sqlite3.Connection) -> CountEvidence:
        rows = conn.execute("PRAGMA foreign_key_check").fetchall()
        samples = tuple(f"{row[0]}:{row[1]}" for row in rows[:_SAMPLE_LIMIT])
        return CountEvidence(len(rows), samples)

    def _logical_orphans(
        self,
        conn: sqlite3.Connection,
        tables: set[str],
        columns: dict[str, set[str]],
    ) -> CountEvidence:
        count = 0
        samples: list[str] = []
        for child, child_id, foreign_key, parent, parent_key in self._LOGICAL_RELATIONSHIPS:
            if (
                child not in tables
                or parent not in tables
                or not {child_id, foreign_key}.issubset(columns[child])
                or parent_key not in columns[parent]
            ):
                continue
            rows = conn.execute(
                f'''SELECT c."{child_id}" FROM "{child}" c
                    LEFT JOIN "{parent}" p ON p."{parent_key}" = c."{foreign_key}"
                    WHERE c."{foreign_key}" IS NOT NULL AND p."{parent_key}" IS NULL
                    LIMIT ?''',
                (_SAMPLE_LIMIT + 1,),
            ).fetchall()
            total = conn.execute(
                f'''SELECT COUNT(*) FROM "{child}" c
                    LEFT JOIN "{parent}" p ON p."{parent_key}" = c."{foreign_key}"
                    WHERE c."{foreign_key}" IS NOT NULL AND p."{parent_key}" IS NULL'''
            ).fetchone()[0]
            count += int(total)
            for row in rows:
                if len(samples) < _SAMPLE_LIMIT:
                    samples.append(f"{child}:{row[0]}")
        return CountEvidence(count, tuple(samples))

    def _domain_violations(
        self,
        conn: sqlite3.Connection,
        tables: set[str],
        columns: dict[str, set[str]],
    ) -> CountEvidence:
        count = 0
        samples: list[str] = []
        for table, identity, predicate, label in self._DOMAIN_RULES:
            if table not in tables or identity not in columns[table]:
                continue
            # Rules are static constants owned by this repository, never caller input.
            try:
                total = int(conn.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE {predicate}'
                ).fetchone()[0])
                rows = conn.execute(
                    f'SELECT "{identity}" FROM "{table}" WHERE {predicate} LIMIT ?',
                    (_SAMPLE_LIMIT,),
                ).fetchall()
            except sqlite3.OperationalError:
                # A legacy table missing a rule column is migration drift, represented by
                # the migration check rather than leaking SQL details from this endpoint.
                continue
            count += total
            for row in rows:
                if len(samples) < _SAMPLE_LIMIT:
                    samples.append(f"{label}:{row[0]}")
        if "users" in tables and {"username", "role"}.issubset(columns["users"]):
            for table, identity, foreign_key, expected_role, label in self._ROLE_RELATIONSHIPS:
                if (
                    table not in tables
                    or not {identity, foreign_key}.issubset(columns[table])
                ):
                    continue
                predicate = (
                    f'u.role <> ? AND t."{foreign_key}" IS NOT NULL'
                )
                total = int(conn.execute(
                    f'''SELECT COUNT(*) FROM "{table}" t
                        JOIN users u ON u.username=t."{foreign_key}"
                        WHERE {predicate}''',
                    (expected_role,),
                ).fetchone()[0])
                rows = conn.execute(
                    f'''SELECT t."{identity}" FROM "{table}" t
                        JOIN users u ON u.username=t."{foreign_key}"
                        WHERE {predicate} LIMIT ?''',
                    (expected_role, _SAMPLE_LIMIT),
                ).fetchall()
                count += total
                for row in rows:
                    if len(samples) < _SAMPLE_LIMIT:
                        samples.append(f"{label}:{row[0]}")
        return CountEvidence(count, tuple(samples))

    @staticmethod
    def _latest_row(
        conn: sqlite3.Connection, tables: set[str], table: str, order_column: str
    ) -> dict[str, Any] | None:
        if table not in tables:
            return None
        row = conn.execute(
            f'SELECT * FROM "{table}" ORDER BY "{order_column}" DESC LIMIT 1'
        ).fetchone()
        return dict(row) if row else None

    def _storage(self) -> StorageEvidence:
        path = Path(str(self._db.database_path)).expanduser()
        parent = path.parent if str(path.parent) else Path(".")
        try:
            usage = shutil.disk_usage(parent)
            free_bytes, total_bytes = usage.free, usage.total
        except OSError:
            free_bytes = total_bytes = 0
        return StorageEvidence(
            database_bytes=self._safe_size(path),
            wal_bytes=self._safe_size(Path(f"{path}-wal")),
            free_bytes=free_bytes,
            total_bytes=total_bytes,
        )

    @staticmethod
    def _safe_size(path: Path) -> int:
        try:
            return os.path.getsize(path)
        except OSError:
            return 0
