"""Add durable account-deletion challenges, identity links, and provider outbox."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "008"
down_revision: Union[str, None] = "007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS auth_identities (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            provider TEXT NOT NULL CHECK(provider IN ('password','google','apple')),
            provider_subject TEXT NOT NULL,
            email TEXT DEFAULT '',
            created_at REAL NOT NULL,
            last_login_at REAL,
            UNIQUE(provider, provider_subject),
            UNIQUE(user_id, provider)
        )
    """))
    conn.execute(sa.text(
        "CREATE INDEX IF NOT EXISTS idx_auth_identities_user ON auth_identities(user_id)"
    ))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS account_deletion_challenges (
            id TEXT PRIMARY KEY,
            user_id_hash TEXT NOT NULL,
            provider TEXT NOT NULL,
            nonce_hash TEXT NOT NULL,
            issued_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            consumed_at REAL
        )
    """))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_deletion_challenges_user
        ON account_deletion_challenges(user_id_hash, consumed_at, expires_at)
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS account_deletion_markers (
            user_id_hash TEXT PRIMARY KEY,
            deleted_at REAL NOT NULL
        )
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS provider_revocation_jobs (
            id TEXT PRIMARY KEY,
            provider TEXT NOT NULL,
            payload_ciphertext TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            attempts INTEGER NOT NULL DEFAULT 0,
            next_attempt_at REAL NOT NULL,
            last_error TEXT,
            created_at REAL NOT NULL,
            completed_at REAL,
            lease_token TEXT
        )
    """))
    revocation_columns = {
        row[1]
        for row in conn.execute(sa.text("PRAGMA table_info(provider_revocation_jobs)"))
    }
    if "lease_token" not in revocation_columns:
        conn.execute(sa.text(
            "ALTER TABLE provider_revocation_jobs ADD COLUMN lease_token TEXT"
        ))
    conn.execute(sa.text("""
        CREATE INDEX IF NOT EXISTS idx_provider_revocation_pending
        ON provider_revocation_jobs(status, next_attempt_at)
    """))
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS protected_action_throttles (
            scope_key TEXT PRIMARY KEY,
            window_started_at REAL NOT NULL,
            failures INTEGER NOT NULL DEFAULT 0,
            blocked_until REAL NOT NULL DEFAULT 0
        )
    """))


def downgrade() -> None:
    op.drop_table("protected_action_throttles")
    op.drop_index("idx_provider_revocation_pending", table_name="provider_revocation_jobs")
    op.drop_table("provider_revocation_jobs")
    op.drop_index("idx_deletion_challenges_user", table_name="account_deletion_challenges")
    op.drop_table("account_deletion_challenges")
    op.drop_table("account_deletion_markers")
    # auth_identities predates Alembic in deployed databases. Never drop it on
    # downgrade because doing so would destroy live social-login linkages.
