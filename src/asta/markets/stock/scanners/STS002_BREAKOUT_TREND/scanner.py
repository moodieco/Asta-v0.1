"""STS002_BREAKOUT_TREND - Breakout Trend scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.stock.strategies.breakout_trend import StockBreakoutTrendStrategy


@register_scanner
class BreakoutTrendScanner(ScannerBase):
    id = "STS002_BREAKOUT_TREND"
    name = "Breakout Trend"
    market = Market.STOCK
    default_timeframe = "1d"
    strategy = "Breakout Trend"
    min_candles = 90
    default_params = StockBreakoutTrendStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = StockBreakoutTrendStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
