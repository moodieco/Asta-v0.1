"""Market-agnostic strategy implementations.

Per-market modules (``markets/<market>/strategies/*.py``) subclass these to
apply market specific defaults (timeframes, RSI bands, volume filters).
"""

from asta.markets.strategies.breakout_trend import BreakoutTrendStrategy
from asta.markets.strategies.ema_crossover import EMACrossoverStrategy
from asta.markets.strategies.rsi_divergence import RSIDivergenceStrategy
from asta.markets.strategies.volume_spike import VolumeSpikeStrategy

__all__ = [
    "BreakoutTrendStrategy",
    "EMACrossoverStrategy",
    "RSIDivergenceStrategy",
    "VolumeSpikeStrategy",
]
