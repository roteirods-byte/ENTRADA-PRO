# worker/worker_pro.py  (GERADOR COMPLETO - SINAIS + FULL + TOP10)
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from engine.config import COINS, DATA_DIR, now_utc_iso, now_brt_str
from engine.exchanges import binance_mark_last, binance_klines, bybit_mark_last
from engine.compute import build_signal
from engine.io import atomic_write_json
from engine.audit import log_prices, log_signals

# arquivos de saída (lidos pela API / painéis)
OUT_FILE  = Path(os.getenv("PRO_JSON",  str(Path(DATA_DIR) / "pro.json")))
TOP10_FILE = Path(os.getenv("TOP10_JSON", str(Path(DATA_DIR) / "top10.json")))

# intervalo (segundos). Padrão: 300 (5 min)
INTERVAL_S = int(os.getenv("WORKER_INTERVAL_S", "300"))

# ===== FILTRO OFICIAL (ATUAL) =====
# FULL: se não bater os mínimos => "NÃO ENTRAR"
FULL_GAIN_MIN_PCT   = float(os.getenv("FULL_GAIN_MIN_PCT",  "2.0"))
FULL_ASSERT_MIN_PCT = float(os.getenv("FULL_ASSERT_MIN_PCT","55.0"))

def log(msg: str) -> None:
    print(f"[WORKER_PRO] {msg}", flush=True)

def _sym(par: str) -> str:
    return f"{par.upper()}USDT"

def _safe_mark(symbol: str) -> Tuple[Optional[float], str]:
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

def _safe_ohlc(symbol: str, interval: str) -> Optional[List[List[float]]]:
    try:
        return binance_klines(symbol, interval=interval, limit=220)
    except Exception:
        return None

def _norm(x) -> str:
    return str(x or "").upper().replace("É","E").replace("Í","I").replace("Ó","O").replace("Á","A").replace("Ã","A").replace("Ç","C")

# ===== PONTUAÇÃO (CORES) =====
# VERDE=3, AMARELO/LARANJA=2, VERMELHO=1
def _pts_zona(z: str) -> int:
    z = _norm(z)
    if z == "ALTA":  return 3
    if z == "MEDIA": return 2
    return 1  # BAIXA/qualquer

def _pts_risco(r: str) -> int:
    r = _norm(r)
    if r == "BAIXO": return 3
    if r == "MEDIO": return 2
    return 1  # ALTO/qualquer

def _pts_prioridade(p: str) -> int:
    p = _norm(p)
    if p == "ALTA":  return 3
    if p == "MEDIA": return 2
    return 1  # BAIXA/qualquer

def build_payload() -> Tuple[Dict, Dict]:
    updated_at = now_utc_iso()
    now_brt = now_brt_str()
    _date, _time = (now_brt.split(" ")[0], now_brt.split(" ")[1] if " " in now_brt else "")

    def _mk_no(par: str, atual: float, src: str) -> Dict:
        # regra: NÃO ENTRAR preenche só PAR, SIDE, ATUAL, DATA, HORA
        return {
            "par": par,
            "side": "NÃO ENTRAR",
            "atual": (None if atual is None else float(atual)),
            "nao_entrar_motivo": None,
            "ttl_expira_em": None,
            "data": _date,
            "hora": _time,
            "alvo": None,
            "ganho_pct": None,
            "assert_pct": None,
            "prazo": None,
            "zona": None,
            "risco": None,
            "prioridade": None,
            "price_source": src,
        }

    items: List[Dict] = []
    ok_count = 0
    miss_count = 0

    for par in COINS:
        symbol = _sym(par)

        mark, src = _safe_mark(symbol)
        if mark is None:
            miss_count += 1
            x=_mk_no(par, None, src)
            x["nao_entrar_motivo"]="sem_mark"
            items.append(x)
            continue

        ohlc_1h = _safe_ohlc(symbol, "1h")
        ohlc_4h = _safe_ohlc(symbol, "4h")
        if (not ohlc_1h) or (not ohlc_4h):
            miss_count += 1
            items.append(_mk_no(par, float(mark), src))
            continue

        # IMPORTANTÍSSIMO: roda o build_signal sem filtro interno
        sig = build_signal(par=par, ohlc_1h=ohlc_1h, ohlc_4h=ohlc_4h, mark_price=float(mark), gain_min_pct=0.0)

        ganho = float(getattr(sig, "ganho_pct", 0.0) or 0.0)
        ass   = float(getattr(sig, "assert_pct", 0.0) or 0.0)

        # FILTRO FULL (55% / 2%)
        if (ass < FULL_ASSERT_MIN_PCT) or (ganho < FULL_GAIN_MIN_PCT):
            sig.side = "NÃO ENTRAR"

        if sig.side not in ("LONG", "SHORT"):
            items.append(_mk_no(sig.par, float(sig.atual), src))
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
                "data": _date,
                "hora": _time,
                "price_source": src,
            })
        ok_count += 1

    # FULL ordenado por par
    items.sort(key=lambda x: (x.get("par") or ""))

    payload = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": now_brt,
        "items": items,
    }

    # TOP10 = recorte do FULL já filtrado (LONG/SHORT) e ordenado por pontos
    cand = []
    for it in items:
        if it.get("side") not in ("LONG", "SHORT"):
            continue
        pts = _pts_zona(it.get("zona")) + _pts_risco(it.get("risco")) + _pts_prioridade(it.get("prioridade"))
        it2 = dict(it)
        it2["rank_pts"] = int(pts)
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

    # auditoria (não pode derrubar o worker)
    try:
        log_prices(top10["items"], updated_at=updated_at)
        log_signals(top10["items"], updated_at=updated_at, gain_min_pct=FULL_GAIN_MIN_PCT)
    except Exception:
        pass

    log(f"OK | coins={len(COINS)} ok={ok_count} missing={miss_count} | FULL(min_gain={FULL_GAIN_MIN_PCT} min_assert={FULL_ASSERT_MIN_PCT}) | TOP10={len(top10['items'])}")
    return payload, top10

def main():
    log(f"START | OUT_FILE={OUT_FILE} | TOP10_FILE={TOP10_FILE} | INTERVAL_S={INTERVAL_S} | COINS={len(COINS)}")
    while True:
        try:
            p, t = build_payload()
            atomic_write_json(OUT_FILE, p)
            atomic_write_json(TOP10_FILE, t)
            log("WROTE pro.json + top10.json")
        except Exception as e:
            log(f"ERROR: {e!r}")
        time.sleep(INTERVAL_S)

if __name__ == "__main__":
    main()
