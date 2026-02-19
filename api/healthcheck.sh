#!/usr/bin/env bash
set -u
ts="$(date -u +%F_%T)"
if curl -fsS http://127.0.0.1:3000/api/pro >/dev/null && curl -fsS http://127.0.0.1:3000/api/top10 >/dev/null; then
  echo "OK $ts api"
else
  echo "FAIL $ts api"
fi
