"""Persistent SQLite database for BizSimAI sessions + users."""

from __future__ import annotations

import json
import os
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from models import (
    Announcement,
    PlayerDecision,
    RoundResult,
    Session,
    SessionConfiguration,
    TeamConfig,
)

DB_PATH = os.environ.get("BIZSIMAI_DB_PATH", "data.db")


def _generate_code() -> str:
    """Generate a random 8-char alphanumeric code for sessions (BIZ-XXXX)."""
    chars = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"
    return "BIZ-" + "".join(secrets.choice(chars) for _ in range(4))


def _generate_id() -> str:
    return secrets.token_hex(8)


class Database:
    """SQLite-backed store for sessions, decisions, announcements, results, and users."""

    # In-memory caches (populated on demand from SQLite)
    sessions: Dict[str, Any] = {}
    decisions: Dict[str, Any] = {}
    announcements: Dict[str, Any] = {}
    results: Dict[str, Any] = {}
    team_states: Dict[str, Any] = {}

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    # ── Connection helpers ────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            os.makedirs(os.path.dirname(DB_PATH) or ".", exist_ok=True)
            self._conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        return self._conn

    def _init_db(self) -> None:
        conn = self._get_conn()
        conn.executescript("""
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
                created_at TEXT DEFAULT (datetime('now'))
            );

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
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS decisions (
                session_code TEXT NOT NULL,
                round_num INTEGER NOT NULL,
                team_id TEXT NOT NULL,
                decision_json TEXT NOT NULL,
                PRIMARY KEY (session_code, round_num, team_id)
            );

            CREATE TABLE IF NOT EXISTS results (
                session_code TEXT NOT NULL,
                round_num INTEGER NOT NULL,
                team_id TEXT NOT NULL,
                result_json TEXT NOT NULL,
                PRIMARY KEY (session_code, round_num, team_id)
            );

            CREATE TABLE IF NOT EXISTS announcements (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                message TEXT NOT NULL,
                author_id TEXT NOT NULL,
                author_name TEXT NOT NULL,
                timestamp TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS team_states (
                session_code TEXT NOT NULL,
                team_id TEXT NOT NULL,
                state_json TEXT NOT NULL,
                PRIMARY KEY (session_code, team_id)
            );

            -- Multi-tenant tables
            CREATE TABLE IF NOT EXISTS professor_codes (
                code TEXT PRIMARY KEY,
                university_name TEXT,
                notes TEXT,
                used INTEGER DEFAULT 0,
                used_by TEXT,
                used_at TEXT,
                expires_at REAL DEFAULT 0,  -- Unix timestamp; 0 = no expiry (legacy)
                max_uses INTEGER DEFAULT 1,
                use_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS classes (
                id TEXT PRIMARY KEY,
                professor_user_id TEXT NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                join_code TEXT UNIQUE NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS class_enrollments (
                id TEXT PRIMARY KEY,
                class_id TEXT NOT NULL,
                student_user_id TEXT NOT NULL,
                enrolled_at TEXT DEFAULT (datetime('now')),
                UNIQUE(class_id, student_user_id)
            );

            -- SOTA: Organizations + Memberships for multi-tenant model
            CREATE TABLE IF NOT EXISTS organizations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                university_name TEXT,
                created_by TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS memberships (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                org_id TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'student',
                created_at TEXT DEFAULT (datetime('now')),
                UNIQUE(user_id, org_id)
            );

            -- SOTA: Audit logging for all auth events
            CREATE TABLE IF NOT EXISTS audit_logs (
                id TEXT PRIMARY KEY,
                actor_username TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT DEFAULT '{}',
                ip_address TEXT,
                timestamp REAL
            );

            CREATE INDEX IF NOT EXISTS idx_decisions ON decisions(session_code, round_num);
            CREATE INDEX IF NOT EXISTS idx_results ON results(session_code, round_num);
            CREATE INDEX IF NOT EXISTS idx_announcements ON announcements(session_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_prof ON sessions(professor_user_id);
            CREATE INDEX IF NOT EXISTS idx_sessions_class ON sessions(class_id);
            CREATE INDEX IF NOT EXISTS idx_enroll_class ON class_enrollments(class_id);
            CREATE INDEX IF NOT EXISTS idx_enroll_student ON class_enrollments(student_user_id);
            CREATE INDEX IF NOT EXISTS idx_classes_prof ON classes(professor_user_id);
            CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_logs(actor_username);
            CREATE INDEX IF NOT EXISTS idx_audit_action ON audit_logs(action);
            CREATE INDEX IF NOT EXISTS idx_memberships_user ON memberships(user_id);
            CREATE INDEX IF NOT EXISTS idx_memberships_org ON memberships(org_id);

            -- SOTA Phase 2: Refresh tokens (rotation + revocation)
            CREATE TABLE IF NOT EXISTS refresh_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                issued_at REAL NOT NULL,
                expires_at REAL NOT NULL,
                revoked INTEGER DEFAULT 0,
                rotated_from TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_refresh_user ON refresh_tokens(user_id);

            -- SOTA Phase 2: MFA secrets
            CREATE TABLE IF NOT EXISTS mfa_secrets (
                user_id TEXT PRIMARY KEY,
                secret TEXT NOT NULL,
                enabled INTEGER DEFAULT 0,
                backup_codes TEXT DEFAULT '[]',
                enabled_at TEXT
            );

            -- SOTA Phase 2: SCIM external ID mapping
            CREATE TABLE IF NOT EXISTS scim_users (
                user_id TEXT PRIMARY KEY,
                external_id TEXT UNIQUE,
                active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            -- Password reset tokens
            CREATE TABLE IF NOT EXISTS password_reset_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                expires_at REAL NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE INDEX IF NOT EXISTS idx_reset_user ON password_reset_tokens(user_id);
        """)
        conn.commit()

    # ── Session CRUD ──────────────────────────────────────────────────────

    def create_session(
        self,
        config: SessionConfiguration,
        teams: List[TeamConfig],
        created_by: str,
        max_human_teams: int = 30,
        professor_user_id: Optional[str] = None,
        class_id: Optional[str] = None,
    ) -> str:
        with self._lock:
            conn = self._get_conn()
            code = _generate_code()
            while conn.execute("SELECT 1 FROM sessions WHERE code=?", (code,)).fetchone():
                code = _generate_code()

            sid = _generate_id()
            config_json = config.model_dump_json()
            teams_json = [t.model_dump() for t in teams]

            conn.execute(
                """INSERT INTO sessions (code, session_id, config_json, teams_json, created_by, professor_user_id, class_id, max_human_teams)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (code, sid, config_json, json.dumps(teams_json), created_by, professor_user_id, class_id, max_human_teams),
            )
            conn.commit()

            # Build in-memory Session object for immediate use
            session = Session(
                id=sid, code=code, config=config, teams=teams,
                created_by=created_by, maxHumanTeams=max_human_teams,
            )
            self.sessions[code] = session
            self.decisions[code] = {}
            self.announcements[code] = []
            self.results[code] = {}
            self.team_states[code] = {}
            return code

    def get_session(self, code: str) -> Optional[Session]:
        # Fast path: in-memory cache
        if code in self.sessions:
            return self.sessions[code]
        # Fallback: DB lookup
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM sessions WHERE code=?", (code,)
            ).fetchone()
        if not row:
            return None
        config_json_str = row["config_json"]
        if isinstance(config_json_str, str):
            import json as _json
            config = SessionConfiguration(**_json.loads(config_json_str))
        else:
            config = SessionConfiguration(**config_json_str)
        teams_raw = row["teams_json"]
        if isinstance(teams_raw, list):
            teams = [TeamConfig(**t) for t in teams_raw]
        else:
            import json as _json
            teams = [TeamConfig(**t) for t in _json.loads(teams_raw)]
        session = Session(
            id=row["session_id"], code=code, config=config, teams=teams,
            created_by=row["created_by"], maxHumanTeams=row["max_human_teams"],
            currentRound=row["current_round"], state=row["state"],
        )
        self.sessions[code] = session
        return session

    def update_session(self, code: str, updates: Dict[str, Any]) -> None:
        # Map camelCase attribute names to snake_case DB column names
        _ATTR_TO_COL = {
            "currentRound": "current_round",
            "maxHumanTeams": "max_human_teams",
            "teams": "teams_json",
        }
        with self._lock:
            conn = self._get_conn()
            session = self.sessions.get(code)
            if not session:
                row = conn.execute("SELECT * FROM sessions WHERE code=?", (code,)).fetchone()
                if row:
                    config_json_str = row["config_json"]
                    if isinstance(config_json_str, str):
                        import json as _json
                        config = SessionConfiguration(**_json.loads(config_json_str))
                    else:
                        config = SessionConfiguration(**config_json_str)
                    teams_raw = row["teams_json"]
                    if isinstance(teams_raw, list):
                        teams = [TeamConfig(**t) for t in teams_raw]
                    else:
                        import json as _json
                        teams = [TeamConfig(**t) for t in _json.loads(teams_raw)]
                    session = Session(
                        id=row["session_id"], code=code, config=config, teams=teams,
                        created_by=row["created_by"], maxHumanTeams=row["max_human_teams"],
                        currentRound=row["current_round"], state=row["state"],
                    )
                    self.sessions[code] = session

            if session:
                for key, value in updates.items():
                    setattr(session, key, value)
                # Persist to DB — map attribute names to column names
                col_updates = []
                values = []
                for key, value in updates.items():
                    col_name = _ATTR_TO_COL.get(key, key)
                    col_updates.append(f"{col_name}=?")
                    if key == "teams":
                        import json as _json
                        values.append(_json.dumps([t.model_dump() for t in value]))
                    elif key == "state" and hasattr(value, "value"):
                        values.append(value.value)
                    else:
                        values.append(value)
                values.append(code)
                set_clause = ", ".join(col_updates)
                conn.execute(f"UPDATE sessions SET {set_clause} WHERE code=?", values)
                conn.commit()

    def get_session_by_id(self, session_id: str) -> Optional[Session]:
        for s in self.sessions.values():
            if s.id == session_id:
                return s
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM sessions WHERE session_id=?", (session_id,)).fetchone()
        if not row:
            return None
        config_json_str = row["config_json"]
        if isinstance(config_json_str, str):
            import json as _json
            config = SessionConfiguration(**_json.loads(config_json_str))
        else:
            config = SessionConfiguration(**config_json_str)
        teams_raw = row["teams_json"]
        if isinstance(teams_raw, list):
            teams = [TeamConfig(**t) for t in teams_raw]
        else:
            import json as _json
            teams = [TeamConfig(**t) for t in _json.loads(teams_raw)]
        session = Session(
            id=row["session_id"], code=row["code"], config=config, teams=teams,
            created_by=row["created_by"], maxHumanTeams=row["max_human_teams"],
            currentRound=row["current_round"], state=row["state"],
        )
        self.sessions[row["code"]] = session
        return session

    # ── Announcements ─────────────────────────────────────────────────────

    def add_announcement(self, session_id: str, announcement: Announcement) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                """INSERT INTO announcements (id, session_id, message, author_id, author_name)
                   VALUES (?, ?, ?, ?, ?)""",
                (announcement.id, session_id, announcement.message,
                 announcement.authorId, announcement.authorName),
            )
            conn.commit()
        if session_id not in self.announcements:
            self.announcements[session_id] = []
        self.announcements[session_id].append(announcement)

    def get_announcements(self, session_id: str) -> List[Announcement]:
        if session_id in self.announcements:
            return self.announcements[session_id]
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM announcements WHERE session_id=?", (session_id,)
            ).fetchall()
        results = []
        for row in rows:
            ts = datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else datetime.now(timezone.utc)
            results.append(Announcement(
                id=row["id"], sessionId=row["session_id"], message=row["message"],
                authorId=row["author_id"], authorName=row["author_name"], timestamp=ts,
            ))
        self.announcements[session_id] = results
        return results

    # ── Decisions ─────────────────────────────────────────────────────────

    def store_decision(self, session_code: str, round_num: int, team_id: str, decision: PlayerDecision) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    "INSERT INTO decisions (session_code, round_num, team_id, decision_json) VALUES (?, ?, ?, ?)",
                    (session_code, round_num, team_id, decision.model_dump_json()),
                )
                conn.commit()
            except sqlite3.IntegrityError:
                return False
        if session_code not in self.decisions:
            self.decisions[session_code] = {}
        if round_num not in self.decisions[session_code]:
            self.decisions[session_code][round_num] = {}
        self.decisions[session_code][round_num][team_id] = decision
        return True

    def get_decisions(self, session_code: str, round_num: int) -> Dict[str, PlayerDecision]:
        if session_code in self.decisions and round_num in self.decisions.get(session_code, {}):
            return self.decisions[session_code][round_num]
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT team_id, decision_json FROM decisions WHERE session_code=? AND round_num=?",
                (session_code, round_num),
            ).fetchall()
        result = {}
        for row in rows:
            d = PlayerDecision(**row["decision_json"]) if isinstance(row["decision_json"], str) else row["decision_json"]
            result[row["team_id"]] = d
        if session_code not in self.decisions:
            self.decisions[session_code] = {}
        self.decisions[session_code][round_num] = result
        return result

    def has_decision(self, session_code: str, round_num: int, team_id: str) -> bool:
        if session_code in self.decisions and round_num in self.decisions.get(session_code, {}):
            return team_id in self.decisions[session_code][round_num]
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT 1 FROM decisions WHERE session_code=? AND round_num=? AND team_id=?",
                (session_code, round_num, team_id),
            ).fetchone()
        return row is not None

    # ── Results ───────────────────────────────────────────────────────────

    def store_results(self, session_code: str, round_num: int, results: List[RoundResult]) -> None:
        with self._lock:
            conn = self._get_conn()
            for r in results:
                conn.execute(
                    "INSERT OR REPLACE INTO results (session_code, round_num, team_id, result_json) VALUES (?, ?, ?, ?)",
                    (session_code, round_num, r.teamId, r.model_dump_json()),
                )
            conn.commit()
        if session_code not in self.results:
            self.results[session_code] = {}
        self.results[session_code][round_num] = results

    def get_results(self, session_code: str, round_num: int) -> Optional[List[RoundResult]]:
        if session_code in self.results and round_num in self.results.get(session_code, {}):
            return self.results[session_code][round_num]
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT team_id, result_json FROM results WHERE session_code=? AND round_num=?",
                (session_code, round_num),
            ).fetchall()
        result = [RoundResult(**row["result_json"]) if isinstance(row["result_json"], str) else row["result_json"] for row in rows]
        if session_code not in self.results:
            self.results[session_code] = {}
        self.results[session_code][round_num] = result
        return result if result else None

    def get_all_results(self, session_code: str) -> Dict[int, List[RoundResult]]:
        if session_code in self.results and self.results[session_code]:
            return self.results[session_code]
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT round_num, team_id, result_json FROM results WHERE session_code=? ORDER BY round_num",
                (session_code,),
            ).fetchall()
        result: Dict[int, List[RoundResult]] = {}
        for row in rows:
            r = RoundResult(**row["result_json"]) if isinstance(row["result_json"], str) else row["result_json"]
            result.setdefault(row["round_num"], []).append(r)
        self.results[session_code] = result
        return result

    # ── Team states ───────────────────────────────────────────────────────

    def get_team_state(self, session_code: str, team_id: str) -> Dict[str, Any]:
        return self.team_states.get(session_code, {}).get(team_id, {})

    def update_team_state(self, session_code: str, team_id: str, updates: Dict[str, Any]) -> None:
        if session_code not in self.team_states:
            self.team_states[session_code] = {}
        if team_id not in self.team_states[session_code]:
            self.team_states[session_code][team_id] = {}
        self.team_states[session_code][team_id].update(updates)

    def count_submitted_decisions(self, session_code: str, round_num: int) -> int:
        return len(self.decisions.get(session_code, {}).get(round_num, {}))

    def list_sessions(self, professor_user_id: Optional[str] = None, class_id: Optional[str] = None) -> List[Session]:
        """List sessions, optionally filtered by professor or class."""
        if not professor_user_id and not class_id:
            # No filter — return all in-memory (backward compat for owner)
            with self._lock:
                return list(self.sessions.values())

        with self._lock:
            conn = self._get_conn()
            if professor_user_id and class_id:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE professor_user_id=? AND class_id=? ORDER BY created_at DESC",
                    (professor_user_id, class_id),
                ).fetchall()
            elif professor_user_id:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE professor_user_id=? ORDER BY created_at DESC",
                    (professor_user_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM sessions WHERE class_id=? ORDER BY created_at DESC",
                    (class_id,),
                ).fetchall()

        result = []
        for row in rows:
            code = row["code"]
            if code in self.sessions:
                result.append(self.sessions[code])
            else:
                # Rebuild from DB row
                import json as _json
                config = SessionConfiguration(**_json.loads(row["config_json"]))
                teams_raw = row["teams_json"]
                if isinstance(teams_raw, list):
                    teams = [TeamConfig(**t) for t in teams_raw]
                else:
                    teams = [TeamConfig(**t) for t in _json.loads(teams_raw)]
                session = Session(
                    id=row["session_id"], code=code, config=config, teams=teams,
                    created_by=row["created_by"], maxHumanTeams=row["max_human_teams"],
                    currentRound=row["current_round"], state=row["state"],
                )
                self.sessions[code] = session
                result.append(session)
        return result

    def delete_session(self, code: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            if code in self.sessions:
                del self.sessions[code]
                conn.execute("DELETE FROM decisions WHERE session_code=?", (code,))
                conn.execute("DELETE FROM results WHERE session_code=?", (code,))
                conn.execute("DELETE FROM announcements WHERE session_id=?", (code,))
                conn.execute("DELETE FROM team_states WHERE session_code=?", (code,))
                conn.execute("DELETE FROM sessions WHERE code=?", (code,))
                conn.commit()
                return True
        return False

    # ── Users ─────────────────────────────────────────────────────────────

    def get_user(self, username: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone()
        if not row:
            return None
        return dict(row)

    def get_user_by_student_id(self, student_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM users WHERE student_id=?", (student_id,)).fetchone()
        if not row:
            return None
        return dict(row)

    def create_user(self, username: str, password_hash: str, role: str,
                    name: Optional[str] = None, student_id: Optional[str] = None,
                    email: Optional[str] = None, provider: str = "password",
                    provider_uid: Optional[str] = None, must_change_password: int = 0) -> bool:
        try:
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    """INSERT INTO users (username, password_hash, role, name, student_id, email, provider, provider_uid, must_change_password)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (username, password_hash, role, name, student_id, email, provider, provider_uid, must_change_password),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def verify_user(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """Verify username/password and return user dict if match.

        Supports both bcrypt (new) and SHA-256 (legacy) hashes.
        On successful SHA-256 verification, silently migrates to bcrypt.
        """
        from security import verify_password, is_legacy_hash, hash_password

        user = self.get_user(username)
        if not user:
            return None
        # Check by name match for students (name stored as username in login)
        if user["role"] == "student" and user.get("name") != username:
            # Try student_id match
            user = self.get_user_by_student_id(username)
            if not user:
                return None
        # Verify password using security module (bcrypt + legacy SHA-256)
        stored_hash = user["password_hash"]
        if verify_password(password, stored_hash):
            # Migrate legacy SHA-256 to bcrypt silently
            if is_legacy_hash(stored_hash):
                new_hash = hash_password(password)
                self.update_user_password(username, new_hash)
            return user
        return None

    def update_user_password(self, username: str, password_hash: str) -> bool:
        """Update a user's password hash."""
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE users SET password_hash=? WHERE username=?",
                    (password_hash, username),
                )
            return True
        except sqlite3.Error:
            return False

    def register_student(self, student_id: str, name: str, password: str) -> bool:
        """Register a new student. Password is already hashed by caller (bcrypt)."""
        return self.create_user(
            username=student_id, password_hash=password, role="student",
            name=name, student_id=student_id,
        )

    # ── Multi-tenant: Professor Codes ──────────────────────────────────────

    def create_professor_code(self, code: str, university_name: str = "", notes: str = "",
                               expires_in_days: int = 7) -> bool:
        """Admin creates a one-time professor access code with expiry (default 7 days)."""
        import time as _time
        try:
            with self._lock:
                conn = self._get_conn()
                expires_at = _time.time() + (expires_in_days * 86400) if expires_in_days > 0 else 0
                conn.execute(
                    "INSERT INTO professor_codes (code, university_name, notes, expires_at) VALUES (?, ?, ?, ?)",
                    (code, university_name, notes, expires_at),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

    def validate_professor_code(self, code: str) -> Optional[Dict[str, Any]]:
        """Check if a professor code is valid, unused, and not expired."""
        import time as _time
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM professor_codes WHERE code=? AND used=0", (code,)
            ).fetchone()
        if not row:
            return None
        # Check expiry (0 = no expiry, for legacy codes)
        expires_at = row["expires_at"] if "expires_at" in row.keys() else 0
        if expires_at and expires_at > 0 and _time.time() > expires_at:
            return None  # Expired
        return dict(row)

    def redeem_professor_code(self, code: str, used_by: str) -> bool:
        """Mark a professor code as used and promote the user to professor."""
        import time as _time
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM professor_codes WHERE code=? AND used=0", (code,)
            ).fetchone()
            if not row:
                return False
            # Check expiry
            expires_at = row["expires_at"] if "expires_at" in row.keys() else 0
            if expires_at and expires_at > 0 and _time.time() > expires_at:
                return False
            conn.execute(
                "UPDATE professor_codes SET used=1, used_by=?, used_at=datetime('now') WHERE code=?",
                (used_by, code),
            )
            conn.execute(
                "UPDATE users SET role='professor' WHERE username=?", (used_by,)
            )
            conn.commit()
        return True

    def list_professor_codes(self) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM professor_codes ORDER BY created_at DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Multi-tenant: Classes ──────────────────────────────────────────────

    def create_class(self, professor_user_id: str, name: str, description: str = "") -> Dict[str, Any]:
        """Professor creates a new class. Returns class dict with join_code."""
        with self._lock:
            conn = self._get_conn()
            class_id = _generate_id()
            join_code = _generate_code()
            while conn.execute("SELECT 1 FROM classes WHERE join_code=?", (join_code,)).fetchone():
                join_code = _generate_code()
            conn.execute(
                "INSERT INTO classes (id, professor_user_id, name, description, join_code) VALUES (?, ?, ?, ?, ?)",
                (class_id, professor_user_id, name, description, join_code),
            )
            conn.commit()
        return {
            "id": class_id,
            "professor_user_id": professor_user_id,
            "name": name,
            "description": description,
            "join_code": join_code,
        }

    def get_class_by_join_code(self, join_code: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM classes WHERE join_code=? AND is_active=1", (join_code,)
            ).fetchone()
        return dict(row) if row else None

    def get_class(self, class_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            row = conn.execute("SELECT * FROM classes WHERE id=?", (class_id,)).fetchone()
        return dict(row) if row else None

    def list_classes_by_professor(self, professor_user_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM classes WHERE professor_user_id=? ORDER BY created_at DESC",
                (professor_user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Multi-tenant: Enrollments ──────────────────────────────────────────

    def enroll_student(self, class_id: str, student_user_id: str) -> bool:
        """Enroll a student in a class."""
        try:
            with self._lock:
                conn = self._get_conn()
                enroll_id = _generate_id()
                conn.execute(
                    "INSERT INTO class_enrollments (id, class_id, student_user_id) VALUES (?, ?, ?)",
                    (enroll_id, class_id, student_user_id),
                )
                conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False  # Already enrolled

    def get_student_classes(self, student_user_id: str) -> List[Dict[str, Any]]:
        """Get all classes a student is enrolled in."""
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT c.* FROM classes c
                   JOIN class_enrollments e ON c.id = e.class_id
                   WHERE e.student_user_id=? AND c.is_active=1
                   ORDER BY c.created_at DESC""",
                (student_user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_class_students(self, class_id: str) -> List[Dict[str, Any]]:
        """Get all students enrolled in a class."""
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT u.username, u.name, u.email, e.enrolled_at
                   FROM users u
                   JOIN class_enrollments e ON u.username = e.student_user_id
                   WHERE e.class_id=?
                   ORDER BY e.enrolled_at""",
                (class_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── Multi-tenant: User updates ────────────────────────────────────────

    def update_user_role(self, username: str, role: str) -> bool:
        with self._lock:
            conn = self._get_conn()
            conn.execute("UPDATE users SET role=? WHERE username=?", (role, username))
            conn.commit()
        return True

    def upsert_user(self, username: str, password_hash: str, role: str,
                    name: str = "", email: str = "", provider: str = "password",
                    provider_uid: str = "", must_change_password: int = 0) -> bool:
        """Insert or update a user (used for Google/Apple sign-in)."""
        try:
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    """INSERT INTO users (username, password_hash, role, name, email, provider, provider_uid, must_change_password)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(username) DO UPDATE SET
                           password_hash=excluded.password_hash,
                           role=excluded.role,
                           name=excluded.name,
                           email=excluded.email,
                           provider=excluded.provider,
                           provider_uid=excluded.provider_uid,
                           must_change_password=excluded.must_change_password""",
                    (username, password_hash, role, name, email, provider, provider_uid, must_change_password),
                )
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    # ── SOTA: Organizations + Memberships ────────────────────────────────

    def get_or_create_organization(self, university_name: str, created_by: str = "") -> Dict[str, Any]:
        """Get or create an organization for a university name."""
        with self._lock:
            conn = self._get_conn()
            row = conn.execute(
                "SELECT * FROM organizations WHERE university_name=?", (university_name,)
            ).fetchone()
            if row:
                return dict(row)
            org_id = _generate_id()
            conn.execute(
                "INSERT INTO organizations (id, name, university_name, created_by) VALUES (?, ?, ?, ?)",
                (org_id, university_name, university_name, created_by),
            )
            conn.commit()
            return {"id": org_id, "name": university_name, "university_name": university_name, "created_by": created_by}

    def add_membership(self, user_id: str, org_id: str, role: str = "student") -> bool:
        """Add a user to an organization with a role."""
        try:
            with self._lock:
                conn = self._get_conn()
                conn.execute(
                    "INSERT OR IGNORE INTO memberships (id, user_id, org_id, role) VALUES (?, ?, ?, ?)",
                    (_generate_id(), user_id, org_id, role),
                )
                conn.commit()
            return True
        except sqlite3.Error:
            return False

    def get_user_orgs(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all organizations a user belongs to."""
        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                """SELECT o.*, m.role as membership_role
                   FROM memberships m JOIN organizations o ON m.org_id = o.id
                   WHERE m.user_id=?""",
                (user_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_primary_org(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get the primary organization for a user (first membership)."""
        orgs = self.get_user_orgs(user_id)
        return orgs[0] if orgs else None

    # ── SOTA Phase 2: Refresh Token Rotation ─────────────────────────────

    def store_refresh_token(self, token_hash: str, user_id: str, issued_at: float,
                            expires_at: float, rotated_from: Optional[str] = None) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO refresh_tokens (token_hash, user_id, issued_at, expires_at, revoked, rotated_from) "
                "VALUES (?, ?, ?, ?, 0, ?)",
                (token_hash, user_id, issued_at, expires_at, rotated_from),
            )
            conn.commit()

    def verify_refresh_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM refresh_tokens WHERE token_hash=? AND revoked=0 AND expires_at>?",
            (token_hash, datetime.now(timezone.utc).timestamp()),
        ).fetchone()
        return dict(row) if row else None

    def revoke_refresh_token(self, token_hash: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("UPDATE refresh_tokens SET revoked=1 WHERE token_hash=?", (token_hash,))
            conn.commit()

    def revoke_all_user_refresh_tokens(self, user_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("UPDATE refresh_tokens SET revoked=1 WHERE user_id=?", (user_id,))
            conn.commit()

    def cleanup_expired_refresh_tokens(self) -> int:
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "DELETE FROM refresh_tokens WHERE expires_at < ?",
                (datetime.now(timezone.utc).timestamp(),),
            )
            conn.commit()
            return cur.rowcount

    # ── SOTA Phase 2: MFA/TOTP ──────────────────────────────────────────

    def set_mfa_secret(self, user_id: str, secret: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO mfa_secrets (user_id, secret, enabled, backup_codes) VALUES (?, ?, 0, '[]')",
                (user_id, secret),
            )
            conn.commit()

    def enable_mfa(self, user_id: str, backup_codes: list) -> None:
        import json
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE mfa_secrets SET enabled=1, backup_codes=?, enabled_at=datetime('now') WHERE user_id=?",
                (json.dumps(backup_codes), user_id),
            )
            conn.commit()

    def disable_mfa(self, user_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM mfa_secrets WHERE user_id=?", (user_id,))
            conn.commit()

    def get_mfa_secret(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM mfa_secrets WHERE user_id=?", (user_id,)).fetchone()
        return dict(row) if row else None

    def is_mfa_enabled(self, user_id: str) -> bool:
        mfa = self.get_mfa_secret(user_id)
        return mfa is not None and mfa.get("enabled") == 1

    def verify_backup_code(self, user_id: str, code: str) -> bool:
        import json
        mfa = self.get_mfa_secret(user_id)
        if not mfa:
            return False
        codes = json.loads(mfa.get("backup_codes", "[]"))
        if code in codes:
            codes.remove(code)
            with self._lock:
                conn = self._get_conn()
                conn.execute("UPDATE mfa_secrets SET backup_codes=? WHERE user_id=?", (json.dumps(codes), user_id))
                conn.commit()
            return True
        return False

    # ── SOTA Phase 2: SCIM user mapping ─────────────────────────────────

    def scim_create_user(self, user_id: str, external_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT OR REPLACE INTO scim_users (user_id, external_id, active, created_at, updated_at) "
                "VALUES (?, ?, 1, datetime('now'), datetime('now'))",
                (user_id, external_id),
            )
            conn.commit()

    def scim_get_user_by_external(self, external_id: str) -> Optional[Dict[str, Any]]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM scim_users WHERE external_id=?", (external_id,)).fetchone()
        return dict(row) if row else None

    def scim_update_status(self, user_id: str, active: bool) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute(
                "UPDATE scim_users SET active=?, updated_at=datetime('now') WHERE user_id=?",
                (1 if active else 0, user_id),
            )
            conn.commit()

    def scim_delete_user(self, user_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            conn.execute("DELETE FROM scim_users WHERE user_id=?", (user_id,))
            conn.commit()

    def scim_list_users(self) -> list:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM scim_users").fetchall()
        return [dict(r) for r in rows]

    # ── Password Reset Tokens ────────────────────────────────────────────────

    def create_reset_token(self, user_id: str, token_hash: str, expires_in_hours: int = 1) -> None:
        """Create a password reset token. Token is stored as SHA-256 hash."""
        import time as _time
        expires_at = _time.time() + (expires_in_hours * 3600)
        with self._lock:
            conn = self._get_conn()
            # Invalidate any existing unused tokens for this user
            conn.execute(
                "UPDATE password_reset_tokens SET used=1 WHERE user_id=? AND used=0",
                (user_id,),
            )
            conn.execute(
                "INSERT INTO password_reset_tokens (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                (token_hash, user_id, expires_at),
            )
            conn.commit()

    def verify_reset_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        """Verify a reset token is valid (exists, unused, not expired). Returns user_id or None."""
        import time as _time
        now = _time.time()
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM password_reset_tokens WHERE token_hash=? AND used=0 AND expires_at>?",
            (token_hash, now),
        ).fetchone()
        return dict(row) if row else None

    def consume_reset_token(self, token_hash: str) -> bool:
        """Mark a reset token as used. Returns True if successful."""
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "UPDATE password_reset_tokens SET used=1 WHERE token_hash=? AND used=0",
                (token_hash,),
            )
            conn.commit()
            return cur.rowcount > 0

    def cleanup_expired_reset_tokens(self) -> int:
        """Remove expired and used reset tokens older than 24 hours."""
        import time as _time
        cutoff = _time.time() - 86400
        with self._lock:
            conn = self._get_conn()
            cur = conn.execute(
                "DELETE FROM password_reset_tokens WHERE expires_at < ? OR used=1",
                (cutoff,),
            )
            conn.commit()
            return cur.rowcount


# Module-level singleton
db = Database()
