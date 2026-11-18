"""Typed wrapper over the ``stockbit-mcp`` tool surface.

The sidecar exposes ~150 MCP tools. ASTA only needs the ones that carry IDX
information no other provider here has — broker flow, depth, fundamentals,
session state — so this module names them explicitly instead of letting callers
pass tool strings around.

**No candle source.** ``chart_series`` is the only price-history tool and its
"timeframe" is a calendar window, not a bar interval; on the daily route the
close arrives as ``value`` while open/high/low/volume arrive empty, so every
point is a flat candle with no volume. Building :class:`~asta.core.signal_model.Candle`
objects out of it would feed every indicator in this repo a series that looks
plausible and is wrong, which is exactly what ``src/asta/providers/base.py``
refuses to do. :meth:`StockbitClient.fetch_candles` therefore raises instead of
returning something that resembles bars. Candles stay on Yahoo; Stockbit adds
the context Yahoo cannot.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from asta.core.signal_model import Candle
from asta.providers.mcp import MCPClient, MCPError
from asta.utils.exceptions import ProviderError
from asta.utils.logger import get_logger

DEFAULT_URL = "http://127.0.0.1:8787/mcp"

#: Calendar windows the ``chart_series`` tool accepts. Uppercase or interval
#: style values are refused upstream, so they are refused here too.
CHART_WINDOWS = ("1w", "1m", "3m", "ytd", "1y", "3y", "5y")

#: Values the sidecar's schema accepts for ``broker_summary/bandar_detector``'s
#: ``period``. Anything else is rejected upstream with a validation error.
BROKER_PERIODS = ("LATEST", "YESTERDAY", "LAST_7_DAYS", "LAST_3_MONTHS", "YEAR_TO_DATE")

CANDLES_UNSUPPORTED = (
    "stockbit-mcp exposes no OHLCV series: chart_series returns close-only points "
    "(open/high/low/volume empty, volume null) and intraday_prices is a minutely "
    "close series for the current session only. Use the yahoo provider for candles."
)


class StockbitError(ProviderError):
    """A Stockbit tool call failed."""


class StockbitClient:
    """IDX quotes, broker flow and fundamentals via the stockbit-mcp sidecar."""

    def __init__(
        self,
        settings: Optional[Dict[str, Any]] = None,
        client: Optional[Any] = None,
    ):
        settings = dict(settings or {})
        env_url = (os.environ.get("STOCKBIT_MCP_URL") or "").strip()
        env_token = (os.environ.get("STOCKBIT_MCP_TOKEN") or "").strip()
        self.url = str(settings.get("url") or settings.get("base_url") or env_url or DEFAULT_URL)
        self.token = str(settings.get("token") or env_token or "")
        self.timeout = float(settings.get("timeout_seconds", 30))
        self._mcp = client or MCPClient(self.url, self.token, timeout=self.timeout)
        self.logger = get_logger("asta.provider.stockbit")

    # -- lifecycle --------------------------------------------------------
    @property
    def mcp(self) -> MCPClient:
        return self._mcp

    def close(self) -> None:
        self._mcp.close()

    def __enter__(self) -> "StockbitClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def is_configured(self) -> bool:
        return bool(self.url and self.token)

    # -- plumbing ---------------------------------------------------------
    @staticmethod
    def normalize_symbol(symbol: str) -> str:
        """IDX ticker: upper-case, without a Yahoo ``.JK`` suffix."""
        ticker = str(symbol).strip().upper()
        if ticker.endswith(".JK"):
            ticker = ticker[:-3]
        return ticker.replace("/", "").replace("-", "")

    @staticmethod
    def _upstream_error(exc: MCPError) -> Tuple[str, str]:
        """Unwrap the sidecar's own error envelope into (message, kind).

        Tool failures arrive as ``isError`` with a JSON blob in ``content[].text``
        carrying ``{"success": false, "error": ..., "kind": ...}``. Without this
        the caller sees a Python repr of the MCP result instead of
        "No Stockbit session stored".
        """
        result = exc.context.get("result")
        if isinstance(result, dict):
            for item in result.get("content") or []:
                if not isinstance(item, dict):
                    continue
                text = item.get("text")
                if not isinstance(text, str):
                    continue
                try:
                    payload = json.loads(text)
                except (TypeError, ValueError):
                    continue
                if isinstance(payload, dict) and payload.get("error"):
                    return str(payload["error"]), str(payload.get("kind") or "")
        return str(exc), ""

    def _call(self, tool: str, **arguments: Any) -> Dict[str, Any]:
        args = {key: value for key, value in arguments.items() if value is not None}
        try:
            payload = self._mcp.call_tool(tool, args)
        except MCPError as exc:
            message, kind = self._upstream_error(exc)
            raise StockbitError(
                "{}: {}".format(tool, message), tool=tool, kind=kind, url=self.url
            ) from exc
        if not isinstance(payload, dict):
            raise StockbitError("{} returned {}".format(tool, type(payload).__name__), tool=tool)
        return payload

    def tools(self) -> List[str]:
        """Names the sidecar currently exposes — useful to assert a profile."""
        return sorted(tool.get("name", "") for tool in self._mcp.tools_list())

    def status(self) -> Dict[str, Any]:
        return self._call("status")

    # -- prices -----------------------------------------------------------
    def quote(self, symbol: str) -> Dict[str, Any]:
        return self._call("quote", symbol=self.normalize_symbol(symbol))

    def orderbook(self, symbol: str) -> Dict[str, Any]:
        return self._call("orderbook", symbol=self.normalize_symbol(symbol))

    def price_bands(self, symbol: str) -> Dict[str, Any]:
        """IDX auto-rejection band (ARA/ARB) plus the session's foreign flow."""
        return self._call("price_bands", symbol=self.normalize_symbol(symbol))

    def chart_series(self, symbol: str, window: str = "1y") -> Dict[str, Any]:
        """Raw chart payload. Close-only — see the module docstring."""
        value = str(window).strip().lower()
        if value not in CHART_WINDOWS:
            raise StockbitError(
                "chart_series window must be one of {}".format(", ".join(CHART_WINDOWS)),
                window=window,
            )
        return self._call("chart_series", symbol=self.normalize_symbol(symbol), timeframe=value)

    def daily_closes(self, symbol: str, window: str = "1y") -> List[Tuple[str, float]]:
        """``(date, close)`` pairs, oldest first.

        This is a price *level* series for context — trend direction, distance
        from a level, relative strength. It is not OHLCV and cannot drive a
        scanner: see :meth:`fetch_candles`.
        """
        payload = self.chart_series(symbol, window)
        bars: List[Any] = []
        raw_bars = payload.get("bars")
        if isinstance(raw_bars, list):
            bars = raw_bars
        else:
            raw_items = payload.get("items")
            if isinstance(raw_items, list):
                bars = raw_items
        closes: List[Tuple[str, float]] = []
        for bar in bars:
            if not isinstance(bar, dict):
                continue
            date = bar.get("date") or bar.get("time")
            close = bar.get("close")
            if close is None:
                close = bar.get("value")
            if close is None:
                continue
            try:
                closes.append((str(date), float(close)))
            except (TypeError, ValueError):
                continue
        return closes

    def fetch_candles(self, symbol: str, timeframe: str = "1d", limit: int = 200) -> List[Candle]:
        """Always raises. Present so a misconfiguration fails loudly."""
        raise StockbitError(
            CANDLES_UNSUPPORTED, symbol=symbol, timeframe=timeframe, provider="stockbit"
        )

    # -- bandarmology -----------------------------------------------------
    def broker_summary(self, symbol: str, **filters: Any) -> Dict[str, Any]:
        """Which brokers net-bought/sold, in lots and IDR, with investor class."""
        period = str(filters.get("period") or "").upper()
        if period and period not in BROKER_PERIODS:
            raise StockbitError(
                "broker_summary period must be one of {}".format(", ".join(BROKER_PERIODS)),
                period=filters.get("period"),
            )
        return self._call("broker_summary", symbol=self.normalize_symbol(symbol), **filters)

    def bandar_detector(self, symbol: str, **filters: Any) -> Dict[str, Any]:
        """Accumulation/distribution reading computed from the broker summary."""
        return self._call("bandar_detector", symbol=self.normalize_symbol(symbol), **filters)

    def broker_activity(self, broker_code: str, **filters: Any) -> Dict[str, Any]:
        return self._call("broker_activity", broker_code=str(broker_code).upper(), **filters)

    # -- fundamentals -----------------------------------------------------
    def keystats(self, symbol: str) -> Dict[str, Any]:
        return self._call("keystats", symbol=self.normalize_symbol(symbol))

    def financials(self, symbol: str, **filters: Any) -> Dict[str, Any]:
        return self._call("financials", symbol=self.normalize_symbol(symbol), **filters)

    def ratios(self, symbol: str, **filters: Any) -> Dict[str, Any]:
        return self._call("ratios", symbol=self.normalize_symbol(symbol), **filters)

    # -- market -----------------------------------------------------------
    def market_session(self) -> Dict[str, Any]:
        """Where the IDX trading day is: pre-opening, session 1, break, session 2, shut."""
        return self._call("market_session")

    def top_movers(self, mover_type: str = "TOP_GAINER", limit: int = 10) -> Dict[str, Any]:
        return self._call("top_movers", type=mover_type, limit=limit)

    def news(self, symbol: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        ticker = self.normalize_symbol(symbol) if symbol else None
        return self._call("news", symbol=ticker, limit=limit)
