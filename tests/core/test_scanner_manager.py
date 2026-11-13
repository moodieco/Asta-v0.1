from datetime import datetime, timedelta, timezone
from typing import Dict, List

from asta.core.deduplication import DeduplicationStore
from asta.core.market_manager import MarketManager, MarketSettings
from asta.core.scanner_manager import ScannerManager
from asta.core.signal_manager import SignalManager
from asta.core.signal_model import Candle, Market, ScanContext, Signal, SignalType
from asta.core.signal_validator import SignalValidator
from asta.providers.base import MarketDataProvider
from asta.storage.cache import TTLCache
from asta.storage.signal_history import SignalHistory
from asta.utils.exceptions import ProviderError
from tests.helpers import make_candles


class StubProvider(MarketDataProvider):
    def __init__(self, market, candles=None, error=None):
        super().__init__({})
        self.market = market
        self.name = "stub-{}".format(market.value)
        self._candles = candles or make_candles([100 + index * 0.1 for index in range(200)])
        self.error = error
        self.calls = []

    def fetch_candles(self, symbol, timeframe, limit=200):
        self.calls.append((symbol, timeframe, limit))
        if self.error:
            raise ProviderError(self.error, symbol=symbol)
        return self._candles


class StubScanner:
    """Minimal scanner double (duck-typed, no registry needed)."""

    def __init__(self, scanner_id, market, symbols=None, raises=None):
        self.id = scanner_id
        self.name = scanner_id
        self.market = market
        self.timeframe = "1h"
        self.min_candles = 10
        self.enabled = True
        self.config = type("Config", (), {"enabled": True})()
        self._symbols = symbols or []
        self.raises = raises

    @property
    def symbols(self):
        return self._symbols

    def scan(self, context):
        if self.raises:
            raise self.raises
        return [
            self.build_signal(context),
        ]

    def build_signal(self, context):
        return Signal(
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


class FailingScanner(StubScanner):
    def scan(self, context):
        raise ProviderError("boom", symbol=context.symbol)


def build_manager(tmp_path, providers, markets, scanners):
    market_manager = MarketManager(providers, markets)
    signal_manager = SignalManager(
        validator=SignalValidator(min_confidence=0.3),
        deduplication=DeduplicationStore(3600, TTLCache(3600)),
        history=SignalHistory(tmp_path / "signals.jsonl"),
        alert_manager=None,
    )
    return ScannerManager(market_manager, signal_manager, scanners)


def test_cycle_runs_every_symbol_and_accepts_signals(tmp_path):
    provider = StubProvider(Market.CRYPTO)
    manager = build_manager(
        tmp_path,
        {Market.CRYPTO: provider},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT", "ETHUSDT"])},
        [StubScanner("CXS999_STUB", Market.CRYPTO)],
    )
    report = manager.run_cycle()
    assert report.scanners_run == 1
    assert report.contexts_built == 2
    assert report.signals_detected == 2
    assert report.signals_accepted == 2
    assert report.errors == []


def test_scanner_symbols_override_market_symbols(tmp_path):
    provider = StubProvider(Market.CRYPTO)
    manager = build_manager(
        tmp_path,
        {Market.CRYPTO: provider},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT"])},
        [StubScanner("CXS999_STUB", Market.CRYPTO, symbols=["SOLUSDT"])],
    )
    manager.run_cycle()
    assert [call[0] for call in provider.calls] == ["SOLUSDT"]


def test_disabled_market_is_skipped(tmp_path):
    provider = StubProvider(Market.FOREX)
    manager = build_manager(
        tmp_path,
        {Market.FOREX: provider},
        {"forex": MarketSettings(enabled=False, symbols=["EUR_USD"])},
        [StubScanner("FXS999_STUB", Market.FOREX)],
    )
    report = manager.run_cycle()
    assert report.scanners_run == 0
    assert provider.calls == []


def test_provider_failure_is_recorded_and_cycle_continues(tmp_path):
    failing = StubProvider(Market.CRYPTO, error="HTTP 503")
    manager = build_manager(
        tmp_path,
        {Market.CRYPTO: failing},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT"])},
        [StubScanner("CXS999_STUB", Market.CRYPTO)],
    )
    report = manager.run_cycle()
    assert report.contexts_built == 0
    assert len(report.errors) == 1
    assert "HTTP 503" in report.errors[0]


def test_scanner_exception_is_recorded(tmp_path):
    manager = build_manager(
        tmp_path,
        {Market.CRYPTO: StubProvider(Market.CRYPTO)},
        {"crypto": MarketSettings(enabled=True, symbols=["BTCUSDT"])},
        [FailingScanner("CXS998_FAIL", Market.CRYPTO)],
    )
    report = manager.run_cycle()
    assert report.errors
    assert "boom" in report.errors[0]
