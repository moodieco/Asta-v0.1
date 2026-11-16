"""Crypto RSI divergence: volume confirmation required (crypto volume is real)."""

from asta.markets.strategies.rsi_divergence import RSIDivergenceStrategy


class CryptoRSIDivergenceStrategy(RSIDivergenceStrategy):
    default_params = {
        **RSIDivergenceStrategy.default_params,
        "lookback": 120,
        "oversold": 30.0,
        "overbought": 70.0,
        "min_rsi_delta": 2.0,
        "volume_confirm": True,
        "min_volume_ratio": 1.0,
        "min_confidence": 0.55,
        "min_candles": 120,
    }
