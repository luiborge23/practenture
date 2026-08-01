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
cd "$ROOT_DIR"

if [ "$#" -eq 0 ]; then
    set -- backend/tests Tests -q
fi

exec "$PYTHON" -m pytest "$@"
