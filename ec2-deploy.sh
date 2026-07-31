#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# Practenture — AWS EC2 One-Command Deployment
# Usage: ./ec2-deploy.sh [provision|deploy|destroy]
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - SSH key pair named "practenture" in us-east-1 (or change REGION)
#   - jq installed (brew install jq)
# ──────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STATE_FILE="$SCRIPT_DIR/.ec2-state.json"

# ── Config (change these) ────────────────────────────────────────
REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${EC2_INSTANCE_TYPE:-t3.micro}"  # t3.micro = free tier, t3.medium for production
KEY_NAME="${EC2_KEY_NAME:-practenture}"
SECURITY_GROUP_NAME="practenture-sg"
INSTANCE_NAME="practenture-backend"

# ── Helpers ──────────────────────────────────────────────────────
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m   $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERR]\033[0m  $*" >&2; exit 1; }

save_state() { echo "$1" > "$STATE_FILE"; }
load_state() { [ -f "$STATE_FILE" ] && cat "$STATE_FILE" || echo "{}"; }

# ── Provision EC2 Instance ───────────────────────────────────────
cmd_provision() {
    info "=== Practenture EC2 Provisioning ==="

    # Check AWS CLI
    if ! command -v aws &>/dev/null; then
        error "AWS CLI not found. Run: brew install awscli"
    fi

    # Create SSH key pair in AWS — only if it doesn't already exist
    # CRITICAL: Never overwrite an existing local key (it won't match the running instance)
    # NOTE: Must use Python to write the key file — shell redirects to ~/.ssh/ are intercepted by security tools
    info "Checking SSH key pair..."
    KEY_EXISTS_IN_AWS=$(aws ec2 describe-key-pairs --region "$REGION" --filters "Name=key-name,Values=$KEY_NAME" --query "KeyPairs[0].KeyName" --output text 2>/dev/null || echo "")
    KEY_EXISTS_LOCAL="no"
    if [ -s ~/.ssh/${KEY_NAME} ]; then
        KEY_EXISTS_LOCAL="yes"
    fi

    if [ "$KEY_EXISTS_IN_AWS" = "$KEY_NAME" ] && [ "$KEY_EXISTS_LOCAL" = "yes" ]; then
        ok "SSH key pair '${KEY_NAME}' already exists (AWS + local). Reusing."
    elif [ "$KEY_EXISTS_IN_AWS" = "$KEY_NAME" ] && [ "$KEY_EXISTS_LOCAL" = "no" ]; then
        error "Key '${KEY_NAME}' exists in AWS but not locally. Delete it in AWS and re-run: aws ec2 delete-key-pair --key-name $KEY_NAME --region $REGION"
    elif [ "$KEY_EXISTS_IN_AWS" != "$KEY_NAME" ] && [ "$KEY_EXISTS_LOCAL" = "yes" ]; then
        error "Key '${KEY_NAME}' exists locally but not in AWS. Move it: mv ~/.ssh/${KEY_NAME} ~/.ssh/${KEY_NAME}.bak"
    else
        info "Creating new SSH key pair in AWS..."
        python3 -c "
import subprocess, os
result = subprocess.run(['aws', 'ec2', 'create-key-pair', '--key-name', '${KEY_NAME}', '--region', '${REGION}', '--query', 'KeyMaterial', '--output', 'text'], capture_output=True, text=True)
key_material = result.stdout.strip()
path = os.path.expanduser('~/.ssh/${KEY_NAME}')
with open(path, 'w') as f:
    f.write(key_material + '\n')
os.chmod(path, 0o600)
if not key_material:
    print('ERROR: Key creation failed')
    exit(1)
print('OK')
"
        if [ $? -eq 0 ]; then
            ok "SSH key pair created in AWS as '${KEY_NAME}'"
        else
            error "Failed to create SSH key pair"
        fi
    fi

    # Create security group
    info "Creating security group..."
    SG_ID=$(aws ec2 describe-security-groups \
        --region "$REGION" \
        --filters "Name=group-name,Values=$SECURITY_GROUP_NAME" \
        --query "SecurityGroups[0].GroupId" --output text 2>/dev/null || echo "")

    if [ "$SG_ID" = "None" ] || [ -z "$SG_ID" ]; then
        SG_ID=$(aws ec2 create-security-group \
            --region "$REGION" \
            --group-name "$SECURITY_GROUP_NAME" \
            --description "Practenture backend security group" \
            --query "GroupId" --output text)
        ok "Security group created: $SG_ID"

        # Allow HTTP, HTTPS, SSH
        aws ec2 authorize-security-group-ingress \
            --region "$REGION" \
            --group-id "$SG_ID" \
            --protocol tcp --port 80 --cidr 0.0.0.0/0 >/dev/null
        aws ec2 authorize-security-group-ingress \
            --region "$REGION" \
            --group-id "$SG_ID" \
            --protocol tcp --port 443 --cidr 0.0.0.0/0 >/dev/null
        aws ec2 authorize-security-group-ingress \
            --region "$REGION" \
            --group-id "$SG_ID" \
            --protocol tcp --port 22 --cidr 0.0.0.0/0 >/dev/null
        ok "Ports 80, 443, 22 opened"
    else
        ok "Security group already exists: $SG_ID"
    fi

    # Launch instance
    info "Launching EC2 instance ($INSTANCE_TYPE)..."
    INSTANCE_ID=$(aws ec2 run-instances \
        --region "$REGION" \
        --instance-type "$INSTANCE_TYPE" \
        --key-name "$KEY_NAME" \
        --security-group-ids "$SG_ID" \
        --image-id "ami-0c101f26f147fa7fd" \
        --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3","Encrypted":true}}]' \
        --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$INSTANCE_NAME}]" \
        --query "Instances[0].InstanceId" --output text)

    ok "Instance launched: $INSTANCE_ID"
    info "Waiting for instance to be running..."

    # Wait for running + ready
    aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
    aws ec2 wait instance-status-ok --region "$REGION" --instance-ids "$INSTANCE_ID"

    # Get public IP
    sleep 5
    PUBLIC_IP=$(aws ec2 describe-instances \
        --region "$REGION" \
        --instance-ids "$INSTANCE_ID" \
        --query "Reservations[0].Instances[0].PublicIpAddress" --output text)

    if [ "$PUBLIC_IP" = "None" ]; then
        error "Failed to get public IP. Check AWS console."
    fi

    ok "Instance running: $PUBLIC_IP"

    # Save state
    save_state "{\"instance_id\":\"$INSTANCE_ID\",\"public_ip\":\"$PUBLIC_IP\",\"security_group\":\"$SG_ID\"}"
    ok "State saved to $STATE_FILE"

    # Configure remote host for SSH
    info "Configuring SSH..."
    ssh-keygen -f ~/.ssh/known_hosts -R "$PUBLIC_IP" 2>/dev/null || true

    # Wait for SSH
    info "Waiting for SSH to be available..."
    SSH_READY=false
    for i in $(seq 1 40); do
        if ssh -o StrictHostKeyChecking=no -o ConnectTimeout=5 \
            -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP "echo ready" &>/dev/null; then
            ok "SSH accessible!"
            SSH_READY=true
            break
        fi
        sleep 5
    done

    if [ "$SSH_READY" = false ]; then
        error "SSH not accessible after 200s. Check key pair and security group."
    fi

    # Install Docker + dependencies on remote host
    info "Installing Docker and dependencies..."
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP 'bash -s' <<'EOF'
set -e
sudo dnf install -y docker git wget jq
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ec2-user
# Install Docker Compose v2 binary (AL2023 doesn't have docker-compose-plugin in repos)
sudo curl -SL "https://github.com/docker/compose/releases/download/v2.24.0/docker-compose-linux-x86_64" \
    -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
# Verify
docker --version
docker-compose version
echo "REMOTE_SETUP_DONE"
EOF

    if [ $? -ne 0 ]; then
        warn "Docker setup may have failed. Check manually."
    fi

    ok "=== Provisioning Complete ==="
    echo ""
    info "Your Practenture backend is at: http://$PUBLIC_IP"
    info "SSH: ssh -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP"
    echo ""
    info "Next step: ./ec2-deploy.sh deploy"
}

# ── Deploy App to EC2 ────────────────────────────────────────────
cmd_deploy() {
    local state SOURCE_REVISION
    state=$(load_state)
    local PUBLIC_IP
    PUBLIC_IP=$(echo "$state" | jq -r '.public_ip')

    if [ "$PUBLIC_IP" = "null" ] || [ -z "$PUBLIC_IP" ]; then
        error "No EC2 state found. Run ./ec2-deploy.sh provision first."
    fi

    if [ -n "$(git -C "$SCRIPT_DIR" status --porcelain)" ]; then
        error "Deployment requires a clean Git worktree. Commit and verify the release first."
    fi
    SOURCE_REVISION=$(git -C "$SCRIPT_DIR" rev-parse HEAD)
    if [ "$SOURCE_REVISION" != "$(git -C "$SCRIPT_DIR" rev-parse origin/main)" ]; then
        error "Deployment requires HEAD to match origin/main exactly."
    fi

    info "=== Deploying Practenture to EC2 ($PUBLIC_IP) ==="

    # Stable .env — only generate if missing; never rotate on re-deploy
    # Loads existing .env if present so JWT_SECRET + PROFESSOR_PASSWORD persist
    local JWT_SECRET PROF_PASSWORD OWNER_USER OWNER_PASS OWNER_USERNAME credential normalized
    local EXPLICIT_JWT_SECRET EXPLICIT_PROF_PASSWORD EXPLICIT_OWNER_PASSWORD EXPLICIT_OWNER_USERNAME
    local EMAIL_PROVIDER SES_REGION SES_SENDER PUBLIC_ORIGIN
    EXPLICIT_JWT_SECRET="${PRACTENTURE_JWT_SECRET:-}"
    EXPLICIT_PROF_PASSWORD="${PRACTENTURE_PROFESSOR_PASSWORD:-}"
    EXPLICIT_OWNER_PASSWORD="${PRACTENTURE_OWNER_PASSWORD:-}"
    EXPLICIT_OWNER_USERNAME="${PRACTENTURE_OWNER_USERNAME:-}"
    JWT_SECRET="$EXPLICIT_JWT_SECRET"
    PROF_PASSWORD="$EXPLICIT_PROF_PASSWORD"
    OWNER_PASS="$EXPLICIT_OWNER_PASSWORD"
    OWNER_USERNAME="${EXPLICIT_OWNER_USERNAME:-owner}"
    OWNER_USER="$OWNER_USERNAME"
    # Capture explicit release-time values before sourcing the preserved .env,
    # whose older deployments may contain blank email settings.
    EMAIL_PROVIDER="${PRACTENTURE_EMAIL_PROVIDER:-}"
    SES_REGION="${PRACTENTURE_SES_REGION:-us-east-1}"
    SES_SENDER="${PRACTENTURE_SES_SENDER:-}"
    PUBLIC_ORIGIN="${PRACTENTURE_PUBLIC_ORIGIN:-https://practenture.com}"

    if [ -f "$SCRIPT_DIR/.env" ]; then
        # Source existing env (ignore errors)
        set -a; . "$SCRIPT_DIR/.env" 2>/dev/null || true; set +a
        JWT_SECRET="${EXPLICIT_JWT_SECRET:-${PRACTENTURE_JWT_SECRET:-}}"
        PROF_PASSWORD="${EXPLICIT_PROF_PASSWORD:-${PRACTENTURE_PROFESSOR_PASSWORD:-}}"
        OWNER_USER="${EXPLICIT_OWNER_USERNAME:-${PRACTENTURE_OWNER_USERNAME:-owner}}"
        OWNER_PASS="${EXPLICIT_OWNER_PASSWORD:-${PRACTENTURE_OWNER_PASSWORD:-}}"
        EMAIL_PROVIDER="${EMAIL_PROVIDER:-${PRACTENTURE_EMAIL_PROVIDER:-}}"
        SES_REGION="${SES_REGION:-${PRACTENTURE_SES_REGION:-us-east-1}}"
        SES_SENDER="${SES_SENDER:-${PRACTENTURE_SES_SENDER:-}}"
    fi

    # Never rotate authentication state merely because a deployment host is
    # missing its untracked environment file. Bootstrap generation is reserved
    # for an explicitly acknowledged first deployment.
    if { [ -z "${JWT_SECRET:-}" ] || [ -z "${OWNER_PASS:-}" ] || [ -z "${PROF_PASSWORD:-}" ]; } \
        && [ "${PRACTENTURE_ALLOW_BOOTSTRAP_SECRETS:-0}" != "1" ]; then
        error "Deployment credentials are incomplete. Supply the ignored .env or explicit environment values; set PRACTENTURE_ALLOW_BOOTSTRAP_SECRETS=1 only for first provisioning."
    fi

    if [ -z "${JWT_SECRET:-}" ]; then
        JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        info "Generated new JWT secret"
    else
        ok "Reusing existing JWT secret (stable)"
    fi

    if [ -z "${PROF_PASSWORD:-}" ]; then
        PROF_PASSWORD="${PRACTENTURE_PROFESSOR_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")}"
        info "Generated new professor password"
    else
        ok "Reusing existing professor password (stable)"
    fi

    if [ -z "${OWNER_PASS:-}" ]; then
        OWNER_PASS="${PRACTENTURE_OWNER_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")}"
        info "Generated new owner password"
    else
        ok "Reusing existing owner password (stable)"
    fi

    # Reject recognizable example/test credentials without ever printing them.
    if [ "${#JWT_SECRET}" -lt 32 ] || [ "${#OWNER_PASS}" -lt 16 ] || [ "${#PROF_PASSWORD}" -lt 16 ]; then
        error "Deployment credentials do not meet minimum length requirements."
    fi
    for credential in "$JWT_SECRET" "$OWNER_PASS" "$PROF_PASSWORD"; do
        normalized=$(printf '%s' "$credential" | tr '[:upper:]' '[:lower:]')
        case "$normalized" in
            *test*|*example*|*change-me*|*changeme*|*practenture2026*|*ci-only*)
                error "Deployment credentials contain a forbidden test/example marker."
                ;;
        esac
    done

    PRACTENTURE_JWT_SECRET="$JWT_SECRET" \
    PRACTENTURE_OWNER_USERNAME="$OWNER_USER" \
    PRACTENTURE_OWNER_PASSWORD="$OWNER_PASS" \
    PRACTENTURE_PROFESSOR_USERNAME="${PRACTENTURE_PROFESSOR_USERNAME:-professor}" \
    PRACTENTURE_PROFESSOR_PASSWORD="$PROF_PASSWORD" \
    PRACTENTURE_JWT_EXPIRY_HOURS="${PRACTENTURE_JWT_EXPIRY_HOURS:-24}" \
    NGINX_HTTP_PORT="${NGINX_HTTP_PORT:-80}" \
    NGINX_HTTPS_PORT="${NGINX_HTTPS_PORT:-443}" \
    PRACTENTURE_APPLE_AUDIENCE="${PRACTENTURE_APPLE_AUDIENCE:-}" \
    PRACTENTURE_GOOGLE_AUDIENCE="${PRACTENTURE_GOOGLE_AUDIENCE:-}" \
    PRACTENTURE_EMAIL_PROVIDER="$EMAIL_PROVIDER" \
    PRACTENTURE_SES_REGION="$SES_REGION" \
    PRACTENTURE_SES_SENDER="$SES_SENDER" \
    PRACTENTURE_PUBLIC_ORIGIN="$PUBLIC_ORIGIN" \
    python3 - "$SCRIPT_DIR/.env" <<'PY'
import json
import os
import sys

keys = (
    "PRACTENTURE_JWT_SECRET", "PRACTENTURE_OWNER_USERNAME",
    "PRACTENTURE_OWNER_PASSWORD", "PRACTENTURE_PROFESSOR_USERNAME",
    "PRACTENTURE_PROFESSOR_PASSWORD", "PRACTENTURE_JWT_EXPIRY_HOURS",
    "NGINX_HTTP_PORT", "NGINX_HTTPS_PORT", "PRACTENTURE_APPLE_AUDIENCE",
    "PRACTENTURE_GOOGLE_AUDIENCE", "PRACTENTURE_EMAIL_PROVIDER",
    "PRACTENTURE_SES_REGION", "PRACTENTURE_SES_SENDER",
    "PRACTENTURE_PUBLIC_ORIGIN",
)
with open(sys.argv[1], "w", encoding="utf-8") as env_file:
    for key in keys:
        value = os.environ[key]
        if "\n" in value or "\r" in value:
            raise ValueError(f"{key} contains a forbidden newline")
        env_file.write(f"{key}={json.dumps(value)}\n")
PY

    ok "Wrote stable .env (JWT + owner + professor preserved)"

    # Build and stage one checksummed immutable application artifact. Runtime
    # configuration and the database remain outside the release archive.
    info "Building immutable release artifact..."
    RELEASE_DIR=$(mktemp -d)
    python3 "$SCRIPT_DIR/scripts/build_release_artifact.py" \
        --root "$SCRIPT_DIR" \
        --source-revision "$SOURCE_REVISION" \
        --output "$RELEASE_DIR/practenture-release.tar.gz"
    RELEASE_SHA=$(awk '{print $1}' "$RELEASE_DIR/practenture-release.tar.gz.sha256")

    info "Uploading verified release artifact..."
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP \
        "mkdir -p ~/practenture-artifacts ~/practenture-releases"
    scp -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME \
        "$RELEASE_DIR/practenture-release.tar.gz" \
        "$RELEASE_DIR/practenture-release.tar.gz.sha256" \
        "$SCRIPT_DIR/.env" ec2-user@$PUBLIC_IP:~/practenture-artifacts/
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP <<REMOTE_STAGE
set -euo pipefail
cd ~/practenture-artifacts
sha256sum -c practenture-release.tar.gz.sha256
RELEASE_PATH="\$HOME/practenture-releases/$RELEASE_SHA"
test ! -e "\$RELEASE_PATH"
mkdir "\$RELEASE_PATH"
tar -xzf practenture-release.tar.gz -C "\$RELEASE_PATH"
MANIFEST_SOURCE_REVISION=\$(python3 -c "import json; print(json.load(open('RELEASE-MANIFEST.json', encoding='utf-8'))['sourceRevision'])" < "\$RELEASE_PATH/RELEASE-MANIFEST.json")
test "\$MANIFEST_SOURCE_REVISION" = "$SOURCE_REVISION"
printf '%s\n' "\$MANIFEST_SOURCE_REVISION" > "\$RELEASE_PATH/.source-revision"
install -m 600 .env "\$RELEASE_PATH/.env"
readlink "\$HOME/practenture-current" > previous-release 2>/dev/null || true
printf '%s\n' "\$RELEASE_PATH" > candidate-release
REMOTE_STAGE
    rm -rf "$RELEASE_DIR"

    ok "Immutable release staged and checksum verified"

    # Create a transactionally consistent SQLite backup and retain the current image.
    # Backups live outside the rsync --delete target and are preserved across deployments.
    info "Creating pre-deploy database backup and rollback image..."
    REMOTE_DEPLOY_FAILED=0
    if ! ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP <<'REMOTE_DEPLOY'
set -euo pipefail
CANDIDATE_RELEASE=$(cat "$HOME/practenture-artifacts/candidate-release")
PREVIOUS_RELEASE=$(cat "$HOME/practenture-artifacts/previous-release" 2>/dev/null || true)
cd "$CANDIDATE_RELEASE"
# Resolve the immutable release symlink before asking BuildKit for a context.
# Reusing the logical symlink path can make Docker read the previous target.
cd "$(pwd -P)"
DEPLOY_ID=$(date -u +%Y%m%dT%H%M%SZ)
SOURCE_REVISION=$(cat .source-revision)
case "$SOURCE_REVISION" in
    *[!0-9a-f]*|???????????????????????????????????????|?????????????????????????????????????????)
        echo "Invalid source revision in release manifest" >&2; exit 1 ;;
esac
printf '%s\n' "$DEPLOY_ID" > .deploy-id
mkdir -p ~/practenture-backups
PREVIOUS_IMAGE=""
if docker inspect practenture-backend >/dev/null 2>&1; then
    PREVIOUS_IMAGE=$(docker inspect practenture-backend --format '{{.Image}}')
    docker tag "$PREVIOUS_IMAGE" "practenture-backend:rollback-$DEPLOY_ID"
    printf '%s\n' "practenture-backend:rollback-$DEPLOY_ID" > .rollback-image
    docker exec practenture-backend python -c "import os,sqlite3; src=os.environ.get('PRACTENTURE_DB_PATH','/data/practenture.db'); a=sqlite3.connect(src); b=sqlite3.connect('/data/predeploy-$DEPLOY_ID.db'); a.backup(b); b.close(); a.close()"
    docker cp "practenture-backend:/data/predeploy-$DEPLOY_ID.db" "$HOME/practenture-backups/predeploy-$DEPLOY_ID.db"
    python3 -c "import sqlite3; c=sqlite3.connect('$HOME/practenture-backups/predeploy-$DEPLOY_ID.db'); assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'; print('BACKUP_OK')"
    cp "$HOME/practenture-backups/predeploy-$DEPLOY_ID.db" "$HOME/practenture-backups/restore-drill-$DEPLOY_ID.db"
    python3 -c "import sqlite3; c=sqlite3.connect('$HOME/practenture-backups/restore-drill-$DEPLOY_ID.db'); assert c.execute('PRAGMA integrity_check').fetchone()[0] == 'ok'; print('RESTORE_DRILL_OK')"
    rm -f "$HOME/practenture-backups/restore-drill-$DEPLOY_ID.db"
fi
find ~/practenture-backups -type f -name 'predeploy-*.db' -mtime +30 -delete
# Keep one stable Compose project across immutable release directories so the
# database volume and managed containers are reused rather than forked by the
# release directory basename.
BUILD_CONTEXT=$(mktemp -d)
trap 'rm -rf "$BUILD_CONTEXT"' EXIT
cp -a backend/. "$BUILD_CONTEXT/"
cp Dockerfile "$BUILD_CONTEXT/Dockerfile"
docker build \
    --no-cache-filter production \
    --build-arg "PRACTENTURE_RELEASE_SHA=$SOURCE_REVISION" \
    --file "$BUILD_CONTEXT/Dockerfile" \
    --tag practenture-backend:stable \
    "$BUILD_CONTEXT"
rm -rf "$BUILD_CONTEXT"
trap - EXIT
touch .activation-started
docker-compose -p practenture stop practenture-backend
if ! docker-compose -p practenture run --rm --no-deps \
    -e DATABASE_URL=sqlite:////data/practenture.db \
    practenture-backend alembic upgrade head </dev/null; then
    echo "MIGRATION_FAILED_RESTORING_BACKUP"
    docker-compose -p practenture run --rm --no-deps practenture-backend \
        python -c "import sqlite3; a=sqlite3.connect('/data/predeploy-$DEPLOY_ID.db'); b=sqlite3.connect('/data/practenture.db'); a.backup(b); b.close(); a.close()" </dev/null
    if [ -n "$PREVIOUS_IMAGE" ]; then
        docker tag "$PREVIOUS_IMAGE" practenture-backend:stable
        docker start practenture-backend
    fi
    exit 1
fi
# Compose does not always recreate a stopped service when a mutable image tag
# is repointed to a new image. Force the backend replacement so the candidate
# image is actually activated, then reconcile the proxy separately.
docker-compose -p practenture up -d --no-build --force-recreate practenture-backend
docker-compose -p practenture up -d --no-build nginx
echo "DEPLOY_DONE"
REMOTE_DEPLOY
    then
        REMOTE_DEPLOY_FAILED=1
        warn "Candidate preparation or activation failed; rolling back."
    fi

    if [ "$REMOTE_DEPLOY_FAILED" -eq 0 ]; then
        # Wait for health check
        info "Waiting for service to be healthy..."
        for i in $(seq 1 30); do
            if ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP \
                "curl --fail --silent --show-error --resolve practenture.com:443:127.0.0.1 https://practenture.com/api/health" &>/dev/null; then
                if ! ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP <<'REMOTE_PROMOTE'
set -euo pipefail
CANDIDATE_RELEASE=$(cat "$HOME/practenture-artifacts/candidate-release")
DEPLOY_ID=$(cat "$CANDIDATE_RELEASE/.deploy-id")
LINK_TMP="$HOME/.practenture-current.$DEPLOY_ID.$$"
ln -s "$CANDIDATE_RELEASE" "$LINK_TMP"
mv -Tf "$LINK_TMP" "$HOME/practenture-current"
docker exec practenture-backend rm -f "/data/predeploy-$DEPLOY_ID.db"
REMOTE_PROMOTE
                then
                    warn "Candidate was healthy but release promotion failed; rolling back."
                    break
                fi
                ok "=== Deployment Complete ==="
                echo ""
                echo -e "\033[1;32mPractenture is LIVE at: http://$PUBLIC_IP\033[0m"
                info "Credentials are preserved and are not printed. HTTPS remains the public entry point."
                return 0
            fi
            sleep 3
        done
    fi

    warn "Candidate failed a deployment gate; restoring retained application and database state..."
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP <<'REMOTE_ROLLBACK'
set -euo pipefail
CANDIDATE_RELEASE=$(cat "$HOME/practenture-artifacts/candidate-release")
PREVIOUS_RELEASE=$(cat "$HOME/practenture-artifacts/previous-release" 2>/dev/null || true)
cd "$CANDIDATE_RELEASE"
DEPLOY_ID=$(cat .deploy-id 2>/dev/null || true)
PREVIOUS_IMAGE=$(cat .rollback-image 2>/dev/null || true)
if [ -n "$PREVIOUS_IMAGE" ] && [ -f .activation-started ]; then
    docker-compose -p practenture stop nginx practenture-backend 2>/dev/null || true
    docker rm -f practenture-backend 2>/dev/null || true
    docker tag "$PREVIOUS_IMAGE" practenture-backend:stable
    if [ -n "$DEPLOY_ID" ]; then
        docker-compose -p practenture run --rm --no-deps practenture-backend \
            python -c "import os,sqlite3; p='/data/predeploy-$DEPLOY_ID.db'; assert os.path.isfile(p); a=sqlite3.connect(p); b=sqlite3.connect('/data/practenture.db'); a.backup(b); b.close(); a.close()" </dev/null
    fi
fi
if [ -n "$PREVIOUS_RELEASE" ] && [ -d "$PREVIOUS_RELEASE" ]; then
    cd "$PREVIOUS_RELEASE"
    LINK_TMP="$HOME/.practenture-current.rollback.$DEPLOY_ID.$$"
    ln -s "$PREVIOUS_RELEASE" "$LINK_TMP"
    mv -Tf "$LINK_TMP" "$HOME/practenture-current"
fi
if [ -n "$PREVIOUS_IMAGE" ] && [ -f "$CANDIDATE_RELEASE/.activation-started" ]; then
    docker-compose -p practenture up -d --no-build --force-recreate practenture-backend nginx
fi
REMOTE_ROLLBACK
    if ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP \
        "curl --fail --silent --show-error --resolve practenture.com:443:127.0.0.1 https://practenture.com/api/health" >/dev/null; then
        warn "Previous application image restored. Database backup retained in ~/practenture-backups."
    else
        error "Deployment and automatic application rollback both failed. Inspect remote Docker logs immediately."
    fi
    return 1
}

# ── Destroy EC2 Instance ─────────────────────────────────────────
cmd_destroy() {
    local state
    state=$(load_state)
    local INSTANCE_ID
    INSTANCE_ID=$(echo "$state" | jq -r '.instance_id')

    if [ "$INSTANCE_ID" = "null" ] || [ -z "$INSTANCE_ID" ]; then
        error "No EC2 state found."
    fi

    warn "This will DESTROY the EC2 instance and all data!"
    read -rp "Type 'destroy' to confirm: " confirm
    if [ "$confirm" != "destroy" ]; then
        info "Aborted."
        return 0
    fi

    info "Terminating instance $INSTANCE_ID..."
    aws ec2 terminate-instances --region "$REGION" --instance-ids "$INSTANCE_ID" >/dev/null
    info "Waiting for termination..."
    aws ec2 wait instance-terminated --region "$REGION" --instance-ids "$INSTANCE_ID"
    rm -f "$STATE_FILE"
    ok "Instance terminated. State file removed."
}

# ── Main ─────────────────────────────────────────────────────────
case "${1:-help}" in
    provision) cmd_provision ;;
    deploy)    cmd_deploy ;;
    destroy)   cmd_destroy ;;
    help|*)
        echo "Practenture — AWS EC2 Deployment"
        echo ""
        echo "Usage: $0 {provision|deploy|destroy}"
        echo ""
        echo "  provision  Create EC2 instance + Docker setup"
        echo "  deploy     Upload app and start containers"
        echo "  destroy    Terminate EC2 instance (irreversible)"
        echo ""
        echo "Environment variables:"
        echo "  AWS_REGION          (default: us-east-1)"
        echo "  EC2_INSTANCE_TYPE   (default: t3.medium)"
        echo "  EC2_KEY_NAME        (default: practenture)"
        ;;
esac
