"""Forex tuned strategies."""

from asta.markets.forex.strategies.ema_crossover import ForexEMACrossoverStrategy
from asta.markets.forex.strategies.rsi_divergence import ForexRSIDivergenceStrategy

__all__ = ["ForexEMACrossoverStrategy", "ForexRSIDivergenceStrategy"]
