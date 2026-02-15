from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


# --- paths base ---
ENGINE_DIR = Path(__file__).resolve().parent          # /app/worker/engine
WORKER_DIR = ENGINE_DIR.parent                       # /app/worker
REPO_DIR = WORKER_DIR.parent                         # /app


# --- defaults (39 moedas) ---
DEFAULT_COINS = [
    "AAVE","ADA","APE","APT","AR","ARB","ATOM","AVAX","AXS","BAT","BCH","BLUR",
    "BNB","BONK","BTC","COMP","CRV","DASH","DENT","DGB","DOGE","DOT","EGLD","EOS",
    "ETC","ETH","FET","FIL","FLOKI","FLOW","FTM","GALA","GLM","GRT","HBAR","ICP",
    "IMX","INJ","IOST","KAS","KAVA","KSM","LINK","LTC","MANA","MATIC","MKR","NEAR",
    "NEO","OMG","ONT","OP","ORDI","PEPE","QNT","QTUM","RNDR","ROSE","RUNE","SAND",
    "SEI","SHIB","SNX","SOL","STX","SUI","SUSHI","THETA","TIA","TRX","UNI","VET",
    "XEM","XLM","XRP","XVS","ZEC","ZRX"
]


def _load_json(fp: Path):
    return json.loads(fp.read_text(encoding="utf-8"))


def _first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        try:
            if p and p.exists() and p.is_file():
                return p
        except Exception:
            pass
    return None


# --- DATA DIR (compartilhado com a API no mesmo container) ---
DATA_DIR = os.environ.get("DATA_DIR", str(REPO_DIR / "data")).strip()

# --- parâmetros ---
GAIN_MIN_PCT = float(os.environ.get("GAIN_MIN_PCT", "3").strip())
ASSERT_MIN_PCT = float(os.environ.get("ASSERT_MIN_PCT", "65").strip())


# --- COINS FILE: tenta vários lugares; se não achar, usa DEFAULT_COINS ---
ENV_COINS_FILE = os.environ.get("COINS_FILE", "").strip()

COINS_FILE_CANDIDATES = []
if ENV_COINS_FILE:
    COINS_FILE_CANDIDATES.append(Path(ENV_COINS_FILE))

COINS_FILE_CANDIDATES += [
    WORKER_DIR / "config" / "coins.json",   # /app/worker/config/coins.json (recomendado)
    REPO_DIR / "config" / "coins.json",     # /app/config/coins.json (compat)
    REPO_DIR / "coins.json",
]

_fp = _first_existing(COINS_FILE_CANDIDATES)

if _fp:
    try:
        obj = _load_json(_fp)
        coins = obj.get("coins", obj.get("COINS", None))
        if isinstance(coins, list) and len(coins) > 0:
            COINS = [str(x).strip().upper() for x in coins if str(x).strip()]
        else:
            COINS = DEFAULT_COINS[:]
    except Exception:
        COINS = DEFAULT_COINS[:]
else:
    COINS = DEFAULT_COINS[:]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def now_brt_str() -> str:
    # BRT (America/Sao_Paulo)
    if ZoneInfo:
        dt = datetime.now(ZoneInfo("America/Sao_Paulo"))
        return dt.strftime("%Y-%m-%d %H:%M")
    # fallback simples
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M")
