from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.config import COINS, DATA_DIR, GAIN_MIN_PCT, ASSERT_MIN_PCT, now_utc_iso, now_brt_str
from engine.exchanges import binance_mark_last, binance_klines, bybit_mark_last
from engine.compute import build_signal
from engine.io import atomic_write_json

OUT_FILE = Path(os.getenv("PRO_JSON", str(Path(DATA_DIR) / "pro.json")))
TOP10_FILE = Path(os.getenv("TOP10_JSON", str(Path(DATA_DIR) / "top10.json")))
INTERVAL_S = int(os.getenv("WORKER_INTERVAL_S", "300"))

def log(msg: str) -> None:
    print(f"[WORKER_PRO] {msg}", flush=True)

def _sym(par: str) -> str:
    return f"{par.upper()}USDT"

def _safe_mark(symbol: str) -> Tuple[Optional[float], str]:
    try:
        j = binance_mark_last(symbol)
        return float(j["mark"]), "BINANCE"
    except Exception:
        pass
    try:
        j = bybit_mark_last(symbol)
        return float(j["mark"]), "BYBIT"
    except Exception:
        return None, "NONE"

def _safe_klines_1h(symbol: str) -> Optional[List[List[float]]]:
    try:
        return binance_klines(symbol, interval="1h", limit=260)
    except Exception:
        return None

def _safe_klines_4h(symbol: str) -> Optional[List[List[float]]]:
    try:
        return binance_klines(symbol, interval="4h", limit=260)
    except Exception:
        return None

def _norm(s: str) -> str:
    return str(s or "").upper().replace("É","E").replace("Í","I").replace("Ó","O").replace("Á","A").replace("Ã","A").replace("Ç","C")

def _pts_zona(z: str) -> int:
    z = _norm(z)
    if z == "ALTA": return 3
    if z == "MEDIA": return 2
    return 1

def _pts_risco(r: str) -> int:
    r = _norm(r)
    if r == "BAIXO": return 3
    if r == "MEDIO": return 2
    return 1

def _pts_prio(p: str) -> int:
    p = _norm(p)
    if p == "ALTA": return 3
    if p == "MEDIA": return 2
    return 1

def build_payload() -> Tuple[Dict, Dict]:
    updated_at = now_utc_iso()
    now_brt = now_brt_str()
    _data, _hora = (now_brt.split(" ", 1) + [""])[:2]

    items = []
    ok_count = 0
    miss_count = 0

    for par in COINS:
        symbol = _sym(par)
        mark, src = _safe_mark(symbol)

        if mark is None:
            miss_count += 1
            items.append({
                "par": par,
                "side": "NÃO ENTRAR",
                "atual": 0.0,
                "alvo": None,
                "ganho_pct": None,
                "assert_pct": None,
                "prazo": "",
                "zona": "",
                "risco": "",
                "prioridade": "",
                "data": _data,
                "hora": _hora,
                "price_source": src,
            })
            continue

        ohlc_1h = _safe_klines_1h(symbol)
        ohlc_4h = _safe_klines_4h(symbol)

        if (not ohlc_1h) or (not ohlc_4h):
            miss_count += 1
            items.append({
                "par": par,
                "side": "NÃO ENTRAR",
                "atual": float(mark),
                "alvo": None,
                "ganho_pct": None,
                "assert_pct": None,
                "prazo": "",
                "zona": "",
                "risco": "",
                "prioridade": "",
                "data": _data,
                "hora": _hora,
                "price_source": src,
            })
            continue

        sig = build_signal(
            par=par,
            ohlc_1h=ohlc_1h,
            ohlc_4h=ohlc_4h,
            mark_price=float(mark),
            gain_min_pct=float(GAIN_MIN_PCT),
            assert_min_pct=float(ASSERT_MIN_PCT),
        )

        if sig.side == "NÃO ENTRAR":
            items.append({
                "par": sig.par,
                "side": "NÃO ENTRAR",
                "atual": float(sig.atual),
                "alvo": None,
                "ganho_pct": None,
                "assert_pct": None,
                # ✅ regra oficial: vazio nessas colunas
                "prazo": "",
                "zona": "",
                "risco": "",
                "prioridade": "",
                "data": _data,
                "hora": _hora,
                "price_source": src,
            })
        else:
            items.append({
                "par": sig.par,
                "side": sig.side,
                "atual": float(sig.atual),
                "alvo": float(sig.alvo),
                "ganho_pct": float(sig.ganho_pct),
                "assert_pct": float(sig.assert_pct),
                "prazo": sig.prazo,
                "zona": sig.zona,
                "risco": sig.risco,
                "prioridade": sig.prioridade,
                "data": _data,
                "hora": _hora,
                "price_source": src,
            })
            ok_count += 1

    items.sort(key=lambda x: (x.get("par") or ""))

    payload = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": now_brt,
        "items": items,
    }

    # TOP10: pontos -> assert -> ganho -> par
    cand = []
    for it in items:
        if it.get("side") not in ("LONG", "SHORT"):
            continue
        g = float(it.get("ganho_pct") or 0.0)
        a = float(it.get("assert_pct") or 0.0)
        if g < float(GAIN_MIN_PCT):
            continue
        if a < float(ASSERT_MIN_PCT):
            continue
        pts = _pts_zona(it.get("zona")) + _pts_risco(it.get("risco")) + _pts_prio(it.get("prioridade"))
        it2 = dict(it)
        it2["rank_pts"] = int(pts)  # debug
        cand.append(it2)

    cand.sort(key=lambda x: (
        -int(x.get("rank_pts") or 0),
        -float(x.get("assert_pct") or 0.0),
        -float(x.get("ganho_pct") or 0.0),
        str(x.get("par") or "")
    ))
    top10 = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": now_brt,
        "items": cand[:10],
    }

    log(f"OK | coins={len(COINS)} ok={ok_count} missing={miss_count} gain_min={GAIN_MIN_PCT} assert_min={ASSERT_MIN_PCT}")
    return payload, top10

def main():
    while True:
        try:
            payload, top10 = build_payload()
            atomic_write_json(OUT_FILE, payload)
            atomic_write_json(TOP10_FILE, top10)
        except Exception as e:
            log(f"ERRO: {e}")
        time.sleep(INTERVAL_S)

if __name__ == "__main__":
    main()
