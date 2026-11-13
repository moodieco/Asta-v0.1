"""Stock tuned strategies (daily bars by default)."""

from asta.markets.stock.strategies.breakout_trend import StockBreakoutTrendStrategy
from asta.markets.stock.strategies.ema_trend import StockEMATrendStrategy

__all__ = ["StockBreakoutTrendStrategy", "StockEMATrendStrategy"]
