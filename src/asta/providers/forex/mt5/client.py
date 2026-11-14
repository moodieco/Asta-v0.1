"""Wrappers around the MetaTrader 5 MCP servers.

* ``terminal``    — local MetaTrader 5 terminal (deep history, needs a logged-in terminal)
* ``marketdata``  — public MetaTrader market data (no terminal, limited window)
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from asta.providers.mcp import MCPClient
from asta.utils.time_utils import isoformat, utcnow


class MT5TerminalClient:
    def __init__(self, url: str, token: str = "", client: Optional[MCPClient] = None):
        self.mcp = client or MCPClient(url, token)

    def close(self) -> None:
        self.mcp.close()

    def terminal_info(self) -> Dict[str, Any]:
        return self.mcp.call_tool("terminal_get_info")

    def is_connected(self) -> bool:
        try:
            info = self.terminal_info()
        except Exception:  # noqa: BLE001 - health probe
            return False
        terminal = info.get("terminal") or info
        connection = terminal.get("connection") or {}
        return str(connection.get("state", "")).lower() == "connected"

    def chart_history(
        self,
        symbol: str,
        period: str,
        start: datetime,
        end: datetime,
        limit: int = 5000,
    ) -> List[Dict[str, Any]]:
        payload = self.mcp.call_tool(
            "get_chart_history",
            {
                "symbol": symbol,
                "period": period,
                "datetime_from": isoformat(start),
                "datetime_to": isoformat(end),
                "limit": int(limit),
            },
        )
        return list(payload.get("history") or [])

    def market_watch(self, symbol: Optional[str] = None, limit: int = 50) -> List[Dict[str, Any]]:
        arguments: Dict[str, Any] = {"limit": limit}
        if symbol:
            arguments["symbol"] = symbol
        payload = self.mcp.call_tool("get_marketwatch_symbols", arguments)
        return list(payload.get("symbols") or [])


class MT5MarketDataClient:
    """Public market-data MCP (no terminal required, ~120 bars per request)."""

    def __init__(self, url: str, token: str = "", client: Optional[MCPClient] = None):
        self.mcp = client or MCPClient(url, token)

    def close(self) -> None:
        self.mcp.close()

    def history(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> List[Dict[str, Any]]:
        payload = self.mcp.call_tool(
            "marketdata_symbol_history",
            {
                "symbol": symbol,
                "timeframe": timeframe,
                "from": isoformat(start),
                "to": isoformat(end),
            },
        )
        return list(payload.get("bars") or [])

    def ping(self, symbol: str = "EURUSD") -> bool:
        from datetime import timedelta

        try:
            bars = self.history(symbol, "1h", utcnow() - timedelta(days=3), utcnow())
        except Exception:  # noqa: BLE001 - health probe
            return False
        return bool(bars)
