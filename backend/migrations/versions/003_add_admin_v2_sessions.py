"""Add server-managed Admin V2 sessions and durable layered login throttling."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ADMIN_SESSIONS = """
CREATE TABLE IF NOT EXISTS admin_sessions (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    csrf_token_hash TEXT NOT NULL,
    owner_user_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role = 'owner'),
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    idle_expires_at TEXT NOT NULL,
    absolute_expires_at TEXT NOT NULL,
    revoked_at TEXT,
    revocation_reason TEXT,
    FOREIGN KEY(owner_user_id) REFERENCES users(username)
)
"""

# Retained for compatibility with already-created pre-layered revision-003 databases.
# New reservations use privileged_login_buckets exclusively.
_PRIVILEGED_LOGIN_ATTEMPTS = """
CREATE TABLE IF NOT EXISTS privileged_login_attempts (
    identity_key TEXT NOT NULL,
    client_key TEXT NOT NULL,
    attempt_count INTEGER NOT NULL,
    window_started_at REAL NOT NULL,
    locked_until REAL,
    last_attempt_at REAL NOT NULL,
    PRIMARY KEY (identity_key, client_key)
)
"""

_PRIVILEGED_LOGIN_BUCKETS = """
CREATE TABLE IF NOT EXISTS privileged_login_buckets (
    scope_type TEXT NOT NULL CHECK(scope_type IN ('pair', 'identity', 'client')),
    scope_key TEXT NOT NULL,
    attempt_count INTEGER NOT NULL CHECK(attempt_count >= 0),
    window_started_at REAL NOT NULL,
    locked_until REAL,
    last_attempt_at REAL NOT NULL,
    PRIMARY KEY (scope_type, scope_key)
)
"""

_ADMIN_MFA_REPLAY_STATE = """
CREATE TABLE IF NOT EXISTS admin_mfa_replay_state (
    owner_user_id TEXT PRIMARY KEY,
    last_accepted_totp_step INTEGER NOT NULL,
    accepted_at TEXT NOT NULL,
    FOREIGN KEY(owner_user_id) REFERENCES users(username)
)
"""

_ADMIN_MFA_CHALLENGES = """
CREATE TABLE IF NOT EXISTS admin_mfa_challenges (
    id TEXT PRIMARY KEY,
    token_hash TEXT NOT NULL UNIQUE,
    owner_user_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT,
    FOREIGN KEY(owner_user_id) REFERENCES users(username) ON DELETE CASCADE
)
"""

_ADMIN_RECENT_AUTH = """
CREATE TABLE IF NOT EXISTS admin_recent_auth (
    session_id TEXT PRIMARY KEY,
    authenticated_at TEXT NOT NULL,
    FOREIGN KEY(session_id) REFERENCES admin_sessions(id) ON DELETE CASCADE
)
"""

_ADMIN_AUDIT_EVENTS = """
CREATE TABLE IF NOT EXISTS admin_audit_events (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    actor_json TEXT NOT NULL,
    target_json TEXT NOT NULL,
    action TEXT NOT NULL,
    outcome TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL
)
"""

_ADMIN_IDEMPOTENCY_RECORDS = """
CREATE TABLE IF NOT EXISTS admin_idempotency_records (
    owner_id TEXT NOT NULL,
    route TEXT NOT NULL,
    key_hash TEXT NOT NULL,
    request_fingerprint TEXT NOT NULL,
    state TEXT NOT NULL CHECK(state IN ('in_progress', 'completed')),
    response_status INTEGER,
    response_body_json TEXT,
    response_headers_json TEXT,
    audit_event_id TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    expires_at TEXT NOT NULL,
    PRIMARY KEY (owner_id, route, key_hash),
    FOREIGN KEY(audit_event_id) REFERENCES admin_audit_events(id),
    CHECK (
        (state = 'in_progress' AND response_status IS NULL
         AND response_body_json IS NULL AND response_headers_json IS NULL
         AND audit_event_id IS NULL AND completed_at IS NULL)
        OR
        (state = 'completed' AND response_status IS NOT NULL
         AND response_body_json IS NOT NULL AND response_headers_json IS NOT NULL
         AND audit_event_id IS NOT NULL AND completed_at IS NOT NULL)
    )
)
"""


def upgrade() -> None:
    conn = op.get_bind()
    conn.execute(sa.text(_ADMIN_SESSIONS))
    conn.execute(sa.text(_PRIVILEGED_LOGIN_ATTEMPTS))
    conn.execute(sa.text(_PRIVILEGED_LOGIN_BUCKETS))
    conn.execute(sa.text(_ADMIN_MFA_REPLAY_STATE))
    conn.execute(sa.text(_ADMIN_MFA_CHALLENGES))
    conn.execute(sa.text(_ADMIN_RECENT_AUTH))
    conn.execute(sa.text(_ADMIN_AUDIT_EVENTS))
    conn.execute(sa.text(_ADMIN_IDEMPOTENCY_RECORDS))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_sessions_owner ON admin_sessions(owner_user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_sessions_expiry ON admin_sessions(idle_expires_at, absolute_expires_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_privileged_login_attempts_expiry ON privileged_login_attempts(locked_until, window_started_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_privileged_login_buckets_last_attempt ON privileged_login_buckets(last_attempt_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_privileged_login_buckets_lock ON privileged_login_buckets(locked_until)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_mfa_replay_state_accepted_at ON admin_mfa_replay_state(accepted_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_mfa_challenges_expiry ON admin_mfa_challenges(expires_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_recent_auth_time ON admin_recent_auth(authenticated_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_audit_events_occurred_at ON admin_audit_events(occurred_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_audit_events_actor_action ON admin_audit_events(actor_json, action, occurred_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_idempotency_expiry ON admin_idempotency_records(expires_at)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_admin_idempotency_state ON admin_idempotency_records(state, created_at)"))
    conn.execute(sa.text("""
        CREATE TRIGGER IF NOT EXISTS trg_admin_audit_events_no_update
        BEFORE UPDATE ON admin_audit_events
        BEGIN
            SELECT RAISE(ABORT, 'admin audit events are immutable');
        END
    """))
    conn.execute(sa.text("""
        CREATE TRIGGER IF NOT EXISTS trg_admin_audit_events_no_delete
        BEFORE DELETE ON admin_audit_events
        BEGIN
            SELECT RAISE(ABORT, 'admin audit events are immutable');
        END
    """))


def downgrade() -> None:
    # Additive security state is intentionally retained across application rollback.
    pass
