# worker/engine/config.py
from __future__ import annotations

import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo
from datetime import datetime, timezone

# ====== TIME ======
_TZ_BRT = ZoneInfo("America/Sao_Paulo")

def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def now_brt_str() -> str:
    return datetime.now(_TZ_BRT).strftime("%d/%m/%Y %H:%M")

# ====== DEFAULT COINS (39) ======
DEFAULT_COINS = [
    "AAVE","ADA","APT","ARB","ATOM","AVAX","AXS","BCH","BNB","BTC",
    "DOGE","DOT","ETH","FET","FIL","FLUX","ICP","INJ","LDO","LINK",
    "LTC","NEAR","OP","PEPE","POL","RATS","RENDER","RUNE","SEI","SHIB",
    "SOL","SUI","TIA","TNSR","TON","TRX","UNI","WIF","XRP"
]

def _read_json(fp: Path) -> dict:
    return json.loads(fp.read_text(encoding="utf-8"))

def _find_coins_file() -> Path | None:
    # 1) Se você quiser, pode setar via ENV: COINS_FILE
    env_fp = os.getenv("COINS_FILE", "").strip()
    if env_fp:
        p = Path(env_fp)
        if p.exists():
            return p

    # 2) caminhos comuns (DO Worker usa /workspace/worker como app root)
    candidates = [
        Path("config/coins.json"),
        Path("worker/config/coins.json"),
        Path("/workspace/worker/config/coins.json"),
        Path("/workspace/config/coins.json"),
    ]
    for c in candidates:
        if c.exists():
            return c
    return None

# ====== DIRS / PARAMS ======
DATA_DIR = os.getenv("DATA_DIR", "/workspace/data").strip() or "/workspace/data"
GAIN_MIN_PCT = float(os.getenv("GAIN_MIN_PCT", "3.0"))  # regra mínima 3%

# ====== COINS LOAD (com fallback) ======
_COINS_FP = _find_coins_file()
if _COINS_FP:
    try:
        COINS = _read_json(_COINS_FP).get("coins", DEFAULT_COINS)
        if not isinstance(COINS, list) or not COINS:
            COINS = DEFAULT_COINS
    except Exception:
        COINS = DEFAULT_COINS
else:
    COINS = DEFAULT_COINS

# normaliza (maiúsculo / sem espaços) e ordena
COINS = sorted({str(x).strip().upper() for x in COINS if str(x).strip()})
