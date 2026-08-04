#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="practenture-certbot-renew.service"
TIMER_NAME="practenture-certbot-renew.timer"
TEST_ROOT=${PRACTENTURE_TLS_TEST_ROOT:-}
if [ -n "$TEST_ROOT" ]; then
    if [ "${PRACTENTURE_TLS_TESTING:-}" != "1" ] || [[ "$TEST_ROOT" != /* ]] || [ ! -d "$TEST_ROOT" ]; then
        echo "PRACTENTURE_TLS_TEST_ROOT requires PRACTENTURE_TLS_TESTING=1 and an existing absolute path" >&2
        exit 2
    fi
    TEST_ROOT=$(cd -P -- "$TEST_ROOT" && pwd -P)
    if [ "$TEST_ROOT" = "/" ]; then
        echo "PRACTENTURE_TLS_TEST_ROOT must not resolve to the production filesystem root" >&2
        exit 2
    fi
    TEST_BIN_DIR="$TEST_ROOT/bin"
    for required_test_command in certbot docker systemctl systemd-analyze; do
        if [ ! -x "$TEST_BIN_DIR/$required_test_command" ]; then
            echo "test mode requires isolated executable: $TEST_BIN_DIR/$required_test_command" >&2
            exit 2
        fi
    done
    CERTBOT_BIN="$TEST_BIN_DIR/certbot"
    DOCKER_BIN="$TEST_BIN_DIR/docker"
    SYSTEMCTL_BIN="$TEST_BIN_DIR/systemctl"
    SYSTEMD_ANALYZE="$TEST_BIN_DIR/systemd-analyze"
    LETSENCRYPT_DIR="$TEST_ROOT/etc/letsencrypt"
    SYSTEMD_DIR="$TEST_ROOT/etc/systemd/system"
    WEBROOT_PATH="$TEST_ROOT/var/www/certbot"
    PROTECTED_STATE_DIR="$TEST_ROOT/var/lib/practenture-deploy"
else
    CERTBOT_BIN=$(command -v certbot || true)
    DOCKER_BIN=$(command -v docker || true)
    SYSTEMCTL_BIN=$(command -v systemctl || true)
    SYSTEMD_ANALYZE=$(command -v systemd-analyze || true)
    LETSENCRYPT_DIR="/etc/letsencrypt"
    SYSTEMD_DIR="/etc/systemd/system"
    WEBROOT_PATH="/var/www/certbot"
    PROTECTED_STATE_DIR="/var/lib/practenture-deploy"
fi
HOOK_PATH="$LETSENCRYPT_DIR/renewal-hooks/deploy/practenture-nginx-reload"
HOOK_DIR=$(dirname -- "$HOOK_PATH")
ATTESTATION_PATH="$PROTECTED_STATE_DIR/tls-renewal-attestation-v1"
ROLLBACK_DIR=${PRACTENTURE_TLS_ROLLBACK_DIR:-}

if [ "${EUID}" -ne 0 ] && [ -z "$TEST_ROOT" ]; then
    exec sudo env PRACTENTURE_TLS_ROLLBACK_DIR="$ROLLBACK_DIR" "$0" "$@"
fi

if [ -n "$ROLLBACK_DIR" ]; then
    if [ "$(dirname -- "$ROLLBACK_DIR")" != "$PROTECTED_STATE_DIR" ] \
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

if [ -z "$CERTBOT_BIN" ]; then
    echo "certbot is required before TLS renewal can be configured" >&2
    exit 1
fi
if [ -z "$DOCKER_BIN" ]; then
    echo "docker is required before TLS renewal can be configured" >&2
    exit 1
fi
if [ -z "$SYSTEMCTL_BIN" ]; then
    echo "systemctl is required before TLS renewal can be configured" >&2
    exit 1
fi

shopt -s nullglob
discovered_renewal_configs=("$LETSENCRYPT_DIR"/renewal/*.conf)
shopt -u nullglob
required_cert_names=("api.practenture.com" "www.practenture.com")
if [ "${#discovered_renewal_configs[@]}" -ne "${#required_cert_names[@]}" ]; then
    echo "expected exactly the api.practenture.com and www.practenture.com renewal lineages" >&2
    exit 1
fi
renewal_configs=()
for cert_name in "${required_cert_names[@]}"; do
    renewal_config="$LETSENCRYPT_DIR/renewal/$cert_name.conf"
    if [ ! -f "$renewal_config" ] || [ -L "$renewal_config" ]; then
        echo "required regular renewal lineage is missing: $cert_name" >&2
        exit 1
    fi
    renewal_configs+=("$renewal_config")
done

work_dir=$(mktemp -d)
service_existed=0
timer_existed=0
hook_existed=0
attestation_existed=0
timer_was_enabled=0
timer_was_active=0
restore_on_error=0
snapshot_created=0
snapshot_staging=""
hook_dir_existed=0
webroot_existed=0
hook_dir_created=0
webroot_created=0

for required_directory in "$HOOK_DIR" "$WEBROOT_PATH"; do
    if [ -e "$required_directory" ]; then
        if [ ! -d "$required_directory" ] || [ -L "$required_directory" ]; then
            echo "TLS runtime path must be a regular directory: $required_directory" >&2
            exit 1
        fi
        if [ "$required_directory" = "$HOOK_DIR" ]; then
            hook_dir_existed=1
        else
            webroot_existed=1
        fi
    fi
done

cleanup() {
    rc=$?
    restore_failed=0
    if [ "$rc" -ne 0 ] && [ "$restore_on_error" -eq 1 ]; then
        set +e
        if [ -f "$SYSTEMD_DIR/$TIMER_NAME" ]; then
            "$SYSTEMCTL_BIN" disable --now "$TIMER_NAME" >/dev/null 2>&1 || restore_failed=1
        fi
        if [ "$restore_failed" -eq 0 ]; then
            if [ "$service_existed" -eq 1 ]; then
                rm -f "$SYSTEMD_DIR/$SERVICE_NAME" \
                    && cp -a "$work_dir/previous-service" "$SYSTEMD_DIR/$SERVICE_NAME" \
                    || restore_failed=1
            else
                rm -f "$SYSTEMD_DIR/$SERVICE_NAME" || restore_failed=1
            fi
            if [ "$timer_existed" -eq 1 ]; then
                rm -f "$SYSTEMD_DIR/$TIMER_NAME" \
                    && cp -a "$work_dir/previous-timer" "$SYSTEMD_DIR/$TIMER_NAME" \
                    || restore_failed=1
            else
                rm -f "$SYSTEMD_DIR/$TIMER_NAME" || restore_failed=1
            fi
            if [ "$hook_existed" -eq 1 ]; then
                rm -f "$HOOK_PATH" \
                    && cp -a "$work_dir/previous-hook" "$HOOK_PATH" \
                    || restore_failed=1
            else
                rm -f "$HOOK_PATH" || restore_failed=1
            fi
            if [ "$attestation_existed" -eq 1 ]; then
                rm -f "$ATTESTATION_PATH" \
                    && cp -a "$work_dir/previous-attestation" "$ATTESTATION_PATH" \
                    || restore_failed=1
            else
                rm -f "$ATTESTATION_PATH" || restore_failed=1
            fi
            for renewal_config in "$work_dir"/previous-renewal-configs/*.conf; do
                destination="$LETSENCRYPT_DIR/renewal/$(basename -- "$renewal_config")"
                rm -f "$destination" \
                    && cp -a "$renewal_config" "$destination" \
                    || restore_failed=1
            done
            if [ "$hook_dir_existed" -eq 1 ]; then
                rm -rf "$HOOK_DIR" \
                    && cp -a "$work_dir/previous-hook-dir" "$HOOK_DIR" \
                    || restore_failed=1
            elif [ "$hook_dir_created" -eq 1 ]; then
                rmdir "$HOOK_DIR" || restore_failed=1
            fi
            if [ "$webroot_existed" -eq 1 ]; then
                rm -rf "$WEBROOT_PATH" \
                    && cp -a "$work_dir/previous-webroot" "$WEBROOT_PATH" \
                    || restore_failed=1
            elif [ "$webroot_created" -eq 1 ]; then
                rmdir "$WEBROOT_PATH" || restore_failed=1
            fi
            "$SYSTEMCTL_BIN" daemon-reload || restore_failed=1
            if [ "$timer_existed" -eq 1 ]; then
                if [ "$timer_was_enabled" -eq 1 ]; then
                    "$SYSTEMCTL_BIN" enable "$TIMER_NAME" || restore_failed=1
                else
                    "$SYSTEMCTL_BIN" disable "$TIMER_NAME" >/dev/null 2>&1 || restore_failed=1
                fi
                if [ "$timer_was_active" -eq 1 ]; then
                    "$SYSTEMCTL_BIN" start "$TIMER_NAME" || restore_failed=1
                else
                    "$SYSTEMCTL_BIN" stop "$TIMER_NAME" >/dev/null 2>&1 || restore_failed=1
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
if [ -f "$ATTESTATION_PATH" ]; then
    if [ -L "$ATTESTATION_PATH" ]; then
        echo "TLS renewal attestation must be a regular file" >&2
        exit 1
    fi
    attestation_existed=1
    cp -a "$ATTESTATION_PATH" "$work_dir/previous-attestation"
fi
if [ "$hook_dir_existed" -eq 1 ]; then
    cp -a "$HOOK_DIR" "$work_dir/previous-hook-dir"
fi
if [ "$webroot_existed" -eq 1 ]; then
    cp -a "$WEBROOT_PATH" "$work_dir/previous-webroot"
fi
if "$SYSTEMCTL_BIN" is-enabled --quiet "$TIMER_NAME" 2>/dev/null; then
    timer_was_enabled=1
fi
if "$SYSTEMCTL_BIN" is-active --quiet "$TIMER_NAME" 2>/dev/null; then
    timer_was_active=1
fi

if [ -n "$ROLLBACK_DIR" ]; then
    snapshot_staging="${ROLLBACK_DIR}.tmp.$$"
    rm -rf "$snapshot_staging"
    install -d -m 700 "$snapshot_staging"
    [ "$service_existed" -eq 1 ] && cp -a "$work_dir/previous-service" "$snapshot_staging/previous-service"
    [ "$timer_existed" -eq 1 ] && cp -a "$work_dir/previous-timer" "$snapshot_staging/previous-timer"
    [ "$hook_existed" -eq 1 ] && cp -a "$work_dir/previous-hook" "$snapshot_staging/previous-hook"
    [ "$attestation_existed" -eq 1 ] && cp -a "$work_dir/previous-attestation" "$snapshot_staging/previous-attestation"
    [ "$hook_dir_existed" -eq 1 ] && cp -a "$work_dir/previous-hook-dir" "$snapshot_staging/previous-hook-dir"
    [ "$webroot_existed" -eq 1 ] && cp -a "$work_dir/previous-webroot" "$snapshot_staging/previous-webroot"
    cp -a "$work_dir/previous-renewal-configs" "$snapshot_staging/previous-renewal-configs"
    [ "$service_existed" -eq 1 ] && touch "$snapshot_staging/service-existed"
    [ "$timer_existed" -eq 1 ] && touch "$snapshot_staging/timer-existed"
    [ "$hook_existed" -eq 1 ] && touch "$snapshot_staging/hook-existed"
    [ "$attestation_existed" -eq 1 ] && touch "$snapshot_staging/attestation-existed"
    [ "$hook_dir_existed" -eq 1 ] && touch "$snapshot_staging/hook-dir-existed"
    [ "$webroot_existed" -eq 1 ] && touch "$snapshot_staging/webroot-existed"
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
Requires=docker.service
After=network-online.target docker.service

[Service]
Type=oneshot
UMask=0077
NoNewPrivileges=yes
PrivateTmp=yes
ProtectHome=yes
ProtectSystem=strict
ReadWritePaths=$LETSENCRYPT_DIR /var/lib/letsencrypt /var/log/letsencrypt $WEBROOT_PATH /run/docker.sock
ExecStartPre=$DOCKER_BIN inspect practenture-nginx
ExecStartPre=$DOCKER_BIN exec practenture-nginx nginx -t
ExecStart=$CERTBOT_BIN renew --quiet --no-random-sleep-on-renew
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

if [ -n "$SYSTEMD_ANALYZE" ]; then
    "$SYSTEMD_ANALYZE" verify \
        "$work_dir/$SERVICE_NAME" "$work_dir/$TIMER_NAME"
fi

configuration_digest() {
    {
        for managed_file in \
            "$work_dir/$SERVICE_NAME" \
            "$work_dir/$TIMER_NAME" \
            "$work_dir/practenture-nginx-reload"; do
            sha256sum "$managed_file" | cut -d ' ' -f 1
        done
        for renewal_config in "${renewal_configs[@]}"; do
            cert_name=$(basename -- "$renewal_config" .conf)
            printf 'cert_name=%s\n' "$cert_name"
            grep -E '^(authenticator|webroot_path) = ' "$renewal_config" | LC_ALL=C sort
        done
    } | sha256sum | cut -d ' ' -f 1
}

write_attestation() {
    digest=$1
    attestation_tmp="$PROTECTED_STATE_DIR/.tls-renewal-attestation-v1.$$"
    install -d -m 700 "$PROTECTED_STATE_DIR"
    umask 077
    {
        printf 'version=1\n'
        printf 'configuration_sha256=%s\n' "$digest"
        printf 'validated_at_epoch=%s\n' "$(date +%s)"
    } > "$attestation_tmp"
    chmod 600 "$attestation_tmp"
    mv "$attestation_tmp" "$ATTESTATION_PATH"
}

# Routine releases must not contact ACME when the complete managed renewal
# configuration is unchanged. A pre-attestation installation may be adopted
# once only when every managed byte, renewal setting, and timer invariant
# already matches this release.
routine_verification=0
if [ "$service_existed" -eq 1 ] && [ "$timer_existed" -eq 1 ] \
    && [ "$hook_existed" -eq 1 ] \
    && cmp -s "$work_dir/$SERVICE_NAME" "$SYSTEMD_DIR/$SERVICE_NAME" \
    && cmp -s "$work_dir/$TIMER_NAME" "$SYSTEMD_DIR/$TIMER_NAME" \
    && cmp -s "$work_dir/practenture-nginx-reload" "$HOOK_PATH"; then
    renewal_settings_valid=1
    for renewal_config in "${renewal_configs[@]}"; do
        grep -Eq '^authenticator = webroot$' "$renewal_config" \
            || renewal_settings_valid=0
        grep -Eq "^webroot_path = ${WEBROOT_PATH//\//\\/},?$" "$renewal_config" \
            || renewal_settings_valid=0
    done
    if [ "$renewal_settings_valid" -eq 1 ] \
        && "$SYSTEMCTL_BIN" is-enabled --quiet "$TIMER_NAME" \
        && "$SYSTEMCTL_BIN" is-active --quiet "$TIMER_NAME"; then
        NEXT_RUN=$("$SYSTEMCTL_BIN" show "$TIMER_NAME" --property=NextElapseUSecRealtime --value)
        test -n "$NEXT_RUN"
        desired_digest=$(configuration_digest)
        if [ "$attestation_existed" -eq 0 ]; then
            routine_verification=1
            echo "TLS_RENEWAL_EXISTING_CONFIGURATION_ADOPTED"
        elif grep -Fxq 'version=1' "$ATTESTATION_PATH" \
            && grep -Fxq "configuration_sha256=$desired_digest" "$ATTESTATION_PATH" \
            && [ -n "$(find "$ATTESTATION_PATH" -mtime -30 -print -quit)" ]; then
            routine_verification=1
            echo "TLS_RENEWAL_ATTESTATION_VERIFIED"
        fi
    fi
fi

if [ "$routine_verification" -eq 1 ]; then
    restore_on_error=1
    write_attestation "$desired_digest"
    if [ -n "$ROLLBACK_DIR" ]; then
        touch "$ROLLBACK_DIR/install-complete"
    fi
    restore_on_error=0
    echo "TLS_RENEWAL_TIMER_READY"
    exit 0
fi

restore_on_error=1
if [ "$hook_dir_existed" -eq 0 ]; then
    install -d -m 755 "$HOOK_DIR"
    hook_dir_created=1
fi
if [ "$webroot_existed" -eq 0 ]; then
    install -d -m 755 "$WEBROOT_PATH"
    webroot_created=1
fi
install -m 755 "$work_dir/practenture-nginx-reload" "$HOOK_PATH"
for renewal_config in "${renewal_configs[@]}"; do
    cert_name=$(basename -- "$renewal_config" .conf)
    "$CERTBOT_BIN" reconfigure \
        --cert-name "$cert_name" \
        --webroot \
        --webroot-path "$WEBROOT_PATH" \
        --run-deploy-hooks
    grep -Eq '^authenticator = webroot$' "$renewal_config"
    grep -Eq "^webroot_path = ${WEBROOT_PATH//\//\\/},?$" "$renewal_config"
done
"$CERTBOT_BIN" renew \
    --dry-run \
    --run-deploy-hooks \
    --no-random-sleep-on-renew
echo "TLS_RENEWAL_DRY_RUN_PASSED"
install -m 644 "$work_dir/$SERVICE_NAME" "$SYSTEMD_DIR/$SERVICE_NAME"
install -m 644 "$work_dir/$TIMER_NAME" "$SYSTEMD_DIR/$TIMER_NAME"
"$SYSTEMCTL_BIN" daemon-reload
"$SYSTEMCTL_BIN" enable "$TIMER_NAME"
"$SYSTEMCTL_BIN" restart "$TIMER_NAME"
"$SYSTEMCTL_BIN" is-enabled --quiet "$TIMER_NAME"
"$SYSTEMCTL_BIN" is-active --quiet "$TIMER_NAME"
NEXT_RUN=$("$SYSTEMCTL_BIN" show "$TIMER_NAME" --property=NextElapseUSecRealtime --value)
test -n "$NEXT_RUN"
write_attestation "$(configuration_digest)"
if [ -n "$ROLLBACK_DIR" ]; then
    touch "$ROLLBACK_DIR/install-complete"
fi
restore_on_error=0

echo "TLS_RENEWAL_TIMER_READY"
