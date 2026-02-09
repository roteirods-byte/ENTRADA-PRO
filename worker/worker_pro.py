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

# ===== TOP10 (ranking por pontuação de cores) =====
def _pts_zona(z: str) -> int:
    z = str(z or "").upper()
    if z == "BAIXA":
        return 3
    if z in ("MÉDIA", "MEDIA"):
        return 2
    return 1  # ALTA

def _pts_risco(r: str) -> int:
    r = str(r or "").upper()
    if r == "BAIXO":
        return 3
    if r in ("MÉDIO", "MEDIO"):
        return 2
    return 1  # ALTO

def _pts_prioridade(p: str) -> int:
    p = str(p or "").upper()
    if p == "ALTA":
        return 3
    if p in ("MÉDIA", "MEDIA"):
        return 2
    return 1  # BAIXA

def _top10_select(items):
    """TOP10 = ranking (não é sinal de operação).
    Regras:
      - entra no ranking se SIDE for LONG/SHORT e GANHO% >= GAIN_MIN_PCT
      - pontuação = ZONA + RISCO + PRIORIDADE (verde=3, amarelo=2, vermelho=1)
      - desempate: maior ASSERT%, depois maior GANHO%
    """
    cand = []
    for it in items:
        if it.get("side") not in ("LONG", "SHORT"):
            continue

        ganho = float(it.get("ganho_pct") or 0.0)
        if ganho < float(GAIN_MIN_PCT):
            continue

        pts = _pts_zona(it.get("zona")) + _pts_risco(it.get("risco")) + _pts_prioridade(it.get("prioridade"))
        ass = float(it.get("assert_pct") or 0.0)
        cand.append((pts, ass, ganho, it))

    # ordena: mais pontos primeiro; depois maior assert; depois maior ganho
    cand.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
    return [t[3] for t in cand[:10]]


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
    # top10: NOVA REGRA (ranking por pontuação de cores)
    top_items = _top10_select(items)
    top10 = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": now_brt,
        "items": top_items,
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
