"""STS004_MOMENTUM_SCALP - Momentum Scalp scanner."""

from typing import List

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.stock.idx_universe import idx_symbols
from asta.markets.strategies.stock_momentum_scalp import StockMomentumScalpStrategy


@register_scanner
class MomentumScalpScanner(ScannerBase):
    id = "STS004_MOMENTUM_SCALP"
    name = "Momentum Scalp"
    market = Market.STOCK
    default_timeframe = "1d"
    strategy = "Momentum Scalp"
    min_candles = 6
    default_params = StockMomentumScalpStrategy.default_params

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = StockMomentumScalpStrategy(**self.params)

    @property
    def symbols(self) -> List[str]:
        """An explicit ``symbols:`` list wins; empty means the full IDX universe."""
        configured = list(self.config.symbols)
        return configured or idx_symbols()

    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
