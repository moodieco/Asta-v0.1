"""CXS002_VOLUME_SPIKE - Volume Spike scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.strategies.crypto_volume_spike import CryptoVolumeSpikeStrategy


@register_scanner
class VolumeSpikeScanner(ScannerBase):
    id = "CXS002_VOLUME_SPIKE"
    name = "Volume Spike"
    market = Market.CRYPTO
    default_timeframe = "15m"
    strategy = "Volume Spike"
    min_candles = 40
    default_params = CryptoVolumeSpikeStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = CryptoVolumeSpikeStrategy(**self.params)

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
