"""FXS003_ASIA_RANGE_BREAKOUT - Asia session range breakout (ICT AMD shape)."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.strategies.forex_asia_range_breakout import ForexAsiaRangeBreakoutStrategy


@register_scanner
class AsiaRangeBreakoutScanner(ScannerBase):
    id = "FXS003_ASIA_RANGE_BREAKOUT"
    name = "Asia Range Breakout"
    market = Market.FOREX
    default_timeframe = "1h"
    strategy = "Asia Range Breakout"
    min_candles = 40
    default_params = ForexAsiaRangeBreakoutStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = ForexAsiaRangeBreakoutStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
