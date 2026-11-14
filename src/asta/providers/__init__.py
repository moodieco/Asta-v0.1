"""Market data providers, one package per broker/exchange."""

from typing import Any, Dict, Optional

from asta.core.signal_model import Market
from asta.providers.base import BaseHttpClient, MarketDataProvider
from asta.utils.exceptions import ConfigurationError

__all__ = ["BaseHttpClient", "MarketDataProvider", "build_providers", "PROVIDER_TYPES"]

#: market -> default provider type
DEFAULT_TYPE: Dict[str, str] = {
    "crypto": "binance",
    "forex": "mt5",
    "stock": "yahoo",
}

#: legacy config key per market (pre market-keyed providers)
LEGACY_KEY: Dict[str, str] = {"crypto": "binance", "forex": "oanda", "stock": "stock"}


def _provider_classes() -> Dict[str, Any]:
    from asta.providers.crypto.binance import BinanceProvider
    from asta.providers.forex.mt5 import MT5Provider
    from asta.providers.forex.oanda import OandaProvider
    from asta.providers.stock.yahoo import StockProvider

    return {
        "binance": BinanceProvider,
        "mt5": MT5Provider,
        "oanda": OandaProvider,
        "yahoo": StockProvider,
    }


PROVIDER_TYPES = tuple(_provider_classes().keys())


def build_providers(settings: Optional[Dict[str, Any]] = None) -> Dict[Market, MarketDataProvider]:
    """Instantiate one provider per market.

    Config is market-keyed and may select the backend with ``type``::

        providers:
          forex:  {type: mt5, terminal_url: ...}
          crypto: {type: binance}
          stock:  {type: yahoo}

    The legacy shape (``providers: {binance: ..., oanda: ..., stock: ...}``) still
    works when no market block is present.
    """
    settings = settings or {}
    classes = _provider_classes()
    providers: Dict[Market, MarketDataProvider] = {}

    for market in Market:
        market_config = settings.get(market.value)
        if market_config is not None:
            merged = dict(market_config)
            provider_type = str(merged.pop("type", DEFAULT_TYPE[market.value])).lower()
        else:
            legacy = LEGACY_KEY[market.value]
            merged = dict(settings.get(legacy) or {})
            provider_type = "oanda" if legacy == "oanda" else DEFAULT_TYPE[market.value]

        provider_class = classes.get(provider_type)
        if provider_class is None:
            raise ConfigurationError(
                "unknown provider type {!r} for {}; available: {}".format(
                    provider_type, market.value, ", ".join(sorted(classes))
                )
            )
        providers[market] = provider_class(merged)
    return providers
