#!/usr/bin/env python3
# worker/worker_pro.py
# Gera data/pro.json e data/top10.json para o painel ENTRADA-PRO (FULL + TOP10)

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
    # sem USDT na planilha; mas no exchange o símbolo é <PAR>USDT
    return f"{par}USDT"

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
            if px is not None and px > 0:
                return float(px), src
        except Exception:
            pass
    return 0.0, "NONE"

def _safe_klines(symbol: str, interval: str, limit: int = 120):
    for src in ("BYBIT", "BINANCE"):
        try:
            kl = fetch_klines(symbol, interval=interval, limit=limit, source=src, timeout=8)
            if kl and len(kl) >= 20:
                return kl, src
        except Exception:
            pass
    return None, "NONE"

def _mk_item(par: str, side: str, atual: float, alvo: float, ganho_pct: float, assert_pct: float,
             data: str, hora: str, prazo: str, zona: str, risco: str, prioridade: str,
             price_source: str, nao_entrar_motivo: str, ttl_expira_em: str) -> Dict:
    # GARANTIA: chaves sempre existem e números nunca são None
    return {
        "par": par,
        "side": side,
        "atual": float(atual or 0.0),
        "alvo": float(alvo or 0.0),
        "ganho_pct": float(ganho_pct or 0.0),
        "assert_pct": float(assert_pct or 0.0),
        "data": data,
        "hora": hora,
        "prazo": prazo or "",
        "zona": zona or "",
        "risco": risco or "",
        "prioridade": prioridade or "",
        "price_source": price_source or "NONE",
        "nao_entrar_motivo": nao_entrar_motivo,
        "ttl_expira_em": ttl_expira_em,
    }

def build_payload() -> Dict:
    settings = load_settings()
    gain_min, assert_min = get_thresholds(settings)
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
            items.append(_mk_item(
                par=par, side="NÃO ENTRAR",
                atual=0.0, alvo=0.0, ganho_pct=0.0, assert_pct=0.0,
                data=date_brt, hora=time_brt,
                prazo="", zona="", risco="", prioridade="",
                price_source=mark_src, nao_entrar_motivo="sem_mark", ttl_expira_em=ttl
            ))
            continue

        k1, src1 = _safe_klines(symbol, "1h", 120)
        k4, src4 = _safe_klines(symbol, "4h", 120)
        if not k1 or not k4:
            miss_kl += 1
            items.append(_mk_item(
                par=par, side="NÃO ENTRAR",
                atual=mark, alvo=mark, ganho_pct=0.0, assert_pct=0.0,
                data=date_brt, hora=time_brt,
                prazo="", zona="", risco="", prioridade="",
                price_source=mark_src, nao_entrar_motivo="sem_klines", ttl_expira_em=ttl
            ))
            continue

        # Compute signal (always returns numeric alvo/ganho/assert even if NÃO ENTRAR)
        sig = build_signal(
            par=par,
            ohlc_1h=k1,
            ohlc_4h=k4,
            mark_price=mark,
            gain_min_pct=gain_min,
            assert_min_pct=assert_min,
        )

        # Decide motivo quando NÃO ENTRAR
        motivo = None
        if sig.side == "NÃO ENTRAR":
            g = float(getattr(sig, "ganho_pct", 0.0) or 0.0)
            a = float(getattr(sig, "assert_pct", 0.0) or 0.0)
            if g < float(gain_min):
                motivo = "gain_min"
            elif a < float(assert_min):
                motivo = "assert_min"
            else:
                motivo = "sem_sinal"

        items.append(_mk_item(
            par=par,
            side=sig.side,
            atual=sig.atual,
            alvo=sig.alvo,
            ganho_pct=sig.ganho_pct,
            assert_pct=sig.assert_pct,
            data=date_brt,
            hora=time_brt,
            prazo=sig.prazo if sig.side != "NÃO ENTRAR" else "",
            zona=sig.zona if sig.side != "NÃO ENTRAR" else "",
            risco=sig.risco if sig.side != "NÃO ENTRAR" else "",
            prioridade=sig.prioridade if sig.side != "NÃO ENTRAR" else "",
            price_source=mark_src,
            nao_entrar_motivo=motivo,
            ttl_expira_em=ttl,
        ))

    # Ordenar por PAR (estável para FULL)
    items.sort(key=lambda x: x["par"])

    payload = {
        "source": "local",
        "updated_at": dt_brt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "updated_at_brt": dt_brt.strftime("%Y-%m-%d %H:%M"),
        "gain_min_pct": gain_min,
        "assert_min_pct": assert_min,
        "miss_mark": miss_mark,
        "miss_klines": miss_kl,
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

    # TOP10 (conforme PROMPT BLOCO 1):
    # 1) filtra somente LONG/SHORT válidos (passaram 55/2)
    # 2) ordena por: maior PRIORIDADE (ALTA>MÉDIA>BAIXA) -> maior ASSERT% -> maior GANHO%
    #    -> menor RISCO (BAIXO melhor) -> menor PRAZO (menor melhor)
    def _pts_prioridade(v: str) -> int:
        v = (v or "").upper()
        if v == "ALTA":
            return 3
        if v in ("MÉDIA", "MEDIA"):
            return 2
        if v == "BAIXA":
            return 1
        return 0

    def _pts_risco(v: str) -> int:
        v = (v or "").upper()
        if v == "BAIXO":
            return 3
        if v in ("MÉDIO", "MEDIO"):
            return 2
        if v == "ALTO":
            return 1
        return 0

    def _prazo_min(p: str) -> float:
        # aceita "4.2h" ou "50m"; se vazio, joga p/ fim
        try:
            s = (p or "").strip().lower()
            if not s:
                return 1e9
            if s.endswith('h'):
                return float(s[:-1].strip()) * 60.0
            if s.endswith('m'):
                return float(s[:-1].strip())
        except Exception:
            pass
        return 1e9

    ls = [x for x in payload["items"] if x.get("side") in ("LONG", "SHORT")]
    ls.sort(
        key=lambda x: (
            _pts_prioridade(x.get("prioridade")),
            float(x.get("assert_pct") or 0.0),
            float(x.get("ganho_pct") or 0.0),
            _pts_risco(x.get("risco")),
            -_prazo_min(x.get("prazo")),
        ),
        reverse=True,
    )
    top10 = dict(payload)
    top10["items"] = ls[:10]
    write_json(os.path.join(DATA_DIR, "top10.json"), top10)

if __name__ == "__main__":
    main()
