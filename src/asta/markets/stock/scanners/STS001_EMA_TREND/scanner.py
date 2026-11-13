"""STS001_EMA_TREND - EMA Trend scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.stock.strategies.ema_trend import StockEMATrendStrategy


@register_scanner
class EMATrendScanner(ScannerBase):
    id = "STS001_EMA_TREND"
    name = "EMA Trend"
    market = Market.STOCK
    default_timeframe = "1d"
    strategy = "EMA Trend"
    min_candles = 220
    default_params = StockEMATrendStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = StockEMATrendStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
