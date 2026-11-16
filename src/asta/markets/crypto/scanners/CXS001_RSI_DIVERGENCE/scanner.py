"""CXS001_RSI_DIVERGENCE - RSI Divergence scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.strategies.crypto_rsi_divergence import CryptoRSIDivergenceStrategy


@register_scanner
class RSIDivergenceScanner(ScannerBase):
    id = "CXS001_RSI_DIVERGENCE"
    name = "RSI Divergence"
    market = Market.CRYPTO
    default_timeframe = "1h"
    strategy = "RSI Divergence"
    min_candles = 120
    default_params = CryptoRSIDivergenceStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = CryptoRSIDivergenceStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
