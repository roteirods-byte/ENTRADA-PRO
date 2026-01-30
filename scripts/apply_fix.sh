#!/usr/bin/env bash
set -euo pipefail

DOMAIN="paineljorge.duckdns.org"
CONF_SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/nginx"
CONF_SRC="${CONF_SRC_DIR}/paineljorge.conf"
MAIN="/etc/nginx/sites-enabled/autotrader-duckdns"
DST="/etc/nginx/sites-enabled/paineljorge.conf"

echo "=== FIX PAINELJORGE: INICIO ==="
test -f "$CONF_SRC" || { echo "ERRO: nao achei $CONF_SRC"; exit 1; }

sudo mkdir -p /etc/nginx/_bkp_sites_enabled /etc/nginx/_disabled_sites

# tirar BKP_ do sites-enabled (evita nginx quebrar)
sudo bash -lc 'shopt -s nullglob; mv -f /etc/nginx/sites-enabled/*.BKP_* /etc/nginx/_bkp_sites_enabled/ || true'

# desativar configs paineljorge antigas em sites-enabled
sudo bash -lc 'shopt -s nullglob; mv -f /etc/nginx/sites-enabled/paineljorge* /etc/nginx/_disabled_sites/ || true'

# backup do MAIN e desativar server_name paineljorge dentro dele (evita conflito/cert errado)
if sudo test -f "$MAIN"; then
  TS="$(date -u +%Y%m%d_%H%M%S)UTC"
  sudo cp -a "$MAIN" "/etc/nginx/_bkp_sites_enabled/autotrader-duckdns.BKP_${TS}"
  sudo python3 - <<PY
p = r"$MAIN"
s = open(p,"r",encoding="utf-8",errors="replace").read()
s2 = s.replace("server_name paineljorge.duckdns.org;","server_name paineljorge.DISABLED.local;")
open(p,"w",encoding="utf-8").write(s2)
print("OK: desativado server_name paineljorge dentro do MAIN")
PY
fi

sudo cp -a "$CONF_SRC" "$DST"
sudo chmod 0644 "$DST"

sudo nginx -t
sudo systemctl restart nginx

echo "=== TESTE ==="
curl -I -k "https://${DOMAIN}/full.html" | head -n 12 || true

echo "=== OK ==="
