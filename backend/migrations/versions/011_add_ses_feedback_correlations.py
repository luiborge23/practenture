"""Persist privacy-preserving SES accepted-message feedback correlation."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS ses_feedback_correlations (
            provider TEXT NOT NULL CHECK(provider='ses'),
            provider_message_id TEXT NOT NULL,
            recipient_hash TEXT NOT NULL CHECK(length(recipient_hash)=64),
            accepted_at TEXT NOT NULL,
            feedback_expires_at TEXT NOT NULL,
            PRIMARY KEY(provider, provider_message_id)
        )
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_ses_feedback_correlations_expiry
        ON ses_feedback_correlations(feedback_expires_at)
    """))


def downgrade() -> None:
    # Compliance feedback-correlation evidence must survive application rollback.
    pass
