#!/usr/bin/env bash
set -e

BACKEND_ROOT="$HOME/gp2/SAHTD_backend"

echo "[sahtd_backend] Starting FastAPI backend from $BACKEND_ROOT"

cd "$BACKEND_ROOT"

# Activate virtualenv if it exists
if [ -d ".venv" ]; then
  source ".venv/bin/activate"
fi

# Run uvicorn (production mode, no --reload)
exec uvicorn app.main:app --host 0.0.0.0 --port 8000
