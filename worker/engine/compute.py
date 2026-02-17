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
    ohlc_1h: List[Tuple[int, float, float, float, float]],
    atual: float,
    atr1: float,
    atr4: float,
    atr24: float,
    gain_min: float = GAIN_MIN_PCT,
    assert_min: float = ASSERT_MIN_PCT,
) -> Signal:
    """
    Regras (projeto):
    - Sempre preencher (mesmo em NÃO ENTRAR): SIDE, ATUAL, ALVO, GANHO %, ASSERT %, DATA, HORA (DATA/HORA vem do worker).
    - Quando NÃO ENTRAR: PRAZO/ZONA/RISCO/PRIORIDADE ficam vazios/zerados.
    - LONG/SHORT só quando passa filtros (gain_min e assert_min) e há concordância 1H/4H.
    """
    # 1) Seleção de ATR (prazo base) e direção bruta
    atr_val = float(atr4 or 0.0) if float(atr4 or 0.0) > 0 else float(atr1 or 0.0)
    prazo_base = "4h" if float(atr4 or 0.0) > 0 else "1h"

    # Direções por janela
    side1 = side_from_ohlc(ohlc_1h, 1)
    side4 = side_from_ohlc(ohlc_1h, 4)
    side24 = side_from_ohlc(ohlc_1h, 24)

    def pick_candidate() -> str:
        for s in (side1, side4, side24):
            if s in ("LONG", "SHORT"):
                return s
        return "LONG"

    cand_side = pick_candidate()

    # 2) Cálculo sempre (mesmo se NÃO ENTRAR)
    # alvo usa 1.5 * ATR (quando existe); se não existir, alvo=atual e ganho=0
    if atr_val <= 0:
        target_dist = 0.0
    else:
        target_dist = 1.5 * atr_val

    if cand_side == "LONG":
        alvo = atual + target_dist
    elif cand_side == "SHORT":
        alvo = atual - target_dist
    else:
        alvo = atual

    gain_pct = pct_gain(cand_side, atual, alvo)
    assert_pct = mfe_mae_assert(ohlc_1h, cand_side, target_dist, atr_val) if target_dist > 0 else 0.0

    # 3) Decisão final de entrada (sem mudar os cálculos)
    concorda = (side1 == side4) and (side1 in ("LONG", "SHORT"))
    passa_filtros = (gain_pct >= float(gain_min)) and (assert_pct >= float(assert_min))

    if concorda and passa_filtros:
        # ENTRAR: preenche tudo
        prazo = _fmt_prazo(target_dist, atr_val, prazo_base)
        risco, prioridade, zona = classify_levels(gain_pct, assert_pct, target_dist, atr_val)
        return Signal(par, side1, "PRO", atual, atual, alvo, gain_pct, prazo, assert_pct, zona, risco, prioridade, "MARK")

    # NÃO ENTRAR: mantém ALVO/GANHO/ASSERT calculados, zera (vazio) PRAZO/ZONA/RISCO/PRIORIDADE
    return Signal(par, "NÃO ENTRAR", "PRO", atual, atual, alvo, gain_pct, "", assert_pct, "", "", "", "MARK")
