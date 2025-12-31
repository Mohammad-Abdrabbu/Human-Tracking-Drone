#!/bin/bash
# Render Build Script for SAHTD Backend
# This script runs during the build phase on Render

set -e

echo "=== SAHTD Backend Build ==="

# Install dependencies
pip install --upgrade pip
pip install -r requirements-render.txt

# Initialize database tables
echo "Initializing database..."
python -c "from app.db import init_db; init_db()"

echo "=== Build Complete ==="
