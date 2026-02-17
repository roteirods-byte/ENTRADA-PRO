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

def build_signal(par: str, ohlc_1h: List[List[float]], ohlc_4h: List[List[float]], mark_price: float, gain_min_pct: float) -> Signal:
    """
    Regras do projeto (versão prática):
    1) SIDE: 1H e 4H precisam concordar (senão: NÃO ENTRAR).
    2) ALVO (ATR do modo escolhido):
       - LONG: ATUAL + 1.5*ATR
       - SHORT: ATUAL - 1.5*ATR
    3) GANHO% = |ALVO-ATUAL|/ATUAL * 100.  Se < 3% => NÃO ENTRAR.
    4) 24h é só freio: aqui usamos a direção das últimas ~48h do 1H para ajustar ZONA/RISCO.
    """
    entrada = float(mark_price)
    atual = float(mark_price)

    def _atr_val(ohlc):
        closes=[x[3] for x in ohlc]
        highs=[x[1] for x in ohlc]
        lows=[x[2] for x in ohlc]
        s=atr(highs,lows,closes,14)
        return (s[-1] if s else 0.0), closes

    atr1, closes1 = _atr_val(ohlc_1h)
    atr4, closes4 = _atr_val(ohlc_4h)

    side1, strength1 = direction_from_indicators(closes1)
    side4, strength4 = direction_from_indicators(closes4)

    # 24h (freio): usa as últimas ~48h do 1H (mais estável que 24h exato)
    closes_24 = closes1[-48:] if len(closes1) >= 48 else closes1
    side24, _ = direction_from_indicators(closes_24)

    # regra principal do SIDE
    side_final = side1 if (side1 == side4 and side1 != "NÃO ENTRAR") else "NÃO ENTRAR"

    # escolher modo (1H se estiver bem forte, senão 4H)
    mode = "4H"
    use_ohlc = ohlc_4h
    atr_val = float(atr4)
    strength = float(min(strength1, strength4))
    if side_final != "NÃO ENTRAR":
        if strength1 >= 0.65 and atr1 > 0:
            mode = "1H"
            use_ohlc = ohlc_1h
            atr_val = float(atr1)

    if atr_val <= 0 or side_final == "NÃO ENTRAR":
        # ainda mostramos zona/risco/prioridade (para o painel não ficar "vazio")
        atr_pct = (atr4 / max(1e-9, atual)) if atr4 > 0 else 0.0
        risco, prioridade, zona = classify_levels(atr_pct, 0.0, "NÃO ENTRAR", side24)
        return Signal(par, "NÃO ENTRAR", "PRO", entrada, atual, atual, 0.0, "-", 0.0, risco, prioridade, zona, "MARK")

    # alvo / ganho (regra oficial)
    target_dist = 1.5 * atr_val
    if side_final == "LONG":
        alvo = atual + target_dist
    else:
        alvo = atual - target_dist

    ganho_pct = abs(alvo - atual) / max(1e-9, atual) * 100.0

    # filtro único de ganho
    if ganho_pct < float(gain_min_pct):
        atr_pct = atr_val / max(1e-9, atual)
        risco, prioridade, zona = classify_levels(atr_pct, 0.0, "NÃO ENTRAR", side24)
        return Signal(par, "NÃO ENTRAR", "PRO", entrada, atual, atual, 0.0, "-", 0.0, risco, prioridade, zona, "MARK")

    # prazo estimado (base no ritmo médio do gráfico escolhido)
    atr_pct = atr_val / max(1e-9, atual)

    import statistics
    trs_pct=[]
    tf_hours = 1.0 if mode == "1H" else 4.0
    for i in range(1, len(use_ohlc)):
        h=float(use_ohlc[i][1]); l=float(use_ohlc[i][2]); c_prev=float(use_ohlc[i-1][3])
        tr = max(h - l, abs(h - c_prev), abs(l - c_prev))
        trs_pct.append(tr / max(1e-9, c_prev))
    tail = trs_pct[-80:] if len(trs_pct) > 80 else trs_pct
    med_tr_pct = statistics.median(tail) if tail else atr_pct
    move_per_hour_pct = max(1e-6, med_tr_pct / tf_hours)

    dist_pct = abs(alvo - atual) / max(1e-9, atual)
    hours = dist_pct / move_per_hour_pct
    hours_min = hours * 0.8
    hours_max = hours * 1.2
    prazo = _fmt_prazo(hours_min, hours_max)

    assert_pct = mfe_mae_assert(use_ohlc, side_final, target_dist, atr_val, lookahead=12)

    risco, prioridade, zona = classify_levels(atr_pct, ganho_pct, side_final, side24)

    return Signal(par, side_final, "PRO", entrada, atual, alvo, ganho_pct, prazo, assert_pct, risco, prioridade, zona, "MARK")
