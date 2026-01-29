#!/usr/bin/env bash
set -euo pipefail

# INSTALADOR ENTRADA-PRO (1 comando)
# Requisitos: Debian/Ubuntu, usuário roteiro_ds, nginx instalado, node>=18, python3
# Este script:
# 1) cria /home/roteiro_ds/ENTRADA-PRO
# 2) instala deps node/python
# 3) cria services systemd (api+worker+audição)
# 4) publica site em /var/www/entrada-pro
# 5) mostra URLs de teste

REPO_DIR="/home/roteiro_ds/ENTRADA-PRO"
SITE_DIR="/var/www/entrada-pro"

echo "=== 1) Preparar pastas ==="
sudo mkdir -p "$REPO_DIR" "$REPO_DIR/data" "$SITE_DIR"
sudo chown -R roteiro_ds:roteiro_ds "$REPO_DIR" "$SITE_DIR"

echo "=== 2) Copiar arquivos do repo (rodar dentro da pasta do repo clonado) ==="
# Este script deve ser executado dentro da pasta do repo (ENTRADA-PRO) já clonada.
SRC="$(pwd)"
if [[ ! -f "$SRC/api/server.js" ]]; then
  echo "ERRO: execute este script dentro da pasta ENTRADA-PRO (onde existe api/server.js)."
  exit 1
fi

sudo rsync -a --delete "$SRC/" "$REPO_DIR/"

echo "=== 3) Publicar site ==="
sudo rsync -a --delete "$REPO_DIR/site/" "$SITE_DIR/"

echo "=== 4) Instalar dependências ==="
cd "$REPO_DIR/api"
npm ci --omit=dev || npm install --omit=dev

cd "$REPO_DIR/worker"
python3 -m pip install --user -r requirements.txt || true

echo "=== 5) Instalar systemd ==="
sudo cp -f "$REPO_DIR/deploy/systemd/entrada-pro-api.service" /etc/systemd/system/
sudo cp -f "$REPO_DIR/deploy/systemd/entrada-pro-worker.service" /etc/systemd/system/
sudo cp -f "$REPO_DIR/deploy/systemd/entrada-pro-audit.service" /etc/systemd/system/
sudo cp -f "$REPO_DIR/deploy/systemd/entrada-pro-audit.timer" /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now entrada-pro-worker.service
sudo systemctl enable --now entrada-pro-api.service
sudo systemctl enable --now entrada-pro-audit.timer

echo "=== 6) Teste local ==="
bash "$REPO_DIR/scripts/audit_gate.sh" "http://127.0.0.1:8090" || true

echo "OK. Agora ajuste o Nginx para apontar /api/ para 127.0.0.1:8090 e root /var/www/entrada-pro"
echo "URLs esperadas:"
echo "  /api/health  /api/version  /api/pro  /api/top10  /api/audit"
echo "  /full.html /top10.html /audit.html"
