"""Provider selection and market settings (config + shipped defaults)."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import yaml
from pydantic import BaseModel, Field

from asta.core.signal_model import Market
from asta.providers.base import MarketDataProvider
from asta.utils.exceptions import ConfigurationError
from asta.utils.logger import get_logger


class MarketSettings(BaseModel):
    enabled: bool = True
    symbols: List[str] = Field(default_factory=list)

    def normalized_symbols(self) -> List[str]:
        return [symbol.strip().upper() for symbol in self.symbols if symbol and symbol.strip()]


class MarketManager:
    """Knows which markets are enabled and which provider serves them."""

    def __init__(
        self,
        providers: Dict[Market, MarketDataProvider],
        markets: Optional[Dict[str, MarketSettings]] = None,
        defaults: Optional[Dict[str, MarketSettings]] = None,
        universes: Optional[Dict[str, List[str]]] = None,
    ):
        self.providers = dict(providers)
        self.defaults = dict(defaults or {})
        self.universes = dict(universes or {})
        self.markets = self._merge(markets or {})
        self.logger = get_logger("asta.market_manager")

    def _merge(self, configured: Dict[str, MarketSettings]) -> Dict[str, MarketSettings]:
        merged: Dict[str, MarketSettings] = dict(self.defaults)
        for key, value in configured.items():
            merged[str(key).lower()] = value
        return merged

    @classmethod
    def load_defaults(cls, root: Optional[Path] = None) -> Dict[str, MarketSettings]:
        """Read ``markets/<market>/market_config.yaml`` shipped with the code."""
        import asta.markets as markets_package

        base = Path(root) if root else Path(list(markets_package.__path__)[0])
        defaults: Dict[str, MarketSettings] = {}
        for path in sorted(base.glob("*/market_config.yaml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                market = str(raw.get("market") or path.parent.name).lower()
                defaults[market] = MarketSettings(
                    enabled=bool(raw.get("enabled", True)),
                    symbols=list(raw.get("symbols") or []),
                )
            except Exception as exc:  # noqa: BLE001 - bad default file must not stop startup
                get_logger("asta.market_manager").error(
                    "invalid market_config.yaml", extra={"path": str(path), "error": str(exc)}
                )
        return defaults

    def settings_for(self, market: Market) -> MarketSettings:
        return self.markets.get(market.value, MarketSettings(enabled=False))

    def is_enabled(self, market: Market) -> bool:
        return self.settings_for(market).enabled

    def symbols_for(self, market: Market) -> List[str]:
        configured = self.settings_for(market).normalized_symbols()
        return configured or list(self.universes.get(market.value, []))

    @classmethod
    def load_universes(cls, root: Optional[Path] = None) -> Dict[str, List[str]]:
        """Read each market's ``universe.py`` for the shipped default symbols."""
        import asta.markets as markets_package

        base = Path(root) if root else Path(list(markets_package.__path__)[0])
        universes: Dict[str, List[str]] = {}
        for path in sorted(base.glob("*/universe.py")):
            market = path.parent.name
            try:
                module = __import__("asta.markets.{}.universe".format(market), fromlist=["symbols"])
                universes[market] = list(module.symbols())
            except Exception as exc:  # noqa: BLE001 - a broken universe must not stop startup
                get_logger("asta.market_manager").error(
                    "invalid universe module", extra={"market": market, "error": str(exc)}
                )
        return universes

    def provider_for(self, market: Market) -> MarketDataProvider:
        provider = self.providers.get(market)
        if provider is None:
            raise ConfigurationError("no market data provider for {}".format(market.value))
        return provider
