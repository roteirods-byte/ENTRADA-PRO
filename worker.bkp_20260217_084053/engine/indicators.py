from __future__ import annotations
from typing import List, Tuple
import math

def ema(values: List[float], period: int) -> List[float]:
    if len(values) < period or period <= 1:
        return []
    k = 2 / (period + 1)
    out = []
    # seed with SMA
    sma = sum(values[:period]) / period
    out.append(sma)
    prev = sma
    for v in values[period:]:
        prev = (v - prev) * k + prev
        out.append(prev)
    return out  # length = len(values)-period+1

def rsi(values: List[float], period: int = 14) -> List[float]:
    if len(values) <= period:
        return []
    gains = []
    losses = []
    for i in range(1, len(values)):
        ch = values[i] - values[i-1]
        gains.append(max(0.0, ch))
        losses.append(max(0.0, -ch))
    # first avg
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    out = []
    def calc(ag, al):
        if al == 0:
            return 100.0
        rs = ag / al
        return 100 - (100 / (1 + rs))
    out.append(calc(avg_gain, avg_loss))
    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        out.append(calc(avg_gain, avg_loss))
    return out  # length = len(values)-period

def atr(high: List[float], low: List[float], close: List[float], period: int = 14) -> List[float]:
    if len(close) < period + 1:
        return []
    trs = []
    for i in range(1, len(close)):
        tr = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        trs.append(tr)
    # first ATR = SMA of first period TRs
    atr0 = sum(trs[:period]) / period
    out = [atr0]
    prev = atr0
    for tr in trs[period:]:
        prev = (prev * (period - 1) + tr) / period
        out.append(prev)
    return out  # length = len(close)-period
