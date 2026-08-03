"""Persist first-login provider email until invitation enrollment completes."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS pending_provider_identities (
            provider TEXT NOT NULL CHECK(provider IN ('google','apple')),
            provider_subject TEXT NOT NULL,
            email TEXT NOT NULL,
            expires_at REAL NOT NULL,
            PRIMARY KEY(provider, provider_subject)
        )
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_pending_provider_identities_expiry
        ON pending_provider_identities(expires_at)
    """))


def downgrade() -> None:
    op.drop_index(
        "idx_pending_provider_identities_expiry",
        table_name="pending_provider_identities",
    )
    op.drop_table("pending_provider_identities")
