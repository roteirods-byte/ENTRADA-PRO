from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional
import math

from .indicators import ema, rsi, atr
import statistics

@dataclass
class Signal:
    par: str
    side: str  # LONG/SHORT/NÃO ENTRAR
    mode: str  # PRO
    entrada: float
    atual: float
    alvo: float
    ganho_pct: float
    prazo: str
    assert_pct: float
    risco: str
    prioridade: str
    zona: str
    price_source: str  # MARK

def _fmt_prazo(hours_min: float, hours_max: float) -> str:
    # PRAZO como número (horas) para variar por moeda
    h = (float(hours_min or 0.0) + float(hours_max or 0.0)) / 2.0
    if h <= 0:
        return "-"
    if h < 1.0:
        return f"{h*60.0:.0f}m"   # ex: 45m
    return f"{h:.1f}h"           # ex: 5.3h

def direction_from_indicators(closes: List[float]) -> Tuple[str, float]:
    # returns (side, strength 0..1)
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    rs = rsi(closes, 14)
    if not e20 or not e50 or not rs:
        return ("NÃO ENTRAR", 0.0)
    # align to last
    ema20 = e20[-1]
    ema50 = e50[-1]
    rsi14 = rs[-1]
    # simple rules
    if ema20 > ema50 and rsi14 >= 55:
        strength = min(1.0, (rsi14-55)/20 + (ema20-ema50)/max(1e-9, closes[-1]*0.01))
        return ("LONG", max(0.0, min(1.0, strength)))
    if ema20 < ema50 and rsi14 <= 45:
        strength = min(1.0, (45-rsi14)/20 + (ema50-ema20)/max(1e-9, closes[-1]*0.01))
        return ("SHORT", max(0.0, min(1.0, strength)))
    return ("NÃO ENTRAR", 0.0)

def mfe_mae_assert(ohlc: List[List[float]], side: str, target_dist: float, atr_val: float, lookahead: int = 12) -> float:
    # lightweight historical assert% using past candles
    # ohlc: list of [o,h,l,c] oldest->newest
    if side not in ("LONG","SHORT"):
        return 0.0
    # need enough candles
    if len(ohlc) < 120:
        return 50.0
    successes=0
    total=0
    mae_limit = 1.0 * atr_val  # simple risk bound
    # iterate over last ~100 entries skipping newest window
    start = max(60, len(ohlc)-180)
    end = len(ohlc)-lookahead-1
    for i in range(start, end):
        entry = ohlc[i][3]
        if side=="LONG":
            max_high = max(x[1] for x in ohlc[i+1:i+1+lookahead])
            min_low  = min(x[2] for x in ohlc[i+1:i+1+lookahead])
            mfe = max_high - entry
            mae = entry - min_low
            if mae <= mae_limit and mfe >= target_dist:
                successes += 1
            total += 1
        else:
            min_low  = min(x[2] for x in ohlc[i+1:i+1+lookahead])
            max_high = max(x[1] for x in ohlc[i+1:i+1+lookahead])
            mfe = entry - min_low
            mae = max_high - entry
            if mae <= mae_limit and mfe >= target_dist:
                successes += 1
            total += 1
    if total <= 0:
        return 50.0
    return max(0.0, min(100.0, (successes/total)*100.0))


def _lvl_up(x: str, levels) -> str:
    i = levels.index(x) if x in levels else len(levels)-1
    return levels[max(0, i-1)]

def _lvl_down(x: str, levels) -> str:
    i = levels.index(x) if x in levels else 0
    return levels[min(len(levels)-1, i+1)]

def classify_levels(atr_pct: float, gain_pct: float, side_final: str, side_24h: str) -> Tuple[str,str,str]:
    """
    Regras simples e seguras (versão para o seu projeto):
    - ZONA: ALTA/MÉDIA/BAIXA (força)
    - RISCO: BAIXO/MÉDIO/ALTO
    - PRIORIDADE: ALTA/MÉDIA/BAIXA
    Observação: 24h é só 'freio' (ajusta 1 nível no máximo).
    """
    # base RISCO por volatilidade (ATR%)
    if atr_pct <= 0.02:
        risco = "BAIXO"
    elif atr_pct <= 0.05:
        risco = "MÉDIO"
    else:
        risco = "ALTO"

    # base ZONA pela situação do 24h
    if side_final == "NÃO ENTRAR":
        zona = "BAIXA"
    else:
        if side_24h == side_final:
            zona = "ALTA"
        elif side_24h == "NÃO ENTRAR":
            zona = "MÉDIA"
        else:
            zona = "BAIXA"

    # freio 24h (ajusta risco 1 nível)
    risk_levels = ["BAIXO","MÉDIO","ALTO"]
    if side_final != "NÃO ENTRAR" and side_24h != "NÃO ENTRAR":
        if side_24h == side_final:
            risco = _lvl_up(risco, risk_levels)   # melhora
        else:
            risco = _lvl_down(risco, risk_levels) # piora

    # PRIORIDADE (direto)
    # ALTA: ganho alto + zona boa + risco baixo
    if side_final != "NÃO ENTRAR" and (gain_pct >= 6.0) and (zona == "ALTA") and (risco == "BAIXO"):
        prioridade = "ALTA"
    elif side_final != "NÃO ENTRAR" and (gain_pct >= 4.0) and (zona != "BAIXA") and (risco != "ALTO"):
        prioridade = "MÉDIA"
    else:
        prioridade = "BAIXA"

    return risco, prioridade, zona

def build_signal(
    par: str,
    ohlc_1h: List[Tuple[float, float, float, float]],
    ohlc_4h: List[Tuple[float, float, float, float]],
    mark_price: float,
    gain_min_pct: float,
    assert_min_pct: float,
) -> Signal:
    """Compute signal and metrics.

    REGRAS DO PROJETO (IMPORTANTE):
    - Mesmo quando for "NÃO ENTRAR", as colunas: SIDE, ATUAL, ALVO, GANHO %, ASSERT %, DATA, HORA
      devem estar sempre preenchidas (com valores calculados).
    - Quando for "NÃO ENTRAR", as colunas: PRAZO, ZONA, RISCO, PRIORIDADE devem ficar "zeradas" (vazias).
    """
    # Defensive
    atual = float(mark_price or 0.0)

    # Side candidates from trend
    side_1h = compute_trade_side(ohlc_1h)
    side_4h = compute_trade_side(ohlc_4h)

    # If timeframes disagree or no signal, treat as NÃO ENTRAR (still fill numeric columns)
    if (side_1h != side_4h) or (side_1h == "NÃO ENTRAR"):
        return Signal(
            par=par,
            side="NÃO ENTRAR",
            atual=atual,
            alvo=atual,
            ganho_pct=0.0,
            assert_pct=0.0,
            prazo="",
            zona="",
            risco="",
            prioridade="",
        )

    side_candidate = side_4h  # agreed side

    # ATR calculations (need at least one)
    atr1 = compute_atr(ohlc_1h, ATR_PERIOD)
    atr4 = compute_atr(ohlc_4h, ATR_PERIOD)
    atr_val = atr4 if atr4 > 0 else atr1
    if atr_val <= 0:
        return Signal(
            par=par,
            side="NÃO ENTRAR",
            atual=atual,
            alvo=atual,
            ganho_pct=0.0,
            assert_pct=0.0,
            prazo="",
            zona="",
            risco="",
            prioridade="",
        )

    # Target + gain (always computed when we have a candidate side + ATR)
    target = compute_target_price(atual, atr_val, side_candidate, mode="atr4h")
    gain_pct = compute_gain_pct(atual, target, side_candidate)

    # Assertiveness (always computed when we have a side candidate)
    assert_pct = compute_assertiveness(par, side_candidate)

    # Only enter if passes thresholds
    passes = (gain_pct >= float(gain_min_pct)) and (assert_pct >= float(assert_min_pct))

    if not passes:
        # NÃO ENTRAR but keep calculated alvo/ganho/assert; blank the qualitative cols
        return Signal(
            par=par,
            side="NÃO ENTRAR",
            atual=atual,
            alvo=float(target),
            ganho_pct=float(gain_pct),
            assert_pct=float(assert_pct),
            prazo="",
            zona="",
            risco="",
            prioridade="",
        )

    # Enterable: compute qualitative fields
    prazo = compute_time_to_target(gain_pct)
    zona = classify_levels(gain_pct, "ZONA")
    risco = classify_levels(gain_pct, "RISCO")
    prioridade = classify_levels(assert_pct, "PRIORIDADE")

    return Signal(
        par=par,
        side=side_candidate,
        atual=atual,
        alvo=float(target),
        ganho_pct=float(gain_pct),
        assert_pct=float(assert_pct),
        prazo=prazo,
        zona=zona,
        risco=risco,
        prioridade=prioridade,
    )

