# engine/config.py
import json
import os
from typing import List

# Default thresholds (can be overridden by settings.json)
# ENTRADA-PRO: defaults seguem o contrato do BLOCO 1 (55/2).
DEFAULT_GAIN_MIN_PCT = float(os.getenv("GAIN_MIN_PCT", "2"))
DEFAULT_ASSERT_MIN_PCT = float(os.getenv("ASSERT_MIN_PCT", "55"))

# Default coins (can be overridden by settings.json)
DEFAULT_COINS = [
  "AAVE","ADA","APE","APT","AR","ARB","ATOM","AVAX","AXS","BAT","BCH","BLUR","BNB","BONK","BTC","COMP","CRV","DOGE","DOT","DYDX",
  "EGLD","EOS","ETH","FET","FIL","FTM","GALA","GRT","ICP","INJ","JTO","KAVA","KSM","LDO","LINK","LTC","MATIC","NEAR","OP",
  "PEPE","POL","RATS","RENDER","RNDR","RUNE","SEI","SHIB","SOL","SUI","TIA","TON","TRX","UNI","WIF","XRP","XLM","XTZ"
]

def _try_load_json(paths: List[str]) -> dict:
    for p in paths:
        if not p:
            continue
        try:
            if os.path.isfile(p):
                with open(p, "r", encoding="utf-8") as f:
                    return json.load(f) or {}
        except Exception:
            continue
    return {}


def load_settings(path: str | None = None):
    """Load settings.json.

    Motivação: no deploy, o arquivo pode estar em locais diferentes.
    Preferência:
    1) SETTINGS_JSON env (se setado)
    2) ./worker/config/settings.json (repo)
    3) /opt/ENTRADA-PRO/config/settings.json (deploy antigo)
    4) /opt/ENTRADA-PRO/worker/config/settings.json (deploy alternativo)
    """
    here = os.path.dirname(os.path.dirname(__file__))  # worker/
    repo_settings = os.path.join(here, "config", "settings.json")

    env_path = os.getenv("SETTINGS_JSON")
    paths = [path, env_path, repo_settings, "/opt/ENTRADA-PRO/config/settings.json", "/opt/ENTRADA-PRO/worker/config/settings.json"]
    return _try_load_json(paths)

def get_thresholds(settings: dict):
    gain = float(settings.get("gain_min_pct", DEFAULT_GAIN_MIN_PCT))
    assert_min = float(settings.get("assert_min_pct", DEFAULT_ASSERT_MIN_PCT))
    return gain, assert_min

def get_coins(settings: dict) -> List[str]:
    # 1) coins dentro do próprio settings.json
    coins = settings.get("coins") or settings.get("COINS") or None
    if coins and isinstance(coins, list) and all(isinstance(x, str) for x in coins):
        return coins

    # 2) coins.json (repo ou deploy)
    here = os.path.dirname(os.path.dirname(__file__))  # worker/
    repo_coins = os.path.join(here, "config", "coins.json")
    coins_obj = _try_load_json([os.getenv("COINS_JSON"), repo_coins, "/opt/ENTRADA-PRO/config/coins.json", "/opt/ENTRADA-PRO/worker/config/coins.json"])
    lst = coins_obj.get("coins") if isinstance(coins_obj, dict) else None
    if lst and isinstance(lst, list) and all(isinstance(x, str) for x in lst):
        return lst

    return DEFAULT_COINS

# --- BLOCO4 (AUDITORIA) compat ---
from datetime import datetime
from zoneinfo import ZoneInfo

# diretório base de dados (padrão do deploy)
DATA_DIR = os.getenv("DATA_DIR", "/opt/ENTRADA-PRO/data")

# mínimo de ganho usado na auditoria (padrão 2%)
GAIN_MIN_PCT = float(os.getenv("GAIN_MIN_PCT", str(DEFAULT_GAIN_MIN_PCT)))

def now_brt_str() -> str:
    """Retorna agora em BRT no formato YYYY-MM-DD HH:MM"""
    tz = ZoneInfo("America/Sao_Paulo")
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M")
