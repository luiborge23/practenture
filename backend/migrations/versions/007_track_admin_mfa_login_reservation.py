"""Track the password-stage throttle reservation on Admin MFA challenges."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(conn, table: str) -> set[str]:
    return {row[1] for row in conn.execute(sa.text(f"PRAGMA table_info({table})"))}


def upgrade() -> None:
    conn = op.get_bind()
    columns = _columns(conn, "admin_mfa_challenges")
    if "login_identity" not in columns:
        conn.execute(sa.text(
            "ALTER TABLE admin_mfa_challenges ADD COLUMN login_identity TEXT"
        ))
    if "login_client_signal" not in columns:
        conn.execute(sa.text(
            "ALTER TABLE admin_mfa_challenges ADD COLUMN login_client_signal TEXT"
        ))
    if "login_identity_window_started_at" not in columns:
        conn.execute(sa.text(
            "ALTER TABLE admin_mfa_challenges "
            "ADD COLUMN login_identity_window_started_at REAL"
        ))
    if "login_pair_window_started_at" not in columns:
        conn.execute(sa.text(
            "ALTER TABLE admin_mfa_challenges "
            "ADD COLUMN login_pair_window_started_at REAL"
        ))
    if "login_client_window_started_at" not in columns:
        conn.execute(sa.text(
            "ALTER TABLE admin_mfa_challenges "
            "ADD COLUMN login_client_window_started_at REAL"
        ))
    # Challenges are five-minute, single-use login artifacts. Invalidate any
    # challenge created by pre-007 code rather than accepting it without the
    # reservation metadata required for exact throttle accounting.
    conn.execute(sa.text("DELETE FROM admin_mfa_challenges"))


def downgrade() -> None:
    with op.batch_alter_table("admin_mfa_challenges") as batch:
        batch.drop_column("login_client_window_started_at")
        batch.drop_column("login_pair_window_started_at")
        batch.drop_column("login_identity_window_started_at")
        batch.drop_column("login_client_signal")
        batch.drop_column("login_identity")
