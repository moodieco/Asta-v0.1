"""Stock breakout on daily bars with volume + overnight gap context."""

from asta.markets.stock.indicators import overnight_gap_pct
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

    def evaluate(self, context):
        results = super().evaluate(context)
        gap = overnight_gap_pct(context.candles)
        for result in results:
            if gap is not None:
                result.indicators["gap_pct"] = round(gap, 3)
        return results
