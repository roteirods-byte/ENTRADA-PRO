#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""ENTRADA-PRO Worker.

Gera /opt/ENTRADA-PRO/data/pro.json e /opt/ENTRADA-PRO/data/top10.json.

Regras (projeto):
1) SIDE/ATUAL/ALVO/GANHO%/ASSERT%/DATA/HORA sempre preenchidos (inclusive em NÃO ENTRAR).
2) PRAZO/ZONA/RISCO/PRIORIDADE ficam vazios quando NÃO ENTRAR.
3) Campos sempre presentes: price_source, nao_entrar_motivo, ttl_expira_em.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

from engine.config import (
    COINS,
    DATA_DIR,
    LOOP_SECONDS,
    TOP10_LIMIT,
)
from engine.exchanges import (
    bybit_mark_last,
    binance_mark_last,
    binance_ohlc_1h,
)
from engine.indicators import atr_from_ohlc
from engine.compute import build_signal
from engine.io import atomic_write_json, ensure_dir


TTL_SECONDS = 60 * 10  # 10 min


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def now_brt_dt() -> datetime:
    # BRT fixa (-03:00)
    return datetime.now(timezone(timedelta(hours=-3)))


def now_brt_str() -> str:
    return now_brt_dt().strftime("%Y-%m-%d %H:%M")


def _sym(par: str) -> str:
    return f"{par}USDT"


def _safe_mark(symbol: str) -> Tuple[float | None, str]:
    """Retorna (mark, source). Preferência: BYBIT -> BINANCE."""
    for fn, src in ((bybit_mark_last, "BYBIT"), (binance_mark_last, "BINANCE")):
        try:
            v = fn(symbol)
            if v is not None and float(v) > 0:
                return float(v), src
        except Exception:
            pass
    return None, "NONE"


def _priority_rank(p: str) -> int:
    p = (p or "").strip().upper()
    if p == "ALTA":
        return 3
    if p in ("MEDIA", "MÉDIA"):
        return 2
    if p == "BAIXA":
        return 1
    return 0


def _mk_item(
    *,
    par: str,
    side: str,
    atual: float,
    alvo: float,
    ganho_pct: float,
    assert_pct: float,
    prazo: str,
    zona: str,
    risco: str,
    prioridade: str,
    date_str: str,
    time_str: str,
    price_source: str,
    nao_entrar_motivo: str | None,
    ttl_expira_em: str,
) -> Dict:
    return {
        "par": par,
        "side": side,
        "atual": float(atual),
        "alvo": float(alvo),
        "ganho_pct": float(ganho_pct),
        "assert_pct": float(assert_pct),
        "prazo": prazo,
        "zona": zona,
        "risco": risco,
        "prioridade": prioridade,
        "data": date_str,
        "hora": time_str,
        "price_source": price_source,
        "nao_entrar_motivo": nao_entrar_motivo,
        "ttl_expira_em": ttl_expira_em,
    }


def build_payload() -> Dict:
    brt = now_brt_dt()
    date_str = brt.strftime("%Y-%m-%d")
    time_str = brt.strftime("%H:%M")

    updated_at = now_utc_iso()
    ttl_expira_em = (datetime.now(timezone.utc) + timedelta(seconds=TTL_SECONDS)).isoformat().replace("+00:00", "Z")

    items: List[Dict] = []

    for par in COINS:
        symbol = _sym(par)
        mark, src = _safe_mark(symbol)

        if mark is None:
            # Sem preço: ainda assim preenche colunas obrigatórias
            items.append(
                _mk_item(
                    par=par,
                    side="NÃO ENTRAR",
                    atual=0.0,
                    alvo=0.0,
                    ganho_pct=0.0,
                    assert_pct=0.0,
                    prazo="",
                    zona="",
                    risco="",
                    prioridade="",
                    date_str=date_str,
                    time_str=time_str,
                    price_source=src,
                    nao_entrar_motivo="sem_mark",
                    ttl_expira_em=ttl_expira_em,
                )
            )
            continue

        # OHLC (para ATR e assertividade). Se falhar, entra vazio e o build_signal cai em 0.
        try:
            ohlc = binance_ohlc_1h(symbol, limit=240)  # ~10 dias
        except Exception:
            ohlc = []

        # ATRs (em preço)
        atr1 = atr_from_ohlc(ohlc, 1)
        atr4 = atr_from_ohlc(ohlc, 4)
        atr24 = atr_from_ohlc(ohlc, 24)

        sig = build_signal(par, ohlc, float(mark), float(atr1), float(atr4), float(atr24))

        motivo = None
        if sig.side == "NÃO ENTRAR":
            motivo = "filtro"  # mantém simples e estável

        items.append(
            _mk_item(
                par=par,
                side=sig.side,
                atual=float(sig.atual),
                alvo=float(sig.alvo),
                ganho_pct=float(sig.ganho_pct),
                assert_pct=float(sig.assert_pct),
                prazo=sig.prazo,
                zona=sig.zona,
                risco=sig.risco,
                prioridade=sig.prioridade,
                date_str=date_str,
                time_str=time_str,
                price_source=src,
                nao_entrar_motivo=motivo,
                ttl_expira_em=ttl_expira_em,
            )
        )

    payload = {
        "ok": True,
        "source": "local",
        "updated_at": updated_at,
        "now_brt": now_brt_str(),
        "items": items,
    }
    return payload


def build_top10(payload: Dict) -> Dict:
    items = payload.get("items", [])
    enterables = [x for x in items if x.get("side") in ("LONG", "SHORT")]

    # Ordenação: prioridade (ALTA>MEDIA>BAIXA) -> assert -> ganho
    enterables.sort(
        key=lambda x: (
            _priority_rank(x.get("prioridade") or ""),
            float(x.get("assert_pct") or 0.0),
            float(x.get("ganho_pct") or 0.0),
        ),
        reverse=True,
    )

    top = enterables[: int(TOP10_LIMIT)]

    return {
        "ok": True,
        "source": payload.get("source"),
        "updated_at": payload.get("updated_at"),
        "now_brt": payload.get("now_brt"),
        "items": top,
    }


def main() -> None:
    ensure_dir(DATA_DIR)

    while True:
        try:
            payload = build_payload()
            atomic_write_json(os.path.join(DATA_DIR, "pro.json"), payload)

            top10 = build_top10(payload)
            atomic_write_json(os.path.join(DATA_DIR, "top10.json"), top10)

        except Exception as e:
            # Não derruba o loop
            try:
                ensure_dir(DATA_DIR)
                atomic_write_json(
                    os.path.join(DATA_DIR, "worker_error.json"),
                    {"ok": False, "error": str(e), "ts": now_utc_iso()},
                )
            except Exception:
                pass

        time.sleep(float(LOOP_SECONDS))


if __name__ == "__main__":
    main()
