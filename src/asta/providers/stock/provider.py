"""Stock provider backed by Yahoo Finance's public chart endpoint.

V0.1 uses Yahoo because it needs no API key. The provider interface is stable,
so swapping in Polygon / Alpaca / Finnhub later is a drop-in change.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List

from asta.core.signal_model import Candle, Market
from asta.providers.base import MarketDataProvider
from asta.utils.exceptions import ProviderError

INTERVALS: Dict[str, str] = {
    "1m": "1m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "60m",
    "1d": "1d",
    "1w": "1wk",
}

#: Yahoo caps history per interval; keep requests inside those windows.
RANGES: Dict[str, str] = {
    "1m": "7d",
    "5m": "1mo",
    "15m": "1mo",
    "30m": "1mo",
    "1h": "3mo",
    "1d": "2y",
    "1w": "5y",
}


class StockProvider(MarketDataProvider):
    market = Market.STOCK
    name = "stock"
    default_base_url = "https://query1.finance.yahoo.com"
    health_symbol = "AAPL"

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        tf = self.validate_timeframe(timeframe)
        interval = INTERVALS.get(tf)
        if interval is None:
            raise ProviderError(
                "stock provider does not support timeframe {!r}".format(timeframe),
                provider=self.name,
            )
        ticker = self.normalize_symbol(symbol)
        payload = self._request_json(
            "{}/v8/finance/chart/{}".format(self.base_url, ticker),
            params={
                "interval": interval,
                "range": RANGES[tf],
                "includePrePost": "false",
                "events": "div,split",
            },
            headers={"Accept": "application/json"},
        )
        candles = self._parse(payload, ticker)
        if not candles:
            raise ProviderError(
                "no usable candles returned", provider=self.name, symbol=ticker
            )
        return candles[-int(limit):] if limit else candles

    def _parse(self, payload: Any, ticker: str) -> List[Candle]:
        if not isinstance(payload, dict):
            raise ProviderError("unexpected payload", provider=self.name, symbol=ticker)
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
                open_, high, low, close = (
                    opens[index],
                    highs[index],
                    lows[index],
                    closes[index],
                )
            except IndexError:
                break
            if None in (open_, high, low, close):
                continue  # Yahoo emits nulls for halted sessions
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
