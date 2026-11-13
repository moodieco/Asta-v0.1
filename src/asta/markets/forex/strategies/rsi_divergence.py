"""Forex RSI divergence: tight RSI bands, no volume filter (FX volume is tick count)."""

from asta.markets.strategies.rsi_divergence import RSIDivergenceStrategy


class ForexRSIDivergenceStrategy(RSIDivergenceStrategy):
    default_params = {
        **RSIDivergenceStrategy.default_params,
        "lookback": 120,
        "oversold": 35.0,
        "overbought": 65.0,
        "min_rsi_delta": 1.5,
        "min_confidence": 0.55,
        "volume_confirm": False,
        "min_candles": 120,
    }
