# worker/engine/config.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore


# ====== LISTA OFICIAL (fallback) ======
DEFAULT_COINS = [
    "AAVE","ADA","APT","ARB","ATOM","AVAX","AXS","BCH","BNB","BTC",
    "DOGE","DOT","ETH","FET","FIL","FLUX","ICP","INJ","LDO","LINK",
    "LTC","NEAR","OP","PEPE","POL","RATS","RENDER","RUNE","SEI","SHIB",
    "SOL","SUI","TIA","TNSR","TON","TRX","UNI","WIF","XRP",
]

BRT_TZ_NAME = "America/Sao_Paulo"


def _safe_read_json(fp: Path) -> dict | None:
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception:
        return None


def _candidate_files(env_key: str, rel_path: str) -> list[Path]:
    """
    Monta uma lista de caminhos possíveis, porque no DigitalOcean
    o worker pode estar rodando com raiz em /workspace/worker
    (sem /workspace/config).
    """
    out: list[Path] = []

    # 1) Caminho via variável de ambiente (se existir)
    env = os.getenv(env_key, "").strip()
    if env:
        out.append(Path(env))

    # 2) Caminhos absolutos comuns no DO
    out.append(Path("/workspace") / rel_path)          # /workspace/config/coins.json
    out.append(Path("/workspace/worker") / rel_path)   # /workspace/worker/config/coins.json

    # 3) Caminhos relativos ao arquivo atual
    here = Path(__file__).resolve()  # .../worker/engine/config.py
    worker_dir = here.parent.parent  # .../worker
    out.append(worker_dir / rel_path)           # .../worker/config/coins.json
    out.append(worker_dir.parent / rel_path)    # .../config/coins.json (se existir)

    # remove duplicados mantendo ordem
    seen = set()
    unique: list[Path] = []
    for p in out:
        s = str(p)
        if s not in seen:
            seen.add(s)
            unique.append(p)
    return unique


def load_coins() -> list[str]:
    """
    Tenta ler coins.json.
    Se não existir, usa DEFAULT_COINS (lista oficial).
    """
    candidates = _candidate_files("COINS_FILE", "config/coins.json")
    for fp in candidates:
        if fp.exists():
            data = _safe_read_json(fp)
            if isinstance(data, dict) and isinstance(data.get("coins"), list):
                coins = [str(x).strip().upper() for x in data["coins"] if str(x).strip()]
                coins = sorted(set(coins))
                if coins:
                    return coins

    # fallback garantido
    return DEFAULT_COINS.copy()


def load_settings() -> dict:
    candidates = _candidate_files("SETTINGS_FILE", "config/settings.json")
    for fp in candidates:
        if fp.exists():
            data = _safe_read_json(fp)
            if isinstance(data, dict):
                return data
    return {}


def _env_float(key: str, default: float) -> float:
    v = os.getenv(key, "").strip().replace(",", ".")
    try:
        return float(v) if v else float(default)
    except Exception:
        return float(default)


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def now_brt_str() -> str:
    if ZoneInfo is None:
        # fallback simples
        return datetime.now().strftime("%H:%M")
    tz = ZoneInfo(BRT_TZ_NAME)
    return datetime.now(tz).strftime("%H:%M")


# ====== CONFIG PRINCIPAL (exportado) ======
SETTINGS = load_settings()

COINS = load_coins()

# DATA_DIR precisa existir
DATA_DIR = os.getenv("DATA_DIR", "/workspace/data")
Path(DATA_DIR).mkdir(parents=True, exist_ok=True)

# regra do projeto: lucro mínimo ~ 3% (default)
GAIN_MIN_PCT = _env_float("GAIN_MIN_PCT", float(SETTINGS.get("gain_min_pct", 3.0)))
