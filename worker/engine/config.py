# worker/engine/config.py
from __future__ import annotations

import json
import os
from pathlib import Path
from datetime import datetime, timezone

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


# =========================
# PATHS (sempre relativos ao worker)
# =========================
WORKER_DIR = Path(__file__).resolve().parent.parent  # .../worker
REPO_DIR = WORKER_DIR.parent                         # .../ (pode não existir no deploy do DO, mas não quebra)

def _first_existing(paths: list[Path]) -> Path | None:
    for p in paths:
        try:
            if p and p.exists():
                return p
        except Exception:
            pass
    return None


# =========================
# DATA_DIR (vem do DO: /workspace/data)
# =========================
DATA_DIR = Path(os.getenv("DATA_DIR", str(WORKER_DIR / "data"))).resolve()
DATA_DIR.mkdir(parents=True, exist_ok=True)


# =========================
# COINS (não pode quebrar deploy)
# =========================
DEFAULT_COINS = [
    "AAVE","ADA","APT","ARB","ATOM","AVAX","AXS","BCH","BNB","BTC","DOGE","DOT","ETH",
    "FET","FIL","FLUX","ICP","INJ","LDO","LINK","LTC","NEAR","OP","PEPE","POL","RATS",
    "RENDER","RUNE","SEI","SHIB","SOL","SUI","TIA","TNSR","TON","TRX","UNI","WIF","XRP"
]

# Você pode apontar COINS_FILE via variável de ambiente, se quiser.
COINS_FILE_ENV = os.getenv("COINS_FILE", "").strip()

CANDIDATE_COINS_FILES = [
    Path(COINS_FILE_ENV) if COINS_FILE_ENV else None,

    # dentro do próprio worker (RECOMENDADO)
    WORKER_DIR / "config" / "coins.json",
    WORKER_DIR / "coins.json",

    # alternativas (se algum dia você usar repo completo no container)
    REPO_DIR / "config" / "coins.json",
    Path("/workspace/config/coins.json"),
    Path("/workspace/worker/config/coins.json"),
]

COINS_FILE = _first_existing([p for p in CANDIDATE_COINS_FILES if p is not None])

def load_json(fp: Path) -> dict:
    return json.loads(fp.read_text(encoding="utf-8"))

def _normalize_coins(lst: list[str]) -> list[str]:
    out = []
    for c in lst:
        c = str(c).strip().upper()
        if not c:
            continue
        # garante sem USDT na lista
        c = c.replace("USDT", "").strip()
        if c and c not in out:
            out.append(c)
    return sorted(out)

if COINS_FILE:
    try:
        raw = load_json(COINS_FILE)
        coins = raw.get("coins", raw if isinstance(raw, list) else None)
        if isinstance(coins, list) and coins:
            COINS = _normalize_coins(coins)
        else:
            COINS = DEFAULT_COINS
    except Exception:
        COINS = DEFAULT_COINS
else:
    COINS = DEFAULT_COINS


# =========================
# REGRAS / LIMITES (defaults seguros)
# =========================
GAIN_MIN_PCT = float(os.getenv("GAIN_MIN_PCT", "3.0"))   # mínimo 3%
ASSERT_MIN_PCT = float(os.getenv("ASSERT_MIN_PCT", "65")) # mínimo 65%


# =========================
# TEMPO
# =========================
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

def now_brt_str() -> str:
    if ZoneInfo:
        dt = datetime.now(ZoneInfo("America/Sao_Paulo"))
    else:
        # fallback simples (não deveria acontecer no Python 3.13)
        dt = datetime.utcnow()
    return dt.strftime("%d/%m/%Y %H:%M")
