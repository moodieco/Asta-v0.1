"""Momentum Scalp (STS004_MOMENTUM_SCALP): price + volume surge on liquid stocks."""

import pytest

from asta.core.signal_model import Market, SignalType
from asta.utils.exceptions import InsufficientDataError, ScannerError
from tests.fixtures.market_data import make_context

SCANNER_ID = "STS004_MOMENTUM_SCALP"


def surge_closes():
    return [1000.0] * 9 + [1030.0]  # +3% on the last bar


def surge_volumes():
    return [20_000_000.0] * 9 + [30_000_000.0]  # +50% on the last bar


def scan(scanners, closes, volumes, market=Market.STOCK):
    context = make_context(market, closes, volumes=volumes, timeframe="1d")
    return scanners[SCANNER_ID].scan(context)


def test_identity(scanners):
    scanner = scanners[SCANNER_ID]
    assert scanner.name == "Momentum Scalp"
    assert scanner.market is Market.STOCK
    assert scanner.timeframe == "1d"
    assert scanner.enabled


def test_fires_on_surge(scanners):
    signals = scan(scanners, surge_closes(), surge_volumes())

    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type is SignalType.LONG
    assert signal.confidence >= 0.55
    assert signal.levels_source == "structure"
    assert signal.stop_loss == pytest.approx(signal.price * 0.98, rel=1e-3)
    assert signal.take_profit == pytest.approx(signal.price * 1.05, rel=1e-3)
    assert signal.indicators["price_change_pct"] >= 2.0
    assert signal.indicators["volume_change_pct"] >= 30.0


def test_quiet_when_price_change_small(scanners):
    closes = [1000.0] * 9 + [1010.0]
    assert scan(scanners, closes, surge_volumes()) == []


def test_quiet_when_volume_flat(scanners):
    assert scan(scanners, surge_closes(), [20_000_000.0] * 10) == []


def test_quiet_when_illiquid(scanners):
    volumes = [1_000_000.0] * 9 + [1_500_000.0]
    assert scan(scanners, surge_closes(), volumes) == []


def test_quiet_below_min_price(scanners):
    closes = [50.0] * 9 + [52.0]
    assert scan(scanners, closes, surge_volumes()) == []


def test_needs_enough_candles(scanners):
    with pytest.raises(InsufficientDataError):
        scan(scanners, surge_closes()[-4:], surge_volumes()[-4:])


def test_rejects_other_market(scanners):
    with pytest.raises(ScannerError):
        scan(scanners, surge_closes(), surge_volumes(), market=Market.CRYPTO)
