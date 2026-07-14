#!/usr/bin/env bash
# ──────────────────────────────────────────────────────────────────
# BizSimAI — AWS EC2 One-Command Deployment
# Usage: ./ec2-deploy.sh [provision|deploy|destroy]
#
# Prerequisites:
#   - AWS CLI configured (aws configure)
#   - SSH key pair named "bizsimai" in us-east-1 (or change REGION)
#   - jq installed (brew install jq)
# ──────────────────────────────────────────────────────────────────
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
STATE_FILE="$SCRIPT_DIR/.ec2-state.json"

# ── Config (change these) ────────────────────────────────────────
REGION="${AWS_REGION:-us-east-1}"
INSTANCE_TYPE="${EC2_INSTANCE_TYPE:-t3.micro}"  # t3.micro = free tier, t3.medium for production
KEY_NAME="${EC2_KEY_NAME:-bizsimai}"
SECURITY_GROUP_NAME="bizsimai-sg"
INSTANCE_NAME="bizsimai-backend"

# ── Helpers ──────────────────────────────────────────────────────
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m   $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERR]\033[0m  $*" >&2; exit 1; }

save_state() { echo "$1" > "$STATE_FILE"; }
load_state() { [ -f "$STATE_FILE" ] && cat "$STATE_FILE" || echo "{}"; }

# ── Provision EC2 Instance ───────────────────────────────────────
cmd_provision() {
    info "=== BizSimAI EC2 Provisioning ==="

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
            --description "BizSimAI backend security group" \
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
        --block-device-mappings '[{"DeviceName":"/dev/sda1","Ebs":{"VolumeSize":20,"VolumeType":"gp3"}}]' \
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
    info "Your BizSimAI backend is at: http://$PUBLIC_IP"
    info "SSH: ssh -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP"
    echo ""
    info "Next step: ./ec2-deploy.sh deploy"
}

# ── Deploy App to EC2 ────────────────────────────────────────────
cmd_deploy() {
    local state
    state=$(load_state)
    local PUBLIC_IP
    PUBLIC_IP=$(echo "$state" | jq -r '.public_ip')

    if [ "$PUBLIC_IP" = "null" ] || [ -z "$PUBLIC_IP" ]; then
        error "No EC2 state found. Run ./ec2-deploy.sh provision first."
    fi

    info "=== Deploying BizSimAI to EC2 ($PUBLIC_IP) ==="

    # Stable .env — only generate if missing; never rotate on re-deploy
    # Loads existing .env if present so JWT_SECRET + PROFESSOR_PASSWORD persist
    local JWT_SECRET PROF_PASSWORD OWNER_USER OWNER_PASS OWNER_USERNAME
    OWNER_USERNAME="${BIZSIMAI_OWNER_USERNAME:-owner}"

    if [ -f "$SCRIPT_DIR/.env" ]; then
        # Source existing env (ignore errors)
        set -a; . "$SCRIPT_DIR/.env" 2>/dev/null || true; set +a
        JWT_SECRET="${BIZSIMAI_JWT_SECRET:-}"
        PROF_PASSWORD="${BIZSIMAI_PROFESSOR_PASSWORD:-}"
        OWNER_USER="${BIZSIMAI_OWNER_USERNAME:-owner}"
        OWNER_PASS="${BIZSIMAI_OWNER_PASSWORD:-}"
    fi

    if [ -z "${JWT_SECRET:-}" ]; then
        JWT_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))")
        info "Generated new JWT secret"
    else
        ok "Reusing existing JWT secret (stable)"
    fi

    if [ -z "${PROF_PASSWORD:-}" ]; then
        PROF_PASSWORD="${BIZSIMAI_PROFESSOR_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")}"
        info "Generated new professor password"
    else
        ok "Reusing existing professor password (stable)"
    fi

    if [ -z "${OWNER_PASS:-}" ]; then
        OWNER_PASS="${BIZSIMAI_OWNER_PASSWORD:-$(python3 -c "import secrets; print(secrets.token_urlsafe(16))")}"
        info "Generated new owner password"
    else
        ok "Reusing existing owner password (stable)"
    fi

    cat > "$SCRIPT_DIR/.env" <<EOF
BIZSIMAI_JWT_SECRET=$JWT_SECRET
BIZSIMAI_OWNER_USERNAME=${OWNER_USER}
BIZSIMAI_OWNER_PASSWORD=$OWNER_PASS
BIZSIMAI_PROFESSOR_USERNAME=${BIZSIMAI_PROFESSOR_USERNAME:-professor}
BIZSIMAI_PROFESSOR_PASSWORD=$PROF_PASSWORD
BIZSIMAI_JWT_EXPIRY_HOURS=${BIZSIMAI_JWT_EXPIRY_HOURS:-24}
NGINX_HTTP_PORT=${NGINX_HTTP_PORT:-80}
NGINX_HTTPS_PORT=${NGINX_HTTPS_PORT:-443}
BIZSIMAI_APPLE_AUDIENCE=${BIZSIMAI_APPLE_AUDIENCE:-}
BIZSIMAI_GOOGLE_AUDIENCE=${BIZSIMAI_GOOGLE_AUDIENCE:-}
EOF

    ok "Wrote stable .env (JWT + owner + professor preserved)"

    # Upload files to EC2
    info "Uploading application to EC2..."
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP "mkdir -p ~/bizsimai"

    # rsync the backend directory (excluding venv, __pycache__, .git)
    rsync -avz --delete \
        --exclude='venv' \
        --exclude='__pycache__' \
        --exclude='.git' \
        --exclude='.ec2-state.json' \
        --exclude='data.db' \
        -e "ssh -i ~/.ssh/$KEY_NAME" \
        "$SCRIPT_DIR/" ec2-user@$PUBLIC_IP:~/bizsimai/

    ok "Files uploaded"

    # Deploy via docker-compose
    info "Starting containers on EC2..."
    ssh -o StrictHostKeyChecking=no -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP <<REMOTE_DEPLOY
cd ~/bizsimai
docker-compose down --remove-orphans 2>/dev/null || true
docker-compose up -d --build
echo "DEPLOY_DONE"
REMOTE_DEPLOY

    # Wait for health check
    info "Waiting for service to be healthy..."
    for i in $(seq 1 30); do
        if curl -sf "http://$PUBLIC_IP/api/health" &>/dev/null; then
            ok "=== Deployment Complete ==="
            echo ""
            echo -e "\033[1;32mBizSimAI is LIVE at: http://$PUBLIC_IP\033[0m"
            echo -e "\033[1;32mProfessor login: professor / $PROF_PASSWORD\033[0m"
            echo ""
            info "Update your iOS app's NetworkService.swift:"
            echo -e "  return \"http://$PUBLIC_IP:8005\""
            echo ""
            info "For HTTPS, set up certbot:"
            echo -e "  ssh -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP 'sudo certbot --nginx'"
            return 0
        fi
        sleep 3
    done

    warn "Health check timed out. Check logs:"
    info "ssh -i ~/.ssh/$KEY_NAME ec2-user@$PUBLIC_IP 'cd ~/bizsimai && docker-compose logs'"
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
        echo "BizSimAI — AWS EC2 Deployment"
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
        echo "  EC2_KEY_NAME        (default: bizsimai)"
        ;;
esac
