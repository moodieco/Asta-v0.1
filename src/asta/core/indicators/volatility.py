"""Volatility indicators (Wilder ATR)."""

from __future__ import annotations

from typing import List, Optional, Sequence

from asta.core.signal_model import Candle


def true_range_series(candles: Sequence[Candle]) -> List[float]:
    ranges: List[float] = []
    for index, candle in enumerate(candles):
        if index == 0:
            ranges.append(candle.high - candle.low)
            continue
        previous_close = candles[index - 1].close
        ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        )
    return ranges


def atr_series(candles: Sequence[Candle], period: int = 14) -> List[Optional[float]]:
    period = int(period)
    if period <= 0:
        raise ValueError("period must be positive")
    out: List[Optional[float]] = [None] * len(candles)
    if len(candles) < period:
        return out
    ranges = true_range_series(candles)
    previous = sum(ranges[:period]) / period
    out[period - 1] = previous
    for index in range(period, len(candles)):
        previous = (previous * (period - 1) + ranges[index]) / period
        out[index] = previous
    return out


def atr(candles: Sequence[Candle], period: int = 14) -> Optional[float]:
    series = atr_series(candles, period)
    return series[-1] if series else None
