"""Forex EMA crossover with a 200 EMA trend filter."""

from asta.markets.strategies.ema_crossover import EMACrossoverStrategy


class ForexEMACrossoverStrategy(EMACrossoverStrategy):
    default_params = {
        **EMACrossoverStrategy.default_params,
        "fast_period": 20,
        "slow_period": 50,
        "trend_period": 200,
        "cross_lookback": 3,
        "min_separation_pct": 0.0005,
        "require_trend_alignment": False,
        "min_confidence": 0.5,
        "min_candles": 220,
    }
