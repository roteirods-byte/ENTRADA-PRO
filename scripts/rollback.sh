#!/usr/bin/env bash
set -euo pipefail

echo "=== ROLLBACK: INICIO ==="
sudo mkdir -p /etc/nginx/_disabled_sites /etc/nginx/_bkp_sites_enabled

sudo rm -f /etc/nginx/sites-enabled/paineljorge.conf || true
sudo bash -lc 'shopt -s nullglob; mv -f /etc/nginx/_disabled_sites/paineljorge* /etc/nginx/sites-enabled/ || true'

sudo nginx -t
sudo systemctl restart nginx
echo "=== ROLLBACK: OK ==="
