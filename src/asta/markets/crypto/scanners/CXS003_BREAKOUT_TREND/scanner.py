"""CXS003_BREAKOUT_TREND - Breakout Trend scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.crypto.strategies.breakout_trend import CryptoBreakoutTrendStrategy


@register_scanner
class BreakoutTrendScanner(ScannerBase):
    id = "CXS003_BREAKOUT_TREND"
    name = "Breakout Trend"
    market = Market.CRYPTO
    default_timeframe = "1h"
    strategy = "Breakout Trend"
    min_candles = 90
    default_params = CryptoBreakoutTrendStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = CryptoBreakoutTrendStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
