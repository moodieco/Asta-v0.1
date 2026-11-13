"""EMA crossover strategy (shared implementation)."""

from __future__ import annotations

from typing import List, Optional

from asta.core.indicators import detect_ema_cross, ema, slope
from asta.core.signal_model import ScanContext, SignalType
from asta.core.strategy import Strategy, StrategyResult


class EMACrossoverStrategy(Strategy):
    name = "EMA Crossover"
    default_params = {
        "fast_period": 20,
        "slow_period": 50,
        "trend_period": 200,
        "cross_lookback": 3,
        "min_separation_pct": 0.0,
        "min_confidence": 0.5,
        "require_trend_alignment": False,
        "min_candles": 80,
    }

    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        context.require(int(self.param("min_candles")))
        closes = context.closes
        fast = int(self.param("fast_period"))
        slow = int(self.param("slow_period"))

        cross = detect_ema_cross(
            closes,
            fast_period=fast,
            slow_period=slow,
            lookback=int(self.param("cross_lookback")),
        )
        if cross is None:
            return []
        if cross.separation_pct < float(self.param("min_separation_pct")):
            return []

        trend_period = int(self.param("trend_period") or 0)
        trend_value: Optional[float] = ema(closes, trend_period) if trend_period > 0 else None
        aligned = True
        if trend_value is not None:
            aligned = (cross.direction == "bullish" and closes[-1] > trend_value) or (
                cross.direction == "bearish" and closes[-1] < trend_value
            )
        if self.param("require_trend_alignment") and not aligned:
            return []

        signal_type = SignalType.LONG if cross.direction == "bullish" else SignalType.SHORT
        confidence = 0.52 + min(0.18, cross.separation_pct * 25.0)
        confidence += 0.06 if aligned else -0.06
        if confidence < float(self.param("min_confidence")):
            return []

        trend_pct = ((closes[-1] - trend_value) / trend_value * 100.0) if trend_value else 0.0
        short_slope = slope(closes, 5) or 0.0
        reason = (
            "EMA{} crossed {} EMA{} {} bars ago at {:.5f} (separation {:.2f}%); "
            "price is {:.2f}% vs EMA{} and the 5-bar slope is {:+.3f}%/bar."
        ).format(
            fast,
            "above" if cross.direction == "bullish" else "below",
            slow,
            len(closes) - 1 - cross.index,
            cross.fast,
            cross.separation_pct * 100.0,
            trend_pct,
            trend_period or slow,
            short_slope * 100.0,
        )

        indicators = {
            "ema_fast": round(cross.fast, 6),
            "ema_slow": round(cross.slow, 6),
            "separation_pct": round(cross.separation_pct * 100.0, 3),
            "slope_5": round(short_slope * 100.0, 4),
        }
        if trend_value is not None:
            indicators["ema_trend"] = round(trend_value, 6)
            indicators["trend_distance_pct"] = round(trend_pct, 3)

        return [
            StrategyResult(
                signal_type=signal_type,
                confidence=min(confidence, 0.95),
                reason=reason,
                indicators=indicators,
                metadata={
                    "cross_bars_ago": len(closes) - 1 - cross.index,
                    "trend_aligned": aligned,
                },
            )
        ]
