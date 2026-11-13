"""Yahoo chart payload -> Candle models."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from asta.core.signal_model import Candle, Market
from asta.providers.base import BaseHttpClient, MarketDataProvider
from asta.providers.stock.yahoo.client import INTERVALS, RANGES, YahooClient
from asta.utils.exceptions import ProviderError


class StockProvider(MarketDataProvider):
    market = Market.STOCK
    name = "yahoo"
    default_base_url = "https://query1.finance.yahoo.com"
    health_symbol = "AAPL"

    def build_client(self) -> BaseHttpClient:
        return YahooClient(self.settings)

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        tf = self.validate_timeframe(timeframe)
        interval = INTERVALS.get(tf)
        if interval is None:
            raise ProviderError(
                "stock provider does not support timeframe {!r}".format(timeframe),
                provider=self.name,
            )
        ticker = self.normalize_symbol(symbol)
        payload = self.client.chart(ticker, interval, RANGES[tf])
        candles = self.filter_closed_candles(self._parse(payload, ticker), tf)
        if not candles:
            raise ProviderError("no usable candles returned", provider=self.name, symbol=ticker)
        return candles[-int(limit):] if limit else candles

    def _parse(self, payload: Dict[str, Any], ticker: str) -> List[Candle]:
        chart = payload.get("chart") or {}
        if chart.get("error"):
            raise ProviderError(
                "yahoo error: {}".format(chart["error"]), provider=self.name, symbol=ticker
            )
        results = chart.get("result") or []
        if not results:
            raise ProviderError("empty chart result", provider=self.name, symbol=ticker)
        result = results[0]
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        opens = quote.get("open") or []
        highs = quote.get("high") or []
        lows = quote.get("low") or []
        closes = quote.get("close") or []
        volumes = quote.get("volume") or []

        candles: List[Candle] = []
        for index, stamp in enumerate(timestamps):
            try:
                open_, high, low, close = opens[index], highs[index], lows[index], closes[index]
            except IndexError:
                break
            if None in (open_, high, low, close):
                continue  # halted sessions come back as nulls
            volume = volumes[index] if index < len(volumes) and volumes[index] is not None else 0.0
            candles.append(
                Candle(
                    timestamp=datetime.fromtimestamp(int(stamp), tz=timezone.utc),
                    open=float(open_),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume),
                )
            )
        return candles
