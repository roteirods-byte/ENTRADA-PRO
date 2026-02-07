# ENTRADA-PRO (PRO - Perp Futures, MARK PRICE)

## O que entrega
- `data/pro.json` (78 moedas)
- `data/top10.json` (Top10 por GANHO% desc — extraído do FULL)
- `data/audit.json` (auditoria + integridade)

## Moedas (78 • ordem alfabética)
AAVE, ADA, APE, APT, AR, ARB, ATOM, AVAX, AXS, BAT, BCH, BLUR, BNB, BONK, BTC, COMP, CRV, DASH, DENT, DGB, DOGE, DOT, EGLD, EOS, ETC, ETH, FET, FIL, FLOKI, FLOW, FTM, GALA, GLM, GRT, HBAR, ICP, IMX, INJ, IOST, KAS, KAVA, KSM, LINK, LTC, MANA, MATIC, MKR, NEAR, NEO, OMG, ONT, OP, ORDI, PEPE, QNT, QTUM, RNDR, ROSE, RUNE, SAND, SEI, SHIB, SNX, SOL, STX, SUI, SUSHI, THETA, TIA, TRX, UNI, VET, XEM, XLM, XRP, XVS, ZEC, ZRX

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
