"""Persist SES invitation delivery acceptance and safe failure state."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_DELIVERIES = """
CREATE TABLE IF NOT EXISTS invitation_email_deliveries (
    id TEXT PRIMARY KEY,
    invitation_id TEXT NOT NULL,
    recipient_email TEXT NOT NULL,
    owner_id TEXT NOT NULL,
    idempotency_key_hash TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('pending', 'accepted', 'failed')),
    provider TEXT,
    provider_message_id TEXT,
    failed_code TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(invitation_id) REFERENCES professor_invitations(id),
    UNIQUE(owner_id, idempotency_key_hash)
)
"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(_DELIVERIES))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_invitation_email_deliveries_invitation "
        "ON invitation_email_deliveries(invitation_id, created_at)"
    ))


def downgrade() -> None:
    # Delivery evidence is retained across application rollback.
    pass
