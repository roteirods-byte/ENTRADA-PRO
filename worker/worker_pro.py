from __future__ import annotations

import sys, time
from pathlib import Path
from typing import Dict, List

from engine.config import COINS, DATA_DIR, GAIN_MIN_PCT, now_utc_iso, now_brt_str
from engine.io import atomic_write_json
from engine.exchanges import binance_mark_last, bybit_mark_last, binance_klines
from engine.compute import build_signal, Signal

def par_to_symbol_usdt(par: str) -> str:
    # Futures symbols are usually like BTCUSDT
    p = par.strip().upper().replace("USDT","")
    return f"{p}USDT"

def safe_fetch_symbol(symbol: str) -> Dict[str, float]:
    # Try Binance first, fallback Bybit
    try:
        return binance_mark_last(symbol)
    except Exception:
        return bybit_mark_last(symbol)

def safe_fetch_ohlc(symbol: str) -> List[List[float]]:
    # Use Binance klines for consistency; if fails, raise (we'll mark coin as NA)
    return binance_klines(symbol, interval="4h", limit=220)

def signal_to_row(sig: Signal) -> Dict:
    return {
        "PAR": sig.par,
        "SIDE": sig.side,
        "MODO": sig.mode,
        "ENTRADA": round(sig.entrada, 6),
        "ATUAL": round(sig.atual, 6),
        "ALVO": round(sig.alvo, 6),
        "GANHO_PCT": round(sig.ganho_pct, 2),
        "PRAZO": sig.prazo,
        "ASSERT_PCT": round(sig.assert_pct, 2),
        "RISCO": sig.risco,
        "PRIORIDADE": sig.prioridade,
        "ZONA": sig.zona,
        "PRICE_SOURCE": sig.price_source,
    }

def main() -> int:
    rows=[]
    errors=[]
    for par in COINS:
        symbol = par_to_symbol_usdt(par)
        try:
            px = safe_fetch_symbol(symbol)
            mark = float(px["mark"])
            ohlc = safe_fetch_ohlc(symbol)
            sig = build_signal(par, ohlc, mark, GAIN_MIN_PCT)
            rows.append(signal_to_row(sig))
        except Exception as e:
            rows.append({
                "PAR": par,
                "SIDE": "NÃO ENTRAR",
                "MODO": "PRO",
                "ENTRADA": 0,
                "ATUAL": 0,
                "ALVO": 0,
                "GANHO_PCT": 0,
                "PRAZO": "-",
                "ASSERT_PCT": 0,
                "RISCO": "ALTO",
                "PRIORIDADE": "BAIXA",
                "ZONA": "ALTA",
                "PRICE_SOURCE": "MARK",
                "ERROR": str(e),
            })
            errors.append({"PAR": par, "symbol": symbol, "error": str(e)})

    # top10: only entries (not NÃO ENTRAR) and gain>=3 already enforced
    candidates=[r for r in rows if r.get("SIDE") in ("LONG","SHORT")]
    candidates.sort(key=lambda r: (r.get("ASSERT_PCT",0), r.get("GANHO_PCT",0)), reverse=True)
    top10=candidates[:10]

    pro_obj={
        "ok": True,
        "service": "entrada-pro-worker",
        "updated_utc": now_utc_iso(),
        "updated_brt": now_brt_str(),
        "count": len(rows),
        "items": rows
    }
    top_obj={
        "ok": True,
        "service": "entrada-pro-worker",
        "updated_utc": now_utc_iso(),
        "updated_brt": now_brt_str(),
        "count": len(top10),
        "items": top10
    }
    audit_obj={
        "ok": True,
        "updated_utc": now_utc_iso(),
        "updated_brt": now_brt_str(),
        "counts": {"pro": len(rows), "top10": len(top10)},
        "rules": {"gain_min_pct": GAIN_MIN_PCT, "price_base": "MARK_PRICE"},
        "errors": errors[:50],
    }

    data_dir = Path(DATA_DIR)
    atomic_write_json(data_dir/"pro.json", pro_obj)
    atomic_write_json(data_dir/"top10.json", top_obj)
    atomic_write_json(data_dir/"audit.json", audit_obj)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
