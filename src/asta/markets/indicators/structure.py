"""Market structure: pivots, RSI divergence, breakouts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Sequence

from asta.core.signal_model import Candle


def pivot_lows(values: Sequence[float], span: int = 2) -> List[int]:
    """Indices whose low is the lowest within +/- ``span`` bars."""
    span = int(span)
    if span <= 0:
        raise ValueError("span must be positive")
    out: List[int] = []
    for index in range(span, len(values) - span):
        window = values[index - span : index + span + 1]
        if values[index] == min(window) and values[index] < min(
            list(values[index - span : index]) + list(values[index + 1 : index + span + 1])
        ):
            out.append(index)
    return out


def pivot_highs(values: Sequence[float], span: int = 2) -> List[int]:
    span = int(span)
    if span <= 0:
        raise ValueError("span must be positive")
    out: List[int] = []
    for index in range(span, len(values) - span):
        window = values[index - span : index + span + 1]
        if values[index] == max(window) and values[index] > max(
            list(values[index - span : index]) + list(values[index + 1 : index + span + 1])
        ):
            out.append(index)
    return out


@dataclass(frozen=True)
class Divergence:
    direction: str  # "bullish" | "bearish"
    first_index: int
    second_index: int
    price_change: float  # fraction, e.g. -0.02 = 2% lower low
    rsi_change: float  # RSI points, e.g. +4.5 = RSI made a higher low

    @property
    def strength(self) -> float:
        """0..1-ish quality score used by scanners for confidence."""
        price_component = min(abs(self.price_change) / 0.05, 1.0)
        rsi_component = min(abs(self.rsi_change) / 10.0, 1.0)
        return round(0.5 * price_component + 0.5 * rsi_component, 3)


def find_divergence(
    closes: Sequence[float],
    rsi_values: Sequence[Optional[float]],
    span: int = 2,
    min_rsi_delta: float = 1.5,
    max_pivot_age: int = 12,
) -> Optional[Divergence]:
    """Classic regular divergence between price pivots and RSI pivots.

    Bullish: price prints a lower low while RSI prints a higher low.
    Bearish: price prints a higher high while RSI prints a lower high.
    """
    if len(closes) != len(rsi_values) or len(closes) < span * 4:
        return None
    last_index = len(closes) - 1

    lows = [i for i in pivot_lows(closes, span) if rsi_values[i] is not None]
    if len(lows) >= 2:
        first, second = lows[-2], lows[-1]
        if last_index - second <= max_pivot_age:
            price_change = (closes[second] - closes[first]) / closes[first] if closes[first] else 0.0
            rsi_change = float(rsi_values[second]) - float(rsi_values[first])
            if price_change < 0 and rsi_change > min_rsi_delta:
                return Divergence("bullish", first, second, price_change, rsi_change)

    highs = [i for i in pivot_highs(closes, span) if rsi_values[i] is not None]
    if len(highs) >= 2:
        first, second = highs[-2], highs[-1]
        if last_index - second <= max_pivot_age:
            price_change = (closes[second] - closes[first]) / closes[first] if closes[first] else 0.0
            rsi_change = float(rsi_values[second]) - float(rsi_values[first])
            if price_change > 0 and rsi_change < -min_rsi_delta:
                return Divergence("bearish", first, second, price_change, rsi_change)

    return None


@dataclass(frozen=True)
class Breakout:
    direction: str  # "bullish" | "bearish"
    level: float
    distance_pct: float
    lookback: int


def detect_breakout(
    candles: Sequence[Candle],
    lookback: int = 30,
    buffer_pct: float = 0.0,
) -> Optional[Breakout]:
    """Close beyond the high/low of the previous ``lookback`` candles."""
    lookback = int(lookback)
    if lookback <= 1 or len(candles) < lookback + 1:
        return None
    history = candles[-lookback - 1 : -1]
    last = candles[-1]
    prior_high = max(candle.high for candle in history)
    prior_low = min(candle.low for candle in history)
    buffer = max(0.0, float(buffer_pct))

    if last.close > prior_high * (1.0 + buffer) and prior_high > 0:
        return Breakout("bullish", prior_high, (last.close - prior_high) / prior_high, lookback)
    if last.close < prior_low * (1.0 - buffer) and prior_low > 0:
        return Breakout("bearish", prior_low, (prior_low - last.close) / prior_low, lookback)
    return None
