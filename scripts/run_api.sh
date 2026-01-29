#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export DATA_DIR="${DATA_DIR:-$ROOT/data}"
export PORT="${PORT:-8090}"
cd "$ROOT/api"
npm install
node server.js
