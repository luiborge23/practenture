#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="practenture-certbot-renew.service"
TIMER_NAME="practenture-certbot-renew.timer"
HOOK_PATH="/etc/letsencrypt/renewal-hooks/deploy/practenture-nginx-reload"
SYSTEMD_DIR="/etc/systemd/system"
WEBROOT_PATH="/var/www/certbot"
ROLLBACK_DIR=${PRACTENTURE_TLS_ROLLBACK_DIR:-}

if [ "${EUID}" -ne 0 ]; then
    exec sudo env PRACTENTURE_TLS_ROLLBACK_DIR="$ROLLBACK_DIR" "$0" "$@"
fi

if [ -n "$ROLLBACK_DIR" ]; then
    if [ "$(dirname -- "$ROLLBACK_DIR")" != "/var/lib/practenture-deploy" ] \
        || [[ "$(basename -- "$ROLLBACK_DIR")" != tls-rollback-* ]] \
        || [[ "$(basename -- "$ROLLBACK_DIR")" == *[!A-Za-z0-9._-]* ]]; then
        echo "PRACTENTURE_TLS_ROLLBACK_DIR is outside the protected deployment state directory" >&2
        exit 2
    fi
    if [ -e "$ROLLBACK_DIR" ]; then
        echo "TLS rollback snapshot already exists: $ROLLBACK_DIR" >&2
        exit 2
    fi
fi

CERTBOT_BIN=$(command -v certbot || true)
DOCKER_BIN=$(command -v docker || true)
if [ -z "$CERTBOT_BIN" ]; then
    echo "certbot is required before TLS renewal can be configured" >&2
    exit 1
fi
if [ -z "$DOCKER_BIN" ]; then
    echo "docker is required before TLS renewal can be configured" >&2
    exit 1
fi

shopt -s nullglob
renewal_configs=(/etc/letsencrypt/renewal/*.conf)
shopt -u nullglob
if [ "${#renewal_configs[@]}" -eq 0 ]; then
    echo "no Let's Encrypt renewal configurations were found" >&2
    exit 1
fi

work_dir=$(mktemp -d)
service_existed=0
timer_existed=0
hook_existed=0
timer_was_enabled=0
timer_was_active=0
restore_on_error=0
snapshot_created=0
snapshot_staging=""

cleanup() {
    rc=$?
    restore_failed=0
    if [ "$rc" -ne 0 ] && [ "$restore_on_error" -eq 1 ]; then
        set +e
        if [ -f "$SYSTEMD_DIR/$TIMER_NAME" ]; then
            systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1 || restore_failed=1
        fi
        if [ "$restore_failed" -eq 0 ]; then
            if [ "$service_existed" -eq 1 ]; then
                install -m 644 "$work_dir/previous-service" "$SYSTEMD_DIR/$SERVICE_NAME" || restore_failed=1
            else
                rm -f "$SYSTEMD_DIR/$SERVICE_NAME" || restore_failed=1
            fi
            if [ "$timer_existed" -eq 1 ]; then
                install -m 644 "$work_dir/previous-timer" "$SYSTEMD_DIR/$TIMER_NAME" || restore_failed=1
            else
                rm -f "$SYSTEMD_DIR/$TIMER_NAME" || restore_failed=1
            fi
            if [ "$hook_existed" -eq 1 ]; then
                install -m 755 "$work_dir/previous-hook" "$HOOK_PATH" || restore_failed=1
            else
                rm -f "$HOOK_PATH" || restore_failed=1
            fi
            for renewal_config in "$work_dir"/previous-renewal-configs/*.conf; do
                install -m 600 "$renewal_config" "/etc/letsencrypt/renewal/$(basename -- "$renewal_config")" \
                    || restore_failed=1
            done
            systemctl daemon-reload || restore_failed=1
            if [ "$timer_existed" -eq 1 ]; then
                if [ "$timer_was_enabled" -eq 1 ]; then
                    systemctl enable "$TIMER_NAME" || restore_failed=1
                else
                    systemctl disable "$TIMER_NAME" >/dev/null 2>&1 || restore_failed=1
                fi
                if [ "$timer_was_active" -eq 1 ]; then
                    systemctl start "$TIMER_NAME" || restore_failed=1
                else
                    systemctl stop "$TIMER_NAME" >/dev/null 2>&1 || restore_failed=1
                fi
            fi
        fi
        if [ "$restore_failed" -eq 0 ]; then
            echo "TLS_RENEWAL_PREVIOUS_CONFIGURATION_RESTORED" >&2
        else
            echo "TLS_RENEWAL_RESTORE_INCOMPLETE; durable rollback snapshot retained at $ROLLBACK_DIR" >&2
        fi
    fi
    if [ "$rc" -ne 0 ] && [ "$snapshot_created" -eq 1 ] \
        && { [ "$restore_on_error" -eq 0 ] || [ "$restore_failed" -eq 0 ]; }; then
        rm -rf "$ROLLBACK_DIR"
    fi
    [ -z "$snapshot_staging" ] || rm -rf "$snapshot_staging"
    rm -rf "$work_dir"
}
trap cleanup EXIT

install -d -m 700 "$work_dir/previous-renewal-configs"
for renewal_config in "${renewal_configs[@]}"; do
    cp -a "$renewal_config" "$work_dir/previous-renewal-configs/"
done
if [ -f "$SYSTEMD_DIR/$SERVICE_NAME" ]; then
    service_existed=1
    cp -a "$SYSTEMD_DIR/$SERVICE_NAME" "$work_dir/previous-service"
fi
if [ -f "$SYSTEMD_DIR/$TIMER_NAME" ]; then
    timer_existed=1
    cp -a "$SYSTEMD_DIR/$TIMER_NAME" "$work_dir/previous-timer"
fi
if [ -f "$HOOK_PATH" ]; then
    hook_existed=1
    cp -a "$HOOK_PATH" "$work_dir/previous-hook"
fi
if systemctl is-enabled --quiet "$TIMER_NAME" 2>/dev/null; then
    timer_was_enabled=1
fi
if systemctl is-active --quiet "$TIMER_NAME" 2>/dev/null; then
    timer_was_active=1
fi

if [ -n "$ROLLBACK_DIR" ]; then
    snapshot_staging="${ROLLBACK_DIR}.tmp.$$"
    rm -rf "$snapshot_staging"
    install -d -m 700 "$snapshot_staging"
    [ "$service_existed" -eq 1 ] && cp -a "$work_dir/previous-service" "$snapshot_staging/previous-service"
    [ "$timer_existed" -eq 1 ] && cp -a "$work_dir/previous-timer" "$snapshot_staging/previous-timer"
    [ "$hook_existed" -eq 1 ] && cp -a "$work_dir/previous-hook" "$snapshot_staging/previous-hook"
    cp -a "$work_dir/previous-renewal-configs" "$snapshot_staging/previous-renewal-configs"
    [ "$service_existed" -eq 1 ] && touch "$snapshot_staging/service-existed"
    [ "$timer_existed" -eq 1 ] && touch "$snapshot_staging/timer-existed"
    [ "$hook_existed" -eq 1 ] && touch "$snapshot_staging/hook-existed"
    [ "$timer_was_enabled" -eq 1 ] && touch "$snapshot_staging/timer-was-enabled"
    [ "$timer_was_active" -eq 1 ] && touch "$snapshot_staging/timer-was-active"
    mv "$snapshot_staging" "$ROLLBACK_DIR"
    snapshot_staging=""
    snapshot_created=1
fi

cat > "$work_dir/practenture-nginx-reload" <<EOF
#!/usr/bin/env bash
set -euo pipefail
"$DOCKER_BIN" inspect practenture-nginx >/dev/null
"$DOCKER_BIN" exec practenture-nginx nginx -t
"$DOCKER_BIN" exec practenture-nginx nginx -s reload
EOF

cat > "$work_dir/$SERVICE_NAME" <<EOF
[Unit]
Description=Renew Practenture Let's Encrypt certificates
Wants=network-online.target
After=network-online.target docker.service

[Service]
Type=oneshot
ExecStart=$CERTBOT_BIN renew --quiet
EOF

cat > "$work_dir/$TIMER_NAME" <<EOF
[Unit]
Description=Run Practenture TLS certificate renewal twice daily

[Timer]
OnCalendar=*-*-* 03,15:00:00
RandomizedDelaySec=3600
Persistent=true
Unit=$SERVICE_NAME

[Install]
WantedBy=timers.target
EOF

SYSTEMD_ANALYZE=$(command -v systemd-analyze || true)
if [ -n "$SYSTEMD_ANALYZE" ]; then
    "$SYSTEMD_ANALYZE" verify \
        "$work_dir/$SERVICE_NAME" "$work_dir/$TIMER_NAME"
fi

restore_on_error=1
install -d -m 755 "$(dirname "$HOOK_PATH")" "$WEBROOT_PATH"
install -m 755 "$work_dir/practenture-nginx-reload" "$HOOK_PATH"
for renewal_config in "${renewal_configs[@]}"; do
    cert_name=$(basename -- "$renewal_config" .conf)
    "$CERTBOT_BIN" reconfigure \
        --cert-name "$cert_name" \
        --webroot \
        --webroot-path "$WEBROOT_PATH" \
        --run-deploy-hooks \
        --no-random-sleep-on-renew
    grep -Eq '^authenticator = webroot$' "$renewal_config"
    grep -Fq "$WEBROOT_PATH" "$renewal_config"
done
"$CERTBOT_BIN" renew \
    --dry-run \
    --run-deploy-hooks \
    --no-random-sleep-on-renew \
    --webroot \
    --webroot-path "$WEBROOT_PATH"
echo "TLS_RENEWAL_DRY_RUN_PASSED"
install -m 644 "$work_dir/$SERVICE_NAME" "$SYSTEMD_DIR/$SERVICE_NAME"
install -m 644 "$work_dir/$TIMER_NAME" "$SYSTEMD_DIR/$TIMER_NAME"
systemctl daemon-reload
systemctl enable "$TIMER_NAME"
systemctl restart "$TIMER_NAME"
systemctl is-enabled --quiet "$TIMER_NAME"
systemctl is-active --quiet "$TIMER_NAME"
NEXT_RUN=$(systemctl show "$TIMER_NAME" --property=NextElapseUSecRealtime --value)
test -n "$NEXT_RUN"
if [ -n "$ROLLBACK_DIR" ]; then
    touch "$ROLLBACK_DIR/install-complete"
fi
restore_on_error=0

echo "TLS_RENEWAL_TIMER_READY"
