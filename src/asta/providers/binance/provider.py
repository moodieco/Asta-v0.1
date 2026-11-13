"""Binance spot klines provider (public REST, no API key needed)."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from asta.core.signal_model import Candle, Market
from asta.providers.base import MarketDataProvider
from asta.utils.exceptions import ProviderError

INTERVALS: Dict[str, str] = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1h",
    "2h": "2h",
    "4h": "4h",
    "6h": "6h",
    "12h": "12h",
    "1d": "1d",
    "1w": "1w",
}


class BinanceProvider(MarketDataProvider):
    market = Market.CRYPTO
    name = "binance"
    default_base_url = "https://api.binance.com"
    health_symbol = "BTCUSDT"

    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper().replace("/", "").replace("-", "").replace("_", "")

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        tf = self.validate_timeframe(timeframe)
        interval = INTERVALS.get(tf)
        if interval is None:
            raise ProviderError(
                "binance does not support timeframe {!r}".format(timeframe), provider=self.name
            )
        payload = self._request_json(
            "{}/api/v3/klines".format(self.base_url),
            params={
                "symbol": self.normalize_symbol(symbol),
                "interval": interval,
                "limit": max(1, min(int(limit), 1000)),
            },
        )
        if not isinstance(payload, list) or not payload:
            raise ProviderError(
                "unexpected klines payload", provider=self.name, symbol=symbol
            )
        candles: List[Candle] = []
        now_ms = int(time.time() * 1000)
        for row in payload:
            try:
                if int(row[6]) > now_ms:  # kline not closed yet
                    continue
                candles.append(
                    Candle(
                        timestamp=datetime.fromtimestamp(int(row[0]) / 1000, tz=timezone.utc),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                    )
                )
            except (IndexError, TypeError, ValueError) as exc:
                raise ProviderError(
                    "malformed kline row", provider=self.name, symbol=symbol, error=str(exc)
                ) from exc
        return candles

    def health_check(self) -> bool:
        try:
            self._request_json("{}/api/v3/ping".format(self.base_url))
            return True
        except ProviderError:
            return False
