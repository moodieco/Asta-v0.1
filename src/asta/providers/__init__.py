"""Market data providers (Binance, OANDA, Yahoo Stocks)."""

from typing import Any, Dict, Optional

from asta.core.signal_model import Market
from asta.providers.base import MarketDataProvider

__all__ = ["MarketDataProvider", "build_providers"]


def build_providers(settings: Optional[Dict[str, Any]] = None) -> Dict[Market, MarketDataProvider]:
    """Instantiate every provider from the ``providers:`` config block.

    A provider is always constructed; missing credentials surface at fetch time
    so one unconfigured market never blocks the others.
    """
    settings = settings or {}
    from asta.providers.binance.provider import BinanceProvider
    from asta.providers.oanda.provider import OandaProvider
    from asta.providers.stock.provider import StockProvider

    providers: Dict[Market, MarketDataProvider] = {
        Market.CRYPTO: BinanceProvider(settings.get("binance") or {}),
        Market.FOREX: OandaProvider(settings.get("oanda") or {}),
        Market.STOCK: StockProvider(settings.get("stock") or {}),
    }
    return providers
