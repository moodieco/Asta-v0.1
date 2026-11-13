from datetime import datetime, timezone

from asta.core.deduplication import DeduplicationStore
from asta.core.event_bus import EventBus
from asta.core.market_manager import MarketManager, MarketSettings
from asta.core.scanner_manager import ScannerManager
from asta.core.signal_manager import SignalManager
from asta.core.signal_model import Market, Signal, SignalType
from asta.core.signal_validator import SignalValidator
from asta.providers.base import MarketDataProvider
from asta.services.analysis_service import AnalysisService
from asta.services.data_service import DataService
from asta.storage.cache import TTLCache
from asta.storage.signal_history import SignalHistory
from asta.utils.exceptions import ProviderError
from tests.fixtures.market_data import make_candles


class StubProvider(MarketDataProvider):
    def __init__(self, market, error=None):
        super().__init__({})
        self.market = market
        self.name = "stub-{}".format(market.value)
        self.error = error
        self.calls = []

    def fetch_candles(self, symbol, timeframe, limit=200):
        self.calls.append((symbol, timeframe, limit))
        if self.error:
            raise ProviderError(self.error, symbol=symbol)
        return make_candles([100 + index * 0.1 for index in range(300)], timeframe=timeframe)


class StubScanner:
    def __init__(self, scanner_id, market, symbols=None, raises=None):
        self.id = scanner_id
        self.name = scanner_id
        self.market = market
        self.timeframe = "1h"
        self.min_candles = 10
        self.enabled = True
        self.strategy = "stub"
        self._symbols = symbols or []
        self.raises = raises
        self.config = type("Config", (), {"enabled": True})()

    @property
    def symbols(self):
        return self._symbols

    def describe(self):
        return {"id": self.id, "market": self.market.value, "timeframe": self.timeframe}

    def scan(self, context):
        if self.raises:
            raise self.raises
        return [
            Signal(
                scanner_id=self.id,
                scanner_name=self.name,
                market=self.market,
                symbol=context.symbol,
                timeframe=context.timeframe,
                signal_type=SignalType.LONG,
                reason="stub scanner always fires on this symbol",
                confidence=0.8,
                price=context.price,
                timestamp=datetime.now(timezone.utc),
            )
        ]


def build_analysis(tmp_path, providers, markets, scanners, event_bus=None):
    market_manager = MarketManager(providers, markets)
    data_service = DataService(market_manager)
    signal_manager = SignalManager(
        validator=SignalValidator(min_confidence=0.3),
        deduplication=DeduplicationStore(3600, TTLCache(3600)),
        history=SignalHistory(tmp_path / "signals.jsonl"),
        notifier=None,
    )
    bus = event_bus or EventBus()
    analysis = AnalysisService(ScannerManager(scanners), signal_manager, data_service, bus)
    return analysis, bus


def test_cycle_runs_every_symbol_and_accepts_signals(tmp_path):
    provider = StubProvider(Market.CRYPTO)
    analysis, _ = build_analysis(
        tmp_path,
        {Market.CRYPTO: provider},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT", "ETHUSDT"])},
        [StubScanner("CXS999_STUB", Market.CRYPTO)],
    )
    report = analysis.run_cycle()
    assert report.scanners_run == 1
    assert report.contexts_built == 2
    assert report.signals_detected == 2
    assert report.signals_accepted == 2
    assert report.errors == []
    assert [call[0] for call in provider.calls] == ["BTCUSDT", "ETHUSDT"]


def test_scanner_symbols_override_market_symbols(tmp_path):
    provider = StubProvider(Market.CRYPTO)
    analysis, _ = build_analysis(
        tmp_path,
        {Market.CRYPTO: provider},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT"])},
        [StubScanner("CXS999_STUB", Market.CRYPTO, symbols=["SOLUSDT"])],
    )
    analysis.run_cycle()
    assert [call[0] for call in provider.calls] == ["SOLUSDT"]


def test_disabled_market_is_skipped(tmp_path):
    provider = StubProvider(Market.FOREX)
    analysis, _ = build_analysis(
        tmp_path,
        {Market.FOREX: provider},
        {"forex": MarketSettings(enabled=False, symbols=["EUR_USD"])},
        [StubScanner("FXS999_STUB", Market.FOREX)],
    )
    report = analysis.run_cycle()
    assert report.scanners_run == 0
    assert provider.calls == []


def test_provider_failure_is_recorded_and_cycle_continues(tmp_path):
    analysis, bus = build_analysis(
        tmp_path,
        {Market.CRYPTO: StubProvider(Market.CRYPTO, error="HTTP 503")},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT"])},
        [StubScanner("CXS999_STUB", Market.CRYPTO)],
    )
    report = analysis.run_cycle()
    assert report.contexts_built == 0
    assert "HTTP 503" in report.errors[0]
    assert any(event.name == "scan.failed" for event in bus.history)


def test_scanner_exception_is_recorded(tmp_path):
    analysis, _ = build_analysis(
        tmp_path,
        {Market.CRYPTO: StubProvider(Market.CRYPTO)},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT"])},
        [StubScanner("CXS998_FAIL", Market.CRYPTO, raises=ProviderError("boom"))],
    )
    report = analysis.run_cycle()
    assert report.errors and "boom" in report.errors[0]


def test_cycle_publishes_events(tmp_path):
    analysis, bus = build_analysis(
        tmp_path,
        {Market.CRYPTO: StubProvider(Market.CRYPTO)},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT"])},
        [StubScanner("CXS999_STUB", Market.CRYPTO)],
    )
    analysis.run_cycle()
    names = [event.name for event in bus.history]
    assert "cycle.started" in names
    assert "signal.detected" in names
    assert "signal.accepted" in names
    assert "cycle.completed" in names


def test_scanner_and_history_inspection(tmp_path):
    analysis, _ = build_analysis(
        tmp_path,
        {Market.CRYPTO: StubProvider(Market.CRYPTO)},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT"])},
        [StubScanner("CXS999_STUB", Market.CRYPTO)],
    )
    assert len(analysis) == 1
    assert analysis.enabled(Market.CRYPTO)
    assert analysis.inventory()[0]["id"] == "CXS999_STUB"
