"""Add status and audit columns to users table.

This migration adds the following columns to the users table:
- status (TEXT, default 'active')
- disabled_at (TEXT)
- disabled_by (TEXT)
- disable_reason (TEXT)
- last_login_at (TEXT)
- password_changed_at (TEXT)
- created_by (TEXT)

This migration is idempotent and safe to run multiple times.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = "000"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Add status column if not exists
    try:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'active'"))
    except Exception:
        pass  # Column may already exist
    
    # Add disabled_at column if not exists
    try:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN disabled_at TEXT"))
    except Exception:
        pass
    
    # Add disabled_by column if not exists
    try:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN disabled_by TEXT"))
    except Exception:
        pass
    
    # Add disable_reason column if not exists
    try:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN disable_reason TEXT"))
    except Exception:
        pass
    
    # Add last_login_at column if not exists
    try:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN last_login_at TEXT"))
    except Exception:
        pass
    
    # Add password_changed_at column if not exists
    try:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN password_changed_at TEXT"))
    except Exception:
        pass
    
    # Add created_by column if not exists
    try:
        conn.execute(sa.text("ALTER TABLE users ADD COLUMN created_by TEXT"))
    except Exception:
        pass


def downgrade() -> None:
    # SQLite doesn't support DROP COLUMN, so leave empty
    pass
