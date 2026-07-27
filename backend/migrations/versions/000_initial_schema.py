"""Initial schema migration for Practenture database.

This migration creates the initial database schema including:
- users table with all columns
- sessions, decisions, results tables
- announcements, team_states tables
- professor_codes table (legacy)
- classes and class_enrollments tables
- organizations and memberships tables
- audit_logs table
- refresh_tokens, mfa_secrets, scim_users tables
- password_reset_tokens table

This is the baseline migration that should be applied to a fresh database.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "000"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    
    # Create users table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('owner','professor','student','pending')),
            name TEXT,
            student_id TEXT,
            email TEXT,
            department TEXT,
            provider TEXT DEFAULT 'password',
            provider_uid TEXT,
            must_change_password INTEGER DEFAULT 0,
            status TEXT DEFAULT 'active',
            disabled_at TEXT,
            disabled_by TEXT,
            disable_reason TEXT,
            last_login_at TEXT,
            password_changed_at TEXT,
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    
    # Create sessions table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS sessions (
            code TEXT PRIMARY KEY,
            session_id TEXT NOT NULL UNIQUE,
            config_json TEXT NOT NULL,
            teams_json TEXT NOT NULL DEFAULT '[]',
            created_by TEXT,
            professor_user_id TEXT,
            class_id TEXT,
            max_human_teams INTEGER DEFAULT 30,
            current_round INTEGER DEFAULT 0,
            state TEXT DEFAULT 'creating',
            scenario_id TEXT NOT NULL DEFAULT 'athletic-footwear-classic',
            scenario_version TEXT NOT NULL DEFAULT '1.0.0',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    
    # Create decisions table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS decisions (
            session_code TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            team_id TEXT NOT NULL,
            decision_json TEXT NOT NULL,
            PRIMARY KEY (session_code, round_num, team_id)
        )
    """))
    
    # Create results table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS results (
            session_code TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            team_id TEXT NOT NULL,
            result_json TEXT NOT NULL,
            PRIMARY KEY (session_code, round_num, team_id)
        )
    """))
    
    # Create announcements table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS announcements (
            id TEXT PRIMARY KEY,
            session_id TEXT NOT NULL,
            message TEXT NOT NULL,
            author_id TEXT NOT NULL,
            author_name TEXT NOT NULL,
            timestamp TEXT DEFAULT (datetime('now'))
        )
    """))
    
    # Create team_states table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS team_states (
            session_code TEXT NOT NULL,
            team_id TEXT NOT NULL,
            state_json TEXT NOT NULL,
            PRIMARY KEY (session_code, team_id)
        )
    """))
    
    # Create professor_codes table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS professor_codes (
            code TEXT PRIMARY KEY,
            university_name TEXT,
            notes TEXT,
            used INTEGER DEFAULT 0,
            used_by TEXT,
            used_at TEXT,
            expires_at REAL DEFAULT 0,
            max_uses INTEGER DEFAULT 1,
            use_count INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    
    # Create classes table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS classes (
            id TEXT PRIMARY KEY,
            professor_user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            join_code TEXT UNIQUE NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    
    # Create class_enrollments table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS class_enrollments (
            id TEXT PRIMARY KEY,
            class_id TEXT NOT NULL,
            student_user_id TEXT NOT NULL,
            enrolled_at TEXT DEFAULT (datetime('now')),
            UNIQUE(class_id, student_user_id)
        )
    """))
    
    # Create organizations table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS organizations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            university_name TEXT,
            slug TEXT UNIQUE,
            status TEXT DEFAULT 'active',
            created_by TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    
    # Create memberships table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS memberships (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            org_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'student',
            created_at TEXT DEFAULT (datetime('now')),
            UNIQUE(user_id, org_id)
        )
    """))
    
    # Create audit_logs table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS audit_logs (
            id TEXT PRIMARY KEY,
            actor_username TEXT NOT NULL,
            action TEXT NOT NULL,
            details TEXT DEFAULT '{}',
            ip_address TEXT,
            timestamp REAL
        )
    """))
    
    # Create indexes for sessions
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_sessions_prof ON sessions(professor_user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_sessions_class ON sessions(class_id)"))
    
    # Create indexes for decisions and results
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_decisions ON decisions(session_code, round_num)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_results ON results(session_code, round_num)"))
    
    # Create indexes for announcements
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_announcements ON announcements(session_id)"))
    
    # Create indexes for enrollments
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_enroll_class ON class_enrollments(class_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_enroll_student ON class_enrollments(student_user_id)"))
    
    # Create indexes for classes
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_classes_prof ON classes(professor_user_id)"))
    
    # Create indexes for audit_logs
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_username)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action)"))
    
    # Create indexes for memberships
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_memberships_org ON memberships(org_id)"))
    
    # Create refresh_tokens table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS refresh_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            issued_at REAL NOT NULL,
            expires_at REAL NOT NULL,
            revoked INTEGER DEFAULT 0,
            rotated_from TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id)"))
    
    # Create mfa_secrets table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS mfa_secrets (
            user_id TEXT PRIMARY KEY,
            secret TEXT NOT NULL,
            enabled INTEGER DEFAULT 0,
            backup_codes TEXT DEFAULT '[]',
            enabled_at TEXT
        )
    """))
    
    # Create scim_users table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS scim_users (
            user_id TEXT PRIMARY KEY,
            external_id TEXT UNIQUE,
            active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        )
    """))
    
    # Create password_reset_tokens table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS password_reset_tokens (
            token_hash TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            expires_at REAL NOT NULL,
            used INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_reset_user ON password_reset_tokens(user_id)"))
    
    # Create professor_invitations table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS professor_invitations (
            id TEXT PRIMARY KEY,
            secret_hash TEXT NOT NULL,
            masked_code TEXT NOT NULL,
            organization_id TEXT NOT NULL,
            intended_email TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            expires_at TEXT NOT NULL,
            max_uses INTEGER DEFAULT 1,
            use_count INTEGER DEFAULT 0,
            issued_by TEXT,
            notes TEXT,
            change_ticket TEXT,
            revoked_at TEXT,
            revoked_by TEXT
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_inv_org ON professor_invitations(organization_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_inv_email ON professor_invitations(intended_email)"))
    
    # Create audit_events table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS audit_events (
            id TEXT PRIMARY KEY,
            occurred_at TEXT NOT NULL,
            actor_user_id TEXT,
            actor_role TEXT NOT NULL,
            action TEXT NOT NULL,
            target_type TEXT,
            target_id TEXT,
            organization_id TEXT,
            request_id TEXT NOT NULL,
            idempotency_key TEXT,
            source_ip TEXT,
            user_agent TEXT,
            reason TEXT,
            outcome TEXT DEFAULT 'success',
            before_json TEXT,
            after_json TEXT,
            metadata_json TEXT
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_events(actor_user_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_events(action)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_audit_target ON audit_events(target_type, target_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_audit_org ON audit_events(organization_id)"))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_audit_occurred_at ON audit_events(occurred_at)"))
    
    # Create cleanup_plans table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS cleanup_plans (
            id TEXT PRIMARY KEY,
            selector_json TEXT NOT NULL,
            plan_hash TEXT NOT NULL,
            preview_counts TEXT NOT NULL,
            total_rows INTEGER NOT NULL,
            status TEXT DEFAULT 'pending',
            created_by TEXT,
            executed_by TEXT,
            expires_at TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now')),
            executed_at TEXT
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_cleanup_status ON cleanup_plans(status)"))
    
    # Create backup_runs table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS backup_runs (
            id TEXT PRIMARY KEY,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT DEFAULT 'pending',
            object_key TEXT,
            checksum TEXT,
            database_size INTEGER,
            migration_version TEXT,
            integrity_result TEXT DEFAULT 'ok'
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_backup_started ON backup_runs(started_at)"))
    
    # Create restore_drills table
    conn.execute(sa.text("""
        CREATE TABLE IF NOT EXISTS restore_drills (
            id TEXT PRIMARY KEY,
            backup_id TEXT NOT NULL,
            started_at TEXT NOT NULL,
            ended_at TEXT,
            status TEXT DEFAULT 'pending',
            error_message TEXT
        )
    """))
    conn.execute(sa.text("CREATE INDEX IF NOT EXISTS idx_drill_backup ON restore_drills(backup_id)"))


def downgrade() -> None:
    conn = op.get_bind()
    
    # Drop tables in reverse order
    conn.execute(sa.text("DROP TABLE IF EXISTS restore_drills"))
    conn.execute(sa.text("DROP TABLE IF EXISTS backup_runs"))
    conn.execute(sa.text("DROP TABLE IF EXISTS cleanup_plans"))
    conn.execute(sa.text("DROP TABLE IF EXISTS audit_events"))
    conn.execute(sa.text("DROP TABLE IF EXISTS professor_invitations"))
    conn.execute(sa.text("DROP TABLE IF EXISTS password_reset_tokens"))
    conn.execute(sa.text("DROP TABLE IF EXISTS scim_users"))
    conn.execute(sa.text("DROP TABLE IF EXISTS mfa_secrets"))
    conn.execute(sa.text("DROP TABLE IF EXISTS refresh_tokens"))
    conn.execute(sa.text("DROP TABLE IF EXISTS memberships"))
    conn.execute(sa.text("DROP TABLE IF EXISTS organizations"))
    conn.execute(sa.text("DROP TABLE IF EXISTS class_enrollments"))
    conn.execute(sa.text("DROP TABLE IF EXISTS classes"))
    conn.execute(sa.text("DROP TABLE IF EXISTS professor_codes"))
    conn.execute(sa.text("DROP TABLE IF EXISTS team_states"))
    conn.execute(sa.text("DROP TABLE IF EXISTS announcements"))
    conn.execute(sa.text("DROP TABLE IF EXISTS results"))
    conn.execute(sa.text("DROP TABLE IF EXISTS decisions"))
    conn.execute(sa.text("DROP TABLE IF EXISTS sessions"))
    conn.execute(sa.text("DROP TABLE IF EXISTS users"))
    conn.execute(sa.text("DROP TABLE IF EXISTS audit_logs"))
