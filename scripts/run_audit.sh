#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROOT/audit/run_audit.py" "${DATA_DIR:-$ROOT/data}"
