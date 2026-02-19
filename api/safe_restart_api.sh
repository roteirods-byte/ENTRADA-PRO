#!/usr/bin/env bash
set -euo pipefail

node -c /opt/ENTRADA-PRO/api/server.js

sudo systemctl restart entrada-pro-api

for i in $(seq 1 10); do
  if curl -fsS -o /dev/null 2>/dev/null http://127.0.0.1:3000/api/pro; then
    echo "OK: restarted + healthy"
    exit 0
  fi
  sleep 1
done

echo "FAIL: api did not come up"
exit 1
