"""Pure indicator maths - no IO, no signals, no config.

Kept dependency free (plain Python) so it is trivially unit-testable and fast
enough for a few hundred candles per symbol.
"""

from asta.markets.indicators.momentum import rate_of_change, rsi, rsi_series
from asta.markets.indicators.structure import (
    Breakout,
    Divergence,
    detect_breakout,
    find_divergence,
    pivot_highs,
    pivot_lows,
)
from asta.markets.indicators.trend import (
    EMACross,
    detect_ema_cross,
    ema,
    ema_series,
    rolling_max,
    rolling_min,
    slope,
    sma,
    sma_series,
)
from asta.markets.indicators.volatility import atr, atr_series, true_range_series
from asta.markets.indicators.volume import VolumeSpike, detect_volume_spike, volume_ratio, volume_sma

__all__ = [
    "Breakout",
    "Divergence",
    "EMACross",
    "VolumeSpike",
    "atr",
    "atr_series",
    "detect_breakout",
    "detect_ema_cross",
    "detect_volume_spike",
    "ema",
    "ema_series",
    "find_divergence",
    "pivot_highs",
    "pivot_lows",
    "rate_of_change",
    "rolling_max",
    "rolling_min",
    "rsi",
    "rsi_series",
    "slope",
    "sma",
    "sma_series",
    "true_range_series",
    "volume_ratio",
    "volume_sma",
]
