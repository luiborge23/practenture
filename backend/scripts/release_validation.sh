#!/bin/bash

# Release Validation Script for Practenture
# This script runs all tests and validations before deployment

set -e

echo "ERROR: This legacy systemd-era validator is retired. Use the GitHub quality gates plus Tests/test_release_contracts.py and the isolated Compose rehearsal documented by the root release tooling." >&2
exit 64

echo "=== Release Validation ==="

# Configuration
BACKEND_DIR="/var/www/practenture/backend"
TEST_RESULTS_DIR="$BACKEND_DIR/test-results"

# Create test results directory
mkdir -p "$TEST_RESULTS_DIR"

# ── Phase 5: Release Validation ──────────────────────────────────────────────

echo ""
echo "Step 1/3: Running unit tests..."
.venv/bin/pytest tests/unit/ -v --tb=short --junitxml="$TEST_RESULTS_DIR/unit.xml" || {
    echo "ERROR: Unit tests failed"
    exit 1
}

echo ""
echo "Step 2/3: Running contract tests..."
.venv/bin/pytest tests/contracts/ -v --tb=short --junitxml="$TEST_RESULTS_DIR/contract.xml" || {
    echo "ERROR: Contract tests failed"
    exit 1
}

echo ""
echo "Step 3/3: Running migration tests..."
.venv/bin/pytest tests/test_migrations.py -v --tb=short --junitxml="$TEST_RESULTS_DIR/migration.xml" || {
    echo "ERROR: Migration tests failed"
    exit 1
}

# ── Database Health Check ────────────────────────────────────────────────────

echo ""
echo "Checking database health..."
.venv/bin/python -c "
from services.database_health_service import DatabaseHealthService
from database import db

health = DatabaseHealthService(db).get_health_report(quick=True)
print(f'Database Health: {health[\"status\"]}')

if health['status'] != 'healthy':
    print('ERROR: Database health check failed')
    exit(1)
"

# ── Backup Validation ────────────────────────────────────────────────────────

echo ""
echo "Validating backup configuration..."
.venv/bin/python -c "
from services.backup_status_service import BackupStatusService
from database import db

status = BackupStatusService(db).get_backup_status()
print(f'Backup Status: {status[\"status\"]}')
"

# ── Code Quality Checks ──────────────────────────────────────────────────────

echo ""
echo "Running code quality checks..."

# Check for Python syntax errors
.venv/bin/python -m py_compile backend/*.py || {
    echo "ERROR: Python syntax errors found"
    exit 1
}

# Check for import errors
.venv/bin/python -c "
import sys
try:
    from main import app
    print('Main application imports successfully')
except Exception as e:
    print(f'ERROR: Import error: {e}')
    sys.exit(1)
"

# ── API Contract Validation ──────────────────────────────────────────────────

echo ""
echo "Validating API contracts..."

# Test that all expected endpoints exist
.venv/bin/python -c "
from routers.owner_admin import router

endpoints = [route.path for route in router.routes]
expected_endpoints = [
    '/professor-invitations',
    '/professors/pre-create',
    '/users',
    '/system/database-health',
    '/audit-events'
]

for endpoint in expected_endpoints:
    if not any(endpoint in e for e in endpoints):
        print(f'ERROR: Missing endpoint: {endpoint}')
        exit(1)

print('All expected endpoints present')
"

# ── Security Validation ──────────────────────────────────────────────────────

echo ""
echo "Running security validation..."

# Check for hardcoded secrets
if grep -r "SECRET_KEY\|API_KEY\|PASSWORD" backend/*.py 2>/dev/null | grep -v "os.environ\|getenv"; then
    echo "WARNING: Potential hardcoded secrets found"
fi

# Check for SQL injection vulnerabilities
if grep -r "execute.*+" backend/*.py 2>/dev/null; then
    echo "WARNING: Potential SQL injection vulnerability found"
fi

echo "Security validation complete"

# ── Final Summary ────────────────────────────────────────────────────────────

echo ""
echo "=== Release Validation Complete ==="
echo ""
echo "Test Results:"
ls -la "$TEST_RESULTS_DIR/"

echo ""
echo "Next steps:"
echo "1. Review test results in $TEST_RESULTS_DIR/"
echo "2. If all checks pass, proceed to Phase 6 deployment"
echo ""
echo "To deploy:"
echo "   cd /var/www/practenture/backend"
echo "   .venv/bin/alembic upgrade head"
echo "   sudo systemctl restart practenture"
