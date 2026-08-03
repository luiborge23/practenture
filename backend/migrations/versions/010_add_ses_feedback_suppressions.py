"""Persist privacy-preserving SES bounce and complaint feedback."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "010"
down_revision: Union[str, None] = "009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ses_recipient_suppressions (
            recipient_hash TEXT PRIMARY KEY CHECK(length(recipient_hash) = 64),
            reason TEXT NOT NULL CHECK(reason IN ('permanent_bounce','complaint')),
            first_observed_at TEXT NOT NULL,
            last_observed_at TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1))
        )
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_ses_recipient_suppressions_active
        ON ses_recipient_suppressions(active, last_observed_at)
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ses_feedback_events (
            sns_message_id TEXT PRIMARY KEY,
            feedback_type TEXT NOT NULL,
            provider_message_id TEXT,
            outcome TEXT NOT NULL CHECK(outcome IN ('suppressed','ignored_transient','ignored_unknown')),
            occurred_at TEXT NOT NULL
        )
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_ses_feedback_events_provider_message
        ON ses_feedback_events(provider_message_id, occurred_at)
    """))


def downgrade() -> None:
    # Compliance feedback and suppression evidence must survive application rollback.
    pass
