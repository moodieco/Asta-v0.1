"""Stock EMA trend following: trend alignment is mandatory on daily bars."""

from asta.markets.strategies.ema_crossover import EMACrossoverStrategy


class StockEMATrendStrategy(EMACrossoverStrategy):
    default_params = {
        **EMACrossoverStrategy.default_params,
        "fast_period": 20,
        "slow_period": 50,
        "trend_period": 200,
        "cross_lookback": 3,
        "require_trend_alignment": True,
        "min_separation_pct": 0.0,
        "min_confidence": 0.55,
        "min_candles": 220,
    }
