"""Add durable organization scope, lifecycle versioning, and create idempotency."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(sa.text(f"PRAGMA table_info({table})"))}


def upgrade() -> None:
    conn = op.get_bind()
    if "organization_id" not in _columns(conn, "classes"):
        conn.execute(sa.text("ALTER TABLE classes ADD COLUMN organization_id TEXT"))
    session_columns = _columns(conn, "sessions")
    if "organization_id" not in session_columns:
        conn.execute(sa.text("ALTER TABLE sessions ADD COLUMN organization_id TEXT"))
    if "version" not in session_columns:
        conn.execute(sa.text("ALTER TABLE sessions ADD COLUMN version INTEGER NOT NULL DEFAULT 0"))

    # Only deterministic one-membership mappings are backfilled. Ambiguous legacy
    # records remain NULL so authorization fails closed instead of guessing a tenant.
    conn.execute(sa.text("""
        UPDATE classes
        SET organization_id = (
            SELECT MIN(m.org_id) FROM memberships m
            WHERE m.user_id = classes.professor_user_id
        )
        WHERE organization_id IS NULL
          AND (SELECT COUNT(*) FROM memberships m
               WHERE m.user_id = classes.professor_user_id) = 1
    """))
    conn.execute(sa.text("""
        UPDATE sessions
        SET organization_id = (
            SELECT MIN(m.org_id) FROM memberships m
            WHERE m.user_id = sessions.professor_user_id
        )
        WHERE organization_id IS NULL
          AND (SELECT COUNT(*) FROM memberships m
               WHERE m.user_id = sessions.professor_user_id) = 1
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS session_create_requests (
            professor_user_id TEXT NOT NULL,
            idempotency_key_hash TEXT NOT NULL,
            request_fingerprint TEXT NOT NULL,
            session_code TEXT NOT NULL,
            response_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (professor_user_id, idempotency_key_hash),
            FOREIGN KEY(session_code) REFERENCES sessions(code)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_classes_org ON classes(organization_id)"
    ))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_sessions_org ON sessions(organization_id)"
    ))


def downgrade() -> None:
    op.drop_index("idx_sessions_org", table_name="sessions")
    op.drop_index("idx_classes_org", table_name="classes")
    op.drop_table("session_create_requests")
    with op.batch_alter_table("sessions") as batch:
        batch.drop_column("version")
        batch.drop_column("organization_id")
    with op.batch_alter_table("classes") as batch:
        batch.drop_column("organization_id")
