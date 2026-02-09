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
<<<<<<< Updated upstream
    # top10: NOVA REGRA (ranking por pontuação de cores)
=======
    # top10: NOVA REGRA (PONTOS/CORES)
    # - entra no ranking: LONG/SHORT e GANHO >= GAIN_MIN_PCT
    # - ordena: PONTOS(desc) -> ASSERT(desc) -> GANHO(desc) -> PAR(asc)
    def _norm(x):
        return str(x or "").upper().replace("É","E").replace("Í","I").replace("Ó","O").replace("Á","A").replace("Ã","A").replace("Ç","C")

    def _pts_zone(z):
        z=_norm(z)
        if z=="BAIXA": return 3
        if z=="MEDIA": return 2
        return 1  # ALTA/qualquer

    def _pts_risk(r):
        r=_norm(r)
        if r=="BAIXO": return 3
        if r=="MEDIO": return 2
        return 1  # ALTO/qualquer

    def _pts_prio(p):
        p=_norm(p)
        if p=="ALTA": return 3
        if p=="MEDIA": return 2
        return 1  # BAIXA/qualquer

    def _top10_select(items):
        cand=[]
        for it in items:
            if it.get("side") not in ("LONG","SHORT"):
                continue
            ganho=float(it.get("ganho_pct") or 0.0)
            if ganho < float(GAIN_MIN_PCT):
                continue

            pts = _pts_zone(it.get("zona")) + _pts_risk(it.get("risco")) + _pts_prio(it.get("prioridade"))
            it2 = dict(it)
            it2["rank_pts"] = int(pts)  # debug (nao quebra o painel)
            cand.append(it2)

        cand.sort(key=lambda x: (
            -int(x.get("rank_pts") or 0),
            -float(x.get("assert_pct") or 0.0),
            -float(x.get("ganho_pct") or 0.0),
            str(x.get("par") or "")
        ))
        return cand[:10]

>>>>>>> Stashed changes
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

# ===== TOP10 (regra por cores) =====
def _col_gain(ganho_pct: float) -> str:
    return "G" if float(ganho_pct or 0.0) >= float(GAIN_MIN_PCT) else "R"

def _col_assert(assert_pct: float) -> str:
    a = float(assert_pct or 0.0)
    if a <= 0.0:
        return "R"  # sem dado
    return "G" if a >= 65.0 else "Y"  # sua regra: <65 = amarelo

def _col_zona(z: str) -> str:
    z = str(z or "").upper()
    if z == "BAIXA": return "G"
    if z in ("MÉDIA","MEDIA"): return "Y"
    return "R"  # ALTA

def _col_risco(r: str) -> str:
    r = str(r or "").upper()
    if r == "BAIXO": return "G"
    if r in ("MÉDIO","MEDIO"): return "Y"
    return "R"  # ALTO

def _col_prioridade(p: str) -> str:
    p = str(p or "").upper()
    if p == "ALTA": return "G"
    if p in ("MÉDIA","MEDIA"): return "Y"
    return "R"  # BAIXA

def _top10_select(items):
    # TOP10 por SCORE (sua planilha):
    # ZONA: BAIXA=3, MÉDIA=2, ALTA=1
    # RISCO: BAIXO=3, MÉDIO=2, ALTO=1
    # PRIORIDADE: ALTA=3, MÉDIA=2, BAIXA=1
    # Ordena: SCORE desc, depois ASSERT desc, depois GANHO desc

    def p_zona(z):
        z = str(z or "").upper()
        if z == "BAIXA": return 3
        if z in ("MÉDIA","MEDIA"): return 2
        return 1  # ALTA

    def p_risco(r):
        r = str(r or "").upper()
        if r == "BAIXO": return 3
        if r in ("MÉDIO","MEDIO"): return 2
        return 1  # ALTO

    def p_prio(p):
        p = str(p or "").upper()
        if p == "ALTA": return 3
        if p in ("MÉDIA","MEDIA"): return 2
        return 1  # BAIXA

    cand = []
    for it in items:
        if it.get("side") not in ("LONG","SHORT"):
            continue

        ganho = float(it.get("ganho_pct") or 0.0)
        if ganho < float(GAIN_MIN_PCT):
            continue

        score = p_zona(it.get("zona")) + p_risco(it.get("risco")) + p_prio(it.get("prioridade"))
        ass = float(it.get("assert_pct") or 0.0)

        cand.append((score, ass, ganho, it))

    cand.sort(key=lambda x: (x[0], x[1], x[2]), reverse=True)
    return [x[3] for x in cand[:10]]



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
