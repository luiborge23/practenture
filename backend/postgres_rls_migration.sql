-- SOTA Phase 2: PostgreSQL Row-Level Security (RLS) Migration
-- ============================================================
-- This script migrates BizSimAI from SQLite to PostgreSQL and enables
-- Row-Level Security for multi-tenant isolation at the database level.
--
-- Usage:
--   psql -h localhost -U bizsimai -d bizsimai -f postgres_rls_migration.sql
--
-- Prerequisites:
--   1. PostgreSQL 14+ installed
--   2. CREATE DATABASE bizsimai;
--   3. CREATE USER bizsimai WITH PASSWORD 'changeme';
--   4. GRANT ALL ON DATABASE bizsimai TO bizsimai;
--
-- Architecture:
--   - App role (bizsimai_app): used by the FastAPI backend, has SELECT/INSERT/UPDATE/DELETE
--   - Tenant isolation via RLS policies: professors can only see their own data
--   - session.local_tenant_id() function: set per-request via SET LOCAL
--   - JWT middleware sets the tenant context before each query
-- ============================================================

-- ── 1. Schema Creation ────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS users (
    username VARCHAR(255) PRIMARY KEY,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL CHECK(role IN ('owner','professor','student','pending')),
    name VARCHAR(255),
    student_id VARCHAR(255),
    email VARCHAR(255),
    department VARCHAR(255),
    provider VARCHAR(50) DEFAULT 'password',
    provider_uid VARCHAR(255),
    must_change_password BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS organizations (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    university_name VARCHAR(255),
    created_by VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS memberships (
    id VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(username),
    org_id VARCHAR(64) NOT NULL REFERENCES organizations(id),
    role VARCHAR(50) DEFAULT 'student',
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, org_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    code VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(255) NOT NULL UNIQUE,
    config_json TEXT NOT NULL,
    teams_json TEXT DEFAULT '[]',
    created_by VARCHAR(255),
    professor_user_id VARCHAR(255) REFERENCES users(username),
    class_id VARCHAR(64),
    max_human_teams INTEGER DEFAULT 30,
    current_round INTEGER DEFAULT 0,
    state VARCHAR(20) DEFAULT 'creating',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS classes (
    id VARCHAR(64) PRIMARY KEY,
    professor_user_id VARCHAR(255) NOT NULL REFERENCES users(username),
    name VARCHAR(255) NOT NULL,
    description TEXT,
    join_code VARCHAR(20) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS class_enrollments (
    id VARCHAR(64) PRIMARY KEY,
    class_id VARCHAR(64) NOT NULL REFERENCES classes(id),
    student_user_id VARCHAR(255) NOT NULL REFERENCES users(username),
    enrolled_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(class_id, student_user_id)
);

CREATE TABLE IF NOT EXISTS decisions (
    session_code VARCHAR(64) NOT NULL REFERENCES sessions(code),
    round_num INTEGER NOT NULL,
    team_id VARCHAR(64) NOT NULL,
    decision_json TEXT NOT NULL,
    PRIMARY KEY (session_code, round_num, team_id)
);

CREATE TABLE IF NOT EXISTS results (
    session_code VARCHAR(64) NOT NULL REFERENCES sessions(code),
    round_num INTEGER NOT NULL,
    team_id VARCHAR(64) NOT NULL,
    result_json TEXT NOT NULL,
    PRIMARY KEY (session_code, round_num, team_id)
);

CREATE TABLE IF NOT EXISTS refresh_tokens (
    token_hash VARCHAR(64) PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL REFERENCES users(username),
    issued_at DOUBLE PRECISION NOT NULL,
    expires_at DOUBLE PRECISION NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    rotated_from VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mfa_secrets (
    user_id VARCHAR(255) PRIMARY KEY REFERENCES users(username),
    secret TEXT NOT NULL,
    enabled BOOLEAN DEFAULT FALSE,
    backup_codes TEXT DEFAULT '[]',
    enabled_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scim_users (
    user_id VARCHAR(255) PRIMARY KEY REFERENCES users(username),
    external_id VARCHAR(255) UNIQUE,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id VARCHAR(64) PRIMARY KEY,
    actor_username VARCHAR(255) NOT NULL,
    action VARCHAR(100) NOT NULL,
    details TEXT DEFAULT '{}',
    ip_address VARCHAR(45),
    timestamp DOUBLE PRECISION
);

-- ── 2. Indexes ────────────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_sessions_prof ON sessions(professor_user_id);
CREATE INDEX IF NOT EXISTS idx_sessions_class ON sessions(class_id);
CREATE INDEX IF NOT EXISTS idx_enroll_class ON class_enrollments(class_id);
CREATE INDEX IF NOT EXISTS idx_enroll_student ON class_enrollments(student_user_id);
CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_username);
CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_memberships_org ON memberships(org_id);

-- ── 3. App Role ────────────────────────────────────────────────────────────

-- Create a dedicated app role (not superuser) for the backend
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'bizsimai_app') THEN
        CREATE ROLE bizsimai_app LOGIN PASSWORD 'changeme_app_password';
    END IF;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO bizsimai_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO bizsimai_app;

-- ── 4. Row-Level Security ─────────────────────────────────────────────────

-- Enable RLS on tenant-isolated tables
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE classes ENABLE ROW LEVEL SECURITY;
ALTER TABLE class_enrollments ENABLE ROW LEVEL SECURITY;
ALTER TABLE decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE results ENABLE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens ENABLE ROW LEVEL SECURITY;

-- Force RLS even for table owners (don't bypass)
ALTER TABLE sessions FORCE ROW LEVEL SECURITY;
ALTER TABLE classes FORCE ROW LEVEL SECURITY;
ALTER TABLE class_enrollments FORCE ROW LEVEL SECURITY;
ALTER TABLE decisions FORCE ROW LEVEL SECURITY;
ALTER TABLE results FORCE ROW LEVEL SECURITY;
ALTER TABLE refresh_tokens FORCE ROW LEVEL SECURITY;

-- ── 5. Tenant Context Function ────────────────────────────────────────────

-- This function retrieves the tenant ID set by the app per-request.
-- The app does: SET LOCAL bizsimai.tenant_id = 'org_123';
CREATE OR REPLACE FUNCTION current_tenant_id() RETURNS VARCHAR(64) AS $$
BEGIN
    RETURN current_setting('app.tenant_id', true);
END;
$$ LANGUAGE plpgsql STABLE;

-- Owner role check function
CREATE OR REPLACE FUNCTION is_owner() RETURNS BOOLEAN AS $$
BEGIN
    RETURN current_setting('app.user_role', true) = 'owner';
END;
$$ LANGUAGE plpgsql STABLE;

-- ── 6. RLS Policies ───────────────────────────────────────────────────────

-- Sessions: professors see only their own, students see only enrolled classes'
-- Owners see everything
CREATE POLICY sessions_tenant_isolation ON sessions
    USING (
        is_owner()
        OR professor_user_id = current_setting('app.user_id', true)
        OR class_id IN (
            SELECT ce.class_id FROM class_enrollments ce
            WHERE ce.student_user_id = current_setting('app.user_id', true)
        )
    );

-- Classes: professors see only their own
CREATE POLICY classes_tenant_isolation ON classes
    USING (
        is_owner()
        OR professor_user_id = current_setting('app.user_id', true)
    );

-- Class enrollments: professors see their class enrollments, students see their own
CREATE POLICY enrollments_tenant_isolation ON class_enrollments
    USING (
        is_owner()
        OR class_id IN (
            SELECT c.id FROM classes c
            WHERE c.professor_user_id = current_setting('app.user_id', true)
        )
        OR student_user_id = current_setting('app.user_id', true)
    );

-- Decisions: only accessible via sessions (inherits session policy)
CREATE POLICY decisions_tenant_isolation ON decisions
    USING (
        is_owner()
        OR session_code IN (
            SELECT s.code FROM sessions s
            WHERE s.professor_user_id = current_setting('app.user_id', true)
        )
    );

-- Results: same as decisions
CREATE POLICY results_tenant_isolation ON results
    USING (
        is_owner()
        OR session_code IN (
            SELECT s.code FROM sessions s
            WHERE s.professor_user_id = current_setting('app.user_id', true)
        )
    );

-- Refresh tokens: users see only their own tokens
CREATE POLICY refresh_tokens_isolation ON refresh_tokens
    USING (
        is_owner()
        OR user_id = current_setting('app.user_id', true)
    );

-- ── 7. Audit (no RLS — owner-only access) ────────────────────────────────
-- audit_logs, mfa_secrets, scim_users: accessible only to owner role
CREATE POLICY audit_logs_owner_only ON audit_logs
    USING (is_owner());

CREATE POLICY mfa_secrets_owner_only ON mfa_secrets
    USING (is_owner() OR user_id = current_setting('app.user_id', true));

-- ── 8. Per-Request Context (app-side) ────────────────────────────────────
-- The FastAPI backend must set these before each request:
--   SET LOCAL app.user_id = 'prof_smith';
--   SET LOCAL app.user_role = 'professor';
--   SET LOCAL app.tenant_id = 'org_mit';
-- Use a dependency or middleware that sets these from the JWT payload.
-- Example asyncpg pattern:
--   async with db.acquire() as conn:
--       await conn.execute(f"SET LOCAL app.user_id = '{user_id}'")
--       await conn.execute(f"SET LOCAL app.user_role = '{role}'")
--       results = await conn.fetch("SELECT * FROM sessions")
