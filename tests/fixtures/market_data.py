"""Deterministic synthetic market data used across the test suite.

No randomness: every pattern below is a fixed piecewise series that triggers
exactly one strategy, so a failing test always means a behaviour change.
"""

from datetime import datetime, timedelta, timezone
from typing import List, Optional, Sequence

from asta.core.signal_model import Candle, Market, ScanContext

START = datetime(2025, 1, 1, tzinfo=timezone.utc)


def segment(start: float, end: float, steps: int) -> List[float]:
    return [start + (end - start) * (index + 1) / steps for index in range(steps)]


def make_candles(
    closes: Sequence[float],
    volumes: Optional[Sequence[float]] = None,
    timeframe: str = "1h",
    spread: float = 0.03,
) -> List[Candle]:
    step = {"1h": timedelta(hours=1), "15m": timedelta(minutes=15), "1d": timedelta(days=1)}.get(
        timeframe, timedelta(hours=1)
    )
    volumes = list(volumes) if volumes is not None else [1000.0] * len(closes)
    candles: List[Candle] = []
    for index, close in enumerate(closes):
        open_ = closes[index - 1] if index else close
        candles.append(
            Candle(
                timestamp=START + step * index,
                open=open_,
                high=max(open_, close) + spread,
                low=min(open_, close) - spread,
                close=close,
                volume=volumes[index],
            )
        )
    return candles


def make_context(
    market: Market,
    closes: Sequence[float],
    volumes: Optional[Sequence[float]] = None,
    timeframe: str = "1h",
    symbol: str = "TEST",
) -> ScanContext:
    return ScanContext(
        market=market,
        symbol=symbol,
        timeframe=timeframe,
        candles=make_candles(closes, volumes, timeframe),
    )


def bullish_divergence_closes() -> List[float]:
    """Steep drop -> bounce -> shallower new low -> small bounce."""
    return (
        [100.0] * 130
        + segment(100, 80, 24)
        + segment(80, 88, 10)
        + segment(88, 78.5, 18)
        + [79.2, 80.0, 80.8]
    )


def ema_bullish_cross_closes() -> List[float]:
    """Long 120 base, 10% decline, then a rally that crosses EMA20 over EMA50."""
    return [120.0] * 200 + segment(120, 110, 40) + segment(110, 126, 12)


def volume_spike_closes() -> List[float]:
    closes = [100.0 + (0.05 if index % 2 else 0.0) for index in range(60)]
    closes[-1] = 103.0
    return closes


def uptrend_closes(count: int = 100, start: float = 100.0, step: float = 0.08) -> List[float]:
    return [start + step * index for index in range(count)]


def crypto_breakout_closes() -> List[float]:
    closes = uptrend_closes(100, 100.0, 0.08)
    closes[-1] = closes[-2] * 1.003
    return closes


def stock_breakout_closes() -> List[float]:
    closes = uptrend_closes(120, 80.0, 0.25)
    closes[-1] = closes[-2] * 1.007
    return closes


def stock_ema_trend_closes() -> List[float]:
    base = uptrend_closes(240, 60.0, 0.25)
    top = base[-1]
    return base + segment(top, top - 8.0, 20) + segment(top - 8.0, top - 4.0, 12)


def flat_volumes(count: int, spike_index: int = -1, spike: float = 1800.0, base: float = 1000.0) -> List[float]:
    volumes = [base] * count
    volumes[spike_index] = spike
    return volumes
