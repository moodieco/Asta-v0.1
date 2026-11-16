"""Forex tuning of the Asia range breakout.

USD/JPY-sized risk: a 5 hour Asian range is rarely wider than ~0.6%, so the
generic 0.10% floor is fine but the ceiling is tightened to keep news-blown
ranges out. Volume filters stay off (FX "volume" is tick count).
"""

from asta.markets.forex.indicators.sessions import session_for
from asta.markets.strategies.asia_range_breakout import AsiaRangeBreakoutStrategy


class ForexAsiaRangeBreakoutStrategy(AsiaRangeBreakoutStrategy):
    default_params = {
        **AsiaRangeBreakoutStrategy.default_params,
        "session_start": "19:00",
        "session_end": "00:00",
        "cutoff": "13:30",
        "buffer_pct": 0.0,
        "min_range_atr": 0.35,
        "max_range_atr": 2.5,
        "max_distance_atr": 1.2,
        "require_sweep": False,
        "atr_period": 14,
        "reward_ratio": 2.0,
        "min_confidence": 0.55,
        "min_risk_pct": 0.02,
        "max_risk_pct": 2.0,
        "max_bars": 13,  # ~13h of 1h bars -> expiry lands near the 13:30 NY exit
        "min_candles": 40,
    }

    def evaluate(self, context):
        results = super().evaluate(context)
        session = session_for(context.last_timestamp)
        for result in results:
            result.metadata.setdefault("session", session)
        return results
