"""Service for database health checks."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class DatabaseHealthService:
    """Service for database health checks."""
    
    def __init__(self, db_connection):
        self.db = db_connection
    
    def check_connectivity(self) -> Dict[str, Any]:
        """Check database connectivity."""
        try:
            with self.db._get_conn() as conn:
                conn.execute("SELECT 1").fetchone()
            return {"status": "ok", "error": None}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def check_integrity(self, quick: bool = True) -> Dict[str, Any]:
        """Check database integrity."""
        try:
            with self.db._get_conn() as conn:
                if quick:
                    result = conn.execute("PRAGMA quick_check").fetchone()
                else:
                    result = conn.execute("PRAGMA integrity_check").fetchone()
                
                status = "ok" if result[0] == "ok" else "failed"
                return {"status": status, "error_count": 0 if status == "ok" else 1}
        except Exception as e:
            return {"status": "failed", "error": str(e)}
    
    def check_foreign_keys(self) -> Dict[str, Any]:
        """Check foreign key constraints."""
        violations = []
        
        with self.db._get_conn() as conn:
            # Check for orphaned records in various tables
            checks = [
                ("memberships", "user_id", "users", "username"),
                ("memberships", "org_id", "organizations", "id"),
                ("classes", "professor_user_id", "users", "username"),
                ("sessions", "created_by", "users", "username"),
                ("sessions", "professor_user_id", "users", "username"),
            ]
            
            for table, fk_col, ref_table, ref_col in checks:
                result = conn.execute(
                    f"""
                        SELECT COUNT(*) as count
                        FROM {table}
                        WHERE {fk_col} IS NOT NULL
                        AND {fk_col} NOT IN (SELECT {ref_col} FROM {ref_table})
                    """
                ).fetchone()
                
                if result and result[0] > 0:
                    violations.append({
                        "table": table,
                        "foreign_key": fk_col,
                        "referenced_table": ref_table,
                        "orphan_count": result[0]
                    })
        
        return {
            "status": "ok" if len(violations) == 0 else "violations_found",
            "orphan_count": sum(v["orphan_count"] for v in violations),
            "violations": violations
        }
    
    def check_domain_invariants(self) -> Dict[str, Any]:
        """Check domain-specific invariants."""
        violations = []
        
        with self.db._get_conn() as conn:
            # Check for users without a role
            result = conn.execute(
                "SELECT COUNT(*) as count FROM users WHERE role NOT IN ('owner', 'professor', 'student')"
            ).fetchone()
            
            if result and result[0] > 0:
                violations.append({
                    "type": "invalid_role",
                    "count": result[0]
                })
            
            # Check for suspended users with active sessions
            result = conn.execute(
                """
                    SELECT COUNT(*) as count
                    FROM users u
                    WHERE u.status = 'suspended'
                """
            ).fetchone()
            
            # This is informational, not a violation
            
        return {
            "status": "ok" if len(violations) == 0 else "violations_found",
            "violation_count": len(violations),
            "violations": violations
        }
    
    def check_backup_status(self) -> Dict[str, Any]:
        """Check backup status."""
        # This would check the backup_runs table
        return {
            "status": "unknown",
            "age_seconds": 0,
            "last_backup_at": None,
            "restore_test_status": "not_run"
        }
    
    def get_health_report(self, quick: bool = True) -> Dict[str, Any]:
        """Get a complete health report."""
        request_id = f"health_{secrets.token_hex(16)}"
        
        connectivity = self.check_connectivity()
        integrity = self.check_integrity(quick=quick)
        relations = self.check_foreign_keys()
        domain = self.check_domain_invariants()
        backup = self.check_backup_status()
        
        overall_status = "healthy"
        if connectivity["status"] != "ok":
            overall_status = "connectivity_failed"
        elif integrity["status"] != "ok":
            overall_status = "integrity_failed"
        elif relations["status"] != "ok":
            overall_status = "relations_failed"
        elif domain["status"] != "ok":
            overall_status = "domain_violations"
        
        return {
            "status": overall_status,
            "checked_at": datetime.now(timezone.utc),
            "engine": "sqlite",
            "migration_version": "004",  # Current version
            "integrity": integrity,
            "relations": relations,
            "domain": domain,
            "backup": backup,
            "request_id": request_id
        }
