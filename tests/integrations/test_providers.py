from datetime import datetime, timezone

import httpx
import pytest

from asta.core.signal_model import Market
from asta.providers import build_providers
from asta.providers.binance.provider import BinanceProvider
from asta.providers.oanda.provider import OandaProvider
from asta.providers.stock.provider import StockProvider
from asta.utils.exceptions import ProviderError
from asta.utils.time_utils import parse_datetime


def client_for(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_build_providers_covers_all_markets():
    providers = build_providers({"oanda": {"api_token": ""}})
    assert set(providers) == {Market.FOREX, Market.CRYPTO, Market.STOCK}
    assert providers[Market.FOREX].is_configured() is False
    assert providers[Market.CRYPTO].is_configured() is True


def test_binance_parses_klines_and_normalises_symbol():
    captured = {}

    def handler(request):
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json=[
                [1704067200000, "42000.0", "42500.0", "41800.0", "42300.0", "123.45", 1704070799999, "0", 0, "0", "0", "0"],
                [1704070800000, "42300.0", "42800.0", "42100.0", "42600.0", "98.76", 1704074399999, "0", 0, "0", "0", "0"],
            ],
        )

    provider = BinanceProvider({}, client=client_for(handler))
    candles = provider.fetch_candles("btc/usdt", "1h", 2)
    assert len(candles) == 2
    assert candles[0].close == 42300.0
    assert candles[0].timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert "symbol=BTCUSDT" in captured["url"]
    assert "interval=1h" in captured["url"]


def test_binance_provider_error_on_http_failure():
    provider = BinanceProvider({"max_attempts": 1}, client=client_for(lambda request: httpx.Response(500, text="boom")))
    with pytest.raises(ProviderError):
        provider.fetch_candles("BTCUSDT", "1h", 10)


def test_oanda_sends_bearer_token_and_parses_candles():
    captured = {}

    def handler(request):
        captured["auth"] = request.headers.get("Authorization")
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "instrument": "EUR_USD",
                "candles": [
                    {
                        "complete": True,
                        "volume": 100,
                        "time": "2025-01-01T12:00:00.000000000Z",
                        "mid": {"o": "1.10000", "h": "1.10200", "l": "1.09900", "c": "1.10100"},
                    },
                    {
                        "complete": False,
                        "volume": 50,
                        "time": "2025-01-01T13:00:00.000000000Z",
                        "mid": {"o": "1.10100", "h": "1.10200", "l": "1.10000", "c": "1.10150"},
                    },
                ],
            },
        )

    provider = OandaProvider({"api_token": "token-123"}, client=client_for(handler))
    candles = provider.fetch_candles("EURUSD", "1h", 2)
    assert captured["auth"] == "Bearer token-123"
    assert "/v3/instruments/EUR_USD/candles" in captured["url"]
    assert len(candles) == 1  # incomplete candle dropped
    assert candles[0].close == 1.101
    assert candles[0].timestamp == datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_oanda_without_token_raises():
    provider = OandaProvider({"api_token": ""})
    with pytest.raises(ProviderError):
        provider.fetch_candles("EUR_USD", "1h", 5)


def test_stock_provider_parses_yahoo_chart_and_skips_nulls():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "chart": {
                    "result": [
                        {
                            "timestamp": [1704067200, 1704153600, 1704240000],
                            "indicators": {
                                "quote": [
                                    {
                                        "open": [100.0, 101.0, None],
                                        "high": [102.0, 103.0, None],
                                        "low": [99.0, 100.5, None],
                                        "close": [101.5, 102.5, None],
                                        "volume": [1000, 1200, None],
                                    }
                                ]
                            },
                        }
                    ],
                    "error": None,
                }
            },
        )

    provider = StockProvider({}, client=client_for(handler))
    candles = provider.fetch_candles("aapl", "1d", 10)
    assert len(candles) == 2
    assert candles[1].close == 102.5
    assert candles[1].volume == 1200.0


def test_stock_provider_surfaces_yahoo_error():
    provider = StockProvider(
        {},
        client=client_for(lambda request: httpx.Response(200, json={"chart": {"result": None, "error": {"code": "Not Found"}}})),
    )
    with pytest.raises(ProviderError):
        provider.fetch_candles("NOPE", "1d", 10)


def test_parse_datetime_handles_nanoseconds():
    parsed = parse_datetime("2025-01-01T12:00:00.123456789Z")
    assert parsed.tzinfo is not None
    assert parsed.microsecond == 123456


def test_filter_closed_candles_drops_the_forming_bar():
    from datetime import timedelta

    from asta.providers.base import MarketDataProvider
    from tests.helpers import make_candles

    candles = make_candles([100, 101, 102], timeframe="1h")
    now = candles[-1].timestamp + timedelta(minutes=30)  # last bar still forming
    closed = MarketDataProvider.filter_closed_candles(candles, "1h", now=now)
    assert len(closed) == 2
    assert closed[-1] is candles[-2]

    # once the bar is complete it is kept
    later = candles[-1].timestamp + timedelta(hours=1, minutes=1)
    assert len(MarketDataProvider.filter_closed_candles(candles, "1h", now=later)) == 3


def test_binance_skips_unclosed_last_kline():
    import time

    now_ms = int(time.time() * 1000)
    closed_open = now_ms - 7200_000
    forming_open = now_ms - 600_000
    rows = [
        [closed_open, "100.0", "101.0", "99.0", "100.5", "10.0", closed_open + 3599_999, "0", 0, "0", "0", "0"],
        [forming_open, "100.5", "102.0", "100.0", "101.5", "5.0", now_ms + 3000_000, "0", 0, "0", "0", "0"],
    ]
    provider = BinanceProvider({}, client=client_for(lambda request: httpx.Response(200, json=rows)))
    candles = provider.fetch_candles("BTCUSDT", "1h", 2)
    assert len(candles) == 1
    assert candles[0].close == 100.5
