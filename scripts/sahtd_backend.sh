#!/usr/bin/env bash
set -e

# Resolve SAHTD_ROOT as the repo root (…/gp2)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
export SAHTD_ROOT

BACKEND_ROOT="$SAHTD_ROOT/SAHTD_backend"

echo "[sahtd_backend] Starting FastAPI backend from $BACKEND_ROOT"

cd "$BACKEND_ROOT"

# Activate virtualenv if it exists
if [ -d ".venv" ]; then
  source ".venv/bin/activate"
fi

# Run uvicorn (production mode, no --reload)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
