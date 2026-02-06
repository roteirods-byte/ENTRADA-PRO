# worker/worker_pro.py  (GERADOR COMPLETO - SINAIS + COLUNAS)
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Optional

from engine.config import COINS, DATA_DIR, GAIN_MIN_PCT, now_utc_iso, now_brt_str
from engine.exchanges import binance_mark_last, binance_klines, bybit_mark_last
from engine.compute import build_signal
from engine.io import atomic_write_json

# arquivos de saída (lidos pela API / painéis)
OUT_FILE = Path(os.getenv("PRO_JSON", str(Path(DATA_DIR) / "pro.json")))
TOP10_FILE = Path(os.getenv("TOP10_JSON", str(Path(DATA_DIR) / "top10.json")))

# intervalo (segundos). Padrão: 300 (5 min)
INTERVAL_S = int(os.getenv("WORKER_INTERVAL_S", "300"))

def log(msg: str) -> None:
    print(f"[WORKER_PRO] {msg}", flush=True)

def _sym(par: str) -> str:
    # FUTURO PERP USDT (linear)
    return f"{par.upper()}USDT"

def _safe_mark(symbol: str) -> tuple[Optional[float], str]:
    # tenta Binance primeiro, depois Bybit
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

def _safe_ohlc(symbol: str) -> Optional[List[List[float]]]:
    # usa 4h (painel Swing/PRO)
    try:
        return binance_klines(symbol, interval="4h", limit=220)
    except Exception:
        return None

def build_payload() -> Dict:
    updated_at = now_utc_iso()
    now_brt = now_brt_str()

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
                "alvo": 0.0,
                "ganho_pct": 0.0,
                "assert_pct": 0.0,
                "prazo": "-",
                "zona": "ALTA",
                "risco": "ALTO",
                "prioridade": "BAIXA",
                "price_source": src,
            })
            continue

        ohlc = _safe_ohlc(symbol)
        if not ohlc:
            miss_count += 1
            items.append({
                "par": par,
                "side": "NÃO ENTRAR",
                "atual": float(mark),
                "alvo": float(mark),
                "ganho_pct": 0.0,
                "assert_pct": 0.0,
                "prazo": "-",
                "zona": "ALTA",
                "risco": "ALTO",
                "prioridade": "BAIXA",
                "price_source": src,
            })
            continue

        sig = build_signal(par=par, ohlc=ohlc, mark_price=float(mark), gain_min_pct=float(GAIN_MIN_PCT))

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
            "price_source": src,
        })
        ok_count += 1

    # ordena por par (alfabético)
    items.sort(key=lambda x: (x.get("par") or ""))

    payload = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": now_brt,
        "items": items,
    }

    # top10: pega só quem tem sinal (LONG/SHORT) e ordena por ganho_pct
    sigs = [it for it in items if it.get("side") in ("LONG", "SHORT")]
    sigs.sort(key=lambda x: float(x.get("ganho_pct") or 0.0), reverse=True)
    top10 = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": now_brt,
        "items": sigs[:10],
    }

    log(f"OK | coins={len(COINS)} ok={ok_count} missing={miss_count}")
    return payload, top10

def main_loop() -> None:
    log(f"START | OUT_FILE={OUT_FILE} | TOP10_FILE={TOP10_FILE} | INTERVAL_S={INTERVAL_S} | COINS={len(COINS)}")
    while True:
        try:
            payload, top10 = build_payload()
            atomic_write_json(OUT_FILE, payload)
            atomic_write_json(TOP10_FILE, top10)
            log("WROTE pro.json + top10.json")
        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")
        time.sleep(INTERVAL_S)

if __name__ == "__main__":
    main_loop()
