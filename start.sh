#!/usr/bin/env bash
set -e

echo "[START] DATA_DIR=${DATA_DIR}"

# sobe o worker em background
python3 -u worker/worker_pro.py &

# sobe a API (fica em foreground)
node server.js
