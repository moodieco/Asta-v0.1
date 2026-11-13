import pytest

from asta.core.scanner_base import ScannerBase, ScannerConfig
from asta.core.signal_model import Market, ScanContext, SignalType
from asta.utils.exceptions import ConfigurationError, InsufficientDataError, ScannerError
from tests.helpers import make_candles


class DummyScanner(ScannerBase):
    id = "DUMMY_001"
    name = "Dummy"
    market = Market.CRYPTO
    default_timeframe = "1h"
    min_candles = 3
    default_params = {"threshold": 10}

    def evaluate(self, context):
        return [
            self.build_signal(
                context,
                SignalType.LONG,
                "dummy signal for testing",
                confidence=0.6,
                indicators={"threshold": self.params["threshold"]},
            )
        ]


def test_config_overrides_merge_params():
    config = ScannerConfig(
        id="DUMMY_001",
        name="Dummy",
        market="crypto",
        timeframe="4h",
        params={"threshold": 42, "extra": True},
    )
    scanner = DummyScanner(config)
    assert scanner.timeframe == "4h"
    assert scanner.params["threshold"] == 42
    assert scanner.params["extra"] is True
    assert scanner.describe()["market"] == "crypto"


def test_market_mismatch_is_rejected_at_construction():
    config = ScannerConfig(id="DUMMY_001", name="Dummy", market="forex")
    with pytest.raises(ConfigurationError):
        DummyScanner(config)


def test_scan_rejects_wrong_market_context():
    scanner = DummyScanner()
    context = ScanContext(
        market=Market.FOREX, symbol="EUR_USD", timeframe="1h", candles=make_candles([1, 2, 3, 4])
    )
    with pytest.raises(ScannerError):
        scanner.scan(context)


def test_scan_raises_when_not_enough_candles():
    scanner = DummyScanner()
    context = ScanContext(
        market=Market.CRYPTO, symbol="BTCUSDT", timeframe="1h", candles=make_candles([1, 2])
    )
    with pytest.raises(InsufficientDataError):
        scanner.scan(context)


def test_scan_builds_signal_with_scanner_identity():
    scanner = DummyScanner()
    context = ScanContext(
        market=Market.CRYPTO,
        symbol="btcusdt",
        timeframe="1h",
        candles=make_candles([1, 2, 3, 4]),
    )
    signals = scanner.scan(context)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.scanner_id == "DUMMY_001"
    assert signal.symbol == "BTCUSDT"
    assert signal.market is Market.CRYPTO
    assert signal.strategy == "Dummy"
    # the caller's context is left untouched (scan works on a copy)
    assert context.scanner_id == ""


def test_disabled_scanner_still_reports_enabled_false():
    config = ScannerConfig(id="DUMMY_001", name="Dummy", market="crypto", enabled=False)
    assert DummyScanner(config).enabled is False
