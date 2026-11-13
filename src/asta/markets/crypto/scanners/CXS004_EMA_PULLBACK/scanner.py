"""CXS004 - trend pullback continuation scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.crypto.strategies.ema_pullback import CryptoEMAPullbackStrategy


@register_scanner
class EMAPullbackScanner(ScannerBase):
    id = "CXS004_EMA_PULLBACK"
    name = "EMA Pullback"
    market = Market.CRYPTO
    default_timeframe = "1h"
    strategy = "EMA Pullback"
    min_candles = 120
    default_params = CryptoEMAPullbackStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = CryptoEMAPullbackStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
