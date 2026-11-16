"""Crypto breakout trend: 30-bar range break with volume expansion."""

from asta.markets.strategies.breakout_trend import BreakoutTrendStrategy


class CryptoBreakoutTrendStrategy(BreakoutTrendStrategy):
    default_params = {
        **BreakoutTrendStrategy.default_params,
        "breakout_lookback": 30,
        "buffer_pct": 0.002,
        "trend_period": 100,
        "min_volume_ratio": 1.2,
        "max_distance_atr": 2.5,
        "min_confidence": 0.55,
        "min_candles": 90,
    }
