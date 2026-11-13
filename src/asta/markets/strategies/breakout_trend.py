"""Breakout + trend continuation strategy (shared implementation)."""

from __future__ import annotations

from typing import List

from asta.core.indicators import atr, detect_breakout, ema, slope, volume_ratio
from asta.core.signal_model import ScanContext, SignalType
from asta.core.strategy import Strategy, StrategyResult


class BreakoutTrendStrategy(Strategy):
    name = "Breakout Trend"
    default_params = {
        "breakout_lookback": 30,
        "buffer_pct": 0.0,
        "trend_period": 100,
        "require_trend_alignment": True,
        "volume_period": 20,
        "min_volume_ratio": 1.2,
        "atr_period": 14,
        "max_distance_atr": 2.5,
        "min_confidence": 0.52,
        "stop_buffer_pct": 0.001,
        "min_candles": 90,
    }

    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        context.require(int(self.param("min_candles")))
        breakout = detect_breakout(
            context.candles,
            lookback=int(self.param("breakout_lookback")),
            buffer_pct=float(self.param("buffer_pct")),
        )
        if breakout is None:
            return []

        closes = context.closes
        trend_period = int(self.param("trend_period") or 0)
        trend_value = ema(closes, trend_period) if trend_period > 0 else None
        aligned = True
        if trend_value is not None:
            aligned = (breakout.direction == "bullish" and closes[-1] > trend_value) or (
                breakout.direction == "bearish" and closes[-1] < trend_value
            )
        if self.param("require_trend_alignment") and not aligned:
            return []

        ratio = volume_ratio(context.volumes, int(self.param("volume_period")))
        if ratio is None or ratio < float(self.param("min_volume_ratio")):
            return []

        atr_value = atr(context.candles, int(self.param("atr_period")))
        distance_atr = 0.0
        if atr_value:
            distance_atr = abs(context.price - breakout.level) / atr_value
            if distance_atr > float(self.param("max_distance_atr")):
                return []  # too extended, chasing

        signal_type = SignalType.LONG if breakout.direction == "bullish" else SignalType.SHORT
        confidence = 0.55 + min(0.20, breakout.distance_pct * 25.0) + min(0.12, (ratio - 1.0) * 0.1)
        confidence += 0.05 if aligned else -0.08
        if confidence < float(self.param("min_confidence")):
            return []

        short_slope = slope(closes, 10) or 0.0
        reason = (
            "{} breakout: close {:.5f} is {:.2f}% beyond the {}bar {} {:.5f} "
            "with {:.2f}x average volume (trend {}, {} bars of slope {:+.3f}%/bar)."
        ).format(
            breakout.direction.capitalize(),
            context.price,
            breakout.distance_pct * 100.0,
            breakout.lookback,
            "high" if breakout.direction == "bullish" else "low",
            breakout.level,
            ratio,
            "aligned" if aligned else "against",
            10,
            short_slope * 100.0,
        )

        indicators = {
            "breakout_level": round(breakout.level, 6),
            "distance_pct": round(breakout.distance_pct * 100.0, 3),
            "volume_ratio": round(ratio, 2),
            "distance_atr": round(distance_atr, 2),
            "slope_10": round(short_slope * 100.0, 4),
        }
        if trend_value is not None:
            indicators["ema_trend"] = round(trend_value, 6)

        return [
            StrategyResult(
                signal_type=signal_type,
                confidence=min(confidence, 0.95),
                reason=reason,
                stop_loss=breakout.level
                * (1.0 - float(self.param("stop_buffer_pct")))
                if breakout.direction == "bullish"
                else breakout.level * (1.0 + float(self.param("stop_buffer_pct"))),
                indicators=indicators,
                metadata={"trend_aligned": aligned, "lookback": breakout.lookback},
            )
        ]
