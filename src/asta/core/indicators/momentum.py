"""Momentum indicators (Wilder RSI, rate of change)."""

from __future__ import annotations

from typing import List, Optional, Sequence


def rsi_series(values: Sequence[float], period: int = 14) -> List[Optional[float]]:
    period = int(period)
    if period <= 0:
        raise ValueError("period must be positive")
    out: List[Optional[float]] = [None] * len(values)
    if len(values) <= period:
        return out

    gains = 0.0
    losses = 0.0
    for index in range(1, period + 1):
        change = float(values[index]) - float(values[index - 1])
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain = gains / period
    avg_loss = losses / period
    out[period] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)

    for index in range(period + 1, len(values)):
        change = float(values[index]) - float(values[index - 1])
        gain = max(change, 0.0)
        loss = max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[index] = 100.0 if avg_loss == 0 else 100.0 - 100.0 / (1.0 + avg_gain / avg_loss)
    return out


def rsi(values: Sequence[float], period: int = 14) -> Optional[float]:
    series = rsi_series(values, period)
    return series[-1] if series else None


def rate_of_change(values: Sequence[float], period: int = 1) -> Optional[float]:
    period = int(period)
    if period <= 0 or len(values) <= period:
        return None
    previous = float(values[-1 - period])
    if previous == 0:
        return None
    return (float(values[-1]) - previous) / abs(previous)
