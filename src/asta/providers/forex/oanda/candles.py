"""OANDA candles -> Candle models."""

from __future__ import annotations

from typing import Dict, List, Optional

from asta.core.signal_model import Candle, Market
from asta.providers.base import BaseHttpClient, MarketDataProvider
from asta.providers.forex.oanda.client import OandaClient
from asta.providers.forex.oanda.pricing import OandaPricing
from asta.utils.exceptions import ProviderError
from asta.utils.time_utils import parse_datetime

GRANULARITY: Dict[str, str] = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D",
    "1w": "W",
}


class OandaProvider(MarketDataProvider):
    market = Market.FOREX
    name = "oanda"
    default_base_url = "https://api-fxpractice.oanda.com"
    health_symbol = "EUR_USD"

    def build_client(self) -> BaseHttpClient:
        return OandaClient(self.settings)

    @property
    def api_token(self) -> str:
        return str(self.settings.get("api_token") or "").strip()

    def is_configured(self) -> bool:
        return bool(self.api_token and self.base_url)

    def normalize_symbol(self, symbol: str) -> str:
        raw = str(symbol).strip().upper().replace("/", "_").replace("-", "_")
        if "_" in raw:
            return raw
        if len(raw) == 6:
            return "{}_{}".format(raw[:3], raw[3:])
        return raw

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        tf = self.validate_timeframe(timeframe)
        granularity = GRANULARITY.get(tf)
        if granularity is None:
            raise ProviderError(
                "oanda does not support timeframe {!r}".format(timeframe), provider=self.name
            )
        instrument = self.normalize_symbol(symbol)
        rows = self.client.candles(instrument, granularity, max(2, min(int(limit), 5000)))

        candles: List[Candle] = []
        for row in rows:
            if not row.get("complete", True):
                continue
            mid = row.get("mid") or {}
            try:
                candles.append(
                    Candle(
                        timestamp=parse_datetime(row["time"]),
                        open=float(mid["o"]),
                        high=float(mid["h"]),
                        low=float(mid["l"]),
                        close=float(mid["c"]),
                        volume=float(row.get("volume", 0) or 0),
                    )
                )
            except (KeyError, TypeError, ValueError) as exc:
                raise ProviderError(
                    "malformed candle row", provider=self.name, symbol=instrument, error=str(exc)
                ) from exc
        return candles

    def fetch_price(self, symbol: str) -> Optional[float]:
        return OandaPricing(self.client).current_price(self.normalize_symbol(symbol))
