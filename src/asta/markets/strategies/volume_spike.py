"""Volume spike strategy (shared implementation)."""

from __future__ import annotations

from typing import List

from asta.core.signal_model import ScanContext, SignalType
from asta.core.strategy import Strategy, StrategyResult
from asta.markets.indicators import detect_volume_spike


class VolumeSpikeStrategy(Strategy):
    name = "Volume Spike"
    default_params = {
        "volume_period": 20,
        "spike_multiplier": 3.0,
        "min_body_ratio": 0.3,
        "max_extension_atr": 3.0,
        "atr_period": 14,
        "min_confidence": 0.5,
        "min_candles": 40,
    }

    def evaluate(self, context: ScanContext) -> List[StrategyResult]:
        context.require(int(self.param("min_candles")))
        spike = detect_volume_spike(
            context.candles,
            period=int(self.param("volume_period")),
            multiplier=float(self.param("spike_multiplier")),
        )
        if spike is None or spike.body_ratio < float(self.param("min_body_ratio")):
            return []

        signal_type = SignalType.LONG if spike.direction == "up" else SignalType.SHORT
        excess = spike.ratio / float(self.param("spike_multiplier")) - 1.0
        confidence = min(0.90, 0.50 + min(0.28, excess * 0.6) + min(0.10, spike.body_ratio * 0.1))
        if confidence < float(self.param("min_confidence")):
            return []

        last = context.last
        move_pct = (last.close - last.open) / last.open * 100.0 if last.open else 0.0
        reason = (
            "Volume spike {:.1f}x the {}-bar average on a {} candle "
            "({:+.2f}% body, {:.0f}% of range)."
        ).format(
            spike.ratio,
            int(self.param("volume_period")),
            "bullish" if last.is_bullish else "bearish",
            move_pct,
            spike.body_ratio * 100.0,
        )

        return [
            StrategyResult(
                signal_type=signal_type,
                confidence=confidence,
                reason=reason,
                indicators={
                    "volume_ratio": round(spike.ratio, 2),
                    "body_ratio": round(spike.body_ratio, 3),
                    "move_pct": round(move_pct, 3),
                },
                metadata={"volume_period": int(self.param("volume_period"))},
            )
        ]
