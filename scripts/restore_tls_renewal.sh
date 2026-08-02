#!/usr/bin/env bash
set -euo pipefail

SERVICE_NAME="practenture-certbot-renew.service"
TIMER_NAME="practenture-certbot-renew.timer"
HOOK_PATH="/etc/letsencrypt/renewal-hooks/deploy/practenture-nginx-reload"
SYSTEMD_DIR="/etc/systemd/system"

if [ "${EUID}" -ne 0 ]; then
    exec sudo -- "$0" "$@"
fi
if [ "$#" -ne 1 ] || [ ! -d "$1" ]; then
    echo "usage: $0 ABSOLUTE_TLS_ROLLBACK_SNAPSHOT" >&2
    exit 2
fi
SNAPSHOT_DIR=$1
if [ "$(dirname -- "$SNAPSHOT_DIR")" != "/var/lib/practenture-deploy" ] \
    || [[ "$(basename -- "$SNAPSHOT_DIR")" != tls-rollback-* ]] \
    || [[ "$(basename -- "$SNAPSHOT_DIR")" == *[!A-Za-z0-9._-]* ]]; then
    echo "TLS rollback snapshot is outside the protected deployment state directory" >&2
    exit 2
fi
if [ ! -d "$SNAPSHOT_DIR/previous-renewal-configs" ] \
    || ! compgen -G "$SNAPSHOT_DIR/previous-renewal-configs/*.conf" >/dev/null; then
    echo "TLS rollback snapshot is missing renewal configurations" >&2
    exit 1
fi

if [ -f "$SYSTEMD_DIR/$TIMER_NAME" ]; then
    systemctl disable --now "$TIMER_NAME" >/dev/null 2>&1
fi
if [ -f "$SNAPSHOT_DIR/service-existed" ]; then
    install -m 644 "$SNAPSHOT_DIR/previous-service" "$SYSTEMD_DIR/$SERVICE_NAME"
else
    rm -f "$SYSTEMD_DIR/$SERVICE_NAME"
fi
if [ -f "$SNAPSHOT_DIR/timer-existed" ]; then
    install -m 644 "$SNAPSHOT_DIR/previous-timer" "$SYSTEMD_DIR/$TIMER_NAME"
else
    rm -f "$SYSTEMD_DIR/$TIMER_NAME"
fi
if [ -f "$SNAPSHOT_DIR/hook-existed" ]; then
    install -m 755 "$SNAPSHOT_DIR/previous-hook" "$HOOK_PATH"
else
    rm -f "$HOOK_PATH"
fi
for renewal_config in "$SNAPSHOT_DIR"/previous-renewal-configs/*.conf; do
    install -m 600 "$renewal_config" "/etc/letsencrypt/renewal/$(basename -- "$renewal_config")"
done
systemctl daemon-reload
if [ -f "$SNAPSHOT_DIR/timer-existed" ]; then
    if [ -f "$SNAPSHOT_DIR/timer-was-enabled" ]; then
        systemctl enable "$TIMER_NAME"
    else
        systemctl disable "$TIMER_NAME" >/dev/null 2>&1
    fi
    if [ -f "$SNAPSHOT_DIR/timer-was-active" ]; then
        systemctl start "$TIMER_NAME"
    else
        systemctl stop "$TIMER_NAME" >/dev/null 2>&1
    fi
fi
rm -rf "$SNAPSHOT_DIR"
echo "TLS_RENEWAL_DEPLOYMENT_ROLLBACK_RESTORED"