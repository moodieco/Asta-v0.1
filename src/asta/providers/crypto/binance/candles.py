"""Binance klines -> Candle models."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from asta.core.signal_model import Candle, Market
from asta.providers.base import BaseHttpClient, MarketDataProvider
from asta.providers.crypto.binance.client import INTERVALS, BinanceClient
from asta.utils.exceptions import ProviderError


class BinanceProvider(MarketDataProvider):
    market = Market.CRYPTO
    name = "binance"
    default_base_url = "https://api.binance.com"
    health_symbol = "BTCUSDT"

    def build_client(self) -> BaseHttpClient:
        return BinanceClient(self.settings)

    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper().replace("/", "").replace("-", "").replace("_", "")

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        tf = self.validate_timeframe(timeframe)
        interval = INTERVALS.get(tf)
        if interval is None:
            raise ProviderError(
                "binance does not support timeframe {!r}".format(timeframe), provider=self.name
            )
        ticker = self.normalize_symbol(symbol)
        try:
            rows = self.client.klines(ticker, interval, limit)
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001 - adapter boundary
            raise ProviderError(
                "failed to fetch klines: {}".format(exc), provider=self.name, symbol=ticker
            ) from exc

        return self._parse_rows(rows, ticker)

    def _parse_rows(self, rows: List[List[Any]], ticker: str) -> List[Candle]:
        candles: List[Candle] = []
        now_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
        for row in rows:
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
                    "malformed kline row", provider=self.name, symbol=ticker, error=str(exc)
                ) from exc
        return candles

    def fetch_history(self, symbol: str, timeframe: str, days: int) -> List[Candle]:
        """Paginated history: Binance caps one request at 1000 klines."""
        tf = self.validate_timeframe(timeframe)
        interval = INTERVALS.get(tf)
        if interval is None:
            raise ProviderError(
                "binance does not support timeframe {!r}".format(timeframe), provider=self.name
            )
        ticker = self.normalize_symbol(symbol)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=int(days))
        cursor = int(start.timestamp() * 1000)
        end_ms = int(end.timestamp() * 1000)
        rows: List[List[Any]] = []
        seen = set()
        for _ in range(200):  # hard stop, 200k candles
            batch = self.client.klines(ticker, interval, 1000, start_time=cursor)
            if not batch:
                break
            for row in batch:
                if row[0] not in seen:
                    seen.add(row[0])
                    rows.append(row)
            if len(batch) < 1000:
                break
            cursor = int(batch[-1][0]) + 1
            if cursor >= end_ms:
                break
        return self._parse_rows(rows, ticker)

    def health_check(self) -> bool:
        return bool(self.client.ping())

    def fetch_price(self, symbol: str) -> Optional[float]:
        """Last traded price, handy for alert previews and diagnostics."""
        ticker = self.normalize_symbol(symbol)
        payload = self.client.request_json("/api/v3/ticker/price", params={"symbol": ticker})
        try:
            return float(payload["price"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ProviderError("malformed ticker payload", provider=self.name, symbol=ticker) from exc
