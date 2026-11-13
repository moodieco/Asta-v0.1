"""Stock 52-week style breakout on daily bars with volume confirmation."""

from asta.markets.strategies.breakout_trend import BreakoutTrendStrategy


class StockBreakoutTrendStrategy(BreakoutTrendStrategy):
    default_params = {
        **BreakoutTrendStrategy.default_params,
        "breakout_lookback": 40,
        "buffer_pct": 0.005,
        "trend_period": 100,
        "min_volume_ratio": 1.3,
        "max_distance_atr": 3.0,
        "min_confidence": 0.55,
        "min_candles": 90,
    }
