from asta.core.market_manager import MarketManager, MarketSettings
from asta.core.signal_model import Market
from asta.providers.base import MarketDataProvider
from asta.services.data_service import DataService
from asta.storage.cache import TTLCache
from tests.fixtures.market_data import make_candles


class CountingProvider(MarketDataProvider):
    market = Market.CRYPTO
    name = "counting"

    def __init__(self):
        super().__init__({})
        self.calls = []

    def fetch_candles(self, symbol, timeframe, limit=200):
        self.calls.append((symbol, timeframe, limit))
        return make_candles([100 + index for index in range(limit)], timeframe=timeframe)

    def health_check(self):
        return True


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class StubScanner:
    id = "CXS999_STUB"
    market = Market.CRYPTO
    timeframe = "1h"
    min_candles = 20


def build_service(clock, symbols=None):
    provider = CountingProvider()
    configured = ["BTCUSDT"] if symbols is None else symbols
    market_manager = MarketManager(
        {Market.CRYPTO: provider},
        {"crypto": MarketSettings(enabled=True, symbols=configured)},
        universes={"crypto": ["BTCUSDT", "ETHUSDT"]},
    )
    service = DataService(market_manager, cache=TTLCache(default_ttl=30, clock=clock))
    return service, provider


def test_same_request_is_cached_within_ttl():
    clock = FakeClock()
    service, provider = build_service(clock)
    scanner = StubScanner()

    first = service.build_context(scanner, "BTCUSDT")
    second = service.build_context(scanner, "BTCUSDT")

    assert len(provider.calls) == 1
    assert first.candles == second.candles
    assert first.scanner_id == scanner.id


def test_cache_expires_and_refetches():
    clock = FakeClock()
    service, provider = build_service(clock)
    scanner = StubScanner()
    service.build_context(scanner, "BTCUSDT")
    clock.now += 31
    service.build_context(scanner, "BTCUSDT")
    assert len(provider.calls) == 2


def test_different_timeframes_are_separate_entries():
    clock = FakeClock()
    service, provider = build_service(clock)

    class OtherScanner(StubScanner):
        timeframe = "4h"

    service.build_context(StubScanner(), "BTCUSDT")
    service.build_context(OtherScanner(), "BTCUSDT")
    assert len(provider.calls) == 2


def test_symbols_fall_back_to_universe():
    clock = FakeClock()
    service, _ = build_service(clock, symbols=[])
    assert service.symbols(Market.CRYPTO) == ["BTCUSDT", "ETHUSDT"]
