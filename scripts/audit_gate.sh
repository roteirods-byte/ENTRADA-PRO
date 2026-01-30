#!/usr/bin/env bash
set -euo pipefail

# Auditor interno (GATE) — ENTRADA-PRO
# Se qualquer item falhar: NÃO PUBLICAR.

BASE_URL="${1:-http://127.0.0.1:8090}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CFG_COINS="${COINS_FILE:-$ROOT/config/coins.json}"

fail() { echo "FALHA: $1" >&2; exit 1; }

export CFG_COINS
expected_count="$(python3 - <<'PY'
import json, os, sys
fp = os.environ.get("CFG_COINS")
try:
    d=json.load(open(fp, "r", encoding="utf-8"))
    print(len(d.get("coins", [])))
except Exception:
    print("0")
PY
)"

echo "=== AUDITOR GATE: ${BASE_URL} | expected_count=${expected_count} ==="

# 1) health
h="$(curl -fsS "${BASE_URL}/api/health" || true)"
echo "$h" | grep -q '"ok":true' || fail "/api/health não retornou ok:true"

# 2) version
v="$(curl -fsS "${BASE_URL}/api/version" || true)"
echo "$v" | grep -q '"ok":true' || fail "/api/version não retornou ok:true"
echo "$v" | grep -q '"version"' || fail "/api/version não mostrou version"

# 3) pro (count deve bater com config/coins.json)
p="$(curl -fsS "${BASE_URL}/api/pro" || true)"
python3 - <<'PY' <<<"$p" || fail "/api/pro inválido (não é JSON)"
import json, sys
json.load(sys.stdin)
PY

pro_ok="$(python3 - <<'PY' <<<"$p"
import json, sys
d=json.load(sys.stdin)
print("1" if d.get("ok") is True else "0")
PY
)"
[ "$pro_ok" = "1" ] || fail "/api/pro não retornou ok:true"

pro_count="$(python3 - <<'PY' <<<"$p"
import json, sys
d=json.load(sys.stdin)
print(int(d.get("count", -1)))
PY
)"
[ "$pro_count" -gt 0 ] || fail "/api/pro count inválido"

if [ "$expected_count" != "0" ] && [ "$pro_count" -ne "$expected_count" ]; then
  fail "/api/pro count=${pro_count} != expected=${expected_count} (config/coins.json)"
fi

# 4) top10 (0..10)
t="$(curl -fsS "${BASE_URL}/api/top10" || true)"
top_ok="$(python3 - <<'PY' <<<"$t"
import json, sys
d=json.load(sys.stdin)
print("1" if d.get("ok") is True else "0")
PY
)"
[ "$top_ok" = "1" ] || fail "/api/top10 não retornou ok:true"

top_count="$(python3 - <<'PY' <<<"$t"
import json, sys
d=json.load(sys.stdin)
print(int(d.get("count", -1)))
PY
)"
[ "$top_count" -le 10 ] || fail "/api/top10 count > 10 (${top_count})"

# 5) audit (nunca HTML)
a="$(curl -fsS "${BASE_URL}/api/audit" || true)"
python3 - <<'PY' <<<"$a" || fail "/api/audit não retornou JSON (parece HTML/erro)"
import json, sys
json.load(sys.stdin)
PY

echo "OK: Auditoria passou."
