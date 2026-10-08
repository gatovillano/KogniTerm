#!/bin/bash
set -e
cd "$(dirname "$0")/.."
bash scripts/dev-backend.sh &
BACK_PID=$!
echo "[desktop] backend pid $BACK_PID"
cd apps/web && npm run dev -- --port 4444
kill $BACK_PID || true
