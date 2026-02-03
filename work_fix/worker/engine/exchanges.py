from __future__ import annotations
import requests
from typing import Dict, List, Tuple, Optional

BINANCE_BASE = "https://fapi.binance.com"
BYBIT_BASE = "https://api.bybit.com"

def _get_json(url: str, params: dict, timeout: int = 10) -> dict:
    r = requests.get(url, params=params, timeout=timeout)
    r.raise_for_status()
    return r.json()

def binance_mark_last(symbol: str) -> Dict[str, float]:
    # premiumIndex endpoint returns markPrice, indexPrice, lastFundingRate, etc.
    j = _get_json(f"{BINANCE_BASE}/fapi/v1/premiumIndex", {"symbol": symbol}, timeout=10)
    return {
        "mark": float(j.get("markPrice")),
        "last": float(j.get("lastPrice")),
        "index": float(j.get("indexPrice")),
    }

def binance_klines(symbol: str, interval: str = "4h", limit: int = 200) -> List[List[float]]:
    j = _get_json(f"{BINANCE_BASE}/fapi/v1/klines", {"symbol": symbol, "interval": interval, "limit": limit}, timeout=15)
    # each kline: [openTime, open, high, low, close, volume, closeTime, ...]
    out=[]
    for k in j:
        out.append([float(k[1]), float(k[2]), float(k[3]), float(k[4])])
    return out

def bybit_mark_last(symbol: str) -> Dict[str, float]:
    j = _get_json(f"{BYBIT_BASE}/v5/market/tickers", {"category":"linear", "symbol": symbol}, timeout=10)
    lst = (j.get("result") or {}).get("list") or []
    if not lst:
        raise RuntimeError("bybit ticker empty")
    t = lst[0]
    return {
        "mark": float(t.get("markPrice")),
        "last": float(t.get("lastPrice")),
        "index": float(t.get("indexPrice")),
    }
