"""Trend pullback continuation for crypto (EMA20/100 + RSI reset)."""

from __future__ import annotations

from typing import List

from asta.core.indicators import ema, rsi_series, slope
from asta.core.signal_model import ScanContext, SignalType
from asta.core.strategy import Strategy, StrategyResult


class CryptoEMAPullbackStrategy(Strategy):
    """Buy the first push out of a shallow pullback inside an uptrend.

    Setup: price above the trend EMA, RSI reset into the pullback band, then a
    bullish candle closing back above the fast EMA. The mirror applies for shorts.
    """

    name = "EMA Pullback"
    default_params = {
        "fast_period": 20,
        "trend_period": 100,
        "rsi_period": 14,
        "rsi_min": 38.0,
        "rsi_max": 52.0,
        "pullback_lookback": 6,
        "min_body_ratio": 0.3,
        "min_slope": 0.0005,
        "min_confidence": 0.55,
        "stop_buffer_pct": 0.001,
        "min_candles": 120,
    }

    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        context.require(int(self.param("min_candles")))
        closes = context.closes
        fast = ema(closes, int(self.param("fast_period")))
        trend = ema(closes, int(self.param("trend_period")))
        rsi = rsi_series(closes, int(self.param("rsi_period")))
        if fast is None or trend is None:
            return []

        lookback = int(self.param("pullback_lookback"))
        recent_rsi = [value for value in rsi[-lookback:] if value is not None]
        if not recent_rsi:
            return []

        last = context.last
        body_ratio = last.body / last.range if last.range else 0.0
        if body_ratio < float(self.param("min_body_ratio")):
            return []

        stop_window = context.candles[-lookback:]
        stop_buffer = float(self.param("stop_buffer_pct"))
        swing_low = min(candle.low for candle in stop_window) * (1.0 - stop_buffer)
        swing_high = max(candle.high for candle in stop_window) * (1.0 + stop_buffer)

        rsi_low = min(recent_rsi)
        rsi_high = max(recent_rsi)
        trend_slope = slope(closes, 10) or 0.0
        min_slope = float(self.param("min_slope"))
        rsi_min = float(self.param("rsi_min"))
        rsi_max = float(self.param("rsi_max"))

        if (
            closes[-1] > trend
            and last.is_bullish
            and last.close > fast
            and rsi_min <= rsi_low <= rsi_max
            and trend_slope >= min_slope
        ):
            confidence = 0.55 + min(0.15, (rsi_max - rsi_low) / 100.0) + min(0.15, trend_slope)
            if confidence < float(self.param("min_confidence")):
                return []
            distance = (last.close - trend) / trend * 100.0
            return [
                StrategyResult(
                    signal_type=SignalType.LONG,
                    confidence=min(confidence, 0.92),
                    reason=(
                        "Uptrend pullback: close {:.5f} above EMA{} and back over EMA{}, "
                        "RSI reset to {:.1f} then turned up, 10-bar slope {:+.3f}%/bar "
                        "({:+.2f}% above the trend EMA)."
                    ).format(
                        last.close,
                        int(self.param("trend_period")),
                        int(self.param("fast_period")),
                        rsi_low,
                        trend_slope * 100.0,
                        distance,
                    ),
                    stop_loss=swing_low,
                    indicators={
                        "rsi": round(float(rsi[-1] or 0.0), 2),
                        "rsi_low": round(rsi_low, 2),
                        "ema_fast": round(fast, 6),
                        "ema_trend": round(trend, 6),
                        "slope_10": round(trend_slope * 100.0, 4),
                        "body_ratio": round(body_ratio, 3),
                    },
                    metadata={"pullback_lookback": lookback, "trend_distance_pct": round(distance, 3)},
                )
            ]

        if (
            closes[-1] < trend
            and not last.is_bullish
            and last.close < fast
            and rsi_min <= (100.0 - rsi_high) <= rsi_max
            and trend_slope <= -min_slope
        ):
            confidence = 0.55 + min(0.15, rsi_high / 100.0) + min(0.15, abs(trend_slope))
            if confidence < float(self.param("min_confidence")):
                return []
            distance = (trend - last.close) / trend * 100.0
            return [
                StrategyResult(
                    signal_type=SignalType.SHORT,
                    confidence=min(confidence, 0.92),
                    reason=(
                        "Downtrend pullback: close {:.5f} below EMA{} and back under EMA{}, "
                        "RSI bounced to {:.1f} then rolled over, 10-bar slope {:+.3f}%/bar "
                        "({:+.2f}% below the trend EMA)."
                    ).format(
                        last.close,
                        int(self.param("trend_period")),
                        int(self.param("fast_period")),
                        rsi_high,
                        trend_slope * 100.0,
                        distance,
                    ),
                    stop_loss=swing_high,
                    indicators={
                        "rsi": round(float(rsi[-1] or 0.0), 2),
                        "rsi_high": round(rsi_high, 2),
                        "ema_fast": round(fast, 6),
                        "ema_trend": round(trend, 6),
                        "slope_10": round(trend_slope * 100.0, 4),
                        "body_ratio": round(body_ratio, 3),
                    },
                    metadata={"pullback_lookback": lookback, "trend_distance_pct": round(distance, 3)},
                )
            ]

        return []
