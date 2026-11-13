"""Crypto tuned strategies."""

from asta.markets.crypto.strategies.breakout_trend import CryptoBreakoutTrendStrategy
from asta.markets.crypto.strategies.rsi_divergence import CryptoRSIDivergenceStrategy
from asta.markets.crypto.strategies.volume_spike import CryptoVolumeSpikeStrategy

__all__ = [
    "CryptoBreakoutTrendStrategy",
    "CryptoRSIDivergenceStrategy",
    "CryptoVolumeSpikeStrategy",
]
