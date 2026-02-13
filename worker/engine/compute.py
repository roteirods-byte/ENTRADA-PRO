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
    """Formata PRAZO como faixa (ex: 35-50m, 4-6h).

    Motivo: no painel, uma faixa é mais fácil de ler do que um número quebrado.
    """
    hmin = float(hours_min or 0.0)
    hmax = float(hours_max or 0.0)
    if hmin <= 0 or hmax <= 0:
        return "-"
    if hmax < 1.0:
        mmin = max(1.0, math.floor(hmin * 60.0))
        mmax = max(mmin, math.ceil(hmax * 60.0))
        return f"{mmin:.0f}-{mmax:.0f}m"
    a = max(1.0, math.floor(hmin))
    b = max(a, math.ceil(hmax))
    return f"{a:.0f}-{b:.0f}h"

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

def classify_levels(atr_pct: float, assert_pct: float, gain_pct: float, strength: float) -> Tuple[str,str,str]:
    # risco, prioridade, zona (BAIXO/MÉDIO/ALTO)
    # risk
    if atr_pct >= 0.06 or assert_pct < 55 or strength < 0.25:
        risco="ALTO"
    elif atr_pct >= 0.035 or assert_pct < 62 or strength < 0.45:
        risco="MÉDIO"
    else:
        risco="BAIXO"

    # prioridade (mais coerente: mistura ASSERT + GANHO e penaliza risco sem exagero)
    # ganho_pct*10: 3% vira 30, 6% vira 60, etc.
    score = 0.6*assert_pct + 0.4*min(100.0, gain_pct*10)

    if risco=="ALTO":
        score -= 6
    elif risco=="MÉDIO":
        score -= 2

    # faixas (para não ficar tudo BAIXA)
    if score >= 60:
        prioridade="ALTA"
    elif score >= 52:
        prioridade="MÉDIA"
    else:
        prioridade="BAIXA"

    # zona (força da oportunidade)
    # quanto maior a força, maior a ZONA
    if strength >= 0.65 and atr_pct <= 0.04:
        zona="ALTA"
    elif strength >= 0.40:
        zona="MÉDIA"
    else:
        zona="BAIXA"

    return risco, prioridade, zona

def build_signal(par: str, ohlc: List[List[float]], mark_price: float, gain_min_pct: float, candle_hours: float = 4.0) -> Signal:
    closes=[x[3] for x in ohlc]
    highs=[x[1] for x in ohlc]
    lows=[x[2] for x in ohlc]
    atr_series=atr(highs,lows,closes,14)
    atr_val = atr_series[-1] if atr_series else 0.0
    side, strength = direction_from_indicators(closes)
    entrada = mark_price
    atual = mark_price
    if atr_val <= 0 or side=="NÃO ENTRAR":
        return Signal(par, "NÃO ENTRAR", "PRO", entrada, atual, atual, 0.0, "-", 0.0, "ALTO", "BAIXA", "ALTA", "MARK")
    atr_pct = atr_val / max(1e-9, mark_price)
    # ALVO baseado em ATR (regra simples e estável)
    # ALVO = 1,5 x ATR (em preço). O filtro de GANHO% continua sendo o freio único.
    target_dist = 1.5 * atr_val
    if side=="LONG":
        alvo = mark_price + target_dist
    else:
        alvo = mark_price - target_dist
    ganho_pct = abs(alvo - mark_price) / mark_price * 100.0
    if ganho_pct < gain_min_pct:
        return Signal(par, "NÃO ENTRAR", "PRO", entrada, atual, atual, ganho_pct, "-", 0.0, "ALTO", "BAIXA", "ALTA", "MARK")
    # PRAZO: distancia até o ALVO dividida pela "velocidade" média do mercado.
    # velocidade por hora (%): mediana do range das velas / horas da vela.
    trs_pct = []
    for i in range(1, len(ohlc)):
        h = float(ohlc[i][1]); l = float(ohlc[i][2]); c_prev = float(ohlc[i-1][3])
        tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
        trs_pct.append(tr / max(1e-9, c_prev))
    tail = trs_pct[-80:] if len(trs_pct) > 80 else trs_pct
    med_tr_pct = statistics.median(tail) if tail else atr_pct
    candle_h = max(1e-6, float(candle_hours or 4.0))
    move_per_hour_pct = max(1e-6, med_tr_pct / candle_h)

    dist_pct = max(1e-6, float(ganho_pct) / 100.0)  # usa o ganho real do sinal
    hours = dist_pct / move_per_hour_pct
    hours_min = hours * 0.8
    hours_max = hours * 1.2
    prazo = _fmt_prazo(hours_min, hours_max)
    assert_pct = mfe_mae_assert(ohlc, side, target_dist, atr_val, lookahead=12)
    risco, prioridade, zona = classify_levels(atr_pct, assert_pct, ganho_pct, strength)
    return Signal(par, side, "PRO", entrada, atual, alvo, ganho_pct, prazo, assert_pct, risco, prioridade, zona, "MARK")
