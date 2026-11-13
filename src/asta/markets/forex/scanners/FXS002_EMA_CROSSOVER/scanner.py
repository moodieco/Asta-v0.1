"""FXS002_EMA_CROSSOVER - EMA Crossover scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.forex.strategies.ema_crossover import ForexEMACrossoverStrategy


@register_scanner
class EMACrossoverScanner(ScannerBase):
    id = "FXS002_EMA_CROSSOVER"
    name = "EMA Crossover"
    market = Market.FOREX
    default_timeframe = "1h"
    strategy = "EMA Crossover"
    min_candles = 220
    default_params = ForexEMACrossoverStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = ForexEMACrossoverStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
