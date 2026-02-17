from __future__ import annotations

import os
import time
import re
from pathlib import Path
from datetime import datetime, timedelta

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

DEFAULT_TTL_HOURS = int(os.getenv("SIGNAL_TTL_HOURS", "6"))

def log(msg: str) -> None:
    print(f"[WORKER_PRO] {msg}", flush=True)

def brt_data_hora():
    if ZoneInfo:
        dt = datetime.now(ZoneInfo("America/Sao_Paulo"))
    else:
        # fallback (UTC) – melhor do que quebrar
        dt = datetime.utcnow()
    return dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")

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

def _parse_ttl_hours(prazo: str) -> int:
    # exemplos: "4-6h", "6h", "1-3H"
    s = str(prazo or "").strip().lower()
    if not s:
        return DEFAULT_TTL_HOURS
    m = re.findall(r"(\d+)", s)
    if not m:
        return DEFAULT_TTL_HOURS
    # pega o MAIOR número encontrado (mais conservador)
    try:
        return max(int(x) for x in m)
    except Exception:
        return DEFAULT_TTL_HOURS

def _mk_item_base(par: str, data: str, hora: str, src: str):
    return {
        "par": par,
        "data": data,
        "hora": hora,
        "price_source": src,
        # campos internos (não exibidos no painel)
        "nao_entrar_motivo": None,
        "ttl_expira_em": None,
    }

def _apply_filters_and_shape(item: dict) -> dict:
    # Regras oficiais:
    # - Só entra se ganho>=GAIN_MIN_PCT e assert>=ASSERT_MIN_PCT.
    # - Se NÃO ENTRAR: deixar vazio prazo/zona/risco/prioridade, mas manter ganho/assert quando existirem.
    side = item.get("side")
    if side in ("LONG","SHORT"):
        g = float(item.get("ganho_pct") or 0.0)
        a = float(item.get("assert_pct") or 0.0)
        if g < float(GAIN_MIN_PCT) or a < float(ASSERT_MIN_PCT):
            motivos = []
            if g < float(GAIN_MIN_PCT): motivos.append("ganho<min")
            if a < float(ASSERT_MIN_PCT): motivos.append("assert<min")
            item["side"] = "NÃO ENTRAR"
            item["alvo"] = None
            item["prazo"] = ""
            item["zona"] = ""
            item["risco"] = ""
            item["prioridade"] = ""
            item["nao_entrar_motivo"] = "+".join(motivos) if motivos else "filtro"
            item["ttl_expira_em"] = None
    return item

def build_payload():
    updated_at = now_utc_iso()
    data, hora = brt_data_hora()

    items = []
    ok_count = 0
    miss_count = 0

    for par in COINS:
        symbol = _sym(par)
        mark, src = _safe_mark(symbol)

        base = _mk_item_base(par, data, hora, src)

        if mark is None:
            miss_count += 1
            it = {
                **base,
                "side": "NÃO ENTRAR",
                "atual": None,
                "alvo": None,
                "ganho_pct": None,
                "assert_pct": None,
                "prazo": "",
                "zona": "",
                "risco": "",
                "prioridade": "",
            }
            it["nao_entrar_motivo"] = "sem_mark"
            items.append(it)
            continue

        o1 = _safe_klines(symbol, "1h")
        o4 = _safe_klines(symbol, "4h")
        if (not o1) or (not o4):
            miss_count += 1
            it = {
                **base,
                "side": "NÃO ENTRAR",
                "atual": float(mark),
                "alvo": None,
                "ganho_pct": None,
                "assert_pct": None,
                "prazo": "",
                "zona": "",
                "risco": "",
                "prioridade": "",
            }
            it["nao_entrar_motivo"] = "sem_klines"
            items.append(it)
            continue

        sig = build_signal(
            par=par,
            ohlc_1h=o1,
            ohlc_4h=o4,
            mark_price=float(mark),
            gain_min_pct=float(GAIN_MIN_PCT),
            assert_min_pct=float(ASSERT_MIN_PCT),
        )

        it = {
            **base,
            "par": sig.par,
            "side": sig.side,
            "atual": None if sig.atual is None else float(sig.atual),
            "alvo": None if sig.alvo is None else float(sig.alvo),
            "ganho_pct": None if sig.ganho_pct is None else float(sig.ganho_pct),
            "assert_pct": None if sig.assert_pct is None else float(sig.assert_pct),
            "prazo": sig.prazo or "",
            "zona": sig.zona or "",
            "risco": sig.risco or "",
            "prioridade": sig.prioridade or "",
            "price_source": src,
        }

        # TTL só para LONG/SHORT
        if it["side"] in ("LONG","SHORT"):
            ttl_h = _parse_ttl_hours(it.get("prazo"))
            exp = datetime.utcnow() + timedelta(hours=ttl_h)
            it["ttl_expira_em"] = exp.replace(microsecond=0).isoformat() + "Z"

        it = _apply_filters_and_shape(it)

        if it.get("side") in ("LONG","SHORT"):
            ok_count += 1

        items.append(it)

    # ordena para FULL
    items.sort(key=lambda x: (x.get("par") or ""))

    payload = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": f"{data} {hora}",
        "items": items,
        "_meta": {
            "coins": len(COINS),
            "ok_count": ok_count,
            "miss_count": miss_count,
            "gain_min_pct": float(GAIN_MIN_PCT),
            "assert_min_pct": float(ASSERT_MIN_PCT),
            "ttl_default_h": DEFAULT_TTL_HOURS,
        },
    }
    return payload

def build_top10(full_payload: dict):
    items = full_payload.get("items") or []
    tradables = [x for x in items if x.get("side") in ("LONG","SHORT")]

    def score(x):
        pts = _pts_z(x.get("zona")) + _pts_r(x.get("risco")) + _pts_p(x.get("prioridade"))
        a = float(x.get("assert_pct") or 0.0)
        g = float(x.get("ganho_pct") or 0.0)
        return (pts, a, g)

    tradables.sort(key=score, reverse=True)
    top = tradables[:10]

    return {
        "ok": True,
        "source": "local",
        "updated_at": full_payload.get("updated_at"),
        "now_brt": full_payload.get("now_brt"),
        "items": top,
    }

def main_loop():
    log(f"start: OUT_FILE={OUT_FILE} TOP10_FILE={TOP10_FILE} interval={INTERVAL_S}s gain_min={GAIN_MIN_PCT} assert_min={ASSERT_MIN_PCT}")
    while True:
        try:
            full = build_payload()
            top10 = build_top10(full)
            atomic_write_json(OUT_FILE, full)
            atomic_write_json(TOP10_FILE, top10)
            log(f"wrote pro={OUT_FILE} top10={TOP10_FILE} ok_count={full.get('_meta',{}).get('ok_count')} miss_count={full.get('_meta',{}).get('miss_count')}")
        except Exception as e:
            log(f"ERROR: {e}")
        time.sleep(INTERVAL_S)

if __name__ == "__main__":
    main_loop()
