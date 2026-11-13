"""Provider selection + ``ScanContext`` construction per market."""

from __future__ import annotations

from typing import Dict, List, Optional

from pydantic import BaseModel, Field

from asta.core.scanner_base import ScannerBase
from asta.core.signal_model import Market, ScanContext
from asta.providers.base import MarketDataProvider
from asta.utils.exceptions import ConfigurationError, ProviderError
from asta.utils.logger import get_logger


class MarketSettings(BaseModel):
    enabled: bool = True
    symbols: List[str] = Field(default_factory=list)

    def normalized_symbols(self) -> List[str]:
        return [symbol.strip().upper() for symbol in self.symbols if symbol and symbol.strip()]


class MarketManager:
    def __init__(self, providers: Dict[Market, MarketDataProvider], markets: Dict[str, MarketSettings]):
        self.providers = dict(providers)
        self.markets = dict(markets)
        self.logger = get_logger("asta.market_manager")

    def settings_for(self, market: Market) -> MarketSettings:
        return self.markets.get(market.value, MarketSettings(enabled=False))

    def is_enabled(self, market: Market) -> bool:
        return self.settings_for(market).enabled

    def symbols_for(self, market: Market) -> List[str]:
        return self.settings_for(market).normalized_symbols()

    def provider_for(self, market: Market) -> MarketDataProvider:
        provider = self.providers.get(market)
        if provider is None:
            raise ConfigurationError("no market data provider for {}".format(market.value))
        return provider

    def build_context(self, scanner: ScannerBase, symbol: str, limit: Optional[int] = None) -> ScanContext:
        if not self.is_enabled(scanner.market):
            raise ProviderError(
                "market {} is disabled".format(scanner.market.value), market=scanner.market.value
            )
        provider = self.provider_for(scanner.market)
        count = limit or max(scanner.min_candles + 40, 120)
        candles = provider.fetch_candles(symbol, scanner.timeframe, count)
        if not candles:
            raise ProviderError(
                "provider returned no candles", provider=provider.name, symbol=symbol
            )
        return ScanContext(
            market=scanner.market,
            symbol=symbol,
            timeframe=scanner.timeframe,
            candles=candles,
            scanner_id=scanner.id,
        )

    def health(self) -> Dict[str, bool]:
        status: Dict[str, bool] = {}
        for market in Market:
            if not self.is_enabled(market):
                status[market.value] = False
                continue
            provider = self.providers.get(market)
            status[market.value] = bool(provider and provider.health_check())
        return status
