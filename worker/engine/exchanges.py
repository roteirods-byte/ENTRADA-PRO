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


def bybit_klines(symbol: str, interval: str = "4h", limit: int = 200) -> List[List[float]]:
    """Bybit v5 kline.

    interval na API é em minutos (string): 1,3,5,15,30,60,120,240,360,720,D,W,M.
    Vamos mapear os intervalos que usamos no worker.
    """
    map_iv = {
        "1m": "1",
        "3m": "3",
        "5m": "5",
        "15m": "15",
        "30m": "30",
        "1h": "60",
        "2h": "120",
        "4h": "240",
        "6h": "360",
        "12h": "720",
        "1d": "D",
    }
    iv = map_iv.get(interval, interval)
    j = _get_json(
        f"{BYBIT_BASE}/v5/market/kline",
        {"category": "linear", "symbol": symbol, "interval": iv, "limit": int(limit)},
        timeout=15,
    )
    lst = (j.get("result") or {}).get("list") or []
    # Bybit retorna mais novo -> mais velho. Vamos inverter para oldest->newest.
    out: List[List[float]] = []
    for k in reversed(lst):
        # [startTime, open, high, low, close, volume, turnover]
        out.append([float(k[1]), float(k[2]), float(k[3]), float(k[4])])
    return out


def fetch_mark_price(symbol: str, source: str = "BINANCE", timeout: int = 10) -> float:
    """Wrapper usado pelo worker (retorna apenas o mark price)."""
    source = (source or "").upper()
    if source == "BYBIT":
        return float(bybit_mark_last(symbol).get("mark"))
    return float(binance_mark_last(symbol).get("mark"))


def fetch_klines(symbol: str, interval: str = "4h", limit: int = 200, source: str = "BINANCE", timeout: int = 15):
    """Wrapper usado pelo worker (retorna lista [o,h,l,c])."""
    source = (source or "").upper()
    if source == "BYBIT":
        return bybit_klines(symbol, interval=interval, limit=limit)
    return binance_klines(symbol, interval=interval, limit=limit)
