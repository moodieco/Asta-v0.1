import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from asta.core.signal_model import Market
from asta.providers import build_providers
from asta.providers.base import MarketDataProvider
from asta.providers.crypto.binance import BinanceClient, BinanceProvider
from asta.providers.forex.oanda import OandaClient, OandaPricing, OandaProvider
from asta.providers.stock.yahoo import StockProvider, YahooClient
from asta.utils.exceptions import ProviderError
from asta.utils.time_utils import parse_datetime
from tests.fixtures.market_data import make_candles

WEBHOOK_JSON = {"message": "boom"}


def http_client(handler):
    return httpx.Client(transport=httpx.MockTransport(handler))


def binance_provider(handler, settings=None):
    config = {"max_attempts": 1, **(settings or {})}
    return BinanceProvider(config, client=BinanceClient(config, client=http_client(handler)))


def oanda_provider(handler, settings=None):
    config = {"api_token": "token-123", "max_attempts": 1, **(settings or {})}
    return OandaProvider(config, client=OandaClient(config, client=http_client(handler)))


def stock_provider(handler, settings=None):
    config = {"max_attempts": 1, **(settings or {})}
    return StockProvider(config, client=YahooClient(config, client=http_client(handler)))


# ---------------------------------------------------------------- factory
def test_build_providers_covers_all_markets():
    providers = build_providers({"oanda": {"api_token": ""}})
    assert set(providers) == {Market.FOREX, Market.CRYPTO, Market.STOCK}
    assert providers[Market.FOREX].is_configured() is False
    assert providers[Market.CRYPTO].is_configured() is True
    assert providers[Market.STOCK].is_configured() is True


# ---------------------------------------------------------------- binance
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

    provider = binance_provider(handler)
    candles = provider.fetch_candles("btc/usdt", "1h", 2)
    assert len(candles) == 2
    assert candles[0].close == 42300.0
    assert candles[0].timestamp == datetime(2024, 1, 1, tzinfo=timezone.utc)
    assert "symbol=BTCUSDT" in captured["url"]
    assert "interval=1h" in captured["url"]


def test_binance_provider_error_on_http_failure():
    def handler(request):
        return httpx.Response(500, text="boom")

    provider = binance_provider(handler)
    with pytest.raises(ProviderError):
        provider.fetch_candles("BTCUSDT", "1h", 10)


def test_binance_skips_unclosed_last_kline():
    now_ms = int(time.time() * 1000)
    closed_open = now_ms - 7200_000
    forming_open = now_ms - 600_000
    rows = [
        [closed_open, "100.0", "101.0", "99.0", "100.5", "10.0", closed_open + 3599_999, "0", 0, "0", "0", "0"],
        [forming_open, "100.5", "102.0", "100.0", "101.5", "5.0", now_ms + 3000_000, "0", 0, "0", "0", "0"],
    ]
    provider = binance_provider(lambda request: httpx.Response(200, json=rows))
    candles = provider.fetch_candles("BTCUSDT", "1h", 2)
    assert len(candles) == 1
    assert candles[0].close == 100.5


def test_binance_ticker_price():
    provider = binance_provider(
        lambda request: httpx.Response(200, json={"symbol": "BTCUSDT", "price": "69060.50"})
    )
    assert provider.fetch_price("btc/usdt") == 69060.50


def test_binance_rejects_unsupported_timeframe():
    provider = binance_provider(lambda request: httpx.Response(200, json=[]))
    with pytest.raises(ValueError):
        provider.fetch_candles("BTCUSDT", "2d", 10)


# ------------------------------------------------------------------ oanda
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

    provider = oanda_provider(handler)
    candles = provider.fetch_candles("EURUSD", "1h", 2)
    assert captured["auth"] == "Bearer token-123"
    assert "/v3/instruments/EUR_USD/candles" in captured["url"]
    assert len(candles) == 1
    assert candles[0].close == 1.101
    assert candles[0].timestamp == datetime(2025, 1, 1, 12, 0, tzinfo=timezone.utc)


def test_oanda_without_token_raises():
    provider = OandaProvider({"api_token": ""})
    assert provider.is_configured() is False
    with pytest.raises(ProviderError):
        provider.fetch_candles("EUR_USD", "1h", 5)


def test_oanda_pricing_mid_and_spread():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "prices": [
                    {
                        "instrument": "EUR_USD",
                        "bids": [{"price": "1.10000"}],
                        "asks": [{"price": "1.10020"}],
                    }
                ]
            },
        )

    client = OandaClient({"api_token": "token-123"}, client=http_client(handler))
    pricing = OandaPricing(client)
    assert pricing.current_price("EUR_USD") == pytest.approx(1.1001)
    assert pricing.spread("EUR_USD") == pytest.approx(0.0002)


# ------------------------------------------------------------------ stock
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

    provider = stock_provider(handler)
    candles = provider.fetch_candles("aapl", "1d", 10)
    assert len(candles) == 2
    assert candles[1].close == 102.5
    assert candles[1].volume == 1200.0


def test_stock_provider_surfaces_yahoo_error():
    provider = stock_provider(
        lambda request: httpx.Response(
            200, json={"chart": {"result": None, "error": {"code": "Not Found"}}}
        )
    )
    with pytest.raises(ProviderError):
        provider.fetch_candles("NOPE", "1d", 10)


# ---------------------------------------------------------------- generic
def test_filter_closed_candles_drops_the_forming_bar():
    candles = make_candles([100, 101, 102], timeframe="1h")
    now = candles[-1].timestamp + timedelta(minutes=30)
    closed = MarketDataProvider.filter_closed_candles(candles, "1h", now=now)
    assert len(closed) == 2
    assert closed[-1] is candles[-2]

    later = candles[-1].timestamp + timedelta(hours=1, minutes=1)
    assert len(MarketDataProvider.filter_closed_candles(candles, "1h", now=later)) == 3


def test_parse_datetime_handles_nanoseconds():
    parsed = parse_datetime("2025-01-01T12:00:00.123456789Z")
    assert parsed.tzinfo is not None
    assert parsed.microsecond == 123456
