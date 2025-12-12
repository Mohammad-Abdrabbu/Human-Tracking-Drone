#!/usr/bin/env bash
set -e

# Resolve SAHTD_ROOT as the repo root (scripts/core/start_web.sh → ../..)
SCRIPT_DIR="$(cd -- "$(dirname "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
SAHTD_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
export SAHTD_ROOT

BACKEND_ROOT="$SAHTD_ROOT/web/backend"
FRONTEND_ROOT="$SAHTD_ROOT/web/frontend"

echo "[sahtd_web] Starting SAHTD Web Stack (Backend + Frontend)"

# Start Backend (FastAPI) in background
echo "[sahtd_web] Starting Backend (FastAPI) on port 8000..."
cd "$BACKEND_ROOT"
if [ -d ".venv" ]; then
  source ".venv/bin/activate"
fi
uvicorn app.main:app --host 0.0.0.0 --port 8000 &
BACKEND_PID=$!
echo "[sahtd_web] Backend started with PID $BACKEND_PID"

# Wait for backend to be ready
sleep 2

# Start Frontend (Vite dev server) in background
echo "[sahtd_web] Starting Frontend (Vite) on port 5173..."
cd "$FRONTEND_ROOT"
npm run dev &
FRONTEND_PID=$!
echo "[sahtd_web] Frontend started with PID $FRONTEND_PID"

echo "[sahtd_web] Web Stack running:"
echo "  - Backend:  http://localhost:8000"
echo "  - Frontend: http://localhost:5173"

# Trap to cleanup both processes on exit
cleanup() {
    echo "[sahtd_web] Shutting down..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait
    echo "[sahtd_web] Shutdown complete."
}
trap cleanup EXIT INT TERM

# Wait for either process to exit
wait
