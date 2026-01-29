# ENTRADA-PRO (PRO - Perp Futures, MARK PRICE)

## O que entrega
- `data/pro.json` (77 moedas)
- `data/top10.json` (Top10 por ASSERT% desc, depois GANHO% desc)
- `data/audit.json` (auditoria + integridade)

## Regras fixas
- SIDE: `LONG` (comprado) | `SHORT` (vendido) | `NÃO ENTRAR`
- `GANHO% < 3` => `NÃO ENTRAR`
- Preço base do cálculo = **MARK PRICE** (perp)
- Atualização recomendada: a cada 5 minutos

## Rodar local (Linux/Mac)
### 1) Worker (gera JSON)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r worker/requirements.txt
export DATA_DIR="$(pwd)/data"
python worker/worker_pro.py
```

### 2) API (serve JSON)
```bash
cd api
npm install
export DATA_DIR="$(pwd)/../data"
export PORT=8090
node server.js
```

### 3) Site
Abra `site/full.html` no navegador (ou sirva via Nginx/Apache).
