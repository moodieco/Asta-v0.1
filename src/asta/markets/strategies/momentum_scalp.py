"""Momentum + volume scalp strategy (shared implementation).

Long only. Every rule is evaluated on the last closed bar:
price floor, liquidity (volume MA and traded-value MA), daily price change
and day-over-day volume change. Stop and target are fixed percentages of entry.
"""

from __future__ import annotations

from typing import List

from asta.core.indicators import sma
from asta.core.signal_model import ScanContext, SignalType
from asta.core.strategy import Strategy, StrategyResult


class MomentumScalpStrategy(Strategy):
    name = "Momentum Scalp"
    default_params = {
        "min_price": 100.0,
        "ma_period": 5,
        "min_volume_ma": 10_000_000.0,
        "min_value_ma": 10_000_000_000.0,
        "min_price_change_pct": 2.0,
        "min_volume_change_pct": 30.0,
        "stop_loss_pct": 2.0,
        "take_profit_pct": 5.0,
        "min_confidence": 0.55,
        "min_candles": 6,
    }

    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        context.require(int(self.param("min_candles")))
        period = int(self.param("ma_period"))

        price = context.price
        if price < float(self.param("min_price")):
            return []

        last = context.candles[-1]
        prev = context.candles[-2]
        if prev.close <= 0 or prev.volume <= 0:
            return []

        volume_ma = sma(context.volumes, period)
        traded_value = [candle.close * candle.volume for candle in context.candles]
        value_ma = sma(traded_value, period)
        if volume_ma is None or value_ma is None:
            return []
        if volume_ma < float(self.param("min_volume_ma")):
            return []
        if value_ma < float(self.param("min_value_ma")):
            return []

        price_change = (price / prev.close - 1.0) * 100.0
        volume_change = (last.volume / prev.volume - 1.0) * 100.0
        min_price_change = float(self.param("min_price_change_pct"))
        min_volume_change = float(self.param("min_volume_change_pct"))
        if price_change < min_price_change or volume_change < min_volume_change:
            return []

        confidence = (
            0.55
            + min(0.20, (price_change - min_price_change) / 50.0)
            + min(0.15, (volume_change - min_volume_change) / 400.0)
        )
        confidence = min(confidence, 0.95)
        if confidence < float(self.param("min_confidence")):
            return []

        stop_loss = price * (1.0 - float(self.param("stop_loss_pct")) / 100.0)
        take_profit = price * (1.0 + float(self.param("take_profit_pct")) / 100.0)

        reason = (
            "Momentum scalp: price +{:.2f}% (>= {:.1f}%), volume +{:.0f}% vs previous bar "
            "(>= {:.0f}%), volume MA{} {:.1f}M, value MA{} {:.1f}B (close x volume)."
        ).format(
            price_change,
            min_price_change,
            volume_change,
            min_volume_change,
            period,
            volume_ma / 1e6,
            period,
            value_ma / 1e9,
        )

        return [
            StrategyResult(
                signal_type=SignalType.LONG,
                confidence=confidence,
                reason=reason,
                stop_loss=stop_loss,
                take_profit=take_profit,
                indicators={
                    "price_change_pct": round(price_change, 2),
                    "volume_change_pct": round(volume_change, 2),
                    "volume_ma": round(volume_ma, 0),
                    "value_ma_billion": round(value_ma / 1e9, 2),
                },
                metadata={"value_basis": "close x volume (approximation)"},
            )
        ]
