"""Crypto volume spike with a percentile read on how unusual the volume is."""

from asta.markets.crypto.indicators import relative_volume_percentile
from asta.markets.strategies.volume_spike import VolumeSpikeStrategy


class CryptoVolumeSpikeStrategy(VolumeSpikeStrategy):
    default_params = {
        **VolumeSpikeStrategy.default_params,
        "volume_period": 20,
        "spike_multiplier": 3.0,
        "min_body_ratio": 0.35,
        "min_confidence": 0.5,
        "min_candles": 40,
    }

    def evaluate(self, context):
        results = super().evaluate(context)
        percentile = relative_volume_percentile(context.volumes, 100)
        for result in results:
            if percentile is not None:
                result.indicators["volume_percentile"] = percentile
        return results
