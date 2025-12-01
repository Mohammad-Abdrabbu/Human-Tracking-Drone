#!/usr/bin/env bash
set -e

# Go to script directory
cd "$(dirname "$0")"

# Activate venv
source .venv/bin/activate

# Run backend in dev mode
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
