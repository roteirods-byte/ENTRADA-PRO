#!/usr/bin/env bash
set -e

mkdir -p "${DATA_DIR:-/app/data}"

# WORKER em loop (não pode morrer, senão o DO derruba/religa)
(
  while true; do
    echo "[START] worker loop..."
    python3 -u /app/worker/worker_pro.py || true
    sleep 10
  done
) &

# API em foreground
echo "[START] api..."
node /app/api/server.js
