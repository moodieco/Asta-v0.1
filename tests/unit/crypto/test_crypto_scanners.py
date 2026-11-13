from asta.core.signal_model import Market, SignalType
from tests.fixtures.market_data import (
    bullish_divergence_closes,
    crypto_breakout_closes,
    make_context,
    volume_spike_closes,
)


def test_cxs001_detects_divergence_with_volume_confirmation(scanners):
    scanner = scanners["CXS001_RSI_DIVERGENCE"]
    closes = bullish_divergence_closes()
    volumes = [1000.0] * (len(closes) - 1) + [1400.0]
    context = make_context(Market.CRYPTO, closes, volumes=volumes, symbol="BTCUSDT")

    signals = scanner.scan(context)
    assert len(signals) == 1
    assert signals[0].signal_type is SignalType.LONG
    assert signals[0].indicators["volume_ratio"] == 1.4


def test_cxs001_requires_volume_expansion(scanners):
    scanner = scanners["CXS001_RSI_DIVERGENCE"]
    closes = bullish_divergence_closes()
    volumes = [1000.0] * len(closes)  # last candle volume ratio == 1.0
    context = make_context(Market.CRYPTO, closes, volumes=volumes, symbol="BTCUSDT")
    # ratio 1.0 passes the >= 1.0 filter; below 1.0 must fail
    assert len(scanner.scan(context)) == 1

    thin = [1000.0] * (len(closes) - 1) + [400.0]
    context = make_context(Market.CRYPTO, closes, volumes=thin, symbol="BTCUSDT")
    assert scanner.scan(context) == []


def test_cxs002_detects_bullish_volume_spike(scanners):
    scanner = scanners["CXS002_VOLUME_SPIKE"]
    closes = volume_spike_closes()
    volumes = [1000.0] * (len(closes) - 1) + [5200.0]
    context = make_context(Market.CRYPTO, closes, volumes=volumes, symbol="ETHUSDT", timeframe="15m")

    signals = scanner.scan(context)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type is SignalType.LONG
    assert signal.indicators["volume_ratio"] == 5.2
    assert signal.timeframe == "15m"


def test_cxs002_detects_bearish_volume_spike(scanners):
    scanner = scanners["CXS002_VOLUME_SPIKE"]
    closes = [100.0] * 60
    closes[-1] = 97.0
    volumes = [1000.0] * 59 + [5200.0]
    context = make_context(Market.CRYPTO, closes, volumes=volumes, symbol="ETHUSDT", timeframe="15m")

    signals = scanner.scan(context)
    assert len(signals) == 1
    assert signals[0].signal_type is SignalType.SHORT


def test_cxs002_ignores_normal_volume(scanners):
    scanner = scanners["CXS002_VOLUME_SPIKE"]
    closes = volume_spike_closes()
    volumes = [1000.0] * 59 + [1200.0]
    context = make_context(Market.CRYPTO, closes, volumes=volumes, symbol="ETHUSDT", timeframe="15m")
    assert scanner.scan(context) == []


def test_cxs003_detects_breakout_with_volume(scanners):
    scanner = scanners["CXS003_BREAKOUT_TREND"]
    closes = crypto_breakout_closes()
    volumes = [1000.0] * (len(closes) - 1) + [1700.0]
    context = make_context(Market.CRYPTO, closes, volumes=volumes, symbol="SOLUSDT")

    signals = scanner.scan(context)
    assert len(signals) == 1
    signal = signals[0]
    assert signal.signal_type is SignalType.LONG
    assert signal.indicators["volume_ratio"] == 1.7
    assert signal.indicators["distance_pct"] > 0


def test_cxs003_requires_volume_confirmation(scanners):
    scanner = scanners["CXS003_BREAKOUT_TREND"]
    closes = crypto_breakout_closes()
    volumes = [1000.0] * len(closes)
    context = make_context(Market.CRYPTO, closes, volumes=volumes, symbol="SOLUSDT")
    assert scanner.scan(context) == []


def test_crypto_scanner_needs_enough_candles(scanners):
    import pytest

    from asta.utils.exceptions import InsufficientDataError

    scanner = scanners["CXS003_BREAKOUT_TREND"]
    context = make_context(Market.CRYPTO, [100.0] * 20, symbol="SOLUSDT")
    with pytest.raises(InsufficientDataError):
        scanner.scan(context)
