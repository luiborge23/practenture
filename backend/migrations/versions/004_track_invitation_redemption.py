"""Track professor invitation redemption lifecycle."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    columns = {
        row[1]
        for row in conn.execute(sa.text("PRAGMA table_info(professor_invitations)"))
    }
    additions = {
        "created_at": "TEXT",
        "last_used_at": "TEXT",
        "redeemed_at": "TEXT",
        "redeemed_by": "TEXT",
    }
    for name, sql_type in additions.items():
        if name not in columns:
            conn.execute(
                sa.text(
                    f"ALTER TABLE professor_invitations ADD COLUMN {name} {sql_type}"
                )
            )
    conn.execute(
        sa.text(
            "UPDATE professor_invitations SET created_at=datetime('now') "
            "WHERE created_at IS NULL"
        )
    )


def downgrade() -> None:
    # Redemption evidence is retained across application rollback.
    pass
