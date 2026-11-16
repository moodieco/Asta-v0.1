"""FXS001_RSI_DIVERGENCE - RSI Divergence scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.strategies.forex_rsi_divergence import ForexRSIDivergenceStrategy


@register_scanner
class RSIDivergenceScanner(ScannerBase):
    id = "FXS001_RSI_DIVERGENCE"
    name = "RSI Divergence"
    market = Market.FOREX
    default_timeframe = "1h"
    strategy = "RSI Divergence"
    min_candles = 120
    default_params = ForexRSIDivergenceStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = ForexRSIDivergenceStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
