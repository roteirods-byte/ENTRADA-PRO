from __future__ import annotations

import os
import time
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
    # prioridade: Binance -> Bybit
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
    return (
        str(s or "")
        .upper()
        .replace("É", "E")
        .replace("Ê", "E")
        .replace("Á", "A")
        .replace("Ã", "A")
        .replace("Ç", "C")
        .replace("Í", "I")
        .replace("Ó", "O")
        .replace("Õ", "O")
        .replace("Ú", "U")
    )


def _pts_z(z):  # ZONA: ALTA=3, MEDIA=2, BAIXA=1
    z = _norm(z)
    if z == "ALTA":
        return 3
    if z == "MEDIA":
        return 2
    return 1


def _pts_r(r):  # RISCO: BAIXO=3, MEDIO=2, ALTO=1
    r = _norm(r)
    if r == "BAIXO":
        return 3
    if r == "MEDIO":
        return 2
    return 1


def _pts_p(p):  # PRIORIDADE: ALTA=3, MEDIA=2, BAIXA=1
    p = _norm(p)
    if p == "ALTA":
        return 3
    if p == "MEDIA":
        return 2
    return 1


def _prazo_to_minutes(prazo: str):
    if not prazo:
        return None
    s = str(prazo).strip().lower()
    try:
        if s.endswith("m"):
            return float(s[:-1])
        if s.endswith("h"):
            return float(s[:-1]) * 60.0
    except Exception:
        return None
    return None


def _ttl_expira_em(updated_at_iso_utc: str, prazo: str) -> str:
    # campo interno: ISO UTC quando expira
    mins = _prazo_to_minutes(prazo)
    if not mins or mins <= 0:
        return ""
    try:
        # updated_at vem em formato ...Z
        base = datetime.fromisoformat(updated_at_iso_utc.replace("Z", "+00:00"))
        exp = base + __import__("datetime").timedelta(minutes=float(mins))
        return exp.isoformat().replace("+00:00", "Z")
    except Exception:
        return ""


def build_payload():
    updated_at = now_utc_iso()
    data, hora = brt_data_hora()

    items = []
    ok_count = 0
    miss_count = 0

    for par in COINS:
        symbol = _sym(par)
        mark, src = _safe_mark(symbol)

        # 1) sem preço
        if mark is None:
            miss_count += 1
            items.append(
                {
                    "par": par,
                    "side": "NÃO ENTRAR",
                    "atual": None,
                    "alvo": None,
                    "ganho_pct": None,
                    "assert_pct": None,
                    # regra oficial: vazios
                    "prazo": "",
                    "zona": "",
                    "risco": "",
                    "prioridade": "",
                    "data": data,
                    "hora": hora,
                    # internos
                    "price_source": src,
                    "nao_entrar_motivo": "sem_mark",
                    "ttl_expira_em": "",
                }
            )
            continue

        # 2) sem candles (não inventa)
        o1 = _safe_klines(symbol, "1h")
        o4 = _safe_klines(symbol, "4h")
        if (not o1) or (not o4):
            miss_count += 1
            items.append(
                {
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
                    "data": data,
                    "hora": hora,
                    "price_source": src,
                    "nao_entrar_motivo": "sem_klines",
                    "ttl_expira_em": "",
                }
            )
            continue

        sig = build_signal(
            par=par,
            ohlc_1h=o1,
            ohlc_4h=o4,
            mark_price=float(mark),
            gain_min_pct=float(GAIN_MIN_PCT),
            assert_min_pct=float(ASSERT_MIN_PCT),
        )

        # segurança: filtro final (mesmo que a engine já faça)
        side = sig.side
        motivo = getattr(sig, "nao_entrar_motivo", "") or ""

        g = float(sig.ganho_pct or 0.0)
        a = float(sig.assert_pct or 0.0)

        if side in ("LONG", "SHORT"):
            if g < float(GAIN_MIN_PCT) or a < float(ASSERT_MIN_PCT):
                side = "NÃO ENTRAR"
                if not motivo:
                    if g < float(GAIN_MIN_PCT) and a < float(ASSERT_MIN_PCT):
                        motivo = f"ganho<{float(GAIN_MIN_PCT):g}+assert<{float(ASSERT_MIN_PCT):g}"
                    elif g < float(GAIN_MIN_PCT):
                        motivo = f"ganho<{float(GAIN_MIN_PCT):g}"
                    else:
                        motivo = f"assert<{float(ASSERT_MIN_PCT):g}"

        # regra do painel: se NÃO ENTRAR, deixar vazios (prazo/zona/risco/prioridade) e alvo vazio
        if side == "NÃO ENTRAR":
            # regra do seu prompt: preencher GANHO% e ASSERT% quando for decisão por filtro (quando existir)
            ganho_out = float(g) if g > 0 else None
            assert_out = float(a) if a > 0 else None

            items.append(
                {
                    "par": sig.par,
                    "side": "NÃO ENTRAR",
                    "atual": float(sig.atual),
                    "alvo": None,
                    "ganho_pct": ganho_out,
                    "assert_pct": assert_out,
                    "prazo": "",
                    "zona": "",
                    "risco": "",
                    "prioridade": "",
                    "data": data,
                    "hora": hora,
                    "price_source": src,
                    "nao_entrar_motivo": motivo,
                    "ttl_expira_em": "",
                }
            )
        else:
            items.append(
                {
                    "par": sig.par,
                    "side": side,
                    "atual": float(sig.atual),
                    "alvo": float(sig.alvo),
                    "ganho_pct": float(sig.ganho_pct),
                    "assert_pct": float(sig.assert_pct),
                    "prazo": sig.prazo,
                    "zona": sig.zona,
                    "risco": sig.risco,
                    "prioridade": sig.prioridade,
                    "data": data,
                    "hora": hora,
                    "price_source": src,
                    "nao_entrar_motivo": "",
                    "ttl_expira_em": _ttl_expira_em(updated_at, sig.prazo),
                }
            )
            ok_count += 1

    # ordem alfabética
    items.sort(key=lambda x: (x.get("par") or ""))

    # TOP10 (pontos -> assert -> ganho -> par) + filtros oficiais
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
        pts = _pts_z(it.get("zona")) + _pts_r(it.get("risco")) + _pts_p(it.get("prioridade"))
        it2 = dict(it)
        it2["rank_pts"] = int(pts)
        cand.append(it2)

    cand.sort(
        key=lambda x: (
            -int(x.get("rank_pts") or 0),
            -float(x.get("assert_pct") or 0.0),
            -float(x.get("ganho_pct") or 0.0),
            str(x.get("par") or ""),
        )
    )

    payload = {"ok": True, "source": "local", "updated_at": updated_at, "items": items}
    top10 = {"ok": True, "source": "local", "updated_at": updated_at, "items": cand[:10]}

    log(
        f"OK | coins={len(COINS)} ok={ok_count} missing={miss_count} "
        f"gain_min={GAIN_MIN_PCT} assert_min={ASSERT_MIN_PCT}"
    )
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
