#!/usr/bin/env bash
set -euo pipefail

# Auditor interno (GATE) — ENTRADA-PRO
# Se qualquer item falhar: NÃO PUBLICAR.

BASE_URL="${1:-http://127.0.0.1:8090}"

fail() { echo "FALHA: $1" >&2; exit 1; }

echo "=== AUDITOR GATE: ${BASE_URL} ==="

# 1) health
h="$(curl -fsS "${BASE_URL}/api/health" || true)"
echo "$h" | grep -q '"ok":true' || fail "/api/health não retornou ok:true"

# 2) version
v="$(curl -fsS "${BASE_URL}/api/version" || true)"
echo "$v" | grep -q '"ok":true' || fail "/api/version não retornou ok:true"
echo "$v" | grep -q '"version"' || fail "/api/version não mostrou version"

# 3) pro (77)
p="$(curl -fsS "${BASE_URL}/api/pro" || true)"
echo "$p" | grep -q '"ok":true' || fail "/api/pro não retornou ok:true"
echo "$p" | grep -q '"count":77' || fail "/api/pro não retornou count=77"

# 4) top10 (0..10)
t="$(curl -fsS "${BASE_URL}/api/top10" || true)"
echo "$t" | grep -q '"ok":true' || fail "/api/top10 não retornou ok:true"

# 5) audit (nunca HTML)
a="$(curl -fsS "${BASE_URL}/api/audit" || true)"
echo "$a" | grep -q '"ok":' || fail "/api/audit não retornou JSON (parece HTML/erro)"

echo "OK: Auditoria passou."
