"""Market data providers, one package per broker."""

from typing import Any, Dict, Optional

from asta.core.signal_model import Market
from asta.providers.base import BaseHttpClient, MarketDataProvider

__all__ = ["BaseHttpClient", "MarketDataProvider", "build_providers"]


def build_providers(settings: Optional[Dict[str, Any]] = None) -> Dict[Market, MarketDataProvider]:
    """Instantiate every provider from the ``providers:`` config block.

    Providers are always constructed; missing credentials surface at fetch time
    so one unconfigured market never blocks the others.
    """
    settings = settings or {}
    from asta.providers.crypto.binance import BinanceProvider
    from asta.providers.forex.oanda import OandaProvider
    from asta.providers.stock.yahoo import StockProvider

    return {
        Market.CRYPTO: BinanceProvider(settings.get("binance") or {}),
        Market.FOREX: OandaProvider(settings.get("oanda") or {}),
        Market.STOCK: StockProvider(settings.get("stock") or {}),
    }
