"""Trend indicators: moving averages, rolling extremes, EMA crosses."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence


def _validate(period: int, name: str = "period") -> int:
    period = int(period)
    if period <= 0:
        raise ValueError("{} must be positive".format(name))
    return period


def sma_series(values: Sequence[float], period: int) -> List[Optional[float]]:
    period = _validate(period)
    out: List[Optional[float]] = [None] * len(values)
    window = 0.0
    for index, value in enumerate(values):
        window += float(value)
        if index >= period:
            window -= float(values[index - period])
        if index >= period - 1:
            out[index] = window / period
    return out


def sma(values: Sequence[float], period: int) -> Optional[float]:
    series = sma_series(values, period)
    return series[-1] if series else None


def ema_series(values: Sequence[float], period: int) -> List[Optional[float]]:
    period = _validate(period)
    out: List[Optional[float]] = [None] * len(values)
    if len(values) < period:
        return out
    multiplier = 2.0 / (period + 1.0)
    previous = sum(float(v) for v in values[:period]) / period
    out[period - 1] = previous
    for index in range(period, len(values)):
        previous = float(values[index]) * multiplier + previous * (1 - multiplier)
        out[index] = previous
    return out


def ema(values: Sequence[float], period: int) -> Optional[float]:
    series = ema_series(values, period)
    return series[-1] if series else None


def rolling_max(values: Sequence[float], period: int) -> List[Optional[float]]:
    period = _validate(period)
    out: List[Optional[float]] = [None] * len(values)
    for index in range(len(values)):
        if index + 1 < period:
            continue
        out[index] = max(float(v) for v in values[index + 1 - period : index + 1])
    return out


def rolling_min(values: Sequence[float], period: int) -> List[Optional[float]]:
    period = _validate(period)
    out: List[Optional[float]] = [None] * len(values)
    for index in range(len(values)):
        if index + 1 < period:
            continue
        out[index] = min(float(v) for v in values[index + 1 - period : index + 1])
    return out


def slope(values: Sequence[float], period: int = 5) -> Optional[float]:
    """Normalised slope over the last ``period`` points (percent per bar)."""
    period = _validate(period)
    if len(values) < period or values[0] == 0:
        return None
    window = [float(v) for v in values[-period:]]
    if window[0] == 0:
        return None
    return (window[-1] - window[0]) / abs(window[0]) / (period - 1)


@dataclass(frozen=True)
class EMACross:
    index: int
    direction: str  # "bullish" | "bearish"
    fast: float
    slow: float

    @property
    def bars_ago_from(self, total: int) -> int:
        return total - 1 - self.index

    @property
    def separation_pct(self) -> float:
        if self.slow == 0:
            return 0.0
        return abs(self.fast - self.slow) / abs(self.slow)


def detect_ema_cross(
    values: Sequence[float],
    fast_period: int = 20,
    slow_period: int = 50,
    lookback: int = 5,
) -> Optional[EMACross]:
    """Return the most recent EMA cross if it happened within ``lookback`` bars."""
    fast_period = _validate(fast_period, "fast_period")
    slow_period = _validate(slow_period, "slow_period")
    if fast_period >= slow_period:
        raise ValueError("fast_period must be smaller than slow_period")
    if len(values) < slow_period + 2:
        return None

    fast_series = ema_series(values, fast_period)
    slow_series = ema_series(values, slow_period)

    points = [
        (index, fast_series[index] - slow_series[index])
        for index in range(len(values))
        if fast_series[index] is not None and slow_series[index] is not None
    ]
    last_index = len(values) - 1
    cross: Optional[EMACross] = None
    for position in range(1, len(points)):
        prev_index, prev_diff = points[position - 1]
        curr_index, curr_diff = points[position]
        if prev_diff <= 0 < curr_diff:
            cross = EMACross(curr_index, "bullish", float(fast_series[curr_index]), float(slow_series[curr_index]))
        elif prev_diff >= 0 > curr_diff:
            cross = EMACross(curr_index, "bearish", float(fast_series[curr_index]), float(slow_series[curr_index]))
    if cross is None or (last_index - cross.index) > lookback:
        return None
    return cross
