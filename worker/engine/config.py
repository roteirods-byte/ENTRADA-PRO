# engine/config.py
import json
import os
from typing import List

# Default thresholds (can be overridden by settings.json)
DEFAULT_GAIN_MIN_PCT = float(os.getenv("GAIN_MIN_PCT", "3"))
DEFAULT_ASSERT_MIN_PCT = float(os.getenv("ASSERT_MIN_PCT", "65"))

# Default coins (can be overridden by settings.json)
DEFAULT_COINS = [
  "AAVE","ADA","APE","APT","AR","ARB","ATOM","AVAX","AXS","BAT","BCH","BLUR","BNB","BONK","BTC","COMP","CRV","DOGE","DOT","DYDX",
  "EGLD","EOS","ETH","FET","FIL","FTM","GALA","GRT","ICP","INJ","JTO","KAVA","KSM","LDO","LINK","LTC","MATIC","NEAR","OP",
  "PEPE","POL","RATS","RENDER","RNDR","RUNE","SEI","SHIB","SOL","SUI","TIA","TON","TRX","UNI","WIF","XRP","XLM","XTZ"
]

def load_settings(path: str = None):
    """Load optional settings.json (same dir as worker by default)."""
    if path is None:
        path = os.getenv("SETTINGS_JSON", "/opt/ENTRADA-PRO/config/settings.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f) or {}
    except Exception:
        return {}

def get_thresholds(settings: dict):
    gain = float(settings.get("gain_min_pct", DEFAULT_GAIN_MIN_PCT))
    assert_min = float(settings.get("assert_min_pct", DEFAULT_ASSERT_MIN_PCT))
    return gain, assert_min

def get_coins(settings: dict) -> List[str]:
    coins = settings.get("coins") or settings.get("COINS") or None
    if coins and isinstance(coins, list) and all(isinstance(x,str) for x in coins):
        return coins
    return DEFAULT_COINS
