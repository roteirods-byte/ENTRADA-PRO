# worker/engine/config.py
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None  # type: ignore


# ---------- Paths ----------
ENGINE_DIR = Path(__file__).resolve().parent            # /workspace/worker/engine
WORKER_DIR = ENGINE_DIR.parent                          # /workspace/worker
REPO_DIR = WORKER_DIR.parent                            # /workspace (se o repo todo estiver presente)

DEFAULT_COINS = [
    "AAVE","ADA","APT","ARB","ATOM","AVAX","AXS","BCH","BNB","BTC","DOGE","DOT","ETH",
    "FET","FIL","FLUX","ICP","INJ","LDO","LINK","LTC","NEAR","OP","PEPE","POL","RATS",
    "RENDER","RUNE","SEI","SHIB","SOL","SUI","TIA","TNSR","TON","TRX","UNI","WIF","XRP"
]


def _load_json_file(fp: Path) -> dict:
    return json.loads(fp.read_text(encoding="utf-8"))


def _resolve_coins() -> list[str]:
    # 1) COINS_FILE por variável de ambiente (se quiser, você pode setar no DO)
    env_fp = os.getenv("COINS_FILE", "").strip()
    candidates: list[Path] = []
    if env_fp:
        candidates.append(Path(env_fp))

    # 2) Caminhos prováveis (depende do Source Directory do DO)
    candidates += [
        REPO_DIR / "config" / "coins.json",     # quando o repo root está no build
        WORKER_DIR / "config" / "coins.json",   # quando Source Directory = worker e você colocar worker/config/coins.json
        ENGINE_DIR / "config" / "coins.json",   # fallback raro
    ]

    for p in candidates:
        try:
            if p.is_file():
                data = _load_json_file(p)
                coins = data.get("coins")
                if isinstance(coins, list) and coins:
                    # normaliza: string, sem espaços, sem USDT, ordem alfabética
                    norm = []
                    for c in coins:
                        if not isinstance(c, str):
                            continue
                        c = c.strip().upper().replace("USDT", "")
                        if c:
                            norm.append(c)
                    return sorted(list(dict.fromkeys(norm)))
        except Exception:
            pass

    # 3) Se não achou, NÃO quebra o worker
    return DEFAULT_COINS


# ---------- Settings ----------
COINS = _resolve_coins()

# Diretório de dados (onde sai pro.json)
DATA_DIR = os.getenv("DATA_DIR", "/workspace/data").strip() or "/workspace/data"
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

# Ganho mínimo (%) antes de publicar sinal
def _float_env(key: str, default: float) -> float:
    v = os.getenv(key, "").strip().replace(",", ".")
    try:
        return float(v) if v else float(default)
    except Exception:
        return float(default)

GAIN_MIN_PCT = _float_env("GAIN_MIN_PCT", 3.0)


# ---------- Time helpers ----------
def now_utc_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def now_brt_str() -> str:
    if ZoneInfo is None:
        return datetime.now().strftime("%H:%M")
    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.now(tz).strftime("%H:%M")
