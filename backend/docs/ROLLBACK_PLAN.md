# Practenture Rollback Plan

## Overview
This document outlines the rollback procedures for Practenture deployments. All deployments must be backup-gated and include a documented rollback plan.

## Prerequisites

### Before Any Deployment
1. Create a pre-deployment backup
2. Verify backup integrity
3. Document current migration version
4. Test rollback procedure in staging

### Required Tools
- AWS CLI (for S3 backup access)
- Alembic CLI (for database migrations)
- Systemd (for service management)

## Rollback Triggers

Rollback should be initiated if:
- Health check fails after deployment
- Smoke tests fail
- Critical errors appear in logs within 15 minutes
- Users report functionality issues

## Rollback Procedures

### Database Rollback

#### Step 1: Stop the Service
```bash
sudo systemctl stop practenture
```

#### Step 2: Restore Database from Backup
```bash
# List available backups
aws s3 ls s3://practenture-backups/prod/

# Download latest backup
aws s3 cp s3://practenture-backups/prod/practenture_pre_deploy_YYYYMMDD_HHMMSS.db /var/www/practenture/backup/

# Restore the database
cp /var/www/practenture/backup/practenture_pre_deploy_YYYYMMDD_HHMMSS.db /var/www/practenture/practenture.db
```

#### Step 3: Downgrade Migrations
```bash
cd /var/www/practenture/backend

# Check current migration version
.venv/bin/alembic current

# Downgrade by one migration (or more if needed)
.venv/bin/alembic downgrade -1

# Verify downgrade
.venv/bin/alembic current
```

#### Step 4: Restart Service
```bash
sudo systemctl start practenture
```

### Full Rollback (if needed)

If the database restore alone doesn't resolve issues:

```bash
# 1. Stop service
sudo systemctl stop practenture

# 2. Restore database (see above)

# 3. Downgrade migrations to pre-deployment version
.venv/bin/alembic downgrade <pre_deployment_version>

# 4. Restart service
sudo systemctl start practenture

# 5. Verify health
curl http://localhost:8000/health
```

## Rollback Verification

After rollback, verify:
1. Service is running: `sudo systemctl status practenture`
2. Health check passes: `curl http://localhost:8000/health`
3. Database integrity: `.venv/bin/python -c "from services.database_health_service import DatabaseHealthService; from database import db; print(DatabaseHealthService(db).get_health_report())"`
4. Critical endpoints work: Test login, session creation

## Post-Rollback Actions

1. **Investigate Root Cause**
   - Review deployment logs
   - Check application logs: `tail -f /var/log/practenture/app.log`
   - Review database migration logs

2. **Document Incident**
   - Record what went wrong
   - Document rollback steps taken
   - Note any data loss or corruption

3. **Create Follow-up Plan**
   - Fix the underlying issue
   - Update tests to catch similar issues
   - Consider additional validation steps

## Emergency Rollback (Zero Downtime)

For critical production issues:

```bash
# 1. Immediately stop accepting traffic
sudo systemctl stop practenture

# 2. Restore from backup (see above)

# 3. Downgrade migrations

# 4. Restart service
sudo systemctl start practenture

# 5. Verify and notify stakeholders
curl http://localhost:8000/health
```

## Prevention

### Best Practices
1. Always run migrations in staging first
2. Keep rollback backups for at least 7 days
3. Test rollback procedure monthly
4. Monitor deployment health closely for 15 minutes after deploy

### Automated Checks
- Pre-deployment: Backup age < 1 hour
- Post-deployment: Health check within 5 minutes
- Continuous: Error rate monitoring

## Contact

For deployment issues:
- DevOps Team: devops@practenture.com
- On-call Engineer: +1-555-DEPLOY

## Revision History

| Version | Date | Changes |
|---------|------|---------|
| 1.0 | 2026-07-25 | Initial rollback plan |
