"""STS003_IDX_LIQUIDITY - BPJS SCANNER.

Intraday IHSG screen: every listed name, all sectors, measured on today's 5m
bars in WIB. First pass at 09:30, re-evaluated until 15:45 (time exit before
the close). Signals are LONG with a 2% stop and a 5% target.

The universe is the shipped IDX list (``asta.markets.stock.idx_universe``) —
955 tickers, which is far too many to fetch in one cycle: the scanner rotates
through it ``batch_size`` symbols at a time, so one full sweep takes
``len(symbols) / batch_size`` cycles.

Net foreign buy/sell is not filtered (the Yahoo-backed provider has no such
field). Every signal carries ``foreign_note``; check it by hand before acting.
"""

from typing import List, Optional

from asta.core.scanner_base import ScannerBase
from asta.core.scanner_registry import register_scanner
from asta.core.signal_model import Market, ScanContext, Signal
from asta.markets.stock.idx_universe import idx_symbols
from asta.markets.strategies.stock_liquidity_momentum import StockLiquidityMomentumStrategy


@register_scanner
class IndexLiquidityScanner(ScannerBase):
    id = "STS003_IDX_LIQUIDITY"
    name = "BPJS SCANNER"
    market = Market.STOCK
    default_timeframe = "5m"
    strategy = "Liquidity Momentum"
    min_candles = 90
    default_params = {**StockLiquidityMomentumStrategy.default_params, "batch_size": 120}

    def __init__(self, config=None):
        super().__init__(config)
        self.impl = StockLiquidityMomentumStrategy(**self.params)
        self._cursor = 0

    # -- universe ---------------------------------------------------------
    @property
    def symbols(self) -> List[str]:
        """An explicit ``symbols:`` list wins; empty means every IDX issuer."""
        configured = list(self.config.symbols)
        return configured or idx_symbols()

    def pick_symbols(self, symbols: List[str], now: Optional[object] = None) -> List[str]:
        """Rotate through the universe so one cycle only fetches one batch."""
        batch = int(self.param("batch_size", 0) or 0)
        total = len(symbols)
        if batch <= 0 or batch >= total:
            return list(symbols)
        start = self._cursor % total
        picked = [symbols[(start + offset) % total] for offset in range(batch)]
        self._cursor = (start + batch) % total
        return picked

    # -- evaluation -------------------------------------------------------
    def evaluate(self, context: ScanContext) -> List[Signal]:
        return self.signals_from(context, self.impl.evaluate(context))
