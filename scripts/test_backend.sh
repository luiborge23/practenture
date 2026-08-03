#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON="$ROOT_DIR/backend/.venv/bin/python"

if [ ! -x "$PYTHON" ]; then
    printf 'Project test interpreter not found: %s\n' "$PYTHON" >&2
    exit 1
fi

# Hermes and other developer tools may export their own site-packages through
# PYTHONPATH. Tests must use only the project environment selected above.
unset PYTHONPATH
# The canonical suite is deterministic and must never inherit live provider
# configuration from an ignored local .env. Provider-specific tests inject
# their own complete credentials with monkeypatch.
export PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY="${PRACTENTURE_PROVIDER_JOB_ENCRYPTION_KEY:-backend-test-provider-job-key-at-least-32-bytes}"
export PRACTENTURE_APPLE_AUDIENCE=""
unset PRACTENTURE_APPLE_TEAM_ID PRACTENTURE_APPLE_KEY_ID PRACTENTURE_APPLE_PRIVATE_KEY
cd "$ROOT_DIR"

if [ "$#" -eq 0 ]; then
    set -- backend/tests Tests -q
fi

exec "$PYTHON" -m pytest "$@"
