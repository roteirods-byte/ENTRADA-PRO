from __future__ import annotations

"""engine/compute.py

Objetivo: gerar os campos do JSON de forma consistente e aplicar as regras:

- Só LONG/SHORT quando (ganho_pct >= gain_min_pct) e (assert_pct >= assert_min_pct)
- Caso contrário: side = "NÃO ENTRAR" e PRAZO/ZONA/RISCO/PRIORIDADE devem ficar vazios ("")
- Mesmo em "NÃO ENTRAR": ATUAL/ALVO/GANHO%/ASSERT% continuam numéricos.

Obs: este arquivo NÃO depende do painel/API; é só cálculo do worker.
"""

from dataclasses import dataclass
from typing import List, Tuple

from .indicators import ema, rsi, atr


@dataclass
class Signal:
    par: str
    side: str  # LONG/SHORT/NÃO ENTRAR
    atual: float
    alvo: float
    ganho_pct: float
    assert_pct: float
    prazo: str
    zona: str
    risco: str
    prioridade: str


def _to_ohlc_list(ohlc_like) -> List[List[float]]:
    """Normaliza para lista de [o,h,l,c] (floats)."""
    out: List[List[float]] = []
    if not ohlc_like:
        return out
    for row in ohlc_like:
        try:
            o, h, l, c = row[0], row[1], row[2], row[3]
            out.append([float(o), float(h), float(l), float(c)])
        except Exception:
            continue
    return out


def _closes(ohlc: List[List[float]]) -> List[float]:
    return [x[3] for x in ohlc if len(x) >= 4]


def _atr_last(ohlc: List[List[float]], period: int = 14) -> float:
    """ATR último valor a partir de lista [o,h,l,c]."""
    if not ohlc or len(ohlc) < period + 2:
        return 0.0
    highs = [x[1] for x in ohlc]
    lows = [x[2] for x in ohlc]
    closes = [x[3] for x in ohlc]
    a = atr(highs, lows, closes, period=period)
    return float(a[-1]) if a else 0.0


def _fmt_prazo(hours: float) -> str:
    if hours <= 0:
        return ""
    if hours < 1.0:
        return f"{hours*60.0:.0f}m"
    return f"{hours:.1f}h"


def direction_from_indicators(closes: List[float]) -> Tuple[str, float]:
    """Retorna (side, strength 0..1)"""
    if not closes or len(closes) < 60:
        return ("NÃO ENTRAR", 0.0)
    e20 = ema(closes, 20)
    e50 = ema(closes, 50)
    rs = rsi(closes, 14)
    if not e20 or not e50 or not rs:
        return ("NÃO ENTRAR", 0.0)

    ema20 = e20[-1]
    ema50 = e50[-1]
    rsi14 = rs[-1]
    last = closes[-1]

    # regras simples e estáveis
    if ema20 > ema50 and rsi14 >= 55:
        strength = min(1.0, (rsi14 - 55) / 20.0 + (ema20 - ema50) / max(1e-9, last * 0.01))
        return ("LONG", max(0.0, min(1.0, strength)))
    if ema20 < ema50 and rsi14 <= 45:
        strength = min(1.0, (45 - rsi14) / 20.0 + (ema50 - ema20) / max(1e-9, last * 0.01))
        return ("SHORT", max(0.0, min(1.0, strength)))
    return ("NÃO ENTRAR", 0.0)


def compute_gain_pct(atual: float, alvo: float, side: str) -> float:
    if not atual or atual <= 0 or not alvo or alvo <= 0:
        return 0.0
    if side == "LONG":
        return ((alvo - atual) / atual) * 100.0
    if side == "SHORT":
        return ((atual - alvo) / atual) * 100.0
    return 0.0


def compute_target_price(atual: float, atr_val: float, side: str, gain_min_pct: float) -> float:
    """Alvo simples e consistente:
    - distância mínima: max(ATR, atual*gain_min_pct%)
    - LONG: atual + dist; SHORT: atual - dist
    """
    if not atual or atual <= 0:
        return 0.0
    dist_min = max(float(atr_val or 0.0), float(atual) * (float(gain_min_pct) / 100.0))
    if side == "LONG":
        return float(atual) + dist_min
    if side == "SHORT":
        return max(1e-12, float(atual) - dist_min)
    return float(atual)


def mfe_mae_assert(ohlc: List[List[float]], side: str, target_dist: float, atr_val: float, lookahead: int = 12) -> float:
    """Assertividade histórica leve (0..100) usando janela de lookahead.
    Não precisa ser perfeito; precisa ser estável e numérico.
    """
    if side not in ("LONG", "SHORT"):
        return 0.0
    if len(ohlc) < 120:
        return 50.0

    mae_limit = 1.0 * float(atr_val or 0.0)
    successes = 0
    total = 0

    start = max(60, len(ohlc) - 180)
    end = len(ohlc) - lookahead - 1
    for i in range(start, end):
        entry = ohlc[i][3]
        window = ohlc[i + 1 : i + 1 + lookahead]
        if not window:
            continue

        if side == "LONG":
            max_high = max(x[1] for x in window)
            min_low = min(x[2] for x in window)
            mfe = max_high - entry
            mae = entry - min_low
            if mae <= mae_limit and mfe >= target_dist:
                successes += 1
            total += 1
        else:
            min_low = min(x[2] for x in window)
            max_high = max(x[1] for x in window)
            mfe = entry - min_low
            mae = max_high - entry
            if mae <= mae_limit and mfe >= target_dist:
                successes += 1
            total += 1

    if total <= 0:
        return 50.0
    return max(0.0, min(100.0, (successes / total) * 100.0))


def classify_qualitatives(strength: float, atr_pct: float, gain_pct: float) -> Tuple[str, str, str]:
    """Retorna (zona, risco, prioridade)"""

    # RISCO por volatilidade (ATR%)
    if atr_pct <= 0.02:
        risco = "BAIXO"
    elif atr_pct <= 0.05:
        risco = "MÉDIO"
    else:
        risco = "ALTO"

    # ZONA por força
    if strength >= 0.66:
        zona = "ALTA"
    elif strength >= 0.33:
        zona = "MÉDIA"
    else:
        zona = "BAIXA"

    # PRIORIDADE: ganho + zona + risco
    if gain_pct >= 6.0 and zona == "ALTA" and risco == "BAIXO":
        prioridade = "ALTA"
    elif gain_pct >= 4.0 and zona != "BAIXA" and risco != "ALTO":
        prioridade = "MÉDIA"
    else:
        prioridade = "BAIXA"

    return zona, risco, prioridade

def build_signal(
    par: str,
    ohlc_1h,
    ohlc_4h,
    mark_price: float,
    gain_min_pct: float,
    assert_min_pct: float,
) -> Signal:
    """Calcula sinal + métricas conforme as regras do projeto (SEM 'NÃO ENTRAR')."""

    # FALLBACK B: se mark_price falhar, usa último close do 4h (senão 1h)
    o1 = _to_ohlc_list(ohlc_1h)
    o4 = _to_ohlc_list(ohlc_4h)
    c1 = _closes(o1)
    c4 = _closes(o4)

    atual = float(mark_price or 0.0)
    if atual <= 0:
        if c4:
            atual = float(c4[-1])
        elif c1:
            atual = float(c1[-1])
        else:
            # Sem preço possível -> mantém numérico estável, mas SEM 'NÃO ENTRAR'
            return Signal(par, "LONG", 0.0, 0.0, 0.0, 0.0, "-", "", "", "")

    side_1h, s1 = direction_from_indicators(c1) if c1 else ("NÃO ENTRAR", 0.0)
    side_4h, s4 = direction_from_indicators(c4) if c4 else ("NÃO ENTRAR", 0.0)

    # SIDE SEMPRE definido (1 linha por moeda):
    if side_4h in ("LONG", "SHORT"):
        side_candidate = side_4h
        strength = float(s4)
    elif side_1h in ("LONG", "SHORT"):
        side_candidate = side_1h
        strength = float(s1)
    else:
        # fallback simples quando os indicadores não definirem direção
        if len(c4) >= 2:
            side_candidate = "LONG" if c4[-1] >= c4[-2] else "SHORT"
        elif len(c1) >= 2:
            side_candidate = "LONG" if c1[-1] >= c1[-2] else "SHORT"
        else:
            side_candidate = "LONG"
        strength = 0.0

    # ATR (usa 4h como principal)
    atr_val = _atr_last(o4, 14) if o4 else 0.0
    if atr_val <= 0:
        atr_val = _atr_last(o1, 14) if o1 else 0.0

    # Se ATR falhar, usa fallback proporcional (evita alvo=atual sempre)
    if atr_val <= 0 and atual > 0:
        atr_val = atual * 0.003  # 0.30% do preço (mínimo estável)

    alvo = compute_target_price(atual, atr_val, side_candidate, gain_min_pct)
    ganho_pct = compute_gain_pct(atual, alvo, side_candidate)

    target_dist = abs(alvo - atual)
    assert_pct = float(mfe_mae_assert(o4, side_candidate, target_dist, atr_val, lookahead=12)) if o4 else 0.0

    # ZONA/RISCO/PRIORIDADE NÃO EXISTEM MAIS -> vazio
    zona = ""
    risco = ""
    prioridade = ""

    # prazo estimado simples (ganho maior -> prazo menor). Escala estável.
    hours = max(0.5, 12.0 / max(1.0, float(ganho_pct)))
    prazo = _fmt_prazo(hours)

    return Signal(
        par=par,
        side=side_candidate,
        atual=atual,
        alvo=float(alvo),
        ganho_pct=float(ganho_pct),
        assert_pct=float(assert_pct),
        prazo=prazo,
        zona=zona,
        risco=risco,
        prioridade=prioridade,
    )
