"""Strategy implementations — one folder, generic + per-market tuning.

Layout rule: every strategy lives here. Market differences are expressed as
subclasses in the same folder with a market prefix (``crypto_*``, ``stock_*``,
``forex_*``), never as duplicated algorithm bodies in the market packages.
Genuinely market-specific plumbing (sessions, overnight gaps, symbol universes)
stays under ``markets/<market>/indicators`` and ``markets/<market>/universe``.

    <name>.py             generic, market-agnostic implementation
    <market>_<name>.py    thin subclass: default_params for that market
"""

from asta.markets.strategies.asia_range_breakout import AsiaRangeBreakoutStrategy
from asta.markets.strategies.breakout_trend import BreakoutTrendStrategy
from asta.markets.strategies.crypto_breakout_trend import CryptoBreakoutTrendStrategy
from asta.markets.strategies.crypto_ema_pullback import CryptoEMAPullbackStrategy
from asta.markets.strategies.crypto_rsi_divergence import CryptoRSIDivergenceStrategy
from asta.markets.strategies.crypto_volume_spike import CryptoVolumeSpikeStrategy
from asta.markets.strategies.ema_crossover import EMACrossoverStrategy
from asta.markets.strategies.forex_asia_range_breakout import ForexAsiaRangeBreakoutStrategy
from asta.markets.strategies.forex_ema_crossover import ForexEMACrossoverStrategy
from asta.markets.strategies.forex_rsi_divergence import ForexRSIDivergenceStrategy
from asta.markets.strategies.liquidity_momentum import LiquidityMomentumStrategy
from asta.markets.strategies.rsi_divergence import RSIDivergenceStrategy
from asta.markets.strategies.stock_breakout_trend import StockBreakoutTrendStrategy
from asta.markets.strategies.stock_ema_trend import StockEMATrendStrategy
from asta.markets.strategies.stock_liquidity_momentum import StockLiquidityMomentumStrategy
from asta.markets.strategies.volume_spike import VolumeSpikeStrategy

__all__ = [
    "AsiaRangeBreakoutStrategy",
    "BreakoutTrendStrategy",
    "CryptoBreakoutTrendStrategy",
    "CryptoEMAPullbackStrategy",
    "CryptoRSIDivergenceStrategy",
    "CryptoVolumeSpikeStrategy",
    "EMACrossoverStrategy",
    "ForexAsiaRangeBreakoutStrategy",
    "ForexEMACrossoverStrategy",
    "ForexRSIDivergenceStrategy",
    "LiquidityMomentumStrategy",
    "RSIDivergenceStrategy",
    "StockBreakoutTrendStrategy",
    "StockEMATrendStrategy",
    "StockLiquidityMomentumStrategy",
    "VolumeSpikeStrategy",
]
