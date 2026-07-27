"""Persist versioned scenario-pack identity on simulation sessions."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


DEFAULT_SCENARIO_ID = "athletic-footwear-classic"
DEFAULT_SCENARIO_VERSION = "1.0.0"


def upgrade() -> None:
    conn = op.get_bind()
    columns = {
        row[1]
        for row in conn.execute(sa.text("PRAGMA table_info(sessions)")).fetchall()
    }
    if "scenario_id" not in columns:
        conn.execute(
            sa.text(
                "ALTER TABLE sessions ADD COLUMN scenario_id TEXT NOT NULL "
                f"DEFAULT '{DEFAULT_SCENARIO_ID}'"
            )
        )
    if "scenario_version" not in columns:
        conn.execute(
            sa.text(
                "ALTER TABLE sessions ADD COLUMN scenario_version TEXT NOT NULL "
                f"DEFAULT '{DEFAULT_SCENARIO_VERSION}'"
            )
        )


def downgrade() -> None:
    # SQLite deployments may not support DROP COLUMN. Keeping identity columns is
    # safe for older application versions, which ignore unknown columns.
    pass
