"""MT5 candles -> Candle models, with pagination and a public fallback."""

from __future__ import annotations

import time
from datetime import timedelta
from typing import Any, Dict, List, Optional

from asta.core.signal_model import Candle, Market
from asta.providers.base import BaseHttpClient, MarketDataProvider
from asta.providers.forex.mt5.client import MT5MarketDataClient, MT5TerminalClient
from asta.utils.exceptions import ProviderError
from asta.utils.logger import get_logger
from asta.utils.time_utils import parse_datetime, timeframe_to_seconds, utcnow

#: ASTA timeframe -> MT5 period
PERIODS: Dict[str, str] = {
    "1m": "M1",
    "5m": "M5",
    "15m": "M15",
    "30m": "M30",
    "1h": "H1",
    "4h": "H4",
    "1d": "D1",
    "1w": "W1",
}

#: timeframes the public market-data MCP can serve
MARKETDATA_TIMEFRAMES = {"1h", "4h", "1d", "1w"}


class MT5Provider(MarketDataProvider):
    market = Market.FOREX
    name = "mt5"
    default_base_url = "http://127.0.0.1:22346/mcp"
    health_symbol = "EURUSD"

    def __init__(self, settings: Optional[Dict[str, Any]] = None, client=None):
        super().__init__(settings, client=client)
        self.logger = get_logger("asta.provider.mt5")
        self.terminal_url = str(settings.get("terminal_url") or self.default_base_url) if settings else self.default_base_url
        self.terminal_token = str((settings or {}).get("terminal_token") or "")
        self.marketdata_url = str((settings or {}).get("marketdata_url") or "")
        self.marketdata_token = str((settings or {}).get("marketdata_token") or "")
        self._terminal: Optional[MT5TerminalClient] = None
        self._marketdata: Optional[MT5MarketDataClient] = None
        self._terminal_ok: Optional[bool] = None
        self._terminal_checked_at = 0.0
        self._terminal_retry_seconds = 300

    # MarketDataProvider expects a BaseHttpClient; MT5 uses MCP instead.
    def build_client(self) -> BaseHttpClient:  # pragma: no cover - not used
        return BaseHttpClient(base_url=self.base_url, timeout=self.timeout)

    def close(self) -> None:
        for client in (self._terminal, self._marketdata):
            if client is not None:
                client.close()
        self._terminal = None
        self._marketdata = None

    # -- clients ----------------------------------------------------------
    @property
    def terminal(self) -> Optional[MT5TerminalClient]:
        if not self.terminal_url:
            return None
        if self._terminal is None:
            self._terminal = MT5TerminalClient(self.terminal_url, self.terminal_token)
        return self._terminal

    @property
    def marketdata(self) -> Optional[MT5MarketDataClient]:
        if not self.marketdata_url:
            return None
        if self._marketdata is None:
            self._marketdata = MT5MarketDataClient(self.marketdata_url, self.marketdata_token)
        return self._marketdata

    def is_configured(self) -> bool:
        return bool(self.terminal_url or self.marketdata_url)

    def normalize_symbol(self, symbol: str) -> str:
        return str(symbol).strip().upper().replace("/", "").replace("_", "").replace("-", "")

    # -- parsing ----------------------------------------------------------
    @staticmethod
    def _to_candle(bar: Dict[str, Any]) -> Optional[Candle]:
        raw_time = bar.get("time") or bar.get("datetime") or bar.get("date")
        if raw_time is None:
            return None
        try:
            volume = bar.get("volume")
            if volume in (None, 0):
                volume = bar.get("tick_volume") or bar.get("real_volume") or 0
            return Candle(
                timestamp=parse_datetime(str(raw_time)),
                open=float(bar["open"]),
                high=float(bar["high"]),
                low=float(bar["low"]),
                close=float(bar["close"]),
                volume=float(volume or 0),
            )
        except (KeyError, TypeError, ValueError):
            return None

    def _parse(self, bars: List[Dict[str, Any]]) -> List[Candle]:
        candles = []
        for bar in bars:
            candle = self._to_candle(bar)
            if candle is not None:
                candles.append(candle)
        candles.sort(key=lambda candle: candle.timestamp)
        # drop duplicates that appear when paginating
        deduped: List[Candle] = []
        for candle in candles:
            if not deduped or candle.timestamp != deduped[-1].timestamp:
                deduped.append(candle)
        return deduped

    # -- fetching ---------------------------------------------------------
    def _window_days(self, timeframe: str, limit: int) -> int:
        seconds = timeframe_to_seconds(timeframe)
        # five trading days per week for FX
        bars_per_day = 86400 / seconds * (5 / 7)
        return max(3, int((limit / max(bars_per_day, 1)) * 1.8) + 2)

    def _terminal_available(self) -> bool:
        """Cache the terminal state so a disconnected terminal costs one probe."""
        client = self.terminal
        if client is None:
            return False
        now = time.monotonic()
        if self._terminal_ok is None or (now - self._terminal_checked_at) > self._terminal_retry_seconds:
            self._terminal_ok = client.is_connected()
            self._terminal_checked_at = now
            if not self._terminal_ok:
                self.logger.info("mt5 terminal disconnected, using public market data")
        return bool(self._terminal_ok)

    def _from_terminal(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        client = self.terminal
        if client is None or not self._terminal_available():
            return []
        end = utcnow()
        start = end - timedelta(days=self._window_days(timeframe, limit))
        try:
            bars = client.chart_history(symbol, PERIODS[timeframe], start, end, limit=max(limit, 500))
        except ProviderError as exc:
            self.logger.warning("mt5 terminal history failed", extra={"error": str(exc)})
            return []
        return self.filter_closed_candles(self._parse(bars), timeframe)

    def _from_marketdata(self, symbol: str, timeframe: str, limit: int) -> List[Candle]:
        client = self.marketdata
        if client is None or timeframe not in MARKETDATA_TIMEFRAMES:
            return []
        end = utcnow()
        start = end - timedelta(days=max(self._window_days(timeframe, 120), 7))
        try:
            bars = client.history(symbol, timeframe, start, end)
        except ProviderError as exc:
            self.logger.warning("mt5 marketdata history failed", extra={"error": str(exc)})
            return []
        return self.filter_closed_candles(self._parse(bars), timeframe)

    def fetch_candles(self, symbol: str, timeframe: str, limit: int = 200) -> List[Candle]:
        tf = self.validate_timeframe(timeframe)
        if tf not in PERIODS:
            raise ProviderError(
                "mt5 provider does not support timeframe {!r}".format(timeframe), provider=self.name
            )
        ticker = self.normalize_symbol(symbol)

        candles = self._from_terminal(ticker, tf, limit)
        source = "terminal"
        if not candles:
            candles = self._from_marketdata(ticker, tf, limit)
            source = "marketdata"
        if not candles:
            raise ProviderError(
                "no candles from MT5 (terminal disconnected and no public data for {})".format(tf),
                provider=self.name,
                symbol=ticker,
            )
        self.logger.debug(
            "mt5 candles", extra={"symbol": ticker, "timeframe": tf, "bars": len(candles), "source": source}
        )
        return candles[-int(limit):] if limit else candles

    def fetch_price(self, symbol: str) -> Optional[float]:
        ticker = self.normalize_symbol(symbol)
        client = self.terminal
        if client is not None:
            entries = client.market_watch(ticker, limit=1)
            for entry in entries:
                bid, ask = entry.get("bid"), entry.get("ask")
                if bid and ask:
                    return (float(bid) + float(ask)) / 2.0
        candles = self.fetch_candles(ticker, "1h", 2)
        return candles[-1].close if candles else None

    def health_check(self) -> bool:
        client = self.terminal
        if client is not None and client.is_connected():
            return True
        marketdata = self.marketdata
        return bool(marketdata and marketdata.ping(self.health_symbol))
