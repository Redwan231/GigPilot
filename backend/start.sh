#!/bin/sh
set -e

# Default port for Hugging Face Spaces
export PORT=${PORT:-7860}

echo "[start] Running Alembic migrations..."
alembic upgrade head

echo "[start] Starting services (web + worker + beat) via honcho..."
exec honcho start
