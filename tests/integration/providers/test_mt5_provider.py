from datetime import timedelta

import pytest

from asta.core.signal_model import Market
from asta.providers import build_providers
from asta.providers.forex.mt5 import MT5Provider
from asta.utils.exceptions import ProviderError
from asta.utils.time_utils import utcnow


def bars(count, timeframe_hours=1, price=1.10):
    now = utcnow().replace(minute=0, second=0, microsecond=0)
    rows = []
    for index in range(count):
        stamp = now - timedelta(hours=timeframe_hours * (count - index))
        rows.append(
            {
                "time": stamp.isoformat().replace("+00:00", "Z"),
                "open": price,
                "high": price + 0.001,
                "low": price - 0.001,
                "close": price + 0.0005,
                "volume": 0,
                "tick_volume": 100 + index,
            }
        )
    return rows


class FakeTerminal:
    def __init__(self, rows=None, connected=True):
        self.rows = rows or []
        self.connected = connected
        self.calls = []

    def is_connected(self):
        return self.connected

    def chart_history(self, symbol, period, start, end, limit=5000):
        self.calls.append((symbol, period, limit))
        return self.rows

    def market_watch(self, symbol=None, limit=50):
        return [{"symbol": symbol, "bid": 1.1, "ask": 1.1002}]

    def close(self):
        pass


class FakeMarketData:
    def __init__(self, rows=None, alive=True):
        self.rows = rows or []
        self.alive = alive
        self.calls = []

    def history(self, symbol, timeframe, start, end):
        self.calls.append((symbol, timeframe))
        return self.rows

    def ping(self, symbol="EURUSD"):
        return self.alive

    def close(self):
        pass


def build_provider(terminal=None, marketdata=None, settings=None):
    provider = MT5Provider(settings or {"terminal_url": "http://x", "marketdata_url": "http://y"})
    provider._terminal = terminal
    provider._marketdata = marketdata
    return provider


def test_build_providers_uses_mt5_for_forex():
    providers = build_providers(
        {"forex": {"type": "mt5", "terminal_url": "http://127.0.0.1:22346/mcp"}}
    )
    assert isinstance(providers[Market.FOREX], MT5Provider)
    assert providers[Market.CRYPTO].name == "binance"
    assert providers[Market.STOCK].name == "yahoo"


def test_terminal_candles_are_parsed_and_closed_only():
    provider = build_provider(terminal=FakeTerminal(bars(30)))
    candles = provider.fetch_candles("EUR_USD", "1h", 130)
    assert len(candles) == 30
    assert candles[0].timestamp < candles[-1].timestamp
    assert candles[-1].volume == 129  # falls back to tick_volume
    assert provider._terminal.calls[0][0] == "EURUSD"
    assert provider._terminal.calls[0][1] == "H1"


def test_fallback_to_public_marketdata_when_terminal_empty():
    provider = build_provider(terminal=FakeTerminal([]), marketdata=FakeMarketData(bars(20)))
    candles = provider.fetch_candles("EUR_USD", "1h", 120)
    assert len(candles) == 20
    assert provider._marketdata.calls


def test_unsupported_timeframe_without_terminal_raises():
    provider = build_provider(terminal=FakeTerminal([]), marketdata=FakeMarketData([]))
    with pytest.raises(ProviderError):
        provider.fetch_candles("EUR_USD", "15m", 100)


def test_health_true_when_marketdata_alive():
    provider = build_provider(terminal=FakeTerminal([], connected=False), marketdata=FakeMarketData(alive=True))
    assert provider.health_check() is True


def test_health_false_when_everything_down():
    provider = build_provider(terminal=FakeTerminal([], connected=False), marketdata=FakeMarketData(alive=False))
    assert provider.health_check() is False


def test_fetch_price_from_market_watch():
    provider = build_provider(terminal=FakeTerminal(bars(5)))
    assert provider.fetch_price("EUR_USD") == pytest.approx(1.1001)
