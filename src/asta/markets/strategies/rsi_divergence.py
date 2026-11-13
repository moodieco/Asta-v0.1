"""RSI divergence strategy (shared implementation)."""

from __future__ import annotations

from typing import List

from asta.core.indicators import find_divergence, rsi_series, volume_ratio
from asta.core.signal_model import ScanContext, SignalType
from asta.core.strategy import Strategy, StrategyResult


class RSIDivergenceStrategy(Strategy):
    name = "RSI Divergence"
    default_params = {
        "rsi_period": 14,
        "lookback": 120,
        "pivot_span": 2,
        "min_rsi_delta": 1.5,
        "max_pivot_age": 12,
        "oversold": 35.0,
        "overbought": 65.0,
        "min_confidence": 0.55,
        "stop_buffer_pct": 0.001,
        "volume_confirm": False,
        "volume_period": 20,
        "min_volume_ratio": 1.0,
        "min_candles": 60,
    }

    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        lookback = int(self.param("lookback"))
        context.require(int(self.param("min_candles")))
        candles = context.tail(lookback)
        closes = [candle.close for candle in candles]
        rsi_values = rsi_series(closes, int(self.param("rsi_period")))

        divergence = find_divergence(
            closes,
            rsi_values,
            span=int(self.param("pivot_span")),
            min_rsi_delta=float(self.param("min_rsi_delta")),
            max_pivot_age=int(self.param("max_pivot_age")),
        )
        if divergence is None:
            return []

        volume = volume_ratio(context.volumes, int(self.param("volume_period")))
        if self.param("volume_confirm") and (volume is None or volume < float(self.param("min_volume_ratio"))):
            return []

        rsi_first = float(rsi_values[divergence.first_index])
        rsi_second = float(rsi_values[divergence.second_index])

        stop_buffer = float(self.param("stop_buffer_pct"))
        pivot_candle = candles[divergence.second_index]
        if divergence.direction == "bullish":
            signal_type = SignalType.LONG
            structural_stop = pivot_candle.low * (1.0 - stop_buffer)
            difficulty = 0.10 if rsi_second < float(self.param("oversold")) else 0.0
            reason = (
                "Regular bullish RSI divergence: price printed a lower low ({:+.2f}%) "
                "while RSI printed a higher low ({:+.1f} pts, {:.1f} -> {:.1f})."
            ).format(
                divergence.price_change * 100.0, divergence.rsi_change, rsi_first, rsi_second
            )
        else:
            signal_type = SignalType.SHORT
            structural_stop = pivot_candle.high * (1.0 + stop_buffer)
            difficulty = 0.10 if rsi_second > float(self.param("overbought")) else 0.0
            reason = (
                "Regular bearish RSI divergence: price printed a higher high ({:+.2f}%) "
                "while RSI printed a lower high ({:+.1f} pts, {:.1f} -> {:.1f})."
            ).format(
                divergence.price_change * 100.0, divergence.rsi_change, rsi_first, rsi_second
            )

        confidence = min(0.95, 0.50 + 0.30 * divergence.strength + difficulty)
        if volume is not None and volume > 1.5:
            confidence = min(0.95, confidence + 0.03)
        if confidence < float(self.param("min_confidence")):
            return []

        indicators = {
            "rsi": round(rsi_second, 2),
            "rsi_prev": round(rsi_first, 2),
            "rsi_delta": round(divergence.rsi_change, 2),
            "price_delta_pct": round(divergence.price_change * 100.0, 3),
            "divergence_strength": divergence.strength,
        }
        if volume is not None:
            indicators["volume_ratio"] = round(volume, 2)

        return [
            StrategyResult(
                signal_type=signal_type,
                confidence=confidence,
                reason=reason,
                stop_loss=structural_stop,
                indicators=indicators,
                metadata={
                    "pivot_bars_ago": len(candles) - 1 - divergence.second_index,
                    "lookback": lookback,
                },
            )
        ]
