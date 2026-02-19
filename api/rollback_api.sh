#!/usr/bin/env bash
set -euo pipefail

echo "[1] Check syntax..."
node -c /opt/ENTRADA-PRO/api/server.js >/dev/null && echo "OK: server.js syntax"

echo "[2] Pick latest backup..."
BKP="$(ls -t /root/backup_ENTRADA-PRO_*.tgz | head -n 1)"
echo "BKP=$BKP"

echo "[3] Restore server.js from backup..."
tar -xzf "$BKP" -C / --wildcards 'ENTRADA-PRO/api/server.js'
mv /ENTRADA-PRO/api/server.js /opt/ENTRADA-PRO/api/server.js

echo "[4] Validate syntax after restore..."
node -c /opt/ENTRADA-PRO/api/server.js

echo "[5] Restart service..."
systemctl restart entrada-pro-api

echo "[6] Wait up (retry)..."
for i in $(seq 1 10); do
  if curl -fsS -o /dev/null 2>/dev/null http://127.0.0.1:3000/api/pro && curl -fsS -o /dev/null 2>/dev/null http://127.0.0.1:3000/api/top10; then
    echo "DONE: rollback ok"
    exit 0
  fi
  sleep 1
done

echo "FAIL: api did not come up"
exit 1
