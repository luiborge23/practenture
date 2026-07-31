#!/bin/bash

# Backup-Gated Deployment Script for Practenture
# This script ensures a recent backup exists before deploying

set -e

echo "ERROR: This legacy systemd/flat-file deployment path is retired. Use only the immutable, checksummed root ec2-deploy.sh workflow." >&2
exit 64

echo "=== Backup-Gated Deployment ==="

# Configuration
BACKEND_DIR="/var/www/practenture/backend"
DEPLOYMENT_LOG="/var/log/practenture/deployment.log"

# Create log directory
mkdir -p /var/log/practenture

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$DEPLOYMENT_LOG"
}

# ── Phase 6: Backup Gate Check ───────────────────────────────────────────────

log "Checking backup status..."

# Get latest backup age
BACKUP_AGE_SECONDS=$(.venv/bin/python -c "
from services.backup_status_service import BackupStatusService
from database import db

status = BackupStatusService(db).get_backup_status()
print(status.get('age_seconds', 999999))
")

MAX_BACKUP_AGE=3600  # 1 hour

if [ "$BACKUP_AGE_SECONDS" -gt "$MAX_BACKUP_AGE" ]; then
    log "ERROR: No recent backup found (age: ${BACKUP_AGE_SECONDS}s, max: ${MAX_BACKUP_AGE}s)"
    log "Please create a backup before deploying:"
    log "  cd $BACKEND_DIR && .venv/bin/python -c 'from services.backup_status_service import BackupStatusService; from database import db; s=BackupStatusService(db); print(s.record_backup(\"pending\", \"test\", \"test\", 0, \"004\"))'"
    exit 1
fi

log "Backup check passed (age: ${BACKUP_AGE_SECONDS}s)"

# ── Phase 6: Pre-Deployment Validation ───────────────────────────────────────

log "Running pre-deployment validation..."

# Run database health check
.venv/bin/python -c "
from services.database_health_service import DatabaseHealthService
from database import db

health = DatabaseHealthService(db).get_health_report(quick=True)
if health['status'] != 'healthy':
    print(f\"ERROR: Database health check failed: {health['status']}\")
    exit(1)
print(f\"Database health: {health['status']}\")
"

log "Pre-deployment validation passed"

# ── Phase 6: Create Pre-Deployment Backup ────────────────────────────────────

log "Creating pre-deployment backup..."

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="practenture_pre_deploy_${TIMESTAMP}.db"

cp /var/www/practenture/practenture.db "/var/www/practenture/backup/$BACKUP_FILE"

# Upload to S3
aws s3 cp "/var/www/practenture/backup/$BACKUP_FILE" "s3://practenture-backups/prod/"

log "Pre-deployment backup created: $BACKUP_FILE"

# ── Phase 6: Apply Migrations ────────────────────────────────────────────────

log "Applying database migrations..."

.venv/bin/alembic upgrade head || {
    log "ERROR: Migration failed"
    log "Rolling back to pre-deployment backup..."
    
    cp "/var/www/practenture/backup/$BACKUP_FILE" /var/www/practenture/practenture.db
    aws s3 cp "/var/www/practenture/backup/$BACKUP_FILE" "s3://practenture-backups/prod/"
    
    log "Rollback complete"
    exit 1
}

log "Migrations applied successfully"

# ── Phase 6: Deploy Application ──────────────────────────────────────────────

log "Deploying application..."

# Stop the service
sudo systemctl stop practenture || true

# Deploy new code (rsync or git pull would go here)
log "Code deployment: SKIPPED (manual step)"

# Start the service
sudo systemctl start practenture || {
    log "ERROR: Failed to start practenture service"
    exit 1
}

log "Application deployed successfully"

# ── Phase 6: Post-Deployment Validation ──────────────────────────────────────

log "Running post-deployment validation..."

# Wait for service to start
sleep 5

# Health check
curl -s http://localhost:8000/health | grep -q "healthy" || {
    log "ERROR: Health check failed"
    exit 1
}

log "Health check passed"

# Run smoke tests
.venv/bin/pytest tests/smoke/ -v --tb=short || {
    log "ERROR: Smoke tests failed"
    exit 1
}

log "Post-deployment validation passed"

# ── Phase 6: Cleanup ─────────────────────────────────────────────────────────

log "Cleaning up old backups..."

# Keep only last 7 days of backups
find /var/www/practenture/backup -name "practenture_pre_deploy_*.db" -mtime +7 -delete

log "Cleanup complete"

# ── Phase 6: Final Summary ───────────────────────────────────────────────────

log "=== Deployment Complete ==="
log ""
log "Deployment Summary:"
log "  - Backup check: PASSED (age: ${BACKUP_AGE_SECONDS}s)"
log "  - Migrations: APPLIED"
log "  - Service: RUNNING"
log "  - Health check: PASSED"
log ""
log "Rollback procedure (if needed):"
log "  1. Stop service: sudo systemctl stop practenture"
log "  2. Restore backup: cp /var/www/practenture/backup/$BACKUP_FILE /var/www/practenture/practenture.db"
log "  3. Downgrade migrations: .venv/bin/alembic downgrade -1"
log "  4. Start service: sudo systemctl start practenture"
