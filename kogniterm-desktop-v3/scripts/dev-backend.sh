#!/bin/bash
set -e
cd "$(dirname "$0")/.."
PORT="${KOGNITERM_PORT:-8765}"
HOST="${KOGNITERM_HOST:-127.0.0.1}"
echo "[v3-backend] http://$HOST:$PORT (kogniterm.server.app:create_app)"
python3 apps/backend/run.py --host "$HOST" --port "$PORT"
