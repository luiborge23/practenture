#!/bin/bash

# Staging Environment Provisioning Script
# This script provisions an isolated staging environment for Practenture

set -e

echo "=== Provisioning Staging Environment ==="

# Configuration
STAGING_DIR="/var/www/practenture-staging"
AWS_REGION="us-east-1"
S3_BUCKET="practenture-backups-staging"

# Create staging directory structure
echo "Creating staging directory structure..."
mkdir -p "$STAGING_DIR"
mkdir -p "$STAGING_DIR/logs"
mkdir -p "$STAGING_DIR/backup"
mkdir -p "$STAGING_DIR/config"

# Create isolated database
echo "Creating isolated staging database..."
sqlite3 "$STAGING_DIR/practenture_staging.db" <<EOF
-- Create the database schema
.schema
EOF

# Copy configuration template
echo "Copying configuration..."
cat > "$STAGING_DIR/config/.env" <<EOF
# Staging Environment Configuration

# Database
DATABASE_URL=sqlite+aiosqlite:///$STAGING_DIR/practenture_staging.db

# JWT
PRACTENTURE_JWT_SECRET=staging-jwt-secret-change-in-production

# AWS (for backups)
AWS_ACCESS_KEY_ID=staging-access-key
AWS_SECRET_ACCESS_KEY=staging-secret-key
AWS_REGION=$AWS_REGION

# S3 Backup Bucket
BACKUP_S3_BUCKET=$S3_BUCKET

# Environment
ENVIRONMENT=staging
DEBUG=true
EOF

# Create nginx configuration for staging
echo "Creating nginx configuration..."
cat > "/etc/nginx/sites-available/practenture-staging" <<'EOF'
# Staging Environment Nginx Configuration

server {
    listen 80;
    server_name staging.practenture.com;

    # Access and error logs
    access_log /var/log/nginx/practenture-staging-access.log;
    error_log /var/log/nginx/practenture-staging-error.log;

    # Static files
    location /static/ {
        alias /var/www/practenture-staging/static/;
        expires 30d;
        add_header Cache-Control "public, immutable";
    }

    # API proxy
    location /api/ {
        proxy_pass http://127.0.0.1:8001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }

    # Owner console
    location /owner/ {
        alias /var/www/practenture-staging/templates/;
        index owner_dashboard.html;
    }

    # Health check
    location /health {
        access_log off;
        return 200 "healthy\n";
        add_header Content-Type text/plain;
    }
}
EOF

# Create systemd service for staging
echo "Creating systemd service..."
cat > "/etc/systemd/system/practenture-staging.service" <<'EOF'
[Unit]
Description=Practenture Staging Server
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/var/www/practenture-staging
Environment="PATH=/var/www/practenture-staging/.venv/bin"
ExecStart=/var/www/practenture-staging/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8001
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create backup script for staging
echo "Creating backup script..."
cat > "$STAGING_DIR/backup.sh" <<'EOF'
#!/bin/bash

# Staging Backup Script
set -e

BACKUP_DIR="/var/www/practenture-staging/backup"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="practenture_staging_${TIMESTAMP}.db"
S3_BUCKET="practenture-backups-staging"

# Create backup
cp /var/www/practenture-staging/practenture_staging.db "$BACKUP_DIR/$BACKUP_FILE"

# Upload to S3
aws s3 cp "$BACKUP_DIR/$BACKUP_FILE" "s3://$S3_BUCKET/staging/"

# Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "practenture_staging_*.db" -mtime +7 -delete

echo "Backup completed: $BACKUP_FILE"
EOF

chmod +x "$STAGING_DIR/backup.sh"

# Create restore script for staging
echo "Creating restore script..."
cat > "$STAGING_DIR/restore.sh" <<'EOF'
#!/bin/bash

# Staging Restore Script
set -e

BACKUP_FILE="$1"
S3_BUCKET="practenture-backups-staging"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: $0 <backup_file>"
    exit 1
fi

# Download from S3
aws s3 cp "s3://$S3_BUCKET/staging/$BACKUP_FILE" "/var/www/practenture-staging/backup/"

# Restore database
cp "/var/www/practenture-staging/backup/$BACKUP_FILE" /var/www/practenture-staging/practenture_staging.db

echo "Restore completed: $BACKUP_FILE"
EOF

chmod +x "$STAGING_DIR/restore.sh"

# Create restore drill script
echo "Creating restore drill script..."
cat > "$STAGING_DIR/restore_drill.sh" <<'EOF'
#!/bin/bash

# Staging Restore Drill Script
set -e

DRILL_DIR="/var/www/practenture-staging/drill"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DRILL_DB="$DRILL_DIR/practenture_drill_${TIMESTAMP}.db"

# Create drill directory
mkdir -p "$DRILL_DIR"

# Get latest backup
LATEST_BACKUP=$(aws s3 ls "s3://$S3_BUCKET/staging/" | sort | tail -1 | awk '{print $4}')

if [ -z "$LATEST_BACKUP" ]; then
    echo "No backups found"
    exit 1
fi

echo "Restoring latest backup for drill: $LATEST_BACKUP"

# Download and restore
aws s3 cp "s3://$S3_BUCKET/staging/$LATEST_BACKUP" "$DRILL_DIR/"
cp "$DRILL_DIR/$LATEST_BACKUP" "$DRILL_DB"

# Run integrity check
sqlite3 "$DRILL_DB" "PRAGMA integrity_check;"

echo "Restore drill completed: $LATEST_BACKUP"
EOF

chmod +x "$STAGING_DIR/restore_drill.sh"

# Create cleanup script for staging
echo "Creating cleanup script..."
cat > "$STAGING_DIR/cleanup.sh" <<'EOF'
#!/bin/bash

# Staging Cleanup Script
set -e

DRILL_DIR="/var/www/practenture-staging/drill"
BACKUP_DIR="/var/www/practenture-staging/backup"

# Clean up old drill databases (keep last 30 days)
find "$DRILL_DIR" -name "practenture_drill_*.db" -mtime +30 -delete

# Clean up old backups (keep last 7 days)
find "$BACKUP_DIR" -name "practenture_staging_*.db" -mtime +7 -delete

echo "Cleanup completed"
EOF

chmod +x "$STAGING_DIR/cleanup.sh"

# Create README for staging
echo "Creating documentation..."
cat > "$STAGING_DIR/README.md" <<'EOF'
# Practenture Staging Environment

## Overview
This is an isolated staging environment for Practenture, used for testing changes before deploying to production.

## Directory Structure
- `/var/www/practenture-staging/` - Main staging directory
- `/var/www/practenture-staging/logs/` - Application logs
- `/var/www/practenture-staging/backup/` - Database backups
- `/var/www/practenture-staging/config/` - Configuration files

## Access
- Staging URL: https://staging.practenture.com
- Owner Console: https://staging.practenture.com/owner/

## Backup Management

### Create a backup
```bash
/var/www/practenture-staging/backup.sh
```

### Restore from backup
```bash
/var/www/practenture-staging/restore.sh <backup_file>
```

### Run restore drill
```bash
/var/www/practenture-staging/restore_drill.sh
```

### Cleanup old files
```bash
/var/www/practenture-staging/cleanup.sh
```

## Maintenance

### View logs
```bash
tail -f /var/log/nginx/practenture-staging-access.log
tail -f /var/log/nginx/practenture-staging-error.log
```

### Restart service
```bash
sudo systemctl restart practenture-staging
```

### Check status
```bash
curl http://localhost:8001/health
```

## Security Notes
- This is an isolated environment - credentials are different from production
- Backups are stored in S3 with versioning enabled
- All access is logged and audited

## Contact
For issues, contact the DevOps team.
EOF

echo "=== Staging Environment Provisioning Complete ==="
echo ""
echo "Next steps:"
echo "1. Enable the nginx site: sudo ln -s /etc/nginx/sites-available/practenture-staging /etc/nginx/sites-enabled/"
echo "2. Test nginx config: sudo nginx -t"
echo "3. Reload nginx: sudo systemctl reload nginx"
echo "4. Start staging service: sudo systemctl start practenture-staging"
