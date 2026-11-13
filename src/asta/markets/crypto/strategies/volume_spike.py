"""Crypto volume spike: 3x the 20-bar average with a directional body."""

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
