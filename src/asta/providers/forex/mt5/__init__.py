"""MetaTrader 5 forex provider (local terminal MCP, public market data fallback)."""

from asta.providers.forex.mt5.candles import PERIODS, MT5Provider
from asta.providers.forex.mt5.client import MT5TerminalClient

__all__ = ["MT5Provider", "MT5TerminalClient", "PERIODS"]
