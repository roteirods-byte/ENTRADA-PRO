from __future__ import annotations
import os, time
from pathlib import Path
from datetime import datetime

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from engine.config import COINS, DATA_DIR, GAIN_MIN_PCT, ASSERT_MIN_PCT, now_utc_iso
from engine.exchanges import binance_mark_last, binance_klines, bybit_mark_last
from engine.compute import build_signal
from engine.io import atomic_write_json

OUT_FILE = Path(os.getenv("PRO_JSON", str(Path(DATA_DIR) / "pro.json")))
TOP10_FILE = Path(os.getenv("TOP10_JSON", str(Path(DATA_DIR) / "top10.json")))
INTERVAL_S = int(os.getenv("WORKER_INTERVAL_S", "300"))

def log(msg: str) -> None:
    print(f"[WORKER_PRO] {msg}", flush=True)

def brt_data_hora():
    if ZoneInfo:
        dt = datetime.now(ZoneInfo("America/Sao_Paulo"))
    else:
        dt = datetime.utcnow()
    return dt.strftime("%d/%m/%Y"), dt.strftime("%H:%M")

def _sym(par: str) -> str:
    return f"{par.upper()}USDT"

def _safe_mark(symbol: str):
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

def _safe_klines(symbol: str, interval: str):
    try:
        return binance_klines(symbol, interval=interval, limit=260)
    except Exception:
        return None

def _norm(s):
    return str(s or "").upper().replace("É","E").replace("Ê","E").replace("Á","A").replace("Ã","A").replace("Ç","C").replace("Í","I").replace("Ó","O").replace("Õ","O").replace("Ú","U")

def _pts_z(z):  # ZONA: ALTA=3, MEDIA=2, BAIXA=1
    z=_norm(z)
    if z=="ALTA": return 3
    if z=="MEDIA": return 2
    return 1

def _pts_r(r):  # RISCO: BAIXO=3, MEDIO=2, ALTO=1
    r=_norm(r)
    if r=="BAIXO": return 3
    if r=="MEDIO": return 2
    return 1

def _pts_p(p):  # PRIORIDADE: ALTA=3, MEDIA=2, BAIXA=1
    p=_norm(p)
    if p=="ALTA": return 3
    if p=="MEDIA": return 2
    return 1

def build_payload():
    updated_at = now_utc_iso()
    data, hora = brt_data_hora()

    items = []
    ok_count = 0
    miss_count = 0

    for par in COINS:
        symbol = _sym(par)
        mark, src = _safe_mark(symbol)

        if mark is None:
            miss_count += 1
            items.append({
                "par": par, "side": "NÃO ENTRAR",
                "atual": 0.0, "alvo": None, "ganho_pct": None, "assert_pct": None,
                # ✅ regra oficial: vazios
                "prazo": "", "zona": "", "risco": "", "prioridade": "",
                "data": data, "hora": hora, "price_source": src
            })
            continue

        o1 = _safe_klines(symbol, "1h")
        o4 = _safe_klines(symbol, "4h")
        if (not o1) or (not o4):
            miss_count += 1
            items.append({
                "par": par, "side": "NÃO ENTRAR",
                "atual": float(mark), "alvo": None, "ganho_pct": None, "assert_pct": None,
                "prazo": "", "zona": "", "risco": "", "prioridade": "",
                "data": data, "hora": hora, "price_source": src
            })
            continue

        sig = build_signal(
            par=par, ohlc_1h=o1, ohlc_4h=o4, mark_price=float(mark),
            gain_min_pct=float(GAIN_MIN_PCT), assert_min_pct=float(ASSERT_MIN_PCT)
        )

        if sig.side == "NÃO ENTRAR":
            items.append({
                "par": sig.par, "side": "NÃO ENTRAR",
                "atual": float(sig.atual),
                "alvo": None, "ganho_pct": None, "assert_pct": None,
                # ✅ regra oficial: vazios
                "prazo": "", "zona": "", "risco": "", "prioridade": "",
                "data": data, "hora": hora, "price_source": src
            })
        else:
            items.append({
                "par": sig.par, "side": sig.side,
                "atual": float(sig.atual),
                "alvo": float(sig.alvo),
                "ganho_pct": float(sig.ganho_pct),
                "assert_pct": float(sig.assert_pct),
                "prazo": sig.prazo, "zona": sig.zona, "risco": sig.risco, "prioridade": sig.prioridade,
                "data": data, "hora": hora, "price_source": src
            })
            ok_count += 1

    items.sort(key=lambda x: (x.get("par") or ""))

    # TOP10 (pontos -> assert -> ganho -> par) + filtros oficiais
    cand = []
    for it in items:
        if it.get("side") not in ("LONG","SHORT"):
            continue
        g = float(it.get("ganho_pct") or 0.0)
        a = float(it.get("assert_pct") or 0.0)
        if g < float(GAIN_MIN_PCT): continue
        if a < float(ASSERT_MIN_PCT): continue
        pts = _pts_z(it.get("zona")) + _pts_r(it.get("risco")) + _pts_p(it.get("prioridade"))
        it2 = dict(it)
        it2["rank_pts"] = int(pts)
        cand.append(it2)

    cand.sort(key=lambda x: (-int(x.get("rank_pts") or 0), -float(x.get("assert_pct") or 0.0), -float(x.get("ganho_pct") or 0.0), str(x.get("par") or "")))

    payload = {"ok": True, "source": "local", "updated_at": updated_at, "items": items}
    top10 = {"ok": True, "source": "local", "updated_at": updated_at, "items": cand[:10]}

    log(f"OK | coins={len(COINS)} ok={ok_count} missing={miss_count} gain_min={GAIN_MIN_PCT} assert_min={ASSERT_MIN_PCT}")
    return payload, top10

def main_loop():
    while True:
        try:
            payload, top10 = build_payload()
            atomic_write_json(OUT_FILE, payload)
            atomic_write_json(TOP10_FILE, top10)
        except Exception as e:
            log(f"ERROR: {type(e).__name__}: {e}")
        time.sleep(INTERVAL_S)

if __name__ == "__main__":
    main_loop()
