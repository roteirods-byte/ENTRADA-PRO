#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATA_DIR="${DATA_DIR:-$ROOT/data}"
python3 "$ROOT/worker/worker_pro.py"
