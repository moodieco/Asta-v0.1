"""Forex EMA crossover with a 200 EMA trend filter and session context."""

from asta.markets.forex.indicators import session_for
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
        "min_risk_pct": 0.02,
        "max_risk_pct": 3.0,
    }

    def evaluate(self, context):
        results = super().evaluate(context)
        session = session_for(context.last_timestamp)
        for result in results:
            result.metadata["session"] = session
        return results
