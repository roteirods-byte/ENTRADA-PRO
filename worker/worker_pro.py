#!/usr/bin/env python3
# worker/worker_pro.py
# Gera data/pro.json e data/top10.json para o painel ENTRADA-PRO (FULL + TOP10)
# REGRAS NOVAS (BLOCO 1):
# - NÃO EXISTE "NÃO ENTRAR" (SIDE sempre LONG/SHORT)
# - NÃO EXISTEM colunas ZONA/RISCO/PRIORIDADE (não saem no JSON)
# - 1 linha por moeda
# - Fallback B do mark_price é tratado dentro do build_signal (compute.py)

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Tuple
from zoneinfo import ZoneInfo

from engine.config import load_settings, get_thresholds, get_coins
from engine.exchanges import fetch_mark_price, fetch_klines
from engine.compute import build_signal

DATA_DIR = os.getenv("DATA_DIR", "/opt/ENTRADA-PRO/data")
TZ_BRT = ZoneInfo("America/Sao_Paulo")

def _sym(par: str) -> str:
    p = par.upper()
    mult = {
        "BONK": "1000BONK",
        "FLOKI": "1000FLOKI",
        "PEPE": "1000PEPE",
        "SHIB": "1000SHIB",
    }
    base = mult.get(p, p)
    return f"{base}USDT"

def _now_brt():
    dt = datetime.now(TZ_BRT)
    return dt, dt.strftime("%Y-%m-%d"), dt.strftime("%H:%M")


def _ttl_iso(minutes: int = 6) -> str:
    return (datetime.now(timezone.utc) + timedelta(minutes=minutes)).isoformat().replace("+00:00", "Z")


def _safe_mark(symbol: str) -> Tuple[float, str]:
    # tenta BYBIT primeiro, depois BINANCE
    for src in ("BYBIT", "BINANCE"):
        try:
            px = fetch_mark_price(symbol, source=src, timeout=5)
            if px is not None and float(px) > 0:
                return float(px), src
        except Exception:
            pass
    return 0.0, "NONE"


def _safe_klines(symbol: str, interval: str, limit: int = 220):
    for src in ("BYBIT", "BINANCE"):
        try:
            kl = fetch_klines(symbol, interval=interval, limit=limit, source=src, timeout=10)
            if kl and len(kl) >= 20:
                return kl, src
        except Exception:
            pass
    return None, "NONE"


def _mk_item(
    par: str,
    side: str,
    atual: float,
    alvo: float,
    ganho_pct: float,
    assert_pct: float,
    data: str,
    hora: str,
    prazo: str,
    price_source: str,
    ttl_expira_em: str,
) -> Dict:
    # GARANTIA: chaves sempre existem e números nunca são None
    # ZONA/RISCO/PRIORIDADE foram removidos do JSON (regra nova)
    return {
        "par": par,
        "side": side,
        "atual": float(atual or 0.0),
        "alvo": float(alvo or 0.0),
        "ganho_pct": float(ganho_pct or 0.0),
        "assert_pct": float(assert_pct or 0.0),
        "data": data,
        "hora": hora,
        "prazo": prazo or "-",
        "price_source": price_source or "NONE",
        # Mantido por compatibilidade: agora sempre vazio
        "nao_entrar_motivo": "",
        "ttl_expira_em": ttl_expira_em,
    }


def _prazo_min(p: str) -> float:
    # aceita "4.2h" ou "50m" (ou "-" / vazio)
    try:
        s = (p or "").strip().lower()
        if not s or s == "-":
            return 1e9
        if s.endswith("h"):
            return float(s[:-1].strip()) * 60.0
        if s.endswith("m"):
            return float(s[:-1].strip())
    except Exception:
        pass
    return 1e9


def build_payload() -> Dict:
    settings = load_settings()
    gain_min, assert_min = get_thresholds(settings)  # mantidos no payload (info)
    coins = get_coins(settings)

    dt_brt, date_brt, time_brt = _now_brt()
    ttl = _ttl_iso(6)

    items: List[Dict] = []
    miss_mark = 0
    miss_kl = 0

    for par in coins:
        symbol = _sym(par)

        mark, mark_src = _safe_mark(symbol)
        if mark <= 0:
            miss_mark += 1

        k1, _src1 = _safe_klines(symbol, "1h", 220)
        k4, _src4 = _safe_klines(symbol, "4h", 220)
        if not k1 or not k4:
            miss_kl += 1

        # Sempre calcula (sem "NÃO ENTRAR"):
        # - se mark=0, build_signal usa fallback B (último close)
        # - se klines faltarem, passa [] para manter estabilidade
        sig = build_signal(
            par=par,
            ohlc_1h=(k1 or []),
            ohlc_4h=(k4 or []),
            mark_price=float(mark or 0.0),
            gain_min_pct=float(gain_min),
            assert_min_pct=float(assert_min),
        )

        # segurança: garantir side válido
        side = sig.side if sig.side in ("LONG", "SHORT") else "LONG"

        items.append(
            _mk_item(
                par=par,
                side=side,
                atual=sig.atual,
                alvo=sig.alvo,
                ganho_pct=sig.ganho_pct,
                assert_pct=sig.assert_pct,
                data=date_brt,
                hora=time_brt,
                prazo=sig.prazo,
                price_source=mark_src,
                ttl_expira_em=ttl,
            )
        )

    # FULL ordenado por PAR (estável)
    items.sort(key=lambda x: x.get("par") or "")

    payload = {
        "ok": True,
        "source": "local",
        "updated_at": dt_brt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "now_brt": dt_brt.strftime("%Y-%m-%d %H:%M"),
        "gain_min_pct": float(gain_min),
        "assert_min_pct": float(assert_min),
        "miss_mark": int(miss_mark),
        "miss_klines": int(miss_kl),
        "items": items,
    }

    return payload


def write_json(path: str, data: Dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def main():
    payload = build_payload()
    write_json(os.path.join(DATA_DIR, "pro.json"), payload)

    # TOP10 (regra nova): ordenar por ASSERT desc -> GANHO desc -> PRAZO asc
    ls = list(payload.get("items") or [])
    ls.sort(
        key=lambda x: (
            float(x.get("assert_pct") or 0.0),
            float(x.get("ganho_pct") or 0.0),
            -_prazo_min(x.get("prazo") or "-"),
        ),
        reverse=True,
    )

    top10 = dict(payload)
    top10["items"] = ls[:10]
    write_json(os.path.join(DATA_DIR, "top10.json"), top10)


if __name__ == "__main__":
    main()
