"""Data access: candles from providers, cached per (symbol, timeframe)."""

from __future__ import annotations

from typing import Dict, List, Optional

from asta.core.market_manager import MarketManager
from asta.core.scanner_base import ScannerBase
from asta.core.signal_model import Candle, Market, ScanContext
from asta.providers.base import MarketDataProvider
from asta.storage.cache import TTLCache
from asta.utils.exceptions import ProviderError
from asta.utils.logger import get_logger


class DataService:
    """Every candle request in a cycle goes through here.

    A short TTL cache means three crypto scanners on the same timeframe reuse one
    HTTP call per symbol instead of hammering the exchange.
    """

    def __init__(
        self,
        market_manager: MarketManager,
        cache: Optional[TTLCache] = None,
        cache_ttl_seconds: int = 30,
    ):
        self.market_manager = market_manager
        self.cache = cache if cache is not None else TTLCache(default_ttl=cache_ttl_seconds)
        self.cache_ttl_seconds = int(cache_ttl_seconds)
        self.logger = get_logger("asta.data")

    # -- accessors --------------------------------------------------------
    def provider(self, market: Market) -> MarketDataProvider:
        return self.market_manager.provider_for(market)

    def symbols(self, market: Market) -> List[str]:
        return self.market_manager.symbols_for(market)

    def is_enabled(self, market: Market) -> bool:
        return self.market_manager.is_enabled(market)

    # -- candles ----------------------------------------------------------
    def fetch_candles(
        self, market: Market, symbol: str, timeframe: str, limit: int
    ) -> List[Candle]:
        key = "candles:{}:{}:{}:{}".format(market.value, symbol.upper(), timeframe, limit)
        cached = self.cache.get(key)
        if cached is not None:
            return cached
        provider = self.provider(market)
        candles = provider.fetch_candles(symbol, timeframe, limit)
        if not candles:
            raise ProviderError("provider returned no candles", symbol=symbol, provider=provider.name)
        self.cache.set(key, candles, ttl=self.cache_ttl_seconds)
        return candles

    def build_context(
        self, scanner: ScannerBase, symbol: str, limit: Optional[int] = None
    ) -> ScanContext:
        count = limit or max(scanner.min_candles + 40, 120)
        candles = self.fetch_candles(scanner.market, symbol, scanner.timeframe, count)
        return ScanContext(
            market=scanner.market,
            symbol=symbol,
            timeframe=scanner.timeframe,
            candles=candles,
            scanner_id=scanner.id,
        )

    # -- health -----------------------------------------------------------
    def health(self) -> Dict[str, bool]:
        status: Dict[str, bool] = {}
        for market in Market:
            if not self.is_enabled(market):
                status[market.value] = False
                continue
            provider = self.market_manager.providers.get(market)
            status[market.value] = bool(provider and provider.health_check())
        return status

    def cache_stats(self) -> Dict[str, int]:
        return {"entries": len(self.cache), "ttl_seconds": self.cache_ttl_seconds}
