"""Stockbit MCP client: IDX depth that Yahoo does not carry.

Stockbit has no public developer API. This package talks to the third-party
``stockbit-mcp`` sidecar (``third_party/stockbit-mcp``) over stateless
Streamable HTTP, using :class:`asta.providers.mcp.MCPClient` — the same
transport the MT5 provider already uses.

What this client is for: quotes, orderbook, broker summary (bandarmology),
keystats, financials, foreign flow, session state. What it is NOT for: OHLCV
candles. See :meth:`StockbitClient.fetch_candles` for why, and
``docs/STOCKBIT_MCP.md`` for the measurement.
"""

from asta.providers.stock.stockbit.client import (
    CANDLES_UNSUPPORTED,
    StockbitClient,
    StockbitError,
)

__all__ = ["CANDLES_UNSUPPORTED", "StockbitClient", "StockbitError"]
